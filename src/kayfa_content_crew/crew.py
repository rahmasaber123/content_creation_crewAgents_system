"""Kayfa Content Marketing Crew -- 3 agents, cost-optimized, MongoDB-persisted.

Two Crew objects, not one: draft_crew (Strategist-Researcher -> Writer-Editor)
and publish_crew (Publisher only). The gap between them IS the human-in-the-
loop gate -- nothing in publish_crew runs until the API's /approve endpoint
is called. This mirrors the notebook's input()-based simulation, but as a
real architectural boundary instead of a blocking prompt.
"""

from __future__ import annotations

import logging
import os

from crewai import Agent, Crew, Process, Task

from kayfa_content_crew.llms import build_llms
from kayfa_content_crew.memory_config import build_crew_memory
from kayfa_content_crew.schemas import BlogPost, SocialOutput
from kayfa_content_crew.tools.brand_voice_tool import brand_voice_check
from kayfa_content_crew.tools.char_limit_tool import validate_char_limit
from kayfa_content_crew.tools.knowledge_search_tool import company_knowledge_search, init_knowledge_tool
from kayfa_content_crew.tools.source_verification_tool import verify_source_claim
from kayfa_content_crew.tools.web_search_tool import web_search

logger = logging.getLogger(__name__)

_output_dir = os.environ.get("OUTPUT_DIR", "./outputs")
os.makedirs(_output_dir, exist_ok=True)


def _init_knowledge() -> None:
    """Wires the persistent MongoDB knowledge store into the knowledge tool.
    Safe to call multiple times; no-op if MONGODB_URI isn't set."""
    mongo_uri = os.environ.get("MONGODB_URI")
    if not mongo_uri:
        logger.warning("MONGODB_URI not set -- company_knowledge_search will report unavailable")
        return
    try:
        from kayfa_content_crew.knowledge.mongo_knowledge_store import MongoKnowledgeStore

        store = MongoKnowledgeStore(
            mongo_uri=mongo_uri,
            db_name=os.environ.get("MONGODB_DB_NAME", "kayfa_crew"),
            openai_api_key=os.environ.get("OPENAI_API_KEY"),
        )
        init_knowledge_tool(store)
    except Exception:
        logger.exception("Failed to initialize knowledge store -- continuing without it")


def build_agents() -> dict[str, Agent]:
    llms = build_llms()

    strategist_researcher = Agent(
        role="Content Strategist & Researcher",
        goal="Plan a content angle and gather verified, current facts before any writing begins.",
        backstory=(
            "A senior content lead at Kayfa who understands the bilingual Arabic/English "
            "e-learning audience deeply, and never lets a plan move forward on unverified assumptions."
        ),
        llm=llms["strategist"],
        tools=[web_search, company_knowledge_search],
        allow_delegation=False,
        verbose=True,
    )

    writer_editor = Agent(
        role="Writer-Editor",
        goal=(
            "Write a complete piece of content following the content plan, adapting tone and "
            "structure to the requested content_type (marketing_blog or technical_writing), "
            "then self-edit and verify every factual claim before finalizing."
        ),
        backstory=(
            "A bilingual writer at Kayfa who can switch between persuasive marketing copy and "
            "precise technical documentation, but never compromises on brand voice or factual accuracy."
        ),
        llm=llms["writer"],
        tools=[brand_voice_check, verify_source_claim, company_knowledge_search],
        allow_delegation=False,
        verbose=True,
    )

    publisher = Agent(
        role="Publisher",
        goal="Turn an approved post into platform-ready social captions with hashtags and bullets.",
        backstory="A distribution specialist who formats and delivers already-approved content, never edits substance.",
        llm=llms["publisher"],
        tools=[validate_char_limit],
        allow_delegation=False,
        verbose=True,
    )

    return {"strategist_researcher": strategist_researcher, "writer_editor": writer_editor, "publisher": publisher}


def build_plan_research_task(agent: Agent) -> Task:
    return Task(
        description="\n".join([
            "Topic: {topic}. Brand: {brand}.",
            "1. Define the target audience and content angle.",
            "2. Produce a 3-6 point outline.",
            "3. Research 3-8 target keywords using web_search.",
            "4. Use company_knowledge_search to ground the plan in Kayfa's actual positioning.",
            "5. List every source URL you actually used.",
        ]),
        expected_output="A structured content plan with audience, angle, outline, keywords, and sources.",
        output_file=os.path.join(_output_dir, "step_1_content_plan.json"),
        agent=agent,
    )


