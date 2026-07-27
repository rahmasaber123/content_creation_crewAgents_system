"""Agent-facing tool for querying the persistent MongoDB knowledge base.

Replaces the notebook's ephemeral StringKnowledgeSource -- knowledge now
lives in MongoDB (seeded once via seed_knowledge.py), survives restarts,
and is queried on-demand instead of being fully re-injected into every
prompt.
"""

from __future__ import annotations

import logging

from crewai.tools import tool

from kayfa_content_crew.knowledge.mongo_knowledge_store import MongoKnowledgeStore

logger = logging.getLogger(__name__)

_store: MongoKnowledgeStore | None = None


def init_knowledge_tool(store: MongoKnowledgeStore) -> None:
    """Call once at app/crew startup before agents run."""
    global _store
    _store = store


@tool("company_knowledge_search")
def company_knowledge_search(query: str) -> str:
    """Search Kayfa's persistent knowledge base (brand voice, company info,
    approved claims, technical style guide) stored in MongoDB. Input: a
    query string. Output: the most relevant knowledge chunks with their
    source file, so claims can be traced back to an approved document."""
    if _store is None:
        logger.error("company_knowledge_search called before init_knowledge_tool()")
        return "Knowledge store not initialized -- call init_knowledge_tool() at startup."

    try:
        results = _store.search(query, limit=5)
    except Exception:
        logger.exception("company_knowledge_search failed for query=%r", query)
        return "Knowledge search temporarily unavailable -- proceed with caution and flag this in your output."

    if not results:
        return "No matching knowledge found for this query."

    return "\n\n".join(
        f"[{r.get('source_file', 'unknown')}] {r.get('content', '')}" for r in results
    )
