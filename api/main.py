"""FastAPI entrypoint. Serves the vanilla-JS chat UI at / and the
/generate + /approve HITL-gated API underneath it."""

from __future__ import annotations

import logging
import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

# AgentOps must init before any crew/agent import that could trigger LLM calls.
try:
    import agentops

    agentops_key = os.environ.get("AGENTOPS_API_KEY")
    if agentops_key:
        agentops.init(api_key=agentops_key, skip_auto_end_session=True, default_tags=["crewai", "kayfa-content-crew"])
        logger.info("AgentOps monitoring initialized")
    else:
        logger.warning("AGENTOPS_API_KEY not set -- monitoring disabled")
except Exception:
    logger.exception("AgentOps init failed -- continuing without monitoring")

from api.routes import approve, generate  # noqa: E402

app = FastAPI(title="Kayfa Content Marketing Crew")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(generate.router)
app.include_router(approve.router)

_static_dir = os.path.join(os.path.dirname(__file__), "static")
app.mount("/", StaticFiles(directory=_static_dir, html=True), name="static")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
