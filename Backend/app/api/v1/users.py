"""Users endpoints — profile management."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Request
from fastapi import status as http_status

from app.dependencies import DBSession, CurrentUser
from app.schemas.common import APIResponse
from app.schemas.user import UserRead, UserUpdate
from app.services.user_service import UserService

router = APIRouter()


@router.get(
    "/me",
    response_model=APIResponse[UserRead],
    summary="Get current user profile",
)
async def get_me(
    current_user: CurrentUser,
    request: Request,
) -> APIResponse[UserRead]:
    """Return the authenticated user's profile."""
    return APIResponse.success(
        data=UserRead.model_validate(current_user),
        request_id=request.headers.get("X-Request-ID", ""),
    )


@router.put(
    "/me",
    response_model=APIResponse[UserRead],
    summary="Update current user profile",
)
async def update_me(
    payload: UserUpdate,
    current_user: CurrentUser,
    db: DBSession,
    request: Request,
) -> APIResponse[UserRead]:
    """Update email or password for the authenticated user."""
    svc = UserService(db=db)
    updated = await svc.update_profile(current_user.id, payload)
    return APIResponse.success(
        data=UserRead.model_validate(updated),
        request_id=request.headers.get("X-Request-ID", ""),
    )
