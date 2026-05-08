"""Keyword matching engine — lemmatized exact + stemmed match with alias expansion."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.pipeline.matching.synonym_expander import expand_aliases
from app.utils.text_utils import lemmatize, tokenize_words


@dataclass
class KeywordResult:
    """Result of keyword matching between resume and JD."""

    score: float                             # 0–100
    matched_required: list[str] = field(default_factory=list)
    missing_required: list[str] = field(default_factory=list)
    matched_preferred: list[str] = field(default_factory=list)
    missing_preferred: list[str] = field(default_factory=list)
    match_rate: float = 0.0
    preferred_match_rate: float = 0.0


def compute_keyword_score(
    resume_text: str,
    required_skills: list[str],
    preferred_skills: list[str] | None = None,
) -> KeywordResult:
    """Compute keyword match score between resume text and JD skill requirements.

    Algorithm:
    1. Lemmatize + lowercase resume text
    2. For each required skill: expand aliases, check if any variant appears in resume tokens
    3. Score = matched_required / total_required * 100
    4. Preferred skills are tracked but don't affect the primary score
    """
    preferred_skills = preferred_skills or []

    # Tokenize resume in two ways:
    # 1. Raw lowercase tokens for multi-word skill matching
    resume_lower = resume_text.lower()
    # 2. Lemmatized tokens for single-word skill matching
    resume_lemmas = set(lemmatize(resume_text))
    resume_words = set(tokenize_words(resume_text))

    def _skill_in_resume(skill: str) -> bool:
        variants = expand_aliases(skill)
        for variant in variants:
            variant_tokens = variant.split()
            if len(variant_tokens) > 1:
                # Multi-word: check substring presence in full text
                if variant.lower() in resume_lower:
                    return True
            else:
                # Single word: check lemmatized tokens
                if variant.lower() in resume_lemmas or variant.lower() in resume_words:
                    return True
        return False

    matched_required: list[str] = []
    missing_required: list[str] = []
    for skill in required_skills:
        if _skill_in_resume(skill):
            matched_required.append(skill)
        else:
            missing_required.append(skill)

    matched_preferred: list[str] = []
    missing_preferred: list[str] = []
    for skill in preferred_skills:
        if _skill_in_resume(skill):
            matched_preferred.append(skill)
        else:
            missing_preferred.append(skill)

    total_required = max(len(required_skills), 1)
    match_rate = len(matched_required) / total_required

    total_preferred = max(len(preferred_skills), 1)
    preferred_rate = len(matched_preferred) / total_preferred if preferred_skills else 0.0

    # Primary score: 100% based on required skills
    # Preferred skills provide a small bonus (up to 5 pts)
    base_score = match_rate * 100
    bonus = preferred_rate * 5
    final_score = min(100.0, base_score + bonus)

    return KeywordResult(
        score=round(final_score, 2),
        matched_required=matched_required,
        missing_required=missing_required,
        matched_preferred=matched_preferred,
        missing_preferred=missing_preferred,
        match_rate=round(match_rate, 3),
        preferred_match_rate=round(preferred_rate, 3),
    )
