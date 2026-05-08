"""Job Description Pydantic schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.core.constants import DegreeLevel, ParseStatus, SeniorityLevel


class JDCreate(BaseModel):
    raw_text: str = Field(min_length=50, description="Full text of the job description.")
    title: str | None = Field(default=None, max_length=512)
    company: str | None = Field(default=None, max_length=512)


class YOERequirement(BaseModel):
    min: int | None = None
    max: int | None = None
    flexible: bool = False


class EducationRequirement(BaseModel):
    level: DegreeLevel | None = None
    field: str | None = None
    required: bool = False


class ParsedJDData(BaseModel):
    role_title: str | None = None
    seniority: SeniorityLevel | None = None
    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    years_experience_required: YOERequirement = Field(default_factory=YOERequirement)
    education_required: EducationRequirement = Field(default_factory=EducationRequirement)
    responsibilities: list[str] = Field(default_factory=list)
    must_have_flags: list[str] = Field(default_factory=list)
    # Quality warnings
    jd_quality_warnings: list[str] = Field(default_factory=list)
    aspirational_requirements: list[str] = Field(default_factory=list)


class JDRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID | None
    title: str | None
    company: str | None
    parse_status: ParseStatus
    created_at: datetime

    model_config = {"from_attributes": True}


class ParsedJDRead(JDRead):
    parsed_data: ParsedJDData | None = None
    raw_text: str
