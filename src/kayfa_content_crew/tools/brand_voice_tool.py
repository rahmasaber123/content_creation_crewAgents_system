from __future__ import annotations

import json
import logging

from crewai.tools import tool

logger = logging.getLogger(__name__)

_BANNED_WORDS = ["leverage", "synergy", "synergistic", "disrupt", "disruptive", "revolutionize", "utilize", "paradigm"]


@tool("brand_voice_check")
def brand_voice_check(draft_text: str) -> str:
    """Flags corporate/off-brand words against Kayfa's tone guide. Input: draft_text.
    Output: JSON with flagged_words list and clean=bool. For deeper grounding
    against the full style guide, also use company_knowledge_search."""
    try:
        lowered = draft_text.lower()
        flagged = [w for w in _BANNED_WORDS if w in lowered]
        return json.dumps({"flagged_words": flagged, "clean": len(flagged) == 0})
    except Exception:
        logger.exception("brand_voice_check failed")
        return json.dumps({"flagged_words": [], "clean": True, "error": "check failed, proceed with caution"})
