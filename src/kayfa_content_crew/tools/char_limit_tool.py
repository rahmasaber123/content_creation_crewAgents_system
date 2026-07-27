from __future__ import annotations

import json
import logging

from crewai.tools import tool

logger = logging.getLogger(__name__)

_LIMITS = {"x": 280, "twitter": 280, "linkedin": 3000}


@tool("validate_char_limit")
def validate_char_limit(text: str, platform: str) -> str:
    """Hard-validates text length against platform limits. Input: text,
    platform ('x' or 'linkedin'). Never trust an LLM to count characters itself."""
    try:
        limit = _LIMITS.get(platform.lower(), 3000)
        return json.dumps({"valid": len(text) <= limit, "char_count": len(text), "limit": limit})
    except Exception:
        logger.exception("validate_char_limit failed")
        return json.dumps({"valid": False, "error": "validation failed"})
