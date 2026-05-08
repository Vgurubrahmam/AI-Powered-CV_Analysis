"""Embedding Celery tasks — generate and refresh resume vector embeddings."""

from __future__ import annotations

import uuid

import structlog
from celery import shared_task

log = structlog.get_logger(__name__)


@shared_task(
    name="app.workers.tasks.embedding_tasks.generate_embeddings",
    bind=True,
    max_retries=2,
    default_retry_delay=60,
    soft_time_limit=180,
)
def generate_embeddings(self, resume_id: str) -> dict:
    """Generate SBERT embeddings for all sections of a parsed resume.

    Sections embedded: full text, experience, skills, education, summary.
    Embeddings stored in the resume_embeddings table for vector search.
    """
    import asyncio

    async def _run() -> dict:
        from app.main import get_db_session
        from app.repositories.resume_repo import ResumeRepository
        from app.integrations.embeddings.client import get_embedding_client
        from app.integrations.embeddings.vector_store import upsert_resume_embeddings
        from app.core.constants import ParseStatus, EmbeddingSection

        async with get_db_session() as db:
            repo = ResumeRepository(db)
            resume = await repo.get(uuid.UUID(resume_id))

            if not resume or resume.parse_status != ParseStatus.SUCCESS.value:
                log.warning("resume_not_ready_for_embedding", resume_id=resume_id)
                return {"status": "SKIPPED"}

            parsed = resume.parsed_data or {}
            client = get_embedding_client()

            # Build section texts
            section_texts: dict[str, str] = {}
            if parsed.get("raw_text"):
                section_texts[EmbeddingSection.FULL.value] = parsed["raw_text"][:8000]
            if parsed.get("summary"):
                section_texts[EmbeddingSection.SUMMARY.value] = parsed["summary"]
            if parsed.get("skills"):
                section_texts[EmbeddingSection.SKILLS.value] = ", ".join(parsed["skills"])
            if parsed.get("sections_dict", {}).get("experience"):
                section_texts[EmbeddingSection.EXPERIENCE.value] = (
                    parsed["sections_dict"]["experience"][:3000]
                )
            if parsed.get("sections_dict", {}).get("education"):
                section_texts[EmbeddingSection.EDUCATION.value] = (
                    parsed["sections_dict"]["education"][:1000]
                )

            if not section_texts:
                return {"status": "SKIPPED", "reason": "no_section_text"}

            # Embed
            texts = list(section_texts.values())
            section_keys = list(section_texts.keys())
            vectors = await client.embed_batch(texts)

            # Upsert into vector store
            await upsert_resume_embeddings(
                db=db,
                resume_id=uuid.UUID(resume_id),
                sections=dict(zip(section_keys, vectors)),
                model_id=client.model_name,
            )

            log.info("embeddings_generated", resume_id=resume_id, sections=len(section_texts))
            return {"status": "SUCCESS", "sections": len(section_texts)}

    try:
        return asyncio.run(_run())
    except Exception as exc:
        log.error("generate_embeddings_failed", resume_id=resume_id, error=str(exc))
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            return {"status": "FAILED", "error": str(exc)}


@shared_task(
    name="app.workers.tasks.embedding_tasks.refresh_embeddings",
    bind=True,
    max_retries=1,
    soft_time_limit=300,
)
def refresh_embeddings(self, model_id: str) -> dict:
    """Re-generate embeddings for all resumes using a new embedding model.

    Used when upgrading the embedding model to ensure vector consistency.
    Processes resumes in batches of 50.
    """
    import asyncio

    async def _run() -> dict:
        from app.main import get_db_session
        from app.repositories.resume_repo import ResumeRepository
        from app.core.constants import ParseStatus

        processed = 0
        async with get_db_session() as db:
            repo = ResumeRepository(db)
            resumes = await repo.get_multi(limit=500)  # process up to 500

            for resume in resumes:
                if resume.parse_status != ParseStatus.SUCCESS.value:
                    continue
                # Re-enqueue individual embedding generation
                generate_embeddings.apply_async(
                    kwargs={"resume_id": str(resume.id)},
                    queue="embeddings",
                )
                processed += 1

        log.info("refresh_embeddings_enqueued", count=processed, model_id=model_id)
        return {"enqueued": processed, "model_id": model_id}

    try:
        return asyncio.run(_run())
    except Exception as exc:
        log.error("refresh_embeddings_failed", error=str(exc))
        return {"status": "FAILED", "error": str(exc)}
