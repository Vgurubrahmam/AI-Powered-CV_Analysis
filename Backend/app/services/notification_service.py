"""Notification service — email (SMTP) and webhook fire-and-forget delivery.

All sends are non-blocking: they enqueue a Celery task rather than sending
inline, so the API response is never delayed by mail/webhook latency.

If Celery is unavailable (e.g. during tests), the service falls back to a
direct asyncio send attempt so integration tests can still exercise the logic.
"""

from __future__ import annotations

import asyncio
import smtplib
import uuid
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

import structlog

from app.config import settings

log = structlog.get_logger(__name__)


class NotificationService:
    """Fire-and-forget notification dispatcher."""

    # ── Email ─────────────────────────────────────────────────────────────────

    def send_analysis_complete_email(
        self,
        user_id: uuid.UUID,
        user_email: str,
        analysis_id: uuid.UUID,
        score: float,
    ) -> None:
        """Enqueue an analysis-complete notification email via Celery."""
        payload = {
            "to": user_email,
            "subject": "Your resume analysis is ready!",
            "body": (
                f"Hi,\n\n"
                f"Your resume analysis has completed with a score of {score:.1f}/100.\n\n"
                f"View your results: {settings.APP_URL}/analysis/{analysis_id}\n\n"
                f"— The ATS Platform Team"
            ),
        }
        self._enqueue_email(payload)

    def send_welcome_email(self, user_email: str, user_name: str = "") -> None:
        """Enqueue a welcome email for new registrations."""
        payload = {
            "to": user_email,
            "subject": "Welcome to ATS Platform!",
            "body": (
                f"Hi {user_name or 'there'},\n\n"
                f"Thanks for signing up. Start by uploading your resume at:\n"
                f"{settings.APP_URL}/upload\n\n"
                f"— The ATS Platform Team"
            ),
        }
        self._enqueue_email(payload)

    def send_parse_failed_email(self, user_email: str, filename: str) -> None:
        """Notify user their resume could not be parsed."""
        payload = {
            "to": user_email,
            "subject": "Resume parse failed",
            "body": (
                f"Hi,\n\nWe were unable to extract text from your file '{filename}'.\n"
                f"Please try uploading a standard PDF or DOCX without scanned images.\n\n"
                f"— The ATS Platform Team"
            ),
        }
        self._enqueue_email(payload)

    # ── Webhook ───────────────────────────────────────────────────────────────

    def send_webhook(
        self,
        url: str,
        event: str,
        payload: dict[str, Any],
        secret: str | None = None,
    ) -> None:
        """Enqueue an outbound webhook delivery with HMAC signature."""
        self._enqueue_webhook(url=url, event=event, payload=payload, secret=secret)

    # ── Internal Celery dispatch ──────────────────────────────────────────────

    def _enqueue_email(self, payload: dict) -> None:
        try:
            from app.workers.tasks.notification_tasks import send_email_task
            send_email_task.apply_async(kwargs={"payload": payload}, queue="default")
            log.debug("email_enqueued", to=payload.get("to"), subject=payload.get("subject"))
        except Exception as exc:
            log.warning("email_enqueue_failed_trying_direct", error=str(exc))
            # Best-effort direct send (dev / test mode)
            asyncio.create_task(_send_smtp_direct(payload))

    def _enqueue_webhook(self, **kwargs) -> None:
        try:
            from app.workers.tasks.notification_tasks import send_webhook_task
            send_webhook_task.apply_async(kwargs=kwargs, queue="default")
            log.debug("webhook_enqueued", url=kwargs.get("url"), event=kwargs.get("event"))
        except Exception as exc:
            log.warning("webhook_enqueue_failed", error=str(exc))


# ─── Direct SMTP helper (dev/test fallback) ───────────────────────────────────

async def _send_smtp_direct(payload: dict) -> None:
    """Attempt a direct SMTP send (non-blocking, best-effort)."""
    if not settings.SMTP_HOST:
        log.debug("smtp_not_configured_skipping")
        return

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = payload["subject"]
        msg["From"] = settings.EMAIL_FROM
        msg["To"] = payload["to"]
        msg.attach(MIMEText(payload["body"], "plain"))

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _smtp_send_sync, msg, payload["to"])
        log.info("email_sent_direct", to=payload["to"])
    except Exception as exc:
        log.error("direct_smtp_failed", error=str(exc))


def _smtp_send_sync(msg: MIMEMultipart, to: str) -> None:
    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
        server.ehlo()
        server.starttls()
        if settings.SMTP_USER:
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD.get_secret_value())
        server.sendmail(settings.EMAIL_FROM, to, msg.as_string())
