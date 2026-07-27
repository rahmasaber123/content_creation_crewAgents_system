"""MongoDB Atlas Vector Search backend for CrewAI's unified memory system.

Implements crewai.memory.storage.backend.StorageBackend (verified against
crewai==1.15.3) so `Memory(storage=MongoStorageBackend(...))` persists every
memory record -- short-term, long-term, entity, all the same collection --
to a real MongoDB Atlas cluster instead of local LanceDB/Qdrant files.

Why one collection, not three: CrewAI's current memory system already
distinguishes short-term vs long-term vs entity via `scope` path prefixes
and `categories`, not separate stores. Mirroring that here (one Mongo
collection, filtered by scope/category) matches the framework's own model
instead of fighting it.

Async methods wrap the sync pymongo calls in asyncio.to_thread rather than
pulling in a second driver (motor) -- pymongo isn't async-native, and
running it in a thread pool is the same runtime cost with a fraction of the
dependency/version-conflict risk (see: half the debugging on this project
was a Colab/Jupyter async-vs-sync mismatch). If this becomes a
high-throughput production service, switching to `motor` is a scoped,
localized change confined to this one file.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any

from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.errors import PyMongoError

from crewai.memory.storage.backend import EmbeddingDimensionMismatchError
from crewai.memory.types import MemoryRecord, ScopeInfo

logger = logging.getLogger(__name__)

VECTOR_INDEX_NAME = "memory_vector_index"
EMBEDDING_FIELD = "embedding"


class MongoStorageBackend:
    """Persistent memory storage backed by MongoDB Atlas Vector Search.

    Requires an Atlas Vector Search index on `embedding` (see
    `ensure_vector_index()` -- attempts to create it automatically, falls
    back to logging the manual JSON definition since some Atlas tiers/roles
    only allow index creation via the UI or Admin API, not the driver).
    """

    def __init__(
        self,
        mongo_uri: str,
        db_name: str = "kayfa_crew",
        collection_name: str = "memory_records",
        embedding_dims: int = 1536,
    ) -> None:
        self.embedding_dims = embedding_dims
        try:
            self._client: MongoClient = MongoClient(
                mongo_uri, serverSelectionTimeoutMS=8000
            )
            # Fail fast on bad URIs/credentials instead of failing silently
            # on the first real memory save mid-crew-run.
            self._client.admin.command("ping")
        except PyMongoError:
            logger.exception("MongoStorageBackend: failed to connect to MongoDB")
            raise

        self._collection: Collection = self._client[db_name][collection_name]
        self.ensure_vector_index()

    # ---------------------------------------------------------------- setup

    def ensure_vector_index(self) -> None:
        """Best-effort Atlas Vector Search index creation.

        Not fatal if this fails -- reads/writes to the collection still
        work, just without `$vectorSearch` until the index exists. Logs the
        manual definition so it can be pasted into Atlas UI > Search
        Indexes if the driver-side creation is rejected (common on shared/
        free tiers, which restrict programmatic index management).
        """
        definition = {
            "fields": [
                {
                    "type": "vector",
                    "path": EMBEDDING_FIELD,
                    "numDimensions": self.embedding_dims,
                    "similarity": "cosine",
                },
                {"type": "filter", "path": "scope"},
                {"type": "filter", "path": "categories"},
            ]
        }
        try:
            existing = list(self._collection.list_search_indexes(VECTOR_INDEX_NAME))
            if existing:
                logger.debug("Vector index '%s' already exists", VECTOR_INDEX_NAME)
                return
            self._collection.create_search_index(
                {"name": VECTOR_INDEX_NAME, "type": "vectorSearch", "definition": definition}
            )
            logger.info("Created Atlas Vector Search index '%s'", VECTOR_INDEX_NAME)
        except PyMongoError as exc:
            logger.warning(
                "Could not auto-create vector index '%s' (%s). "
                "Create it manually in Atlas UI > Search Indexes with:\n%s",
                VECTOR_INDEX_NAME,
                exc,
                definition,
            )

    # -------------------------------------------------------------- helpers

    @staticmethod
    def _to_doc(record: MemoryRecord) -> dict[str, Any]:
        doc = record.model_dump(mode="json")
        doc["_id"] = record.id
        doc[EMBEDDING_FIELD] = record.embedding
        return doc

    @staticmethod
    def _from_doc(doc: dict[str, Any]) -> MemoryRecord:
        doc = dict(doc)
        doc["id"] = doc.pop("_id")
        return MemoryRecord(**doc)

    def _check_embedding_dims(self, embedding: list[float]) -> None:
        if embedding and len(embedding) != self.embedding_dims:
            raise EmbeddingDimensionMismatchError(self.embedding_dims, len(embedding))

    # ---------------------------------------------------------------- save

    def save(self, records: list[MemoryRecord]) -> None:
        if not records:
            return
        try:
            for record in records:
                if record.embedding:
                    self._check_embedding_dims(record.embedding)
            docs = [self._to_doc(r) for r in records]
            for doc in docs:
                self._collection.replace_one({"_id": doc["_id"]}, doc, upsert=True)
            logger.debug("Saved %d memory record(s) to MongoDB", len(records))
        except PyMongoError:
            logger.exception("MongoStorageBackend.save failed for %d record(s)", len(records))
            raise

    async def asave(self, records: list[MemoryRecord]) -> None:
        await asyncio.to_thread(self.save, records)

    # -------------------------------------------------------------- search

    def search(
        self,
        query_embedding: list[float],
        scope_prefix: str | None = None,
        categories: list[str] | None = None,
        metadata_filter: dict[str, Any] | None = None,
        limit: int = 10,
        min_score: float = 0.0,
    ) -> list[tuple[MemoryRecord, float]]:
        try:
            self._check_embedding_dims(query_embedding)

            vector_stage: dict[str, Any] = {
                "index": VECTOR_INDEX_NAME,
                "path": EMBEDDING_FIELD,
                "queryVector": query_embedding,
                "numCandidates": max(limit * 10, 100),
                "limit": limit,
            }
            pre_filter: dict[str, Any] = {}
            if scope_prefix:
                pre_filter["scope"] = {"$regex": f"^{scope_prefix}"}
            if categories:
                pre_filter["categories"] = {"$in": categories}
            if pre_filter:
                vector_stage["filter"] = pre_filter

            pipeline: list[dict[str, Any]] = [
                {"$vectorSearch": vector_stage},
                {"$addFields": {"_score": {"$meta": "vectorSearchScore"}}},
            ]
            if metadata_filter:
                pipeline.append(
                    {"$match": {f"metadata.{k}": v for k, v in metadata_filter.items()}}
                )
            pipeline.append({"$match": {"_score": {"$gte": min_score}}})

            results: list[tuple[MemoryRecord, float]] = []
            for doc in self._collection.aggregate(pipeline):
                score = doc.pop("_score", 0.0)
                results.append((self._from_doc(doc), score))
            return results
        except PyMongoError:
            logger.exception("MongoStorageBackend.search failed")
            # Degrade gracefully -- an empty recall shouldn't crash the crew,
            # it should just mean "no relevant memory found this run."
            return []

    async def asearch(
        self,
        query_embedding: list[float],
        scope_prefix: str | None = None,
        categories: list[str] | None = None,
        metadata_filter: dict[str, Any] | None = None,
        limit: int = 10,
        min_score: float = 0.0,
    ) -> list[tuple[MemoryRecord, float]]:
        return await asyncio.to_thread(
            self.search,
            query_embedding,
            scope_prefix,
            categories,
            metadata_filter,
            limit,
            min_score,
        )

    # -------------------------------------------------------------- delete

    def delete(
        self,
        scope_prefix: str | None = None,
        categories: list[str] | None = None,
        record_ids: list[str] | None = None,
        older_than: datetime | None = None,
        metadata_filter: dict[str, Any] | None = None,
    ) -> int:
        try:
            query: dict[str, Any] = {}
            if scope_prefix:
                query["scope"] = {"$regex": f"^{scope_prefix}"}
            if categories:
                query["categories"] = {"$in": categories}
            if record_ids:
                query["_id"] = {"$in": record_ids}
            if older_than:
                query["created_at"] = {"$lt": older_than.isoformat()}
            if metadata_filter:
                query.update({f"metadata.{k}": v for k, v in metadata_filter.items()})

            result = self._collection.delete_many(query)
            logger.debug("Deleted %d memory record(s)", result.deleted_count)
            return result.deleted_count
        except PyMongoError:
            logger.exception("MongoStorageBackend.delete failed")
            return 0

    async def adelete(
        self,
        scope_prefix: str | None = None,
        categories: list[str] | None = None,
        record_ids: list[str] | None = None,
        older_than: datetime | None = None,
        metadata_filter: dict[str, Any] | None = None,
    ) -> int:
        return await asyncio.to_thread(
            self.delete, scope_prefix, categories, record_ids, older_than, metadata_filter
        )

    # -------------------------------------------------------------- update

    def update(self, record: MemoryRecord) -> None:
        try:
            self._collection.replace_one(
                {"_id": record.id}, self._to_doc(record), upsert=True
            )
        except PyMongoError:
            logger.exception("MongoStorageBackend.update failed for id=%s", record.id)
            raise

    # ----------------------------------------------------------------- get

    def get_record(self, record_id: str) -> MemoryRecord | None:
        try:
            doc = self._collection.find_one({"_id": record_id})
            return self._from_doc(doc) if doc else None
        except PyMongoError:
            logger.exception("MongoStorageBackend.get_record failed for id=%s", record_id)
            return None

    def list_records(
        self, scope_prefix: str | None = None, limit: int = 200, offset: int = 0
    ) -> list[MemoryRecord]:
        try:
            query = {"scope": {"$regex": f"^{scope_prefix}"}} if scope_prefix else {}
            cursor = (
                self._collection.find(query)
                .sort("created_at", -1)
                .skip(offset)
                .limit(limit)
            )
            return [self._from_doc(doc) for doc in cursor]
        except PyMongoError:
            logger.exception("MongoStorageBackend.list_records failed")
            return []

    def get_scope_info(self, scope: str) -> ScopeInfo:
        try:
            query = {"scope": {"$regex": f"^{scope}"}}
            docs = list(self._collection.find(query))
            if not docs:
                return ScopeInfo(path=scope)
            categories = sorted({c for d in docs for c in d.get("categories", [])})
            timestamps = sorted(d["created_at"] for d in docs if d.get("created_at"))
            children = sorted(
                {
                    d["scope"].split("/")[len(scope.split("/"))]
                    for d in docs
                    if d["scope"] != scope and d["scope"].startswith(scope)
                }
            )
            return ScopeInfo(
                path=scope,
                record_count=len(docs),
                categories=categories,
                oldest_record=datetime.fromisoformat(timestamps[0]) if timestamps else None,
                newest_record=datetime.fromisoformat(timestamps[-1]) if timestamps else None,
                child_scopes=children,
            )
        except PyMongoError:
            logger.exception("MongoStorageBackend.get_scope_info failed for scope=%s", scope)
            return ScopeInfo(path=scope)

    def list_scopes(self, parent: str = "/") -> list[str]:
        try:
            scopes = self._collection.distinct("scope", {"scope": {"$regex": f"^{parent}"}})
            depth = len([p for p in parent.split("/") if p]) + 1
            children = {
                "/" + "/".join([p for p in s.split("/") if p][:depth]) for s in scopes
            }
            return sorted(children)
        except PyMongoError:
            logger.exception("MongoStorageBackend.list_scopes failed")
            return []

    def list_categories(self, scope_prefix: str | None = None) -> dict[str, int]:
        try:
            query = {"scope": {"$regex": f"^{scope_prefix}"}} if scope_prefix else {}
            counts: dict[str, int] = {}
            for doc in self._collection.find(query, {"categories": 1}):
                for cat in doc.get("categories", []):
                    counts[cat] = counts.get(cat, 0) + 1
            return counts
        except PyMongoError:
            logger.exception("MongoStorageBackend.list_categories failed")
            return {}

    def count(self, scope_prefix: str | None = None) -> int:
        try:
            query = {"scope": {"$regex": f"^{scope_prefix}"}} if scope_prefix else {}
            return self._collection.count_documents(query)
        except PyMongoError:
            logger.exception("MongoStorageBackend.count failed")
            return 0

    # ----------------------------------------------------------------- reset

    def reset(self, scope_prefix: str | None = None) -> None:
        try:
            query = {"scope": {"$regex": f"^{scope_prefix}"}} if scope_prefix else {}
            result = self._collection.delete_many(query)
            logger.info("Reset memory: deleted %d record(s)", result.deleted_count)
        except PyMongoError:
            logger.exception("MongoStorageBackend.reset failed")
            raise
