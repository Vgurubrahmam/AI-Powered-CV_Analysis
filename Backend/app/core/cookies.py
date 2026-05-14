"""Cookie helpers — set and clear HttpOnly auth cookies on responses."""

from __future__ import annotations

from fastapi.responses import JSONResponse

from app.config import settings


def _cookie_kwargs() -> dict:
    """Base cookie parameters from settings."""
    kwargs: dict = {
        "httponly": settings.COOKIE_HTTPONLY,
        "secure": settings.COOKIE_SECURE,
        "samesite": settings.COOKIE_SAMESITE,
        "path": settings.COOKIE_PATH,
    }
    if settings.COOKIE_DOMAIN:
        kwargs["domain"] = settings.COOKIE_DOMAIN
    return kwargs


def set_auth_cookies(
    response: JSONResponse,
    access_token: str,
    refresh_token: str,
    access_max_age: int | None = None,
    refresh_max_age: int | None = None,
) -> JSONResponse:
    """Attach HttpOnly access + refresh cookies to a response."""
    if access_max_age is None:
        access_max_age = settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60
    if refresh_max_age is None:
        refresh_max_age = settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS * 86400

    base = _cookie_kwargs()

    response.set_cookie(
        key="access_token",
        value=access_token,
        max_age=access_max_age,
        **base,
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        max_age=refresh_max_age,
        # Scope refresh cookie to auth endpoints only
        **{**base, "path": "/api/v1/auth"},
    )
    return response


def clear_auth_cookies(response: JSONResponse) -> JSONResponse:
    """Delete access + refresh cookies by setting max_age=0."""
    base = _cookie_kwargs()

    response.delete_cookie(key="access_token", **base)
    response.delete_cookie(
        key="refresh_token",
        **{**base, "path": "/api/v1/auth"},
    )
    return response
