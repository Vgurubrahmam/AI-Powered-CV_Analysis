"""Custom ASGI middleware: request ID injection, timing header, context binding."""

from __future__ import annotations

import time
import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

log = structlog.get_logger(__name__)


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Inject a unique request_id into every request and bind it to structlog context.

    Also adds:
      - X-Request-ID response header
      - X-Process-Time response header (ms)
    """

    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[override]
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id

        # Bind request_id + path to structlog so all logs within this request carry them
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
        )

        start = time.perf_counter()

        try:
            response: Response = await call_next(request)
        except Exception as exc:
            elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
            log.error(
                "request_failed",
                status_code=500,
                duration_ms=elapsed_ms,
                exc_info=exc,
            )
            raise

        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)

        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time"] = f"{elapsed_ms}ms"

        log.info(
            "request_completed",
            status_code=response.status_code,
            duration_ms=elapsed_ms,
        )

        return response
