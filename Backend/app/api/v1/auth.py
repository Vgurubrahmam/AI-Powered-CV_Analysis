"""Auth endpoints — login, refresh, logout, register.

Login and refresh now set HttpOnly Secure cookies instead of returning
tokens in the response body. The Authorization header is still supported
as a fallback for API clients and Swagger UI.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi import status as http_status
from fastapi.responses import JSONResponse

from app.core.cookies import clear_auth_cookies, set_auth_cookies
from app.dependencies import DBSession, RedisClient, CurrentUserPayload
from app.schemas.auth import LoginRequest
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
    status_code=http_status.HTTP_200_OK,
    summary="Authenticate user and receive auth cookies",
)
async def login(
    payload: LoginRequest,
    db: DBSession,
    redis: RedisClient,
    request: Request,
) -> JSONResponse:
    """Exchange email + password for HttpOnly auth cookies.

    Tokens are set via Set-Cookie headers — never exposed in the response body.
    """
    svc = AuthService(db=db)
    token_pair = await svc.login(
        email=payload.email,
        password=payload.password,
        ip=request.client.host if request.client else "",
    )

    body = APIResponse.success(
        data={"message": "Login successful."},
        request_id=request.headers.get("X-Request-ID", ""),
    ).model_dump()

    response = JSONResponse(content=body, status_code=200)
    set_auth_cookies(response, token_pair.access_token, token_pair.refresh_token)
    return response


@router.post(
    "/refresh",
    status_code=http_status.HTTP_200_OK,
    summary="Refresh auth tokens via cookie",
)
async def refresh_token(
    request: Request,
    db: DBSession,
    redis: RedisClient,
) -> JSONResponse:
    """Rotate token pair using the refresh_token cookie.

    Falls back to reading refresh_token from the request body for API clients.
    """
    # Read refresh token from cookie first, then body fallback
    refresh_tok = request.cookies.get("refresh_token")
    if not refresh_tok:
        try:
            body = await request.json()
            refresh_tok = body.get("refresh_token")
        except Exception:
            pass
    if not refresh_tok:
        # No refresh token at all — clear any stale cookies and return 401
        resp = JSONResponse(
            content=APIResponse.failure(
                code="AUTH_ERROR",
                message="Refresh token missing. Please log in again.",
                request_id=request.headers.get("X-Request-ID", ""),
            ).model_dump(),
            status_code=401,
        )
        clear_auth_cookies(resp)
        return resp

    try:
        svc = AuthService(db=db)
        token_pair = await svc.refresh(refresh_tok)
    except Exception:
        # Invalid/expired refresh token — clear stale cookies so browser stops sending them
        resp = JSONResponse(
            content=APIResponse.failure(
                code="AUTH_ERROR",
                message="Session expired. Please log in again.",
                request_id=request.headers.get("X-Request-ID", ""),
            ).model_dump(),
            status_code=401,
        )
        clear_auth_cookies(resp)
        return resp

    resp_body = APIResponse.success(
        data={"message": "Token refreshed."},
        request_id=request.headers.get("X-Request-ID", ""),
    ).model_dump()

    response = JSONResponse(content=resp_body, status_code=200)
    set_auth_cookies(response, token_pair.access_token, token_pair.refresh_token)
    return response


@router.delete(
    "/logout",
    status_code=http_status.HTTP_200_OK,
    summary="Invalidate the current access token and clear cookies",
)
async def logout(
    user_payload: CurrentUserPayload,
    redis: RedisClient,
    request: Request,
) -> JSONResponse:
    """Blacklist the current JWT and clear auth cookies."""
    # Best-effort blacklist (skip if Redis is unavailable)
    try:
        svc = AuthService(db=None, redis=redis)  # type: ignore[arg-type]
        await svc.logout(user_payload)
    except Exception:
        pass  # Cookies are still cleared below

    body = APIResponse.success(
        data={"message": "Logged out successfully."},
        request_id=request.headers.get("X-Request-ID", ""),
    ).model_dump()

    response = JSONResponse(content=body, status_code=200)
    clear_auth_cookies(response)
    return response
