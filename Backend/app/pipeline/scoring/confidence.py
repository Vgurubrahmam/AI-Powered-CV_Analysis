"""Parse confidence propagation to final score confidence interval."""

from __future__ import annotations


def compute_confidence_interval(
    score: float, confidence: float, spread_factor: float = 8.0
) -> dict[str, float]:
    """Compute a symmetric confidence interval around the composite score.

    A score of 78 with confidence=0.6 produces approximately [70, 86]
    A score of 78 with confidence=1.0 produces approximately [76, 80]

    Args:
        score: The composite score (0–100).
        confidence: Parse + coverage confidence (0.0–1.0).
        spread_factor: Maximum spread in score points at zero confidence.

    Returns:
        dict with 'lower', 'upper', 'confidence' keys.
    """
    # As confidence approaches 1, spread approaches 0
    spread = spread_factor * (1.0 - confidence)
    lower = round(max(0.0, score - spread), 2)
    upper = round(min(100.0, score + spread), 2)
    return {"lower": lower, "upper": upper, "confidence": round(confidence, 3)}


def format_score_display(score: float, confidence: float) -> str:
    """Return a human-readable score display string.

    High confidence: "78/100"
    Low confidence: "~78/100 (±8 pts)"
    """
    ci = compute_confidence_interval(score, confidence)
    spread = round((ci["upper"] - ci["lower"]) / 2, 1)
    if confidence >= 0.85:
        return f"{score:.0f}/100"
    return f"~{score:.0f}/100 (±{spread:.0f} pts)"
