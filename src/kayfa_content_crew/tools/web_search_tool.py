from __future__ import annotations

import json
import logging
import os

from crewai.tools import tool
from tavily import TavilyClient

logger = logging.getLogger(__name__)
_client: TavilyClient | None = None


def _get_client() -> TavilyClient:
    global _client
    if _client is None:
        api_key = os.environ.get("TAVILY_API_KEY")
        if not api_key:
            raise RuntimeError("TAVILY_API_KEY not set")
        _client = TavilyClient(api_key=api_key)
    return _client


@tool("web_search")
def web_search(query: str) -> str:
    """Live web search for current facts, trends, and competitor content. Input: a query string."""
    try:
        results = _get_client().search(query=query, max_results=5)
        return json.dumps(results)
    except Exception:
        logger.exception("web_search failed for query=%r", query)
        return json.dumps({"error": "search failed", "query": query, "results": []})
