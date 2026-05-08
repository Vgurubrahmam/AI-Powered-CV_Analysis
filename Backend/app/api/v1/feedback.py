"""Feedback endpoints — accept feedback, get single item."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Request
from fastapi import status as http_status

from app.dependencies import DBSession, CurrentUser
from app.schemas.common import APIResponse
from app.schemas.feedback import FeedbackItemRead
from app.services.feedback_service import FeedbackService

router = APIRouter()


@router.get(
    "/{feedback_id}",
    response_model=APIResponse[FeedbackItemRead],
    summary="Get a single feedback item",
)
async def get_feedback_item(
    feedback_id: uuid.UUID,
    current_user: CurrentUser,
    db: DBSession,
    request: Request,
) -> APIResponse[FeedbackItemRead]:
    """Return a single feedback item by ID (user-scoped via analysis ownership)."""
    svc = FeedbackService(db=db)
    item = await svc.get_feedback_item(feedback_id, current_user.id)
    return APIResponse.success(
        data=FeedbackItemRead.model_validate(item),
        request_id=request.headers.get("X-Request-ID", ""),
    )


@router.patch(
    "/{feedback_id}/accept",
    response_model=APIResponse[FeedbackItemRead],
    summary="Mark a feedback item as accepted",
)
async def accept_feedback(
    feedback_id: uuid.UUID,
    current_user: CurrentUser,
    db: DBSession,
    request: Request,
) -> APIResponse[FeedbackItemRead]:
    """Mark that the candidate has accepted and applied this feedback."""
    svc = FeedbackService(db=db)
    item = await svc.mark_accepted(feedback_id, current_user.id)
    return APIResponse.success(
        data=FeedbackItemRead.model_validate(item),
        request_id=request.headers.get("X-Request-ID", ""),
    )
