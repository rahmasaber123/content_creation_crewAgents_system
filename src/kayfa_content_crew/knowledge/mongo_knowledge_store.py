"""Persistent company knowledge base backed by MongoDB Atlas Vector Search.

Separate collection from `storage/mongo_storage.py`'s memory records --
knowledge (brand voice, approved claims, technical style) is curated,
human-authored, and versioned by re-running `seed_knowledge.py`; memory is
agent-generated and evolves on its own. Keeping them apart means resetting
one never touches the other, and knowledge search/scoring logic doesn't
have to share the recency/importance weighting that memory recall uses.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from openai import OpenAI
from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.errors import PyMongoError

logger = logging.getLogger(__name__)

VECTOR_INDEX_NAME = "knowledge_vector_index"
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMS = 1536
CHUNK_SIZE = 800  # characters -- generous for markdown paragraphs, small enough for precise retrieval


class MongoKnowledgeStore:
    """Chunk, embed, and persist markdown knowledge files; query by similarity."""

    def __init__(
        self,
        mongo_uri: str,
        db_name: str = "kayfa_crew",
        collection_name: str = "knowledge_chunks",
        openai_api_key: str | None = None,
    ) -> None:
        try:
            self._client = MongoClient(mongo_uri, serverSelectionTimeoutMS=8000)
            self._client.admin.command("ping")
        except PyMongoError:
            logger.exception("MongoKnowledgeStore: failed to connect to MongoDB")
            raise

        self._collection: Collection = self._client[db_name][collection_name]
        self._openai = OpenAI(api_key=openai_api_key)
        self._ensure_vector_index()

    def _ensure_vector_index(self) -> None:
        definition = {
            "fields": [
                {
                    "type": "vector",
                    "path": "embedding",
                    "numDimensions": EMBEDDING_DIMS,
                    "similarity": "cosine",
                },
                {"type": "filter", "path": "source_file"},
            ]
        }
        try:
            if list(self._collection.list_search_indexes(VECTOR_INDEX_NAME)):
                return
            self._collection.create_search_index(
                {"name": VECTOR_INDEX_NAME, "type": "vectorSearch", "definition": definition}
            )
            logger.info("Created Atlas Vector Search index '%s'", VECTOR_INDEX_NAME)
        except PyMongoError as exc:
            logger.warning(
                "Could not auto-create '%s' (%s). Create manually in Atlas UI > "
                "Search Indexes with:\n%s",
                VECTOR_INDEX_NAME,
                exc,
                definition,
            )

    # --------------------------------------------------------------- embed

    def _embed(self, texts: list[str]) -> list[list[float]]:
        try:
            response = self._openai.embeddings.create(model=EMBEDDING_MODEL, input=texts)
            return [d.embedding for d in response.data]
        except Exception:
            logger.exception("MongoKnowledgeStore: embedding call failed for %d chunk(s)", len(texts))
            raise

    @staticmethod
    def _chunk(text: str, size: int = CHUNK_SIZE) -> list[str]:
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        chunks: list[str] = []
        buf = ""
        for p in paragraphs:
            if len(buf) + len(p) < size:
                buf = f"{buf}\n\n{p}".strip()
            else:
                if buf:
                    chunks.append(buf)
                buf = p
        if buf:
            chunks.append(buf)
        return chunks or [text]

    # ---------------------------------------------------------------- seed

    def seed_from_file(self, path: str | Path) -> int:
        """Chunk + embed + upsert one markdown file. Returns chunks written."""
        path = Path(path)
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            logger.exception("MongoKnowledgeStore.seed_from_file: could not read %s", path)
            raise

        chunks = self._chunk(text)
        if not chunks:
            logger.warning("MongoKnowledgeStore.seed_from_file: %s produced no chunks", path)
            return 0

        try:
            # Clear old chunks for this file before re-inserting, so
            # re-running the seed script after an edit doesn't leave stale
            # chunks alongside the updated ones.
            self._collection.delete_many({"source_file": path.name})
            embeddings = self._embed(chunks)
            docs = [
                {
                    "_id": f"{path.stem}::{i}",
                    "source_file": path.name,
                    "chunk_index": i,
                    "content": chunk,
                    "embedding": emb,
                }
                for i, (chunk, emb) in enumerate(zip(chunks, embeddings, strict=True))
            ]
            self._collection.insert_many(docs)
            logger.info("Seeded %d chunk(s) from %s", len(docs), path.name)
            return len(docs)
        except PyMongoError:
            logger.exception("MongoKnowledgeStore.seed_from_file: write failed for %s", path)
            raise

    def seed_from_directory(self, directory: str | Path, pattern: str = "*.md") -> int:
        directory = Path(directory)
        total = 0
        for file in sorted(directory.glob(pattern)):
            try:
                total += self.seed_from_file(file)
            except Exception:
                # One bad file shouldn't stop the rest of the knowledge base
                # from seeding -- log and continue.
                logger.error("Skipping %s due to error above", file)
        return total

    # --------------------------------------------------------------- query

    def search(self, query: str, limit: int = 5, min_score: float = 0.0) -> list[dict]:
        try:
            query_embedding = self._embed([query])[0]
        except Exception:
            return []

        try:
            pipeline = [
                {
                    "$vectorSearch": {
                        "index": VECTOR_INDEX_NAME,
                        "path": "embedding",
                        "queryVector": query_embedding,
                        "numCandidates": max(limit * 10, 50),
                        "limit": limit,
                    }
                },
                {"$addFields": {"score": {"$meta": "vectorSearchScore"}}},
                {"$match": {"score": {"$gte": min_score}}},
                {"$project": {"embedding": 0}},
            ]
            return list(self._collection.aggregate(pipeline))
        except PyMongoError:
            logger.exception("MongoKnowledgeStore.search failed for query=%r", query)
            return []

    async def asearch(self, query: str, limit: int = 5, min_score: float = 0.0) -> list[dict]:
        return await asyncio.to_thread(self.search, query, limit, min_score)
