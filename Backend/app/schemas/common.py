"""Common Pydantic schemas: response envelope, pagination, error response."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class Meta(BaseModel):
    """Standard response metadata."""
    request_id: str = ""
    timestamp: str = ""
    version: str = "v1"


class ErrorDetail(BaseModel):
    """Structured error information."""
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class APIResponse(BaseModel, Generic[T]):
    """Standard API response envelope for all endpoints."""
    data: T | None = None
    error: ErrorDetail | None = None
    meta: Meta = Field(default_factory=Meta)

    @classmethod
    def success(cls, data: T, request_id: str = "") -> "APIResponse[T]":
        from datetime import UTC
        return cls(
            data=data,
            error=None,
            meta=Meta(
                request_id=request_id,
                timestamp=datetime.now(UTC).isoformat(),
            ),
        )

    @classmethod
    def failure(
        cls,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
        request_id: str = "",
    ) -> "APIResponse[None]":
        from datetime import UTC
        return cls(
            data=None,
            error=ErrorDetail(code=code, message=message, details=details or {}),
            meta=Meta(
                request_id=request_id,
                timestamp=datetime.now(UTC).isoformat(),
            ),
        )


class CursorPage(BaseModel, Generic[T]):
    """Cursor-based paginated result set."""
    items: list[T]
    next_cursor: str | None = None
    total_count: int | None = None
    has_more: bool = False


class HealthCheck(BaseModel):
    """Health check response."""
    status: str
    env: str
    version: str
