"""JD parser — LLM-backed structured extraction of job description requirements."""

from __future__ import annotations

import json
import re
from typing import Any

import structlog

log = structlog.get_logger(__name__)

_JD_PARSE_PROMPT = """You are an expert HR analyst. Extract structured information from the job description below.

Return ONLY valid JSON matching this exact schema:
{
  "role_title": "string or null",
  "seniority": "intern|junior|mid|senior|lead|principal|director|vp|c_level or null",
  "required_skills": ["list of required skills"],
  "preferred_skills": ["list of preferred/nice-to-have skills"],
  "years_experience_required": {"min": number or null, "max": number or null, "flexible": boolean},
  "education_required": {"level": "high_school|associate|bachelor|master|phd|mba|bootcamp|certification or null", "field": "string or null", "required": boolean},
  "responsibilities": ["list of key responsibilities"],
  "must_have_flags": ["any hard requirements or certifications explicitly stated as mandatory"]
}

Rules:
- If a skill appears with "must", "required", "essential" → put in required_skills
- If a skill appears with "preferred", "nice to have", "a plus", "bonus" → put in preferred_skills  
- If unclear, use context to infer
- Do NOT include skills not mentioned in the JD
- Return ONLY the JSON object, no explanations

Job Description:
"""


async def parse_jd(raw_text: str) -> dict[str, Any]:
    """Parse a job description using LLM structured extraction.

    Falls back to rule-based parsing if LLM is unavailable.
    """
    from app.integrations.llm.client import get_llm_client
    from app.config import settings

    # Try LLM extraction first
    try:
        client = get_llm_client()
        prompt = _JD_PARSE_PROMPT + raw_text[:4000]  # Truncate to avoid token limits
        response = await client.complete(
            prompt=prompt,
            model=settings.NVIDIA_DEFAULT_MODEL,
            max_tokens=1500,
            temperature=0.1,
        )
        parsed = _extract_json(response)
        if parsed:
            parsed = _add_quality_warnings(parsed, raw_text)
            log.info("jd_parsed_via_llm", role=parsed.get("role_title"))
            return parsed
    except Exception as exc:
        log.warning("jd_llm_parse_failed", error=str(exc), fallback="rule_based")

    # Fallback: rule-based extraction
    return _rule_based_jd_parse(raw_text)


async def parse_job_description(raw_text: str) -> dict[str, Any]:
    """Backward-compatible alias used across workers/orchestrator imports."""
    return await parse_jd(raw_text)


def _extract_json(text: str) -> dict | None:
    """Extract JSON object from LLM response text."""
    # Try direct parse
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass
    # Try extracting JSON block from markdown
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    # Try finding first { ... } block
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass
    return None


def _rule_based_jd_parse(text: str) -> dict[str, Any]:
    """Simple rule-based JD parser as LLM fallback."""
    # Extract years of experience
    yoe_match = re.search(r"(\d+)\+?\s*(?:years?|yrs?)\s+(?:of\s+)?experience", text, re.IGNORECASE)
    min_yoe = int(yoe_match.group(1)) if yoe_match else None

    # Extract skills (look for comma-separated lists after common patterns)
    skills: list[str] = []
    skill_sections = re.findall(
        r"(?:skills?|requirements?|qualifications?|proficiency in)[:\s]+([^\n.]+)", text, re.IGNORECASE
    )
    for section in skill_sections:
        items = re.split(r"[,;/]", section)
        skills.extend(s.strip() for s in items if 1 < len(s.strip()) < 50)

    return {
        "role_title": None,
        "seniority": None,
        "required_skills": list(set(skills[:20])),
        "preferred_skills": [],
        "years_experience_required": {"min": min_yoe, "max": None, "flexible": True},
        "education_required": {"level": None, "field": None, "required": False},
        "responsibilities": [],
        "must_have_flags": [],
        "jd_quality_warnings": ["Parsed using fallback rule-based method — accuracy may be reduced."],
        "aspirational_requirements": [],
    }


def _add_quality_warnings(parsed: dict, raw_text: str) -> dict:
    """Add JD quality warning flags to the parsed output."""
    from app.core.constants import JD_MAX_REASONABLE_REQUIRED_SKILLS, JD_MAX_YOE_FOR_TECH

    warnings: list[str] = []
    aspirational: list[str] = []

    parsed.setdefault("jd_quality_warnings", [])
    parsed.setdefault("aspirational_requirements", [])

    required = parsed.get("required_skills", [])
    if len(required) > JD_MAX_REASONABLE_REQUIRED_SKILLS:
        warnings.append(
            f"JD lists {len(required)} required skills — this appears to be a wishlist. "
            f"Requirements beyond skill #{JD_MAX_REASONABLE_REQUIRED_SKILLS} carry reduced weight."
        )

    yoe = parsed.get("years_experience_required", {})
    min_yoe = yoe.get("min") if yoe else None
    if min_yoe and min_yoe > JD_MAX_YOE_FOR_TECH:
        warnings.append(
            f"JD requires {min_yoe}+ years of experience, which exceeds typical career norms for most technologies."
        )
        aspirational.append(f"{min_yoe}+ years experience")

    parsed["jd_quality_warnings"] = warnings
    parsed["aspirational_requirements"] = aspirational
    return parsed
