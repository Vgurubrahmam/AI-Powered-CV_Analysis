"""Experience analyzer — career trajectory, YOE calculation, seniority inference."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.core.constants import SeniorityLevel
from app.utils.date_utils import calculate_duration_months, extract_years_of_experience


@dataclass
class ExperienceAnalysisResult:
    total_yoe: float
    required_yoe: Optional[float]
    score: float                   # 0–100
    seniority_inferred: Optional[str]
    seniority_required: Optional[str]
    career_progression_score: float
    gap_detected: bool
    details: dict


# Backward-compatible alias used by analysis package exports/imports.
ExperienceResult = ExperienceAnalysisResult


_SENIORITY_YOE_MAP = {
    SeniorityLevel.INTERN: (0, 1),
    SeniorityLevel.JUNIOR: (0, 3),
    SeniorityLevel.MID: (2, 6),
    SeniorityLevel.SENIOR: (5, 12),
    SeniorityLevel.LEAD: (7, 15),
    SeniorityLevel.PRINCIPAL: (10, 20),
    SeniorityLevel.DIRECTOR: (12, 30),
    SeniorityLevel.VP: (15, 30),
    SeniorityLevel.C_LEVEL: (20, 40),
}


def infer_seniority(yoe: float) -> SeniorityLevel:
    """Infer seniority level from years of experience."""
    if yoe < 1:
        return SeniorityLevel.INTERN
    if yoe < 3:
        return SeniorityLevel.JUNIOR
    if yoe < 6:
        return SeniorityLevel.MID
    if yoe < 10:
        return SeniorityLevel.SENIOR
    if yoe < 14:
        return SeniorityLevel.LEAD
    if yoe < 18:
        return SeniorityLevel.PRINCIPAL
    return SeniorityLevel.DIRECTOR


def analyze_experience(
    positions: list[dict],
    required_yoe_min: Optional[float] = None,
    required_yoe_max: Optional[float] = None,
    required_seniority: Optional[str] = None,
) -> ExperienceAnalysisResult:
    """Analyze experience from parsed position data.

    Score computation:
    - If no YOE requirement: score based on absolute experience (capped at 15 YOE → 100)
    - If YOE requirement: score based on meeting/exceeding requirement
    - Seniority match adds/subtracts up to 10 points
    """
    total_yoe = extract_years_of_experience(positions)
    inferred_seniority = infer_seniority(total_yoe)

    # ── Base score from YOE ───────────────────────────────────────────────
    if required_yoe_min is not None:
        if total_yoe >= required_yoe_min:
            # Meeting requirement: 70–90 pts
            excess = total_yoe - required_yoe_min
            score = min(90.0, 70.0 + excess * 3)
        else:
            # Below requirement
            ratio = total_yoe / max(required_yoe_min, 1)
            score = max(10.0, ratio * 70.0)
    else:
        # No specified requirement: experience is additive
        score = min(85.0, total_yoe * 8)  # 10 YOE → 80pts

    # ── Seniority match bonus/penalty ────────────────────────────────────
    seniority_delta = 0.0
    if required_seniority:
        req_level = SeniorityLevel(required_seniority) if required_seniority in [s.value for s in SeniorityLevel] else None
        if req_level:
            req_min_yoe, _ = _SENIORITY_YOE_MAP.get(req_level, (0, 100))
            if total_yoe >= req_min_yoe:
                seniority_delta = 10.0
            else:
                seniority_delta = -10.0

    final_score = round(min(100.0, max(0.0, score + seniority_delta)), 2)

    # ── Career progression ────────────────────────────────────────────────
    # Heuristic: more positions in shorter time = faster progression
    positions_count = len(positions)
    if positions_count == 0:
        progression_score = 0.0
    elif positions_count == 1:
        progression_score = 50.0
    else:
        avg_tenure_months = (total_yoe * 12) / positions_count
        if avg_tenure_months >= 18:  # avg. 1.5+ years = healthy
            progression_score = 80.0
        elif avg_tenure_months >= 12:
            progression_score = 60.0
        else:
            progression_score = 40.0  # too many short stints

    return ExperienceAnalysisResult(
        total_yoe=total_yoe,
        required_yoe=required_yoe_min,
        score=final_score,
        seniority_inferred=inferred_seniority.value,
        seniority_required=required_seniority,
        career_progression_score=round(progression_score, 2),
        gap_detected=False,  # TODO: implement gap detection
        details={
            "positions_count": positions_count,
            "yoe_score_base": round(score, 2),
            "seniority_delta": seniority_delta,
        },
    )
