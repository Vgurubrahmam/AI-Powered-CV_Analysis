"""Resume Pydantic schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.core.constants import FileType, ParseStatus


class ResumeUploadResponse(BaseModel):
    resume_id: uuid.UUID
    status: ParseStatus
    message: str = "Resume uploaded. Parsing queued."


class ParsedContact(BaseModel):
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    linkedin: str | None = None
    github: str | None = None
    location: str | None = None
    website: str | None = None


class ParsedExperienceItem(BaseModel):
    company: str | None = None
    title: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    duration_months: int | None = None
    bullets: list[str] = Field(default_factory=list)
    location: str | None = None


class ParsedEducationItem(BaseModel):
    institution: str | None = None
    degree: str | None = None
    field: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    gpa: float | None = None


class ParsedResumeData(BaseModel):
    contact: ParsedContact = Field(default_factory=ParsedContact)
    summary: str | None = None
    experience: list[ParsedExperienceItem] = Field(default_factory=list)
    education: list[ParsedEducationItem] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    projects: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)
    sections_detected: list[str] = Field(default_factory=list)
    total_yoe: float | None = None


class ResumeRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    storage_key: str | None = None
    filename: str = Field(alias="filename", serialization_alias="file_name")
    file_type: str | None = None
    file_size_bytes: int | None = None
    content_type: str | None = None
    parse_status: ParseStatus
    parse_confidence: float | None = None
    version: int | None = 1
    language: str | None = "en"
    created_at: datetime

    model_config = {"from_attributes": True, "populate_by_name": True}


class ParsedResumeRead(ResumeRead):
    parsed_data: ParsedResumeData | None = None
    raw_text: str | None = None
