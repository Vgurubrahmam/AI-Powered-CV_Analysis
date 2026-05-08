"""Inbound webhook receiver — HMAC-verified event ingestion."""

from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any

import structlog
from fastapi import APIRouter, Header, HTTPException, Request
from fastapi import status as http_status

from app.config import settings
from app.schemas.common import APIResponse

log = structlog.get_logger(__name__)

router = APIRouter()

# Shared signing secret for inbound webhooks (set in .env as WEBHOOK_SECRET)
_WEBHOOK_SECRET = getattr(settings, "WEBHOOK_SECRET", "")


@router.post(
    "/inbound",
    response_model=APIResponse[dict[str, Any]],
    status_code=http_status.HTTP_200_OK,
    summary="Receive an inbound signed webhook event",
)
async def receive_webhook(
    request: Request,
    x_ats_signature_256: str | None = Header(default=None, alias="X-ATS-Signature-256"),
    x_ats_event: str | None = Header(default=None, alias="X-ATS-Event"),
) -> APIResponse[dict[str, Any]]:
    """Receive and verify an inbound webhook.

    Validates HMAC-SHA256 signature if WEBHOOK_SECRET is configured.
    Logs the event and returns 200 immediately (async processing).
    """
    raw_body = await request.body()

    # ── Signature verification ────────────────────────────────────────────────
    if _WEBHOOK_SECRET:
        if not x_ats_signature_256:
            raise HTTPException(
                status_code=http_status.HTTP_401_UNAUTHORIZED,
                detail="Missing X-ATS-Signature-256 header.",
            )
        expected = "sha256=" + hmac.new(
            _WEBHOOK_SECRET.encode(),
            raw_body,
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(expected, x_ats_signature_256):
            log.warning("webhook_signature_invalid", event=x_ats_event)
            raise HTTPException(
                status_code=http_status.HTTP_401_UNAUTHORIZED,
                detail="Webhook signature verification failed.",
            )

    # ── Parse payload ─────────────────────────────────────────────────────────
    try:
        payload: dict[str, Any] = json.loads(raw_body)
    except Exception:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="Webhook payload must be valid JSON.",
        )

    log.info(
        "inbound_webhook_received",
        event=x_ats_event,
        payload_keys=list(payload.keys()),
    )

    # ── Route to handler (extend here for specific events) ────────────────────
    event = x_ats_event or payload.get("event", "unknown")
    await _dispatch_event(event, payload)

    return APIResponse.success(
        data={"received": True, "event": event},
        request_id=request.headers.get("X-Request-ID", ""),
    )


async def _dispatch_event(event: str, payload: dict[str, Any]) -> None:
    """Route inbound webhook events to appropriate handlers."""
    if event == "analysis.rerun_requested":
        analysis_id = payload.get("data", {}).get("analysis_id")
        if analysis_id:
            from app.workers.tasks.analysis_tasks import run_full_analysis
            run_full_analysis.apply_async(
                kwargs={"analysis_id": analysis_id},
                queue="default",
            )
            log.info("webhook_rerun_enqueued", analysis_id=analysis_id)
    else:
        log.debug("webhook_event_not_handled", event=event)
