"""Builds a MongoDB-persisted Memory instance for the crew.

Usage in crew.py:

    from kayfa_content_crew.memory_config import build_crew_memory
    crew = Crew(..., memory=build_crew_memory(strategist_llm))

Falls back to CrewAI's built-in local memory (LanceDB) with a logged
warning if MONGODB_URI isn't set, so a missing env var degrades the crew
to ephemeral memory instead of crashing it outright -- memory persistence
not working is recoverable; a hard crash mid-pipeline is not.
"""

from __future__ import annotations

import logging
import os

from crewai.memory.unified_memory import Memory

from kayfa_content_crew.storage.mongo_storage import MongoStorageBackend

logger = logging.getLogger(__name__)


def build_crew_memory(llm, embedder: dict | None = None) -> Memory | bool:
    """Returns a Memory instance backed by MongoDB, or True (built-in local
    memory) if MongoDB isn't configured. `llm` and optional `embedder` are
    passed through to CrewAI's Memory for its consolidation/recall flows."""
    mongo_uri = os.environ.get("MONGODB_URI")
    if not mongo_uri:
        logger.warning(
            "MONGODB_URI not set -- falling back to local (non-persistent) memory. "
            "Set MONGODB_URI in .env to persist memory across restarts/deployments."
        )
        return True  # Crew(memory=True) -- built-in local default

    db_name = os.environ.get("MONGODB_DB_NAME", "kayfa_crew")
    embed_dims = int(os.environ.get("MEMORY_EMBEDDING_DIMS", "1536"))

    try:
        backend = MongoStorageBackend(
            mongo_uri=mongo_uri, db_name=db_name, embedding_dims=embed_dims
        )
    except Exception:
        logger.exception(
            "Failed to initialize MongoStorageBackend -- falling back to local memory"
        )
        return True

    memory_kwargs = {
        "storage": backend,
        "llm": llm,
        # Pinned to match MongoStorageBackend's embedding_dims (1536).
        # CrewAI's own default embedder changed to text-embedding-3-large
        # (3072 dims) in a recent release -- without pinning this explicitly,
        # every memory save/search throws EmbeddingDimensionMismatchError
        # since the Mongo store and the embedder disagree on vector size.
        "embedder": embedder or {"provider": "openai", "config": {"model": "text-embedding-3-small"}},
    }

    try:
        return Memory(**memory_kwargs)
    except Exception:
        logger.exception("Failed to construct Memory with Mongo backend -- falling back to local memory")
        return True