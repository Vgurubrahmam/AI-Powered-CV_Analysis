"""Impact scorer — bullet STAR analysis and quantification check."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import structlog

from app.utils.text_utils import has_quantified_impact, split_bullet_points

log = structlog.get_logger(__name__)

_IMPACT_PROMPT_TEMPLATE = """You are a senior technical recruiter and career coach.

Analyze these resume bullet points and rate their impact quality on a scale of 0-100.

Evaluation criteria:
- Quantified outcomes (%, $, numbers, ×): +30 pts
- Action verbs (led, built, increased, reduced, designed): +20 pts
- Clear result/outcome stated: +25 pts
- Specificity (technologies, team size, timeframe): +25 pts

For each bullet, rate it and explain the key weakness (max 20 words per explanation).

Bullets to analyze:
{bullets}

Return JSON array:
[{{"bullet": "...", "score": 0-100, "weakness": "...", "has_quantification": true/false}}]

Return ONLY valid JSON, no other text."""


@dataclass
class BulletAnalysis:
    bullet: str
    score: float
    weakness: str | None = None
    has_quantification: bool = False


@dataclass
class ImpactScoreResult:
    score: float                                    # 0–100 aggregate
    bullet_analyses: list[BulletAnalysis] = field(default_factory=list)
    quantification_rate: float = 0.0
    total_bullets: int = 0
    method: str = "rule_based"


# Backward-compatible alias used by analysis package exports/imports.
ImpactResult = ImpactScoreResult


async def score_impact(
    experience_text: str | list[str],
    use_llm: bool = True,
) -> ImpactScoreResult:
    """Score the impact quality of resume experience bullets."""
    if isinstance(experience_text, list):
        bullets = [b.strip() for b in experience_text if b and str(b).strip()]
    else:
        bullets = split_bullet_points(experience_text)
    if not bullets:
        # Try line-based splitting if no bullets found
        bullets = [
            l.strip() for l in (experience_text or "").split("\n")
            if len(l.strip()) > 20
        ][:20]

    if not bullets:
        return ImpactScoreResult(score=30.0, method="no_bullets_found")

    # Rule-based quantification analysis
    quantified = sum(1 for b in bullets if has_quantified_impact(b))
    quantification_rate = quantified / max(len(bullets), 1)

    # Try LLM assessment for deeper quality analysis
    if use_llm and len(bullets) > 0:
        try:
            from app.integrations.llm.client import get_llm_client
            from app.config import settings
            import json

            client = get_llm_client()
            sample_bullets = bullets[:10]  # Limit to 10 to control token cost
            bullets_text = "\n".join(f"- {b}" for b in sample_bullets)
            prompt = _IMPACT_PROMPT_TEMPLATE.format(bullets=bullets_text)

            response = await client.complete(
                prompt=prompt,
                model=settings.NVIDIA_DEFAULT_MODEL,
                max_tokens=1000,
                temperature=0.1,
            )

            # Parse LLM response
            analyses = _parse_llm_impact_response(response, sample_bullets)
            if analyses:
                llm_score = sum(a.score for a in analyses) / len(analyses)
                # Blend with rule-based quantification score
                quant_score = quantification_rate * 100
                blended_score = llm_score * 0.7 + quant_score * 0.3
                return ImpactScoreResult(
                    score=round(blended_score, 2),
                    bullet_analyses=analyses,
                    quantification_rate=round(quantification_rate, 3),
                    total_bullets=len(bullets),
                    method="llm",
                )
        except Exception as exc:
            log.warning("impact_llm_failed", error=str(exc), fallback="rule_based")

    # Fallback: rule-based scoring
    analyses = []
    total_score = 0.0
    for bullet in bullets[:20]:
        b_score, weakness = _rule_based_bullet_score(bullet)
        analyses.append(BulletAnalysis(
            bullet=bullet,
            score=b_score,
            weakness=weakness,
            has_quantification=has_quantified_impact(bullet),
        ))
        total_score += b_score

    avg_score = total_score / max(len(analyses), 1)

    return ImpactScoreResult(
        score=round(avg_score, 2),
        bullet_analyses=analyses,
        quantification_rate=round(quantification_rate, 3),
        total_bullets=len(bullets),
        method="rule_based",
    )


def _rule_based_bullet_score(bullet: str) -> tuple[float, str | None]:
    """Rule-based bullet scoring."""
    import re
    score = 30.0  # base

    # Quantification
    if has_quantified_impact(bullet):
        score += 30

    # Action verb
    action_verbs = r"\b(led|built|designed|implemented|increased|reduced|improved|launched|created|architected|developed|managed|delivered|spearheaded|drove|established|transformed)\b"
    if re.search(action_verbs, bullet, re.IGNORECASE):
        score += 20

    # Length and specificity
    if len(bullet) > 80:
        score += 10
    if len(bullet) > 120:
        score += 10

    weakness = None
    if score < 50:
        weakness = "Lacks quantified outcomes and specific impact metrics."
    elif score < 75:
        weakness = "Could be stronger with specific numbers or measurable results."

    return round(min(100.0, score), 2), weakness


def _parse_llm_impact_response(response: str, bullets: list[str]) -> list[BulletAnalysis]:
    """Parse LLM JSON response into BulletAnalysis objects."""
    import json, re
    try:
        # Extract JSON array from response
        match = re.search(r"\[.*\]", response, re.DOTALL)
        if match:
            data = json.loads(match.group(0))
            return [
                BulletAnalysis(
                    bullet=item.get("bullet", bullets[i] if i < len(bullets) else ""),
                    score=float(item.get("score", 50)),
                    weakness=item.get("weakness"),
                    has_quantification=bool(item.get("has_quantification", False)),
                )
                for i, item in enumerate(data)
            ]
    except (json.JSONDecodeError, Exception):
        pass
    return []