def build_write_edit_task(agent: Agent, plan_task: Task, content_type: str = "marketing_blog") -> Task:
    if content_type == "technical_writing":
        instructions = [
            "Using the content plan, write a TECHNICAL GUIDE (content_type='technical_writing').",
            "List prerequisites the reader needs before starting.",
            "Write numbered 'steps' (not 'sections'): heading is the step title, body is the "
            "instruction + expected result, using exact copy-pasteable values.",
            "Prioritize accuracy over persuasion -- no hashtags, no CTA, no hype language.",
            "Add a short troubleshooting note for the most likely failure point.",
            "Use company_knowledge_search for the technical_style_guide's formatting rules.",
            "Run brand_voice_check anyway -- Kayfa tone still applies, minus the marketing layer.",
            "Run verify_source_claim on every factual/technical claim before finalizing.",
            "Leave 'cta', 'hashtags', and 'sections' empty; use 'steps' instead.",
        ]
        expected = "A complete, accurate, brand-checked technical guide with prerequisites and numbered steps."
    else:
        instructions = [
            "Write a MARKETING BLOG POST (content_type='marketing_blog') on {topic} for {brand}, 500-700 words.",
            "This is a social/blog POST, not an academic article, whitepaper, or lecture -- write accordingly:",
            "- Open with a hook sentence, not a definition. Never start a section with 'Introduction' or 'Overview'.",
            "- Section headings must be curiosity or benefit-driven (e.g. 'The Mistake Most Teams Make'), never generic essay headers like 'Introduction', 'Conclusion', 'Future Outlook', 'Common Challenges'.",
            "- Each section body is 2-4 SHORT sentences or a short bullet list -- never a dense paragraph.",
            "- Never write a 'Conclusion' section. End with one punchy closing line + the CTA instead.",
            "- Avoid corporate/report language: no 'organizations should consider', 'landscape', 'inherent challenges', 'unlock the full potential'. Write like you're talking to one person, not presenting to a board.",
            "- Use real markdown bullets ('- point') for lists inside a section body -- these will render as an actual bulleted list, not inline text.",
            "Include a 'key_takeaways' bullet list summarizing the post up top.",
            "Use company_knowledge_search to check approved_claims before stating anything about Kayfa.",
            "Run brand_voice_check on your draft and rewrite any flagged phrases.",
            "Run verify_source_claim on every factual claim before finalizing.",
            "Generate 5-8 hashtags: 2-3 broad e-learning tags, 2-3 topic-specific tags, 1-2 branded (#Kayfa).",
            "Leave 'prerequisites' and 'steps' empty; use 'sections' instead.",
        ]
        expected = "A complete, brand-checked, fact-verified marketing blog post."

    return Task(
        description="\n".join(instructions),
        expected_output=expected,
        output_pydantic=BlogPost,
        output_file=os.path.join(_output_dir, "step_2_blog_post.json"),
        agent=agent,
        context=[plan_task],
    )


def build_repurpose_task(agent: Agent) -> Task:
    return Task(
        description="\n".join([
            "Using the approved blog post, write a LinkedIn post (bullet points + hashtags)",
            "and 2 tweets (use validate_char_limit to confirm each is under 280 characters).",
            "Reuse the same hashtags as the blog post where relevant.",
        ]),
        expected_output="LinkedIn post and 2 tweets, all within platform character limits.",
        output_pydantic=SocialOutput,
        output_file=os.path.join(_output_dir, "step_3_social_output.json"),
        agent=agent,
    )


def build_draft_crew(content_type: str = "marketing_blog") -> Crew:
    _init_knowledge()
    agents = build_agents()
    plan_task = build_plan_research_task(agents["strategist_researcher"])
    write_task = build_write_edit_task(agents["writer_editor"], plan_task, content_type)

    memory = build_crew_memory(llm=agents["strategist_researcher"].llm)

    return Crew(
        agents=[agents["strategist_researcher"], agents["writer_editor"]],
        tasks=[plan_task, write_task],
        process=Process.sequential,
        memory=memory,
        verbose=True,
    )


def build_publish_crew() -> Crew:
    agents = build_agents()
    repurpose_task = build_repurpose_task(agents["publisher"])
    return Crew(
        agents=[agents["publisher"]],
        tasks=[repurpose_task],
        process=Process.sequential,
        verbose=True,
    )