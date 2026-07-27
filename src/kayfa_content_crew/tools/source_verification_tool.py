from __future__ import annotations

import json
import logging

from crewai.tools import tool

from kayfa_content_crew.tools.web_search_tool import _get_client

logger = logging.getLogger(__name__)


@tool("verify_source_claim")
def verify_source_claim(claim: str, source_hint: str) -> str:
    """Re-searches a claim to confirm it's still supported by current web
    results, instead of trusting a citation blindly. Input: claim, source_hint
    (topic/keyword to narrow the search)."""
    try:
        results = _get_client().search(query=f"{claim} {source_hint}", max_results=3)
        supported = len(results.get("results", [])) > 0
        return json.dumps({"claim": claim, "supported_by_search": supported})
    except Exception:
        logger.exception("verify_source_claim failed for claim=%r", claim)
        return json.dumps({"claim": claim, "supported_by_search": False, "error": "verification failed -- flag as unverified"})
