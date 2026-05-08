"""Resume endpoints — upload, retrieve, delete."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, File, Query, Request, UploadFile
from fastapi import status as http_status

from app.dependencies import DBSession, RedisClient, CurrentUser
from app.schemas.common import APIResponse, CursorPage
from app.schemas.resume import ResumeRead, ParsedResumeRead, ResumeUploadResponse
from app.services.resume_service import ResumeService

router = APIRouter()


@router.post(
    "/upload",
    response_model=APIResponse[ResumeUploadResponse],
    status_code=http_status.HTTP_202_ACCEPTED,
    summary="Upload a resume file (PDF, DOCX, or TXT)",
)
async def upload_resume(
    file: UploadFile = File(..., description="Resume file (PDF, DOCX, or TXT, max 10 MB)"),
    current_user: CurrentUser = ...,
    db: DBSession = ...,
    redis: RedisClient = ...,
    request: Request = ...,
) -> APIResponse[ResumeUploadResponse]:
    """Upload and enqueue a resume for parsing.

    Validates MIME type and file size, stores in S3, creates DB record,
    runs AV scan, then enqueues async parse task.
    Returns immediately with a resume_id to poll.
    """
    file_bytes = await file.read()
    svc = ResumeService(db=db, redis=redis)
    result = await svc.upload_resume(
        user_id=current_user.id,
        filename=file.filename or "resume",
        content_type=file.content_type or "application/octet-stream",
        file_bytes=file_bytes,
    )
    return APIResponse.success(
        data=result,
        request_id=request.headers.get("X-Request-ID", ""),
    )


@router.get(
    "/{resume_id}",
    response_model=APIResponse[ResumeRead],
    summary="Get resume metadata",
)
async def get_resume(
    resume_id: uuid.UUID,
    current_user: CurrentUser,
    db: DBSession,
    request: Request,
) -> APIResponse[ResumeRead]:
    """Return resume metadata (status, confidence, file info) for a specific resume."""
    svc = ResumeService(db=db)
    resume = await svc.get_resume(resume_id, current_user.id)
    return APIResponse.success(
        data=ResumeRead.model_validate(resume),
        request_id=request.headers.get("X-Request-ID", ""),
    )


@router.get(
    "/{resume_id}/parsed",
    response_model=APIResponse[ParsedResumeRead],
    summary="Get parsed resume data",
)
async def get_parsed_resume(
    resume_id: uuid.UUID,
    current_user: CurrentUser,
    db: DBSession,
    request: Request,
) -> APIResponse[ParsedResumeRead]:
    """Return structured parsed data for a resume (sections, skills, experience, etc.)."""
    svc = ResumeService(db=db)
    parsed = await svc.get_parsed_data(resume_id, current_user.id)
    return APIResponse.success(
        data=parsed,
        request_id=request.headers.get("X-Request-ID", ""),
    )


@router.delete(
    "/{resume_id}",
    response_model=APIResponse[dict],
    status_code=http_status.HTTP_200_OK,
    summary="Delete a resume and its S3 file",
)
async def delete_resume(
    resume_id: uuid.UUID,
    current_user: CurrentUser,
    db: DBSession,
    request: Request,
) -> APIResponse[dict]:
    """Permanently delete a resume record and its associated S3 file."""
    svc = ResumeService(db=db)
    await svc.delete_resume(resume_id, current_user.id)
    return APIResponse.success(
        data={"deleted": True, "resume_id": str(resume_id)},
        request_id=request.headers.get("X-Request-ID", ""),
    )


@router.get(
    "",
    response_model=APIResponse[CursorPage[ResumeRead]],
    summary="List resumes for the authenticated user",
)
async def list_resumes(
    current_user: CurrentUser,
    db: DBSession,
    request: Request,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> APIResponse[CursorPage[ResumeRead]]:
    """Return paginated list of resumes for the authenticated user."""
    svc = ResumeService(db=db)
    items = await svc.list_resumes(current_user.id, limit=limit, offset=offset)
    total = await svc.count_resumes(current_user.id)
    page: CursorPage[ResumeRead] = CursorPage(
        items=[ResumeRead.model_validate(r) for r in items],
        total_count=total,
        has_more=(offset + limit) < total,
    )
    return APIResponse.success(
        data=page,
        request_id=request.headers.get("X-Request-ID", ""),
    )

