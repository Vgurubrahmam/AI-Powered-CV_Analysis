"""Resume service — upload orchestration, version management."""

from __future__ import annotations

import uuid

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.constants import FileType, ParseStatus
from app.core.exceptions import (
    FileTooLargeException,
    PermissionException,
    ResourceNotFoundException,
    UnsupportedFileTypeException,
)
from app.integrations.av_scanner import scan_bytes
from app.repositories.audit_repo import AuditRepository
from app.repositories.resume_repo import ResumeRepository
from app.schemas.resume import ResumeUploadResponse, ParsedResumeRead
from app.services.storage_service import StorageService
from app.utils.file_utils import detect_mime_type, get_file_extension

log = structlog.get_logger(__name__)

_MIME_TO_FILE_TYPE = {
    "application/pdf": FileType.PDF.value,
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": FileType.DOCX.value,
    "text/plain": FileType.TXT.value,
}


class ResumeService:
    def __init__(self, db: AsyncSession, redis=None) -> None:
        self.db = db
        self.redis = redis
        self.repo = ResumeRepository(db)
        self.audit_repo = AuditRepository(db)
        self.storage = StorageService()

    async def upload(
        self,
        user_id: uuid.UUID,
        file_bytes: bytes,
        filename: str,
        *,
        ip: str = "",
    ) -> ResumeUploadResponse:
        """Validate, store, and register a new resume. Enqueues async parse task."""
        # ── 1. Size check ──────────────────────────────────────────────────
        if len(file_bytes) > settings.file_max_size_bytes:
            raise FileTooLargeException(
                f"File exceeds maximum size of {settings.FILE_MAX_SIZE_MB}MB."
            )

        # ── 2. MIME type check (magic bytes, not just extension) ───────────
        mime_type = detect_mime_type(file_bytes)
        if mime_type not in settings.allowed_mime_types_list:
            raise UnsupportedFileTypeException(
                f"File type '{mime_type}' is not supported. "
                "Please upload a PDF, DOCX, or plain text file."
            )

        # ── 3. Malware scan ────────────────────────────────────────────────
        await scan_bytes(file_bytes)

        # ── 4. Upload to storage ───────────────────────────────────────────
        file_type = _MIME_TO_FILE_TYPE[mime_type]
        storage_key = await self.storage.upload_resume(
            user_id=user_id,
            file_bytes=file_bytes,
            filename=filename,
            content_type=mime_type,
        )

        # ── 5. Create DB record ────────────────────────────────────────────
        resume = await self.repo.create(
            {
                "user_id": user_id,
                "storage_key": storage_key,
                "filename": filename,
                "file_type": file_type,
                "file_size_bytes": len(file_bytes),
                "content_type": mime_type,
                "parse_status": ParseStatus.PENDING.value,
            }
        )

        # ── 6. Enqueue async parse task ────────────────────────────────────
        from app.workers.tasks.parsing_tasks import parse_resume_async
        parse_resume_async.apply_async(
            kwargs={"resume_id": str(resume.id)},
            queue="parsing",
        )

        await self.audit_repo.log(
            "resume.uploaded",
            user_id=user_id,
            resource="resume",
            resource_id=resume.id,
            ip_address=ip,
            metadata={"filename": filename, "file_type": file_type, "size": len(file_bytes)},
        )
        log.info("resume_queued_for_parsing", resume_id=str(resume.id))

        return ResumeUploadResponse(resume_id=resume.id, status=ParseStatus.PENDING)

    async def get_resume(self, resume_id: uuid.UUID, user_id: uuid.UUID):
        """Get resume scoped to user. Raises ResourceNotFoundException if not found."""
        resume = await self.repo.get_user_resume(resume_id, user_id)
        if not resume:
            raise ResourceNotFoundException(f"Resume '{resume_id}' not found.")
        return resume

    async def delete_resume(self, resume_id: uuid.UUID, user_id: uuid.UUID) -> None:
        """Delete resume record and associated storage object."""
        resume = await self.get_resume(resume_id, user_id)
        await self.storage.delete_resume(resume.storage_key)
        await self.repo.delete(resume)
        await self.audit_repo.log(
            "resume.deleted", user_id=user_id, resource="resume", resource_id=resume_id
        )

    async def upload_resume(
        self,
        user_id: uuid.UUID,
        filename: str,
        content_type: str,
        file_bytes: bytes,
    ) -> ResumeUploadResponse:
        """Alias used by the API route — delegates to upload()."""
        return await self.upload(
            user_id=user_id,
            file_bytes=file_bytes,
            filename=filename,
        )

    async def get_parsed_data(self, resume_id: uuid.UUID, user_id: uuid.UUID):
        """Return parsed resume data for the given resume."""
        resume = await self.get_resume(resume_id, user_id)
        return ParsedResumeRead.model_validate(resume)

    async def list_resumes(
        self, user_id: uuid.UUID, *, limit: int = 20, offset: int = 0
    ) -> list:
        return await self.repo.get_by_user(user_id, limit=limit, offset=offset)

    async def count_resumes(self, user_id: uuid.UUID) -> int:
        return await self.repo.count_by_user(user_id)

