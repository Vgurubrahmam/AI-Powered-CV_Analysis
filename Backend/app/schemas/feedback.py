"""Feedback Pydantic schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.core.constants import FeedbackCategory, FeedbackSeverity


class FeedbackItemRead(BaseModel):
    id: uuid.UUID
    analysis_id: uuid.UUID
    category: FeedbackCategory
    severity: FeedbackSeverity
    title: str
    description: str
    original_text: str | None = None
    suggested_text: str | None = None
    score_delta: float | None = None
    source_section: str | None = None
    accepted: bool | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class FeedbackAcceptRequest(BaseModel):
    accepted: bool


class RewriteRequest(BaseModel):
    feedback_item_id: uuid.UUID
    section: str = Field(description="Resume section to rewrite (e.g. 'experience', 'summary')")


class RewriteResult(BaseModel):
    feedback_item_id: uuid.UUID
    original_text: str
    rewritten_text: str
    hallucination_check_passed: bool
    flagged_entities: list[str] = Field(default_factory=list)
    warning: str | None = None
