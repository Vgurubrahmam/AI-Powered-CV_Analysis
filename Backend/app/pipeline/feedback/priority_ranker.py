"""Priority ranker — sort feedback items by score impact and severity."""

from __future__ import annotations

from app.pipeline.feedback.feedback_generator import FeedbackItemData

_SEVERITY_WEIGHT: dict[str, int] = {
    "critical": 4,
    "high": 3,
    "medium": 2,
    "low": 1,
}

_CATEGORY_PRIORITY: dict[str, int] = {
    "keyword": 6,
    "semantic": 5,
    "ats": 4,
    "impact": 3,
    "experience": 2,
    "education": 1,
    "formatting": 0,
}


def rank_feedback_items(
    items: list[FeedbackItemData],
    max_items: int | None = None,
) -> list[FeedbackItemData]:
    """Sort feedback items by actionability: score_delta → severity → category.

    Args:
        items: Feedback items from the generator.
        max_items: Optional cap on returned items.

    Returns:
        Sorted list, most impactful first.
    """
    def sort_key(item: FeedbackItemData) -> tuple:
        delta = item.score_delta or 0.0
        sev = _SEVERITY_WEIGHT.get((item.severity or "").lower(), 0)
        cat = _CATEGORY_PRIORITY.get((item.category or "").lower(), 0)
        return (-delta, -sev, -cat)

    ranked = sorted(items, key=sort_key)
    if max_items is not None:
        ranked = ranked[:max_items]
    return ranked


def group_feedback_by_category(
    items: list[FeedbackItemData],
) -> dict[str, list[FeedbackItemData]]:
    """Group and internally sort feedback by category."""
    groups: dict[str, list[FeedbackItemData]] = {}
    for item in items:
        cat = item.category or "other"
        groups.setdefault(cat, []).append(item)
    for cat in groups:
        groups[cat] = rank_feedback_items(groups[cat])
    return groups


def compute_total_score_potential(items: list[FeedbackItemData]) -> float:
    """Sum score_delta across all items — theoretical max improvement, capped at 100."""
    return round(min(100.0, sum(item.score_delta or 0.0 for item in items)), 2)
