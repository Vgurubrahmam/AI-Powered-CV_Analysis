"""Hallucination guard — verify LLM rewrites against source resume facts."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from rapidfuzz import fuzz


@dataclass
class HallucinationCheckResult:
    passed: bool
    flagged_entities: list[str] = field(default_factory=list)
    warning: str | None = None


def _extract_entities(text: str) -> list[str]:
    """Extract named entities (companies, numbers, tech names) from text."""
    entities: list[str] = []

    # Capitalized words/phrases (potential company/product names)
    cap_words = re.findall(r"\b[A-Z][a-zA-Z]{1,}(?:\s+[A-Z][a-zA-Z]+)*\b", text)
    entities.extend(cap_words)

    # Numbers and metrics
    numbers = re.findall(r"\$[\d,]+|\d+%|\d+[kKmMbB]|\d{4}|\b\d{2,}\b", text)
    entities.extend(numbers)

    # Quoted terms
    quoted = re.findall(r'"([^"]{3,50})"', text)
    entities.extend(quoted)

    # Deduplicate while preserving order
    seen: set[str] = set()
    result: list[str] = []
    for e in entities:
        if e not in seen and len(e) > 2:
            seen.add(e)
            result.append(e)

    return result


def check_hallucinations(
    rewritten_text: str,
    source_resume_text: str,
    fuzzy_threshold: int = 85,
) -> HallucinationCheckResult:
    """Check if any entities in the rewrite are absent from the source resume.

    Algorithm:
    1. Extract named entities (companies, numbers, tech names) from rewrite
    2. For each entity, check if it appears in the source text (exact or fuzzy match)
    3. If not found → flag as potential hallucination

    Args:
        rewritten_text: The LLM-generated rewrite.
        source_resume_text: The original resume text to validate against.
        fuzzy_threshold: Minimum fuzzy match score (0–100) to accept as present.

    Returns:
        HallucinationCheckResult with pass/fail and list of flagged entities.
    """
    source_lower = source_resume_text.lower()
    rewrite_entities = _extract_entities(rewritten_text)

    flagged: list[str] = []

    for entity in rewrite_entities:
        entity_lower = entity.lower()

        # Exact substring check
        if entity_lower in source_lower:
            continue

        # Fuzzy match: check similarity against any 50-char window
        found = False
        step = max(1, len(entity_lower))
        for i in range(0, len(source_lower), step // 2 or 1):
            window = source_lower[i: i + len(entity_lower) + 20]
            if not window:
                break
            similarity = fuzz.partial_ratio(entity_lower, window)
            if similarity >= fuzzy_threshold:
                found = True
                break

        if not found:
            flagged.append(entity)

    if flagged:
        return HallucinationCheckResult(
            passed=False,
            flagged_entities=flagged,
            warning=(
                f"The following entities in the rewrite were not found in the source resume: "
                f"{', '.join(flagged[:5])}. These may be hallucinated."
            ),
        )

    return HallucinationCheckResult(passed=True)
