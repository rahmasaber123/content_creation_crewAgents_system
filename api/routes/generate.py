from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter()

# In-memory pending-draft store for this sandbox/demo. Swap for a real DB
# (e.g. a Mongo collection) once this needs to survive process restarts
# or run behind more than one worker process.
_pending_drafts: dict[str, dict] = {}


class GenerateRequest(BaseModel):
    topic: str
    brand: str = "Kayfa"
    content_type: str = "marketing_blog"


@router.post("/generate")
async def generate_draft(req: GenerateRequest) -> dict:
    try:
        from kayfa_content_crew.crew import build_draft_crew

        crew = build_draft_crew(content_type=req.content_type)
        result = await crew.kickoff_async(
            inputs={"topic": req.topic, "brand": req.brand, "content_type": req.content_type}
        )
    except Exception:
        logger.exception("generate_draft failed for topic=%r", req.topic)
        raise HTTPException(status_code=500, detail="Draft generation failed -- check server logs")

    if result.pydantic is None:
        logger.error("generate_draft: crew returned no structured output for topic=%r", req.topic)
        raise HTTPException(status_code=502, detail="Draft did not produce valid structured output")

    draft_id = str(uuid.uuid4())
    _pending_drafts[draft_id] = result.pydantic.model_dump()

    return {"draft_id": draft_id, "draft": _pending_drafts[draft_id]}


def get_pending_draft(draft_id: str) -> dict | None:
    return _pending_drafts.get(draft_id)


def pop_pending_draft(draft_id: str) -> dict | None:
    return _pending_drafts.pop(draft_id, None)
