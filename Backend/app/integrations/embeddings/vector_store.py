"""Vector store — pgvector insert and cosine similarity search.

Wraps raw SQLAlchemy operations for the resume_embeddings table so that
callers don't need to know the pgvector SQL syntax.

All operations are async and scoped to a provided AsyncSession.
"""

from __future__ import annotations

import uuid
from typing import Any

import structlog
from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

log = structlog.get_logger(__name__)


async def upsert_resume_embeddings(
    db: AsyncSession,
    resume_id: uuid.UUID,
    sections: dict[str, list[float]],
    model_id: str,
) -> None:
    """Upsert section embeddings for a resume.

    Deletes existing embeddings for the resume+model combo, then inserts
    fresh rows — one per section. This ensures clean re-indexing on model
    upgrades.

    Args:
        db: Async SQLAlchemy session.
        resume_id: UUID of the resume.
        sections: Mapping of section_name → embedding vector (list of floats).
        model_id: Embedding model identifier (stored for provenance).
    """
    from app.models.resume_embedding import ResumeEmbedding

    # Delete stale embeddings for this resume + model
    await db.execute(
        delete(ResumeEmbedding).where(
            ResumeEmbedding.resume_id == resume_id,
            ResumeEmbedding.model_id == model_id,
        )
    )

    # Insert fresh embeddings
    for section_name, vector in sections.items():
        embedding = ResumeEmbedding(
            resume_id=resume_id,
            section=section_name,
            model_id=model_id,
            embedding=vector,
        )
        db.add(embedding)

    await db.commit()
    log.info(
        "resume_embeddings_upserted",
        resume_id=str(resume_id),
        sections=list(sections.keys()),
        model_id=model_id,
    )


async def cosine_search(
    db: AsyncSession,
    query_vector: list[float],
    model_id: str,
    section: str | None = None,
    limit: int = 10,
    min_similarity: float = 0.5,
) -> list[dict[str, Any]]:
    """Find the most similar resume embeddings to a query vector.

    Uses pgvector's ``<=>`` operator (cosine distance = 1 - similarity).

    Args:
        db: Async SQLAlchemy session.
        query_vector: Query embedding (same dimension as stored vectors).
        model_id: Only compare against embeddings from this model.
        section: Optional filter to a specific section ('full', 'skills', etc.).
        limit: Maximum number of results.
        min_similarity: Minimum cosine similarity to include in results.

    Returns:
        List of dicts with keys: resume_id, section, similarity.
    """
    from app.models.resume_embedding import ResumeEmbedding

    # Build the pgvector query using the <=> (cosine distance) operator
    vector_str = "[" + ",".join(str(v) for v in query_vector) + "]"

    filters = [
        f"model_id = :model_id",
        f"1 - (embedding <=> '{vector_str}'::vector) >= :min_sim",
    ]
    params: dict[str, Any] = {
        "model_id": model_id,
        "min_sim": min_similarity,
        "limit": limit,
    }

    if section:
        filters.append("section = :section")
        params["section"] = section

    where_clause = " AND ".join(filters)

    sql = text(f"""
        SELECT
            resume_id,
            section,
            1 - (embedding <=> '{vector_str}'::vector) AS similarity
        FROM resume_embeddings
        WHERE {where_clause}
        ORDER BY embedding <=> '{vector_str}'::vector
        LIMIT :limit
    """)

    result = await db.execute(sql, params)
    rows = result.fetchall()

    results = [
        {
            "resume_id": str(row.resume_id),
            "section": row.section,
            "similarity": round(float(row.similarity), 4),
        }
        for row in rows
    ]

    log.debug(
        "cosine_search_complete",
        results=len(results),
        model_id=model_id,
        section=section,
    )
    return results


async def get_resume_embedding(
    db: AsyncSession,
    resume_id: uuid.UUID,
    model_id: str,
    section: str = "full",
) -> list[float] | None:
    """Fetch a stored embedding for a specific resume section.

    Returns:
        The embedding vector as a list of floats, or None if not found.
    """
    from app.models.resume_embedding import ResumeEmbedding

    result = await db.execute(
        select(ResumeEmbedding.embedding).where(
            ResumeEmbedding.resume_id == resume_id,
            ResumeEmbedding.model_id == model_id,
            ResumeEmbedding.section == section,
        )
    )
    row = result.scalar_one_or_none()
    return list(row) if row is not None else None


async def delete_resume_embeddings(
    db: AsyncSession,
    resume_id: uuid.UUID,
) -> int:
    """Delete all embeddings for a resume (e.g. when resume is deleted).

    Returns:
        Number of rows deleted.
    """
    from app.models.resume_embedding import ResumeEmbedding

    result = await db.execute(
        delete(ResumeEmbedding)
        .where(ResumeEmbedding.resume_id == resume_id)
        .returning(ResumeEmbedding.id)
    )
    await db.commit()
    count = len(result.fetchall())
    log.info("resume_embeddings_deleted", resume_id=str(resume_id), count=count)
    return count
