"""Feedback generator — LLM-backed specific feedback per score gap."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

import structlog

from app.core.constants import FeedbackCategory, FeedbackSeverity

log = structlog.get_logger(__name__)

_FEEDBACK_PROMPT = """You are a senior recruiter and career coach with 15 years of experience.

A candidate's resume was analyzed against a job description. Generate specific, actionable feedback.

CRITICAL RULES:
- Be SPECIFIC. Reference the exact gap, not generic advice.
- Each feedback item must explain WHY it matters for THIS specific role.
- Do NOT give generic advice that applies to any resume.
- Limit to the {max_items} most impactful gaps.

Resume Score: {composite_score}/100
Role: {role_title}
Missing Required Skills: {missing_required}
Weak Bullet Points (low quantification): {weak_bullets}
ATS Issues: {ats_warnings}
Experience Gap: {experience_gap}

Return a JSON array of feedback items:
[
  {{
    "category": "<EXACTLY ONE of: keyword, semantic, impact, ats, education, experience, formatting>",
    "severity": "critical|high|medium|low",
    "title": "Short title (max 10 words)",
    "description": "Specific description of the issue and why it matters (2-3 sentences)",
    "original_text": "The specific text from the resume that needs improvement (or null)",
    "score_delta": <estimated score points improvement if fixed, 1-15>,
    "source_section": "experience|skills|education|summary|formatting"
  }}
]

IMPORTANT: The "category" field must be exactly ONE of these values: keyword, semantic, impact, ats, education, experience, formatting.
Do NOT combine multiple categories. Each feedback item gets ONE category.

Return ONLY the JSON array, no other text."""


_VALID_CATEGORIES = {c.value for c in FeedbackCategory}
_VALID_SEVERITIES = {s.value for s in FeedbackSeverity}


def _normalize_category(raw: str) -> str:
    """Ensure category is a single valid FeedbackCategory value."""
    if not raw:
        return FeedbackCategory.ATS.value
    val = raw.strip().lower()
    # LLM sometimes returns pipe-delimited categories — take the first valid one
    if "|" in val:
        for part in val.split("|"):
            part = part.strip()
            if part in _VALID_CATEGORIES:
                return part
    if val in _VALID_CATEGORIES:
        return val
    return FeedbackCategory.ATS.value


def _normalize_severity(raw: str) -> str:
    """Ensure severity is a single valid FeedbackSeverity value."""
    if not raw:
        return FeedbackSeverity.MEDIUM.value
    val = raw.strip().lower()
    if val in _VALID_SEVERITIES:
        return val
    return FeedbackSeverity.MEDIUM.value


@dataclass
class FeedbackItemData:
    category: str
    severity: str
    title: str
    description: str
    original_text: str | None = None
    score_delta: float | None = None
    source_section: str | None = None


async def generate_feedback(
    analysis_data: dict[str, Any],
    max_items: int = 10,
) -> list[FeedbackItemData]:
    """Generate prioritized feedback items using LLM.

    Falls back to rule-based feedback if LLM fails.
    """
    from app.integrations.llm.client import get_llm_client
    from app.config import settings

    try:
        client = get_llm_client()
        prompt = _build_feedback_prompt(analysis_data, max_items)

        response = await client.complete(
            prompt=prompt,
            model=settings.NVIDIA_DEFAULT_MODEL,
            max_tokens=2000,
            temperature=0.2,
        )

        items = _parse_feedback_response(response)
        if items:
            log.info("feedback_generated_via_llm", count=len(items))
            return items

    except Exception as exc:
        log.warning("feedback_llm_failed", error=str(exc), fallback="rule_based")

    # Fallback: rule-based feedback
    return _rule_based_feedback(analysis_data)


def _build_feedback_prompt(data: dict, max_items: int) -> str:
    keyword_data = data.get("keyword_result", {})
    missing_required = keyword_data.get("missing_required", [])[:10]
    weak_bullets = data.get("weak_bullets", [])[:5]
    ats_warnings = data.get("ats_warnings", [])[:3]
    experience_gap = data.get("experience_gap", "None identified")
    composite = data.get("composite_score", 0)
    role_title = data.get("role_title", "the specified role")

    return _FEEDBACK_PROMPT.format(
        max_items=max_items,
        composite_score=composite,
        role_title=role_title,
        missing_required=", ".join(missing_required) if missing_required else "None",
        weak_bullets="\n".join(f"- {b}" for b in weak_bullets) if weak_bullets else "None",
        ats_warnings="\n".join(f"- {w}" for w in ats_warnings) if ats_warnings else "None",
        experience_gap=experience_gap,
    )


def _parse_feedback_response(response: str) -> list[FeedbackItemData]:
    """Extract feedback items from LLM JSON response."""
    try:
        match = re.search(r"\[.*\]", response, re.DOTALL)
        if not match:
            return []
        data = json.loads(match.group(0))
        return [
            FeedbackItemData(
                category=_normalize_category(item.get("category", "")),
                severity=_normalize_severity(item.get("severity", "")),
                title=item.get("title", "Improvement needed"),
                description=item.get("description", ""),
                original_text=item.get("original_text"),
                score_delta=float(item.get("score_delta", 0)) if item.get("score_delta") else None,
                source_section=item.get("source_section"),
            )
            for item in data
            if item.get("title") and item.get("description")
        ]
    except Exception:
        return []


def _rule_based_feedback(data: dict) -> list[FeedbackItemData]:
    """Generate basic feedback without LLM."""
    items: list[FeedbackItemData] = []
    keyword_data = data.get("keyword_result", {})

    for skill in keyword_data.get("missing_required", [])[:5]:
        items.append(FeedbackItemData(
            category=FeedbackCategory.KEYWORD.value,
            severity=FeedbackSeverity.HIGH.value,
            title=f"Missing required skill: {skill}",
            description=f"The job description lists '{skill}' as a required skill, but it was not detected in your resume. Add this to your skills section if you have experience with it.",
            score_delta=5.0,
            source_section="skills",
        ))

    ats_warnings = data.get("ats_warnings", [])
    for warning in ats_warnings[:3]:
        items.append(FeedbackItemData(
            category=FeedbackCategory.ATS.value,
            severity=FeedbackSeverity.HIGH.value,
            title="ATS Formatting Issue",
            description=str(warning),
            score_delta=3.0,
            source_section="formatting",
        ))

    return items
