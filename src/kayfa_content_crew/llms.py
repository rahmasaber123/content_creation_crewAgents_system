"""Per-agent LLM routing. Match model cost to task complexity:
real reasoning gets a frontier-tier model, formatting-only work gets the
cheapest tier available. Requires `litellm` installed for the Groq model
(non-native provider) -- see requirements.txt.
"""

from __future__ import annotations

import logging

from crewai import LLM

logger = logging.getLogger(__name__)


def build_llms() -> dict[str, LLM]:
    try:
        strategist_llm = LLM(model="gpt-4o-mini", temperature=0.3)
        writer_llm = LLM(model="gpt-4o-mini", temperature=0.5)
        publisher_llm = LLM(model="groq/llama-3.3-70b-versatile", temperature=0.2)
    except ImportError:
        logger.exception(
            "LLM init failed -- likely missing `litellm` for the Groq model. "
            "pip install litellm"
        )
        raise
    return {"strategist": strategist_llm, "writer": writer_llm, "publisher": publisher_llm}
