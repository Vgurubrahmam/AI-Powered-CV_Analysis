"""Semantic matching engine — SBERT embeddings + cosine similarity + cross-encoder rerank."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import structlog

log = structlog.get_logger(__name__)

STRONG_MATCH_THRESHOLD = 0.70
PARTIAL_MATCH_THRESHOLD = 0.50


@dataclass
class SemanticResult:
    """Result of semantic matching."""

    score: float                              # 0–100, aggregated
    per_requirement_scores: dict[str, float] = field(default_factory=dict)
    strong_matches: list[str] = field(default_factory=list)
    partial_matches: list[str] = field(default_factory=list)
    weak_matches: list[str] = field(default_factory=list)
    mean_similarity: float = 0.0
    embedding_model: str = "unknown"


async def compute_semantic_score(
    resume_chunks: list[str],
    jd_requirements: list[str],
    embedding_client=None,
    use_reranker: bool = True,
) -> SemanticResult:
    """Compute semantic similarity between resume chunks and JD requirements.

    Algorithm:
    1. Embed all resume chunks + JD requirements via SBERT
    2. For each JD requirement, find max cosine similarity across all resume chunks
    3. Optionally rerank top pairs with cross-encoder for higher accuracy
    4. Aggregate: mean of per-requirement max scores → scale to 0–100
    """
    if not jd_requirements:
        return SemanticResult(score=0.0, embedding_model="none")

    if not resume_chunks:
        return SemanticResult(score=0.0, embedding_model="none")

    if embedding_client is None:
        from app.integrations.embeddings.client import get_embedding_client
        embedding_client = get_embedding_client()

    try:
        # Embed resume chunks
        resume_embeddings = await embedding_client.embed_batch(resume_chunks)
        # Embed JD requirements
        jd_embeddings = await embedding_client.embed_batch(jd_requirements)

        resume_arr = np.array(resume_embeddings, dtype=np.float32)
        jd_arr = np.array(jd_embeddings, dtype=np.float32)

        # Normalize for cosine similarity
        resume_norms = np.linalg.norm(resume_arr, axis=1, keepdims=True) + 1e-9
        jd_norms = np.linalg.norm(jd_arr, axis=1, keepdims=True) + 1e-9
        resume_normed = resume_arr / resume_norms
        jd_normed = jd_arr / jd_norms

        # Cosine similarity matrix: (num_jd_reqs, num_resume_chunks)
        sim_matrix = np.dot(jd_normed, resume_normed.T)

        per_req_scores: dict[str, float] = {}
        top_pairs_for_rerank: list[tuple[str, str, float]] = []

        for i, req in enumerate(jd_requirements):
            sims = sim_matrix[i]
            max_sim = float(np.max(sims))
            best_chunk_idx = int(np.argmax(sims))
            per_req_scores[req] = round(max_sim, 4)
            top_pairs_for_rerank.append((req, resume_chunks[best_chunk_idx], max_sim))

        # ── Cross-encoder reranking (top-k pairs only) ────────────────────
        if use_reranker and len(top_pairs_for_rerank) > 0:
            try:
                from app.pipeline.matching.reranker import rerank_pairs
                reranked = await rerank_pairs(
                    [(req, chunk) for req, chunk, _ in top_pairs_for_rerank[:20]]
                )
                for i, (req, _, _) in enumerate(top_pairs_for_rerank[:20]):
                    if i < len(reranked):
                        # Blend reranker score with cosine similarity
                        cosine_score = per_req_scores[req]
                        reranker_score = reranked[i]
                        blended = cosine_score * 0.4 + reranker_score * 0.6
                        per_req_scores[req] = round(blended, 4)
            except Exception as exc:
                log.warning("reranker_failed_falling_back_to_cosine", error=str(exc))

        # ── Categorize matches ────────────────────────────────────────────
        strong, partial, weak = [], [], []
        for req, sim in per_req_scores.items():
            if sim >= STRONG_MATCH_THRESHOLD:
                strong.append(req)
            elif sim >= PARTIAL_MATCH_THRESHOLD:
                partial.append(req)
            else:
                weak.append(req)

        mean_sim = float(np.mean(list(per_req_scores.values()))) if per_req_scores else 0.0
        score = round(mean_sim * 100, 2)

        return SemanticResult(
            score=score,
            per_requirement_scores=per_req_scores,
            strong_matches=strong,
            partial_matches=partial,
            weak_matches=weak,
            mean_similarity=round(mean_sim, 4),
            embedding_model=embedding_client.model_name,
        )

    except Exception as exc:
        log.error("semantic_scoring_failed", error=str(exc))
        return SemanticResult(score=0.0, embedding_model="error")
