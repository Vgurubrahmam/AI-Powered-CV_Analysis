"""Percentile calibrator — estimate score percentile against a benchmark distribution."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from app.pipeline.scoring.score_engine import ScoreResult

log = structlog.get_logger(__name__)

# Simple pre-computed percentile table (score → percentile)
# This would be updated by the calibrate_scores.py script in production
_DEFAULT_PERCENTILE_TABLE: list[tuple[float, float]] = [
    (10, 5), (20, 10), (30, 18), (40, 28), (50, 42),
    (55, 50), (60, 58), (65, 65), (70, 73), (75, 80),
    (80, 87), (85, 92), (90, 96), (95, 98), (100, 100),
]

_CALIBRATION_FILE = Path(__file__).parent / "calibration_data.json"


def _load_percentile_table() -> list[tuple[float, float]]:
    """Load percentile table from file or return defaults."""
    if _CALIBRATION_FILE.exists():
        try:
            data = json.loads(_CALIBRATION_FILE.read_text())
            return [(entry["score"], entry["percentile"]) for entry in data]
        except Exception as exc:
            log.warning("calibration_load_failed", error=str(exc))
    return _DEFAULT_PERCENTILE_TABLE


def score_to_percentile(score: float) -> float:
    """Interpolate percentile from a composite score.

    Args:
        score: Composite score 0–100.

    Returns:
        Estimated percentile (0–100).
    """
    table = _load_percentile_table()

    if score <= table[0][0]:
        return table[0][1]
    if score >= table[-1][0]:
        return table[-1][1]

    for i in range(len(table) - 1):
        s1, p1 = table[i]
        s2, p2 = table[i + 1]
        if s1 <= score <= s2:
            # Linear interpolation
            t = (score - s1) / (s2 - s1)
            return round(p1 + t * (p2 - p1), 1)

    return 50.0  # fallback


def calibrate_score(score_result: "ScoreResult") -> "ScoreResult":
    """Attach a percentile rank to an existing ScoreResult.

    Mutates the score_result in-place by setting ``percentile`` if the
    dataclass has the field, otherwise returns it unchanged.

    Returns:
        The same ScoreResult object (for chaining).
    """
    try:
        percentile = score_to_percentile(score_result.composite)
        # Attach as dynamic attribute — ScoreResult is a dataclass so we can
        # use object.__setattr__ to avoid frozen-dataclass errors.
        object.__setattr__(score_result, "percentile", percentile)
        log.debug("score_calibrated", composite=score_result.composite, percentile=percentile)
    except Exception as exc:
        log.warning("calibrate_score_failed", error=str(exc))
    return score_result


async def rebuild_percentile_table(db) -> int:
    """Recompute the percentile distribution from completed analyses in DB.

    Pulls composite scores from all DONE analyses, computes 5-point quantile
    bands, and writes the result to calibration_data.json.

    Args:
        db: AsyncSession (SQLAlchemy).

    Returns:
        Number of analysis samples used.
    """
    from sqlalchemy import select
    try:
        from app.models.analysis import Analysis
        from app.core.constants import AnalysisStatus

        result = await db.execute(
            select(Analysis.score)
            .where(
                Analysis.status == AnalysisStatus.DONE.value,
                Analysis.score.is_not(None),
            )
            .limit(10_000)
        )
        scores = sorted(float(r[0]) for r in result.fetchall())

        if len(scores) < 20:
            log.warning("rebuild_skipped_not_enough_data", count=len(scores))
            return len(scores)

        # Build percentile table in 5-point bands
        n = len(scores)
        table = []
        for pct in range(0, 101, 5):
            idx = min(int(pct / 100 * n), n - 1)
            table.append({"score": round(scores[idx], 2), "percentile": float(pct)})

        _CALIBRATION_FILE.write_text(json.dumps(table, indent=2))
        log.info("calibration_table_rebuilt", samples=n, bands=len(table))
        return n

    except Exception as exc:
        log.error("rebuild_percentile_table_failed", error=str(exc))
        return 0
