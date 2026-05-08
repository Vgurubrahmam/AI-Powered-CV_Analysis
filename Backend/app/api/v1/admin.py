"""Admin endpoints — platform stats and user management (system_admin only)."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from fastapi import status as http_status
from sqlalchemy import func, select

from app.core.constants import UserRole
from app.dependencies import DBSession, CurrentUser, require_role
from app.schemas.common import APIResponse, CursorPage
from app.schemas.user import UserRead, UserAdminUpdate
from app.services.user_service import UserService

router = APIRouter()

# All admin routes require system_admin role
_admin_dep = Depends(require_role(UserRole.SYSTEM_ADMIN))


@router.get(
    "/stats",
    response_model=APIResponse[dict[str, Any]],
    dependencies=[_admin_dep],
    summary="Platform-wide statistics",
)
async def get_stats(
    db: DBSession,
    request: Request,
) -> APIResponse[dict[str, Any]]:
    """Return aggregate counts: total users, resumes, analyses, completed analyses."""
    from app.models.user import User
    from app.models.resume import Resume
    from app.models.analysis import Analysis
    from app.core.constants import AnalysisStatus

    async def count(model):
        result = await db.execute(select(func.count()).select_from(model))
        return result.scalar_one()

    total_users = await count(User)
    total_resumes = await count(Resume)
    total_analyses = await count(Analysis)

    done_result = await db.execute(
        select(func.count())
        .select_from(Analysis)
        .where(Analysis.status == AnalysisStatus.DONE.value)
    )
    completed_analyses = done_result.scalar_one()

    stats = {
        "total_users": total_users,
        "total_resumes": total_resumes,
        "total_analyses": total_analyses,
        "completed_analyses": completed_analyses,
        "completion_rate": (
            round(completed_analyses / total_analyses * 100, 1)
            if total_analyses else 0.0
        ),
    }
    return APIResponse.success(data=stats, request_id=request.headers.get("X-Request-ID", ""))


@router.get(
    "/users",
    response_model=APIResponse[CursorPage[UserRead]],
    dependencies=[_admin_dep],
    summary="List all platform users",
)
async def list_users(
    db: DBSession,
    request: Request,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> APIResponse[CursorPage[UserRead]]:
    """Return paginated list of all users (admin only)."""
    svc = UserService(db=db)
    users = await svc.list_users(limit=limit, offset=offset)
    page: CursorPage[UserRead] = CursorPage(
        items=[UserRead.model_validate(u) for u in users],
        has_more=len(users) == limit,
    )
    return APIResponse.success(data=page, request_id=request.headers.get("X-Request-ID", ""))


@router.patch(
    "/users/{user_id}",
    response_model=APIResponse[UserRead],
    dependencies=[_admin_dep],
    summary="Update user role or plan tier",
)
async def admin_update_user(
    user_id: uuid.UUID,
    payload: UserAdminUpdate,
    db: DBSession,
    request: Request,
) -> APIResponse[UserRead]:
    """Allow admins to change a user's role or plan tier."""
    svc = UserService(db=db)
    updated = await svc.admin_update(user_id, payload)
    return APIResponse.success(
        data=UserRead.model_validate(updated),
        request_id=request.headers.get("X-Request-ID", ""),
    )
