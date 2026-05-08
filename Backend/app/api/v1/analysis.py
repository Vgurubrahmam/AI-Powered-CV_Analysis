"""Analysis endpoints — create, poll status, score, feedback, rewrite."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Query, Request
from fastapi import status as http_status

from app.dependencies import DBSession, RedisClient, CurrentUser
from app.schemas.common import APIResponse, CursorPage
from app.schemas.analysis import (
    AnalysisRequest,
    AnalysisRead,
    AnalysisResultRead,
    AnalysisCreateResponse,
)
from app.schemas.feedback import FeedbackItemRead, RewriteRequest, RewriteResult
from app.services.analysis_service import AnalysisService
from app.services.feedback_service import FeedbackService

router = APIRouter()


# ── Static routes MUST come before /{analysis_id} ─────────────────────────────

@router.post(
    "",
    response_model=APIResponse[AnalysisCreateResponse],
    status_code=http_status.HTTP_202_ACCEPTED,
    summary="Start a new resume analysis",
)
async def create_analysis(
    payload: AnalysisRequest,
    current_user: CurrentUser,
    db: DBSession,
    redis: RedisClient,
    request: Request,
) -> APIResponse[AnalysisCreateResponse]:
    """Queue a full AI analysis for a resume + job description pair."""
    svc = AnalysisService(db=db, redis=redis)
    result = await svc.create_analysis(payload, current_user.id)
    return APIResponse.success(
        data=result,
        request_id=request.headers.get("X-Request-ID", ""),
    )


@router.get(
    "",
    response_model=APIResponse[CursorPage[AnalysisRead]],
    summary="List analyses for the authenticated user",
)
async def list_analyses(
    current_user: CurrentUser,
    db: DBSession,
    request: Request,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> APIResponse[CursorPage[AnalysisRead]]:
    """Return paginated list of analyses for the authenticated user."""
    svc = AnalysisService(db=db, redis=None)  # type: ignore[arg-type]
    items, total = await svc.list_analyses(current_user.id, limit=limit, offset=offset)
    page: CursorPage[AnalysisRead] = CursorPage(
        items=[AnalysisRead.model_validate(a) for a in items],
        total_count=total,
        has_more=(offset + limit) < total,
    )
    return APIResponse.success(
        data=page,
        request_id=request.headers.get("X-Request-ID", ""),
    )


@router.get(
    "/stats",
    response_model=APIResponse[dict],
    summary="Get analysis stats for dashboard",
)
async def get_analysis_stats(
    current_user: CurrentUser,
    db: DBSession,
    request: Request,
) -> APIResponse[dict]:
    """Return summary stats: total analyses, average score."""
    svc = AnalysisService(db=db, redis=None)  # type: ignore[arg-type]
    stats = await svc.get_stats(current_user.id)
    return APIResponse.success(
        data=stats,
        request_id=request.headers.get("X-Request-ID", ""),
    )


# ── Parameterized routes ──────────────────────────────────────────────────────

@router.get(
    "/{analysis_id}",
    response_model=APIResponse[AnalysisRead],
    summary="Get analysis status and basic result",
)
async def get_analysis(
    analysis_id: uuid.UUID,
    current_user: CurrentUser,
    db: DBSession,
    request: Request,
) -> APIResponse[AnalysisRead]:
    """Poll analysis status. Returns QUEUED → PARSING → MATCHING → SCORING → DONE."""
    svc = AnalysisService(db=db, redis=None)  # type: ignore[arg-type]
    analysis = await svc.get_analysis(analysis_id, current_user.id)
    return APIResponse.success(
        data=AnalysisRead.model_validate(analysis),
        request_id=request.headers.get("X-Request-ID", ""),
    )


@router.get(
    "/{analysis_id}/score",
    response_model=APIResponse[AnalysisResultRead],
    summary="Get detailed analysis score breakdown",
)
async def get_score(
    analysis_id: uuid.UUID,
    current_user: CurrentUser,
    db: DBSession,
    request: Request,
) -> APIResponse[AnalysisResultRead]:
    """Return full score breakdown with keyword, semantic, experience, ATS sub-scores."""
    svc = AnalysisService(db=db, redis=None)  # type: ignore[arg-type]
    analysis = await svc.get_analysis(analysis_id, current_user.id)
    return APIResponse.success(
        data=AnalysisResultRead.model_validate(analysis),
        request_id=request.headers.get("X-Request-ID", ""),
    )


@router.get(
    "/{analysis_id}/feedback",
    response_model=APIResponse[list[FeedbackItemRead]],
    summary="Get prioritized feedback items for an analysis",
)
async def get_feedback(
    analysis_id: uuid.UUID,
    current_user: CurrentUser,
    db: DBSession,
    request: Request,
) -> APIResponse[list[FeedbackItemRead]]:
    """Return prioritized feedback items (highest score_delta first)."""
    svc = FeedbackService(db=db)
    items = await svc.get_feedback_for_analysis(analysis_id, current_user.id)
    return APIResponse.success(
        data=[FeedbackItemRead.model_validate(i) for i in items],
        request_id=request.headers.get("X-Request-ID", ""),
    )


@router.post(
    "/{analysis_id}/rewrite",
    response_model=APIResponse[RewriteResult],
    summary="Request an LLM rewrite for a feedback item",
)
async def rewrite_feedback(
    analysis_id: uuid.UUID,
    payload: RewriteRequest,
    current_user: CurrentUser,
    db: DBSession,
    request: Request,
) -> APIResponse[RewriteResult]:
    """Request a constrained LLM rewrite for a feedback item's original text."""
    svc = FeedbackService(db=db)
    result = await svc.request_rewrite(
        feedback_id=payload.feedback_item_id,
        user_id=current_user.id,
    )
    return APIResponse.success(
        data=RewriteResult(
            feedback_item_id=payload.feedback_item_id,
            original_text=result["original_text"],
            rewritten_text=result["rewritten_text"],
            hallucination_check_passed=result["hallucination_check_passed"],
            flagged_entities=result["flagged_entities"],
            warning=result.get("warning"),
        ),
        request_id=request.headers.get("X-Request-ID", ""),
    )
