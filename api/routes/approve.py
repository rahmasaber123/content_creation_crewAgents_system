from __future__ import annotations

import logging
import os

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter()


class ApproveRequest(BaseModel):
    draft_id: str
    approved: bool
    edited_content: dict | None = None  # optional human edits before publishing


@router.post("/approve")
async def approve_and_publish(req: ApproveRequest) -> dict:
    from api.routes.generate import pop_pending_draft
    from kayfa_content_crew.schemas import BlogPost
    from kayfa_content_crew.tools.email_sender_tool import send_email_with_pdf
    from kayfa_content_crew.tools.pdf_generator_tool import generate_pdf

    draft_data = pop_pending_draft(req.draft_id)
    if draft_data is None:
        raise HTTPException(status_code=404, detail="draft_id not found or already processed")

    if not req.approved:
        logger.info("Draft %s rejected by human reviewer", req.draft_id)
        return {"status": "rejected", "draft_id": req.draft_id}

    try:
        merged = {**draft_data, **(req.edited_content or {})}
        blog_post = BlogPost(**merged)
    except Exception:
        logger.exception("approve_and_publish: failed to parse edited_content for draft_id=%s", req.draft_id)
        raise HTTPException(status_code=400, detail="edited_content did not match the BlogPost schema")

    output_dir = os.environ.get("OUTPUT_DIR", "./outputs")
    os.makedirs(output_dir, exist_ok=True)
    pdf_path = os.path.join(output_dir, f"{req.draft_id}.pdf")

    try:
        generate_pdf(blog_post, pdf_path)
    except Exception:
        logger.exception("approve_and_publish: PDF generation failed for draft_id=%s", req.draft_id)
        raise HTTPException(status_code=500, detail="PDF generation failed -- check server logs")

    social_output = None
    if blog_post.content_type != "technical_writing":
        try:
            from kayfa_content_crew.crew import build_publish_crew

            publish_crew = build_publish_crew()
            social_result = await publish_crew.kickoff_async(inputs={"approved_post": blog_post.model_dump_json()})
            social_output = social_result.pydantic.model_dump() if social_result.pydantic else None
        except Exception:
            logger.exception("approve_and_publish: social repurposing failed for draft_id=%s", req.draft_id)
            # Not fatal -- PDF is already generated; continue to email step.

    recipients = os.environ.get("EMAIL_RECIPIENTS", "")
    email_result = "No recipients configured"
    if recipients:
        try:
            email_result = send_email_with_pdf(
                recipient=recipients.split(",")[0].strip(),
                subject=f"Approved post ready: {blog_post.title}",
                pdf_path=pdf_path,
            )
        except Exception:
            logger.exception("approve_and_publish: email step failed for draft_id=%s", req.draft_id)
            email_result = "Email failed -- see server logs"

    return {
        "status": "published",
        "draft_id": req.draft_id,
        "pdf_path": pdf_path,
        "social_output": social_output,
        "email_result": email_result,
    }
