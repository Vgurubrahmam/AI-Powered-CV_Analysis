"""Cross-encoder reranker for top candidate pairs."""

from __future__ import annotations

import structlog

log = structlog.get_logger(__name__)

_reranker = None
_RERANKER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"


def _get_reranker():
    global _reranker
    if _reranker is None:
        try:
            from sentence_transformers import CrossEncoder
            _reranker = CrossEncoder(_RERANKER_MODEL, max_length=512)
            log.info("cross_encoder_loaded", model=_RERANKER_MODEL)
        except Exception as exc:
            log.warning("cross_encoder_load_failed", error=str(exc))
            _reranker = False  # Mark as failed so we don't retry
    return _reranker if _reranker is not False else None


async def rerank_pairs(pairs: list[tuple[str, str]]) -> list[float]:
    """Score a list of (query, passage) pairs using cross-encoder.

    Returns list of scores in [0, 1] range, same length as input pairs.
    Falls back to [0.5] * len(pairs) on failure.
    """
    if not pairs:
        return []

    import asyncio

    reranker = _get_reranker()
    if reranker is None:
        return [0.5] * len(pairs)

    try:
        # Run in thread pool since cross-encoder is CPU-bound
        loop = asyncio.get_event_loop()
        scores = await loop.run_in_executor(None, reranker.predict, pairs)
        # Normalize scores to [0, 1] range using sigmoid
        import numpy as np
        normalized = 1 / (1 + np.exp(-np.array(scores, dtype=np.float32)))
        return [round(float(s), 4) for s in normalized]
    except Exception as exc:
        log.warning("reranker_predict_failed", error=str(exc))
        return [0.5] * len(pairs)
