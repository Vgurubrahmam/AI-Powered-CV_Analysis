"""Education analyzer — degree level mapping, field relevance, certification detection.

Maps parsed education entries to a normalized degree level, scores relevance
to the job description field requirements, and detects professional certifications.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

import structlog

from app.core.constants import DegreeLevel

log = structlog.get_logger(__name__)

# ─── Degree level ranking (higher = better) ───────────────────────────────────
_DEGREE_RANK: dict[DegreeLevel, int] = {
    DegreeLevel.HIGH_SCHOOL: 1,
    DegreeLevel.BOOTCAMP: 2,
    DegreeLevel.CERTIFICATION: 3,
    DegreeLevel.ASSOCIATE: 4,
    DegreeLevel.BACHELOR: 5,
    DegreeLevel.MBA: 6,
    DegreeLevel.MASTER: 7,
    DegreeLevel.PHD: 8,
    DegreeLevel.OTHER: 2,
}

# ─── Keyword → DegreeLevel mapping ───────────────────────────────────────────
_DEGREE_KEYWORDS: list[tuple[list[str], DegreeLevel]] = [
    (["phd", "ph.d", "doctor", "doctorate", "d.phil"], DegreeLevel.PHD),
    (["mba", "m.b.a", "master of business"], DegreeLevel.MBA),
    (["master", "m.sc", "m.s.", "ms ", "msc", "m.eng", "m.tech"], DegreeLevel.MASTER),
    (["bachelor", "b.sc", "b.s.", "b.eng", "b.tech", "b.a.", "undergraduate"], DegreeLevel.BACHELOR),
    (["associate", "a.a.", "a.s."], DegreeLevel.ASSOCIATE),
    (["bootcamp", "boot camp", "intensive program", "nanodegree", "nanodegrees"], DegreeLevel.BOOTCAMP),
    (["certification", "certificate", "certified", "cpa", "cfa", "cissp", "pmp", "aws certified"], DegreeLevel.CERTIFICATION),
    (["high school", "secondary school", "ged", "diploma"], DegreeLevel.HIGH_SCHOOL),
]

# ─── STEM field keywords ──────────────────────────────────────────────────────
_STEM_FIELDS = {
    "computer science", "computer engineering", "software engineering",
    "information technology", "information systems", "data science",
    "electrical engineering", "electronics", "mathematics", "statistics",
    "physics", "cybersecurity", "artificial intelligence", "machine learning",
}

# ─── Professional certifications (for detection) ─────────────────────────────
_CERT_PATTERNS = [
    r"AWS\s+Certified",
    r"Google\s+Cloud\s+(Professional|Associate|Engineer)",
    r"Microsoft\s+Certified",
    r"CPA",
    r"CFA\b",
    r"PMP\b",
    r"CISSP\b",
    r"CISM\b",
    r"CompTIA\s+(Security|Network|A)\+",
    r"Kubernetes\s+(CKAD|CKA|CKS)",
    r"Terraform\s+Associate",
    r"Certified\s+Scrum",
    r"TOGAF",
    r"ITIL\b",
]


@dataclass
class EducationEntry:
    """Parsed education record."""

    degree_level: DegreeLevel
    field_of_study: str = ""
    institution: str = ""
    graduation_year: Optional[int] = None
    gpa: Optional[float] = None
    is_stem: bool = False


@dataclass
class EducationAnalysisResult:
    """Result of education analysis."""

    score: float                             # 0–100
    highest_degree: Optional[DegreeLevel]
    meets_requirement: bool
    field_relevance_score: float             # 0–100, STEM/relevant field match
    certifications_found: list[str] = field(default_factory=list)
    education_entries: list[EducationEntry] = field(default_factory=list)
    details: dict = field(default_factory=dict)


def analyze_education(
    education_data: list[dict],
    required_degree: Optional[str] = None,
    preferred_fields: Optional[list[str]] = None,
    full_resume_text: str = "",
) -> EducationAnalysisResult:
    """Analyze education from parsed education entries.

    Args:
        education_data: List of parsed education dicts (degree, field, institution, year).
        required_degree: Minimum required degree level string (e.g. "bachelor").
        preferred_fields: List of preferred study fields (e.g. ["computer science"]).
        full_resume_text: Full resume text (used for certification detection).

    Returns:
        EducationAnalysisResult with score and detailed breakdown.
    """
    entries = [_parse_education_entry(e) for e in education_data]
    certifications = _detect_certifications(full_resume_text)

    if not entries and not certifications:
        return EducationAnalysisResult(
            score=0.0,
            highest_degree=None,
            meets_requirement=False,
            field_relevance_score=0.0,
            certifications_found=certifications,
        )

    # ── Highest degree ────────────────────────────────────────────────────────
    highest = max(entries, key=lambda e: _DEGREE_RANK.get(e.degree_level, 0)) if entries else None
    highest_degree = highest.degree_level if highest else None

    # ── Requirement check ─────────────────────────────────────────────────────
    meets_req = True
    if required_degree and highest_degree:
        req_level = _parse_degree_level(required_degree)
        if req_level:
            meets_req = _DEGREE_RANK.get(highest_degree, 0) >= _DEGREE_RANK.get(req_level, 0)
        else:
            meets_req = True  # unknown requirement → don't penalize

    # ── Base score from degree level ──────────────────────────────────────────
    degree_score = _degree_to_score(highest_degree) if highest_degree else 20.0
    if not meets_req:
        degree_score = max(10.0, degree_score - 25.0)

    # ── Field relevance ───────────────────────────────────────────────────────
    field_relevance = _compute_field_relevance(entries, preferred_fields)

    # ── Certification bonus ───────────────────────────────────────────────────
    cert_bonus = min(15.0, len(certifications) * 5.0)

    # ── Composite score ───────────────────────────────────────────────────────
    # 60% degree level + 25% field relevance + 15% certs
    score = degree_score * 0.60 + field_relevance * 0.25 + cert_bonus
    score = round(min(100.0, max(0.0, score)), 2)

    log.debug(
        "education_analysis_complete",
        score=score,
        highest_degree=highest_degree,
        meets_req=meets_req,
        certs=len(certifications),
    )

    return EducationAnalysisResult(
        score=score,
        highest_degree=highest_degree,
        meets_requirement=meets_req,
        field_relevance_score=round(field_relevance, 2),
        certifications_found=certifications,
        education_entries=entries,
        details={
            "degree_score": round(degree_score, 2),
            "cert_bonus": round(cert_bonus, 2),
            "required_degree": required_degree,
        },
    )


# ─── Internal helpers ─────────────────────────────────────────────────────────

def _parse_education_entry(raw: dict) -> EducationEntry:
    """Parse raw education dict to EducationEntry."""
    degree_raw = raw.get("degree", "") or ""
    field_raw = raw.get("field", "") or raw.get("field_of_study", "") or ""
    institution = raw.get("institution", "") or ""
    year_raw = raw.get("graduation_year") or raw.get("year")

    degree_level = _parse_degree_level(degree_raw) or DegreeLevel.OTHER
    is_stem = any(f in field_raw.lower() for f in _STEM_FIELDS)

    graduation_year: Optional[int] = None
    if year_raw:
        try:
            graduation_year = int(str(year_raw)[:4])
        except (ValueError, TypeError):
            pass

    return EducationEntry(
        degree_level=degree_level,
        field_of_study=field_raw,
        institution=institution,
        graduation_year=graduation_year,
        is_stem=is_stem,
    )


def _parse_degree_level(text: str) -> Optional[DegreeLevel]:
    """Attempt to map a raw degree string to a DegreeLevel enum."""
    text_lower = text.lower()
    for keywords, level in _DEGREE_KEYWORDS:
        if any(kw in text_lower for kw in keywords):
            return level
    return None


def _degree_to_score(level: DegreeLevel) -> float:
    """Convert degree level to base score (0–85)."""
    mapping = {
        DegreeLevel.HIGH_SCHOOL: 20.0,
        DegreeLevel.BOOTCAMP: 35.0,
        DegreeLevel.CERTIFICATION: 40.0,
        DegreeLevel.ASSOCIATE: 50.0,
        DegreeLevel.BACHELOR: 70.0,
        DegreeLevel.MBA: 80.0,
        DegreeLevel.MASTER: 82.0,
        DegreeLevel.PHD: 85.0,
        DegreeLevel.OTHER: 30.0,
    }
    return mapping.get(level, 30.0)


def _compute_field_relevance(
    entries: list[EducationEntry],
    preferred_fields: Optional[list[str]],
) -> float:
    """Score how relevant the candidate's study fields are to preferred fields."""
    if not entries:
        return 0.0

    # STEM base relevance
    stem_entries = [e for e in entries if e.is_stem]
    if stem_entries:
        base = 60.0
    else:
        base = 20.0

    if not preferred_fields:
        return base

    # Check for direct field matches
    pref_lower = [f.lower() for f in preferred_fields]
    for entry in entries:
        field_lower = entry.field_of_study.lower()
        for pref in pref_lower:
            if pref in field_lower or field_lower in pref:
                return 100.0  # direct match

    # Partial token overlap
    pref_tokens = {tok for pref in pref_lower for tok in pref.split()}
    for entry in entries:
        field_tokens = set(entry.field_of_study.lower().split())
        overlap = len(pref_tokens & field_tokens)
        if overlap >= 2:
            return 75.0
        if overlap >= 1:
            return 55.0

    return base


def _detect_certifications(text: str) -> list[str]:
    """Scan resume text for professional certification mentions."""
    found: list[str] = []
    for pattern in _CERT_PATTERNS:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches:
            label = match if isinstance(match, str) else " ".join(match)
            if label and label not in found:
                found.append(label.strip())
    return found
