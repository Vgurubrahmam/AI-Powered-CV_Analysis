"""Skill extractor — taxonomy lookup + LLM hybrid skill extraction.

Strategy:
1. Rule-based pass: scan resume tokens/phrases against full taxonomy index.
2. LLM pass (optional): ask LLM to extract skills not caught by rules.
3. Merge and normalize: deduplicate, map to canonical taxonomy names.
4. Output: SkillExtractionResult with taxonomy-normalized and raw lists.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

import structlog

from app.pipeline.matching.skill_taxonomy import (
    get_taxonomy,
    normalize_skill,
    is_known_skill,
    find_closest_canonical,
)

log = structlog.get_logger(__name__)

_LLM_SKILL_PROMPT = """Extract ALL technical and professional skills from the following resume text.

Rules:
- Include programming languages, frameworks, tools, platforms, cloud services, methodologies, and soft skills.
- Output ONLY a JSON array of strings, no explanation.
- Normalize names (e.g. "k8s" → "kubernetes", "ML" → "machine learning").
- Maximum 60 skills.

Resume text:
\"\"\"
{text}
\"\"\"

Return ONLY: ["skill1", "skill2", ...]"""


@dataclass
class SkillExtractionResult:
    """Extracted and normalized skill set from a resume."""

    canonical_skills: list[str] = field(default_factory=list)   # taxonomy-normalized
    raw_skills: list[str] = field(default_factory=list)          # as extracted
    unknown_skills: list[str] = field(default_factory=list)      # not in taxonomy
    extraction_method: str = "rule_based"                        # "rule_based" | "hybrid" | "llm"
    confidence: float = 1.0


async def extract_skills(
    resume_text: str,
    use_llm: bool = True,
    sections: dict[str, str] | None = None,
) -> SkillExtractionResult:
    """Extract and normalize skills from resume text.

    Args:
        resume_text: Full resume text.
        use_llm: Whether to run the LLM pass for skills not caught by rules.
        sections: Optional section-split dict (key=section_name, value=text).
                  If provided, skills section text is weighted higher.

    Returns:
        SkillExtractionResult with canonical and raw skill lists.
    """
    # ── Phase 1: Rule-based taxonomy scan ────────────────────────────────────
    rule_based_skills = _rule_based_extract(resume_text, sections)
    log.debug("rule_based_skills_extracted", count=len(rule_based_skills))

    if not use_llm:
        canonical = [normalize_skill(s) for s in rule_based_skills]
        canonical = _deduplicate(canonical)
        unknown = [s for s in rule_based_skills if not is_known_skill(s)]
        return SkillExtractionResult(
            canonical_skills=canonical,
            raw_skills=rule_based_skills,
            unknown_skills=unknown,
            extraction_method="rule_based",
            confidence=0.85,
        )

    # ── Phase 2: LLM pass ────────────────────────────────────────────────────
    llm_skills: list[str] = []
    method = "rule_based"
    try:
        llm_skills = await _llm_extract(resume_text)
        method = "hybrid"
        log.debug("llm_skills_extracted", count=len(llm_skills))
    except Exception as exc:
        log.warning("skill_extractor_llm_failed", error=str(exc))

    # ── Phase 3: Merge & normalize ────────────────────────────────────────────
    all_raw = list({*rule_based_skills, *llm_skills})
    canonical = [normalize_skill(s) for s in all_raw]
    canonical = _deduplicate(canonical)
    unknown = [s for s in all_raw if not is_known_skill(s)]

    return SkillExtractionResult(
        canonical_skills=canonical,
        raw_skills=all_raw,
        unknown_skills=unknown,
        extraction_method=method,
        confidence=0.92 if llm_skills else 0.85,
    )


def _rule_based_extract(
    text: str,
    sections: dict[str, str] | None = None,
) -> list[str]:
    """Scan text against all taxonomy aliases (longest-match first)."""
    taxonomy = get_taxonomy()

    # Build search corpus: skills section gets doubled weight via repetition
    corpus = text.lower()
    if sections:
        skills_text = sections.get("skills", "") or sections.get("technical skills", "")
        if skills_text:
            corpus = skills_text.lower() + "\n" + corpus

    found: set[str] = set()

    # Sort aliases by length descending to prefer longer matches
    sorted_aliases = sorted(taxonomy.keys(), key=len, reverse=True)

    for alias in sorted_aliases:
        # Word-boundary aware matching
        pattern = r"(?<!\w)" + re.escape(alias) + r"(?!\w)"
        if re.search(pattern, corpus):
            canonical = taxonomy[alias]
            found.add(canonical)

    return sorted(found)


async def _llm_extract(text: str) -> list[str]:
    """Call LLM to extract skills not caught by rule-based scan."""
    from app.integrations.llm.client import get_llm_client
    from app.config import settings

    # Truncate to avoid token overflow
    truncated = text[:4000] if len(text) > 4000 else text
    prompt = _LLM_SKILL_PROMPT.format(text=truncated)

    client = get_llm_client()
    response = await client.complete(
        prompt=prompt,
        model=settings.NVIDIA_DEFAULT_MODEL,
        max_tokens=800,
        temperature=0.0,
    )

    return _parse_skill_list(response)


def _parse_skill_list(response: str) -> list[str]:
    """Parse JSON array of skill strings from LLM response."""
    try:
        match = re.search(r"\[.*?\]", response, re.DOTALL)
        if not match:
            return []
        data = json.loads(match.group(0))
        return [s.strip() for s in data if isinstance(s, str) and s.strip()]
    except Exception:
        return []


def _deduplicate(skills: list[str]) -> list[str]:
    """Deduplicate preserving first-occurrence order, case-insensitive."""
    seen: set[str] = set()
    result: list[str] = []
    for skill in skills:
        key = skill.lower()
        if key not in seen:
            seen.add(key)
            result.append(skill)
    return result


def compute_skill_depth_score(
    candidate_skills: list[str],
    required_skills: list[str],
    preferred_skills: list[str] | None = None,
) -> float:
    """Score skill depth: how well candidate skills cover JD requirements.

    Considers both required (weighted 80%) and preferred (20%) skills,
    normalized to 0–100.

    Args:
        candidate_skills: Canonical skills extracted from resume.
        required_skills: Canonical required skills from JD.
        preferred_skills: Canonical preferred skills from JD.

    Returns:
        Float score 0–100.
    """
    preferred_skills = preferred_skills or []

    candidate_set = {s.lower() for s in candidate_skills}

    req_matched = sum(1 for s in required_skills if s.lower() in candidate_set)
    req_total = max(len(required_skills), 1)
    req_score = (req_matched / req_total) * 100

    if preferred_skills:
        pref_matched = sum(1 for s in preferred_skills if s.lower() in candidate_set)
        pref_total = max(len(preferred_skills), 1)
        pref_score = (pref_matched / pref_total) * 100
    else:
        pref_score = 0.0

    # Weighted blend: 80% required + 20% preferred
    final = req_score * 0.80 + pref_score * 0.20
    return round(min(100.0, final), 2)
