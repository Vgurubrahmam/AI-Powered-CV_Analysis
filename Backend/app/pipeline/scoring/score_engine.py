"""Scoring engine — weighted aggregation of sub-scores into composite score."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import structlog

from app.pipeline.scoring.weight_configs import WEIGHT_PROFILES, get_weight_profile
from app.pipeline.scoring.confidence import compute_confidence_interval

log = structlog.get_logger(__name__)


@dataclass
class SubScores:
    """Container for all pipeline sub-scores (0–100 each)."""
    keyword: Optional[float] = None
    semantic: Optional[float] = None
    skill_depth: Optional[float] = None
    experience: Optional[float] = None
    impact: Optional[float] = None
    education: Optional[float] = None


@dataclass
class ScoreResult:
    """Final composite score with breakdown and confidence interval."""
    composite: float
    breakdown: dict[str, float]
    confidence: float
    confidence_interval: dict[str, float]
    role_type: str
    weights_used: dict[str, float]
    missing_components: list[str]


def compute_composite_score(
    sub_scores: SubScores,
    role_type: str = "default",
    parse_confidence: float = 1.0,
) -> ScoreResult:
    """Compute weighted composite score from sub-scores.

    Rules:
    - Missing sub-scores are excluded and weights renormalized to 100%
    - Parse confidence propagates to final score's confidence interval
    - Never return exactly 0 for a component that had data — use 1 as floor
    """
    weights = get_weight_profile(role_type).copy()

    breakdown: dict[str, float] = {}
    effective_weights: dict[str, float] = {}
    missing: list[str] = []

    score_map = {
        "keyword": sub_scores.keyword,
        "semantic": sub_scores.semantic,
        "skill_depth": sub_scores.skill_depth,
        "experience": sub_scores.experience,
        "impact": sub_scores.impact,
        "education": sub_scores.education,
    }

    # Filter to only components with actual scores
    for component, score in score_map.items():
        if score is not None:
            breakdown[component] = round(score, 2)
            effective_weights[component] = weights.get(component, 0.0)
        else:
            missing.append(component)

    if not effective_weights:
        log.warning("no_sub_scores_available")
        return ScoreResult(
            composite=0.0,
            breakdown={},
            confidence=0.0,
            confidence_interval={"lower": 0.0, "upper": 0.0},
            role_type=role_type,
            weights_used={},
            missing_components=missing,
        )

    # Renormalize weights to sum to 1.0
    total_weight = sum(effective_weights.values())
    normalized_weights = {k: v / total_weight for k, v in effective_weights.items()}

    # Compute weighted sum
    composite = sum(breakdown[k] * normalized_weights[k] for k in breakdown)
    composite = round(min(100.0, max(0.0, composite)), 2)

    # Confidence = min(parse_confidence, data coverage)
    coverage = len(breakdown) / max(len(score_map), 1)
    confidence = round(parse_confidence * coverage, 3)

    ci = compute_confidence_interval(composite, confidence)

    log.info(
        "composite_score_computed",
        composite=composite,
        confidence=confidence,
        role_type=role_type,
        missing=missing,
    )

    return ScoreResult(
        composite=composite,
        breakdown=breakdown,
        confidence=confidence,
        confidence_interval=ci,
        role_type=role_type,
        weights_used=normalized_weights,
        missing_components=missing,
    )
