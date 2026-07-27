"""Pydantic schemas shared across tasks -- the 'content contract'.

No min_items/max_items on LLM-generated lists (see project history: this
caused repeated ValidationError crashes on real runs since real LLM output
length varies run to run). Guidance on target length lives in task
descriptions instead; schemas stay permissive with default_factory=list.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ContentPlan(BaseModel):
    audience: str
    angle: str
    outline: list[str] = Field(default_factory=list, description="3-6 point outline, guidance only")
    target_keywords: list[str] = Field(default_factory=list, description="3-8 keywords, guidance only")
    sources: list[str] = Field(default_factory=list, description="URLs used for research")


class PostSection(BaseModel):
    heading: str
    body: str = Field(..., description="Can include markdown bullet points, e.g. '- point one'")


class BlogPost(BaseModel):
    title: str
    slug: str
    meta_description: str
    content_type: str = Field(default="marketing_blog", description="'marketing_blog' or 'technical_writing'")

    # marketing_blog fields
    key_takeaways: list[str] = Field(default_factory=list)
    sections: list[PostSection] = Field(default_factory=list)
    cta: str = ""
    hashtags: list[str] = Field(default_factory=list)

    # technical_writing fields
    prerequisites: list[str] = Field(default_factory=list)
    steps: list[PostSection] = Field(default_factory=list)

    intro: str
    conclusion: str
    word_count: int = 0
    sources: list[str] = Field(default_factory=list)


class SocialOutput(BaseModel):
    linkedin_post: str
    tweets: list[str] = Field(default_factory=list)
    hashtags: list[str] = Field(default_factory=list)
