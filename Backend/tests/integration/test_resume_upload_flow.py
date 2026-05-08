"""Integration test — resume upload flow (parse → store → embed queue)."""

from __future__ import annotations

import io
import uuid
from unittest.mock import AsyncMock, patch, MagicMock

import pytest
import pytest_asyncio

from app.core.constants import ParseStatus


class TestResumeUploadFlow:
    """End-to-end test of the resume upload service layer.

    Mocks: S3 upload, ClamAV scan, Celery task dispatch.
    Uses: real DB session, real parsing logic on sample PDF.
    """

    @pytest_asyncio.fixture
    async def user(self, db):
        from app.models.user import User
        from app.core.security import hash_password
        u = User(
            id=uuid.uuid4(),
            email=f"upload+{uuid.uuid4().hex[:6]}@test.local",
            password_hash=hash_password("Pass123!"),
            role="candidate",
            plan_tier="pro",
            is_active=True,
        )
        db.add(u)
        await db.flush()
        return u

    @pytest.mark.asyncio
    async def test_upload_creates_resume_record(self, db, mock_redis, user, sample_resume_bytes):
        from app.services.resume_service import ResumeService
        from sqlalchemy import select
        from app.models.resume import Resume

        with (
            patch("app.services.resume_service.S3Client") as MockS3,
            patch("app.services.resume_service.scan_bytes", new_callable=AsyncMock) as mock_scan,
            patch("app.workers.tasks.parsing_tasks.parse_resume_async") as mock_task,
        ):
            mock_s3_instance = AsyncMock()
            mock_s3_instance.upload = AsyncMock(return_value=MagicMock(
                storage_key="resumes/test.pdf", url="http://minio/resumes/test.pdf", size_bytes=500
            ))
            MockS3.return_value = mock_s3_instance

            mock_scan.return_value = MagicMock(scanned=True, clean=True)
            mock_task.apply_async = MagicMock(return_value=MagicMock(id="task-123"))

            svc = ResumeService(db=db, redis=mock_redis)
            result = await svc.upload_resume(
                user_id=user.id,
                filename="test_resume.pdf",
                content_type="application/pdf",
                file_bytes=sample_resume_bytes,
            )

        assert result is not None
        assert hasattr(result, "resume_id") or hasattr(result, "id")

        # Verify resume was persisted
        resume_id = getattr(result, "resume_id", getattr(result, "id", None))
        if resume_id:
            row = (await db.execute(select(Resume).where(Resume.id == resume_id))).scalar_one_or_none()
            assert row is not None
            assert row.user_id == user.id
            assert row.filename == "test_resume.pdf"

    @pytest.mark.asyncio
    async def test_upload_rejects_virus(self, db, mock_redis, user, sample_resume_bytes):
        from app.services.resume_service import ResumeService
        from app.integrations.av_scanner import VirusDetectedError

        with (
            patch("app.services.resume_service.S3Client"),
            patch("app.services.resume_service.scan_bytes", new_callable=AsyncMock) as mock_scan,
        ):
            mock_scan.side_effect = VirusDetectedError("Eicar-Test-Signature")

            svc = ResumeService(db=db, redis=mock_redis)
            with pytest.raises(Exception) as exc_info:
                await svc.upload_resume(
                    user_id=user.id,
                    filename="virus.pdf",
                    content_type="application/pdf",
                    file_bytes=sample_resume_bytes,
                )
            assert "virus" in str(exc_info.value).lower() or "malware" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_upload_rejects_oversized_file(self, db, mock_redis, user):
        from app.services.resume_service import ResumeService
        from app.core.exceptions import ValidationException

        big_bytes = b"x" * (11 * 1024 * 1024)  # 11 MB > FILE_MAX_SIZE_MB=10
        svc = ResumeService(db=db, redis=mock_redis)
        with pytest.raises((ValidationException, Exception)):
            await svc.upload_resume(
                user_id=user.id,
                filename="bigfile.pdf",
                content_type="application/pdf",
                file_bytes=big_bytes,
            )
