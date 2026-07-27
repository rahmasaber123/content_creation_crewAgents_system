"""Seed knowledge/*.md into MongoDB Atlas Vector Search.

Run once at setup, and again any time a knowledge file changes:

    python -m kayfa_content_crew.seed_knowledge

Re-running is safe -- seed_from_file() clears old chunks for a given
source file before re-inserting, so edits don't leave stale chunks behind.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from kayfa_content_crew.knowledge.mongo_knowledge_store import MongoKnowledgeStore

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def main() -> int:
    load_dotenv()

    mongo_uri = os.environ.get("MONGODB_URI")
    openai_key = os.environ.get("OPENAI_API_KEY")
    if not mongo_uri:
        logger.error("MONGODB_URI is not set -- check your .env file")
        return 1
    if not openai_key:
        logger.error("OPENAI_API_KEY is not set -- required for embeddings")
        return 1

    knowledge_dir = Path(__file__).resolve().parents[2] / "knowledge"
    if not knowledge_dir.exists():
        logger.error("Knowledge directory not found at %s", knowledge_dir)
        return 1

    try:
        store = MongoKnowledgeStore(mongo_uri=mongo_uri, openai_api_key=openai_key)
    except Exception:
        logger.exception("Failed to initialize MongoKnowledgeStore -- check MONGODB_URI and network access")
        return 1

    try:
        total = store.seed_from_directory(knowledge_dir)
    except Exception:
        logger.exception("Seeding failed")
        return 1

    if total == 0:
        logger.warning("No chunks were written -- check that knowledge/*.md files exist and aren't empty")
        return 1

    logger.info("Done. %d total chunk(s) seeded from %s", total, knowledge_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
