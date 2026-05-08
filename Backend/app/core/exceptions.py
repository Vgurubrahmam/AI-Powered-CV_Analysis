"""Custom exception hierarchy and global exception handlers.

All domain exceptions inherit from AppException.
The global handler maps each exception class → HTTP status code + structured error response.
"""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

log = structlog.get_logger(__name__)


# ─── Exception Hierarchy ──────────────────────────────────────────────────────

class AppException(Exception):
    """Base class for all application-level exceptions."""

    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    error_code: str = "INTERNAL_ERROR"

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class ParseException(AppException):
    """Resume or JD parsing failure."""
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    error_code = "PARSE_FAILED"


class ValidationException(AppException):
    """Input does not meet schema requirements."""
    status_code = status.HTTP_400_BAD_REQUEST
    error_code = "VALIDATION_ERROR"


class AuthException(AppException):
    """Authentication or authorization failure."""
    status_code = status.HTTP_401_UNAUTHORIZED
    error_code = "AUTH_ERROR"


class PermissionException(AppException):
    """User does not have permission for this action."""
    status_code = status.HTTP_403_FORBIDDEN
    error_code = "FORBIDDEN"


class ResourceNotFoundException(AppException):
    """Requested resource does not exist."""
    status_code = status.HTTP_404_NOT_FOUND
    error_code = "NOT_FOUND"


class ConflictException(AppException):
    """Resource already exists or state conflict."""
    status_code = status.HTTP_409_CONFLICT
    error_code = "CONFLICT"


class LLMException(AppException):
    """LLM API error, timeout, or all retries exhausted."""
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    error_code = "LLM_ERROR"


class StorageException(AppException):
    """File storage (S3/MinIO) failure."""
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    error_code = "STORAGE_ERROR"


class PipelineException(AppException):
    """Any failure during the analysis pipeline."""
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    error_code = "PIPELINE_ERROR"


class RateLimitException(AppException):
    """Rate limit exceeded."""
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    error_code = "RATE_LIMIT_EXCEEDED"


class FileTooLargeException(AppException):
    """Uploaded file exceeds maximum size."""
    status_code = status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
    error_code = "FILE_TOO_LARGE"


class UnsupportedFileTypeException(AppException):
    """File type is not supported."""
    status_code = status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
    error_code = "UNSUPPORTED_FILE_TYPE"


class MalwareDetectedException(AppException):
    """File flagged by antivirus scanner."""
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    error_code = "MALWARE_DETECTED"


# ─── Response helpers ─────────────────────────────────────────────────────────

def _error_response(
    request: Request,
    status_code: int,
    error_code: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> JSONResponse:
    """Build the standard error envelope."""
    import uuid
    from datetime import UTC, datetime

    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return JSONResponse(
        status_code=status_code,
        content={
            "data": None,
            "error": {
                "code": error_code,
                "message": message,
                "details": details or {},
            },
            "meta": {
                "request_id": request_id,
                "timestamp": datetime.now(UTC).isoformat(),
                "version": "v1",
            },
        },
    )


# ─── Exception Handlers ───────────────────────────────────────────────────────

def register_exception_handlers(app: FastAPI) -> None:
    """Register all global exception handlers on the FastAPI app."""

    @app.exception_handler(AppException)
    async def handle_app_exception(request: Request, exc: AppException) -> JSONResponse:
        log.warning(
            "app_exception",
            error_code=exc.error_code,
            message=exc.message,
            details=exc.details,
            path=request.url.path,
        )
        return _error_response(
            request,
            exc.status_code,
            exc.error_code,
            exc.message,
            exc.details,
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        log.warning("request_validation_error", errors=exc.errors(), path=request.url.path)
        return _error_response(
            request,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "VALIDATION_ERROR",
            "Request validation failed.",
            {"errors": exc.errors()},
        )

    @app.exception_handler(Exception)
    async def handle_unhandled_exception(request: Request, exc: Exception) -> JSONResponse:
        log.error(
            "unhandled_exception",
            exc_type=type(exc).__name__,
            message=str(exc),
            path=request.url.path,
            exc_info=exc,
        )
        return _error_response(
            request,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "INTERNAL_ERROR",
            "An unexpected error occurred. Please try again later.",
        )
