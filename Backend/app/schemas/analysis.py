"""Analysis Pydantic schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.core.constants import AnalysisStatus


class AnalysisRequest(BaseModel):
    resume_id: uuid.UUID
    job_id: uuid.UUID


class ScoreBreakdown(BaseModel):
    keyword: float | None = None
    semantic: float | None = None
    skill_depth: float | None = None
    experience: float | None = None
    impact: float | None = None
    education: float | None = None


class ConfidenceInterval(BaseModel):
    lower: float
    upper: float
    confidence: float


class KeywordDetail(BaseModel):
    matched_required: list[str] = Field(default_factory=list)
    missing_required: list[str] = Field(default_factory=list)
    matched_preferred: list[str] = Field(default_factory=list)
    match_rate: float = 0.0


class SemanticDetail(BaseModel):
    per_requirement_scores: dict[str, float] = Field(default_factory=dict)
    mean_score: float = 0.0
    strong_matches: list[str] = Field(default_factory=list)
    weak_matches: list[str] = Field(default_factory=list)


class ExperienceDetail(BaseModel):
    total_yoe: float | None = None
    required_yoe: float | None = None
    seniority_inferred: str | None = None
    seniority_required: str | None = None
    career_progression_score: float | None = None


class AnalysisRead(BaseModel):
    id: uuid.UUID
    resume_id: uuid.UUID
    job_id: uuid.UUID
    status: AnalysisStatus
    score: float | None = Field(default=None, alias="score", serialization_alias="score_composite")
    confidence: float | None = None
    percentile: float | None = None
    created_at: datetime
    completed_at: datetime | None = None
    celery_task_id: str | None = None

    model_config = {"from_attributes": True, "populate_by_name": True}


class AnalysisResultRead(AnalysisRead):
    score_breakdown: ScoreBreakdown | None = None
    confidence_interval: ConfidenceInterval | None = None
    keyword_detail: KeywordDetail | None = None
    semantic_detail: SemanticDetail | None = None
    experience_detail: ExperienceDetail | None = None
    ats_warnings: list[str] | None = Field(default_factory=list)
    pipeline_meta: dict[str, Any] | None = None


class AnalysisCreateResponse(BaseModel):
    analysis_id: uuid.UUID
    status: AnalysisStatus
    message: str = "Analysis queued. Poll /analysis/{id} for status."
