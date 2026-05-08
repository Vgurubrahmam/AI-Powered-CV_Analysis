"""Job description endpoints — create, retrieve, list."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Query, Request
from fastapi import status as http_status

from app.dependencies import DBSession, CurrentUser
from app.schemas.common import APIResponse, CursorPage
from app.schemas.job import JDCreate, JDRead, ParsedJDRead
from app.services.job_service import JobService

router = APIRouter()


@router.post(
    "",
    response_model=APIResponse[JDRead],
    status_code=http_status.HTTP_201_CREATED,
    summary="Create a new job description",
)
async def create_job(
    payload: JDCreate,
    current_user: CurrentUser,
    db: DBSession,
    request: Request,
) -> APIResponse[JDRead]:
    """Create a JD record and enqueue async LLM parsing.

    Returns immediately with a job_id. Poll GET /jobs/{id} for parsed status.
    """
    svc = JobService(db=db)
    jd = await svc.create_job(user_id=current_user.id, payload=payload)
    return APIResponse.success(
        data=JDRead.model_validate(jd),
        request_id=request.headers.get("X-Request-ID", ""),
    )


@router.get(
    "/{job_id}",
    response_model=APIResponse[JDRead],
    summary="Get job description metadata",
)
async def get_job(
    job_id: uuid.UUID,
    current_user: CurrentUser,
    db: DBSession,
    request: Request,
) -> APIResponse[JDRead]:
    """Return JD metadata for a specific job_id."""
    svc = JobService(db=db)
    jd = await svc.get_job(job_id, current_user.id)
    return APIResponse.success(
        data=JDRead.model_validate(jd),
        request_id=request.headers.get("X-Request-ID", ""),
    )


@router.get(
    "/{job_id}/parsed",
    response_model=APIResponse[ParsedJDRead],
    summary="Get parsed job description data",
)
async def get_parsed_job(
    job_id: uuid.UUID,
    current_user: CurrentUser,
    db: DBSession,
    request: Request,
) -> APIResponse[ParsedJDRead]:
    """Return LLM-parsed structured JD data (required_skills, YOE, etc.)."""
    svc = JobService(db=db)
    parsed = await svc.get_parsed_job(job_id, current_user.id)
    return APIResponse.success(
        data=parsed,
        request_id=request.headers.get("X-Request-ID", ""),
    )


@router.get(
    "",
    response_model=APIResponse[CursorPage[JDRead]],
    summary="List job descriptions",
)
async def list_jobs(
    current_user: CurrentUser,
    db: DBSession,
    request: Request,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> APIResponse[CursorPage[JDRead]]:
    """Return paginated list of job descriptions for the authenticated user."""
    svc = JobService(db=db)
    items, total = await svc.list_jobs(current_user.id, limit=limit, offset=offset)
    page: CursorPage[JDRead] = CursorPage(
        items=[JDRead.model_validate(jd) for jd in items],
        total_count=total,
        has_more=(offset + limit) < total,
    )
    return APIResponse.success(
        data=page,
        request_id=request.headers.get("X-Request-ID", ""),
    )
