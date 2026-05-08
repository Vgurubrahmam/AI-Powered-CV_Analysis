"""Bias auditor — anonymized proxy-field risk detection.

This module does NOT make hiring decisions. It flags resume fields that are
legally protected proxy attributes (age, gender signals, nationality markers, etc.)
that COULD introduce bias in automated screening.

Usage is purely informational / audit-trail, never to filter candidates.

All outputs are stored in the analysis audit_log, not exposed to candidates directly.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import structlog

log = structlog.get_logger(__name__)


class BiasRiskLevel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class BiasFlag:
    """A single detected proxy-field risk."""

    field: str                   # e.g. "graduation_year", "name_gender_signal"
    risk_level: BiasRiskLevel
    description: str
    recommendation: str


@dataclass
class BiasAuditResult:
    """Result of bias audit on a parsed resume."""

    risk_score: float                            # 0–100 (higher = more proxy fields present)
    flags: list[BiasFlag] = field(default_factory=list)
    proxy_fields_detected: list[str] = field(default_factory=list)
    audit_note: str = ""


# ─── Proxy-field detectors ────────────────────────────────────────────────────

# Gender-coded language patterns (not gender of person, but coded language)
_GENDERED_LANGUAGE_PATTERNS = [
    (r"\b(he|him|his)\b", "male pronoun usage"),
    (r"\b(she|her|hers)\b", "female pronoun usage"),
    (r"\b(they|them|their)\b", None),          # neutral, not flagged
]

# Age proxy patterns (graduation years can reveal age)
_GRADUATION_YEAR_RANGE = (1960, 2005)  # years that reveal likely age > 40

# Name-based nationality signals — only flag if JD has no location requirement
# We detect patterns that might correlate with protected characteristics
_RELIGIOUS_TERMS = re.compile(
    r"\b(church|mosque|temple|synagogue|pastor|imam|rabbi|deacon|"
    r"christian fellowship|islamic|jewish|hindu|buddhist)\b",
    re.IGNORECASE,
)

# Military discharge codes or veteran status (protected in some jurisdictions)
_MILITARY_PATTERNS = re.compile(
    r"\b(veteran|honorable discharge|military service|armed forces|usmc|us army|us navy|"
    r"us air force|national guard|reserves)\b",
    re.IGNORECASE,
)

# Photo / physical appearance references
_PHOTO_PATTERNS = re.compile(
    r"\b(photo|photograph|headshot|picture|attached photo|see photo)\b",
    re.IGNORECASE,
)

# Marital status / family situation
_MARITAL_PATTERNS = re.compile(
    r"\b(married|single|divorced|widowed|spouse|husband|wife|children|kids|"
    r"father of|mother of|parent of)\b",
    re.IGNORECASE,
)

# Age — explicit mentions
_AGE_MENTION = re.compile(r"\bage[d]?\s*\d{2}\b|\b\d{2}\s*years?\s*old\b", re.IGNORECASE)


def audit_bias_risks(
    resume_text: str,
    parsed_data: dict | None = None,
) -> BiasAuditResult:
    """Scan resume for proxy fields that may introduce demographic bias.

    Args:
        resume_text: Full resume plain text.
        parsed_data: Optional parsed resume dict (for structured field checks).

    Returns:
        BiasAuditResult with risk score and flagged fields.
    """
    flags: list[BiasFlag] = []

    text = resume_text or ""
    parsed = parsed_data or {}

    # ── 1. Explicit age mention ───────────────────────────────────────────────
    if _AGE_MENTION.search(text):
        flags.append(BiasFlag(
            field="explicit_age",
            risk_level=BiasRiskLevel.HIGH,
            description="Resume explicitly states the candidate's age.",
            recommendation="Remove age from resume. Age is not relevant to job qualifications.",
        ))

    # ── 2. Graduation year reveals age ───────────────────────────────────────
    education = parsed.get("education", [])
    for edu in education:
        yr = edu.get("graduation_year") or edu.get("year")
        if yr:
            try:
                year_int = int(str(yr)[:4])
                if _GRADUATION_YEAR_RANGE[0] <= year_int <= _GRADUATION_YEAR_RANGE[1]:
                    flags.append(BiasFlag(
                        field="graduation_year",
                        risk_level=BiasRiskLevel.LOW,
                        description=(
                            f"Graduation year {year_int} may indirectly reveal the candidate's approximate age."
                        ),
                        recommendation="Consider whether graduation year is necessary for screening.",
                    ))
                    break
            except (ValueError, TypeError):
                pass

    # ── 3. Photo reference ────────────────────────────────────────────────────
    if _PHOTO_PATTERNS.search(text):
        flags.append(BiasFlag(
            field="photo_reference",
            risk_level=BiasRiskLevel.HIGH,
            description="Resume references or includes a photo, which may reveal race, gender, or age.",
            recommendation="Do not use candidate photos in ATS screening. Anonymize before review.",
        ))

    # ── 4. Marital / family status ────────────────────────────────────────────
    if _MARITAL_PATTERNS.search(text):
        flags.append(BiasFlag(
            field="marital_or_family_status",
            risk_level=BiasRiskLevel.MEDIUM,
            description="Resume mentions marital or family status, which is a legally protected characteristic.",
            recommendation="Family status should be ignored in screening. Flag for anonymization.",
        ))

    # ── 5. Religious affiliation ──────────────────────────────────────────────
    if _RELIGIOUS_TERMS.search(text):
        flags.append(BiasFlag(
            field="religious_affiliation",
            risk_level=BiasRiskLevel.MEDIUM,
            description="Resume references religious organizations or activities.",
            recommendation="Religious affiliation is protected. Ensure it has no influence on scoring.",
        ))

    # ── 6. Military / veteran status ─────────────────────────────────────────
    if _MILITARY_PATTERNS.search(text):
        flags.append(BiasFlag(
            field="veteran_status",
            risk_level=BiasRiskLevel.LOW,
            description="Resume mentions military service or veteran status.",
            recommendation=(
                "Veteran status is a protected characteristic in many jurisdictions. "
                "Ensure it is not used as a negative signal."
            ),
        ))

    # ── 7. Address / zip code ────────────────────────────────────────────────
    contact = parsed.get("contact", {})
    address = contact.get("address", "") or ""
    if address and len(address) > 10:
        flags.append(BiasFlag(
            field="residential_address",
            risk_level=BiasRiskLevel.LOW,
            description="Full address present — neighborhood data can correlate with protected characteristics.",
            recommendation="Limit location data to city/state for screening purposes.",
        ))

    # ── Score: 0 = no issues, 100 = max risk ─────────────────────────────────
    weight_map = {
        BiasRiskLevel.HIGH: 25,
        BiasRiskLevel.MEDIUM: 15,
        BiasRiskLevel.LOW: 5,
    }
    risk_score = min(100.0, sum(weight_map[f.risk_level] for f in flags))
    proxy_fields = [f.field for f in flags]

    log.info(
        "bias_audit_complete",
        risk_score=risk_score,
        flags=len(flags),
        proxy_fields=proxy_fields,
    )

    audit_note = (
        "⚠ This audit is informational only. Bias flags must not be used to filter or rank candidates."
        if flags else
        "No high-risk proxy fields detected."
    )

    return BiasAuditResult(
        risk_score=round(risk_score, 2),
        flags=flags,
        proxy_fields_detected=proxy_fields,
        audit_note=audit_note,
    )
