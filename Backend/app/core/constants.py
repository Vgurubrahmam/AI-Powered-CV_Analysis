"""Domain enums and constant values used across the application.

Never use raw strings for status codes or role names — always import from here.
"""

from __future__ import annotations

from enum import Enum


class UserRole(str, Enum):
    CANDIDATE = "candidate"
    RECRUITER = "recruiter"
    RECRUITER_ADMIN = "recruiter_admin"
    SYSTEM_ADMIN = "system_admin"


class PlanTier(str, Enum):
    FREE = "free"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class AnalysisStatus(str, Enum):
    QUEUED = "QUEUED"
    PARSING = "PARSING"
    MATCHING = "MATCHING"
    SCORING = "SCORING"
    FEEDBACK = "FEEDBACK"
    DONE = "DONE"
    FAILED = "FAILED"
    PARTIAL = "PARTIAL"


class ParseStatus(str, Enum):
    PENDING = "PENDING"
    SUCCESS = "SUCCESS"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


class FileType(str, Enum):
    PDF = "pdf"
    DOCX = "docx"
    TXT = "txt"


class FeedbackCategory(str, Enum):
    KEYWORD = "keyword"
    SEMANTIC = "semantic"
    IMPACT = "impact"
    ATS = "ats"
    EDUCATION = "education"
    EXPERIENCE = "experience"
    FORMATTING = "formatting"


class FeedbackSeverity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class EmbeddingSection(str, Enum):
    SUMMARY = "summary"
    EXPERIENCE = "experience"
    SKILLS = "skills"
    EDUCATION = "education"
    FULL = "full"


class ResumeSection(str, Enum):
    SUMMARY = "summary"
    OBJECTIVE = "objective"
    EXPERIENCE = "experience"
    EDUCATION = "education"
    SKILLS = "skills"
    CERTIFICATIONS = "certifications"
    PROJECTS = "projects"
    AWARDS = "awards"
    PUBLICATIONS = "publications"
    VOLUNTEERING = "volunteering"
    CONTACT = "contact"
    UNKNOWN = "unknown"


class SeniorityLevel(str, Enum):
    INTERN = "intern"
    JUNIOR = "junior"
    MID = "mid"
    SENIOR = "senior"
    LEAD = "lead"
    PRINCIPAL = "principal"
    DIRECTOR = "director"
    VP = "vp"
    C_LEVEL = "c_level"


class DegreeLevel(str, Enum):
    HIGH_SCHOOL = "high_school"
    ASSOCIATE = "associate"
    BACHELOR = "bachelor"
    MASTER = "master"
    PHD = "phd"
    MBA = "mba"
    BOOTCAMP = "bootcamp"
    CERTIFICATION = "certification"
    OTHER = "other"


# ─── Magic constants ──────────────────────────────────────────────────────────

# Semantic matching thresholds
SEMANTIC_STRONG_MATCH = 0.70
SEMANTIC_PARTIAL_MATCH = 0.50

# Parse confidence thresholds
PARSE_CONFIDENCE_OCR_MAX = 0.60
PARSE_CONFIDENCE_PARTIAL_THRESHOLD = 0.70

# Analysis requeue timeout (minutes)
ANALYSIS_STUCK_TIMEOUT_MINUTES = 10

# Score calibration
SCORE_STABILITY_TOLERANCE = 2.0   # pts — same input re-analysis must stay within ±2

# JD quality warnings
JD_MAX_REASONABLE_REQUIRED_SKILLS = 15
JD_MAX_YOE_FOR_TECH = 10          # Flag if JD requires > 10 YOE for a tech skill

# Token limits per task type (for OpenRouter)
TOKEN_LIMITS = {
    "jd_parse": 2000,
    "skill_extract": 1500,
    "impact_score": 2000,
    "feedback_generate": 3000,
    "rewrite": 2500,
}
