"""Auth endpoints — login, refresh, logout, register."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi import status as http_status

from app.dependencies import DBSession, RedisClient, CurrentUserPayload
from app.schemas.auth import LoginRequest, TokenPair, RefreshRequest
from app.schemas.common import APIResponse
from app.schemas.user import UserCreate, UserRead
from app.services.auth_service import AuthService

router = APIRouter()


@router.post(
    "/register",
    response_model=APIResponse[UserRead],
    status_code=http_status.HTTP_201_CREATED,
    summary="Register a new user account",
)
async def register(
    payload: UserCreate,
    db: DBSession,
    request: Request,
) -> APIResponse[UserRead]:
    """Create a new user account. Returns the created user profile."""
    svc = AuthService(db=db)
    user = await svc.register(
        payload,
        ip=request.client.host if request.client else "",
    )
    return APIResponse.success(
        data=UserRead.model_validate(user),
        request_id=request.headers.get("X-Request-ID", ""),
    )


@router.post(
    "/login",
    response_model=APIResponse[TokenPair],
    status_code=http_status.HTTP_200_OK,
    summary="Authenticate user and receive JWT token pair",
)
async def login(
    payload: LoginRequest,
    db: DBSession,
    redis: RedisClient,
    request: Request,
) -> APIResponse[TokenPair]:
    """Exchange email + password for an access/refresh token pair."""
    svc = AuthService(db=db)
    token_pair = await svc.login(
        email=payload.email,
        password=payload.password,
        ip=request.client.host if request.client else "",
    )
    return APIResponse.success(
        data=token_pair,
        request_id=request.headers.get("X-Request-ID", ""),
    )


@router.post(
    "/refresh",
    response_model=APIResponse[TokenPair],
    status_code=http_status.HTTP_200_OK,
    summary="Exchange a refresh token for a new token pair",
)
async def refresh_token(
    payload: RefreshRequest,
    db: DBSession,
    redis: RedisClient,
    request: Request,
) -> APIResponse[TokenPair]:
    """Rotate token pair using a valid refresh token."""
    svc = AuthService(db=db)
    token_pair = await svc.refresh(payload.refresh_token)
    return APIResponse.success(
        data=token_pair,
        request_id=request.headers.get("X-Request-ID", ""),
    )


@router.delete(
    "/logout",
    response_model=APIResponse[dict],
    status_code=http_status.HTTP_200_OK,
    summary="Invalidate the current access token",
)
async def logout(
    user_payload: CurrentUserPayload,
    redis: RedisClient,
    request: Request,
) -> APIResponse[dict]:
    """Blacklist the current JWT (stateless logout via Redis)."""
    svc = AuthService(db=None, redis=redis)  # type: ignore[arg-type]
    await svc.logout(user_payload)
    return APIResponse.success(
        data={"message": "Logged out successfully."},
        request_id=request.headers.get("X-Request-ID", ""),
    )
