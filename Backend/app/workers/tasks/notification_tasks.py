"""Notification Celery tasks — email and webhook delivery."""

from __future__ import annotations

import hashlib
import hmac
import json
import time

import httpx
import structlog
from celery import shared_task

from app.config import settings

log = structlog.get_logger(__name__)


@shared_task(
    name="app.workers.tasks.notification_tasks.send_email_task",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    soft_time_limit=30,
)
def send_email_task(self, payload: dict) -> dict:
    """Send a transactional email via SMTP.

    Args:
        payload: dict with keys: to, subject, body.
    """
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText

    if not settings.SMTP_HOST:
        log.info("smtp_not_configured_skipping_email", to=payload.get("to"))
        return {"status": "SKIPPED", "reason": "smtp_not_configured"}

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = payload["subject"]
        msg["From"] = settings.EMAIL_FROM
        msg["To"] = payload["to"]
        msg.attach(MIMEText(payload["body"], "plain"))

        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            if settings.SMTP_USER:
                server.login(
                    settings.SMTP_USER,
                    settings.SMTP_PASSWORD.get_secret_value(),
                )
            server.sendmail(settings.EMAIL_FROM, payload["to"], msg.as_string())

        log.info("email_sent", to=payload["to"], subject=payload["subject"])
        return {"status": "SENT"}

    except Exception as exc:
        log.warning("email_send_failed", error=str(exc), attempt=self.request.retries)
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            log.error("email_max_retries_exceeded", to=payload.get("to"))
            return {"status": "FAILED", "error": str(exc)}


@shared_task(
    name="app.workers.tasks.notification_tasks.send_webhook_task",
    bind=True,
    max_retries=4,
    default_retry_delay=30,
    soft_time_limit=30,
)
def send_webhook_task(
    self,
    url: str,
    event: str,
    payload: dict,
    secret: str | None = None,
) -> dict:
    """Deliver an outbound webhook with optional HMAC-SHA256 signature.

    Retry on 5xx or network errors with exponential backoff.

    Args:
        url: Target webhook URL.
        event: Event type string (e.g. 'analysis.complete').
        payload: JSON-serializable event body.
        secret: Optional HMAC signing secret. If provided, adds
                X-ATS-Signature-256 header.
    """
    body = json.dumps({
        "event": event,
        "timestamp": int(time.time()),
        "data": payload,
    }, default=str)

    headers = {
        "Content-Type": "application/json",
        "X-ATS-Event": event,
        "User-Agent": "ATS-Platform/1.0",
    }

    if secret:
        sig = hmac.new(
            secret.encode(),
            body.encode(),
            hashlib.sha256,
        ).hexdigest()
        headers["X-ATS-Signature-256"] = f"sha256={sig}"

    try:
        with httpx.Client(timeout=15.0) as client:
            response = client.post(url, content=body, headers=headers)

        if response.status_code >= 500:
            raise RuntimeError(f"Webhook target returned {response.status_code}")

        log.info("webhook_delivered", url=url, event=event, status=response.status_code)
        return {"status": "DELIVERED", "http_status": response.status_code}

    except Exception as exc:
        attempt = self.request.retries
        # Exponential backoff: 30s, 60s, 120s, 240s
        delay = 30 * (2 ** attempt)
        log.warning("webhook_failed_retrying", url=url, error=str(exc), attempt=attempt, delay=delay)
        try:
            raise self.retry(exc=exc, countdown=delay)
        except self.MaxRetriesExceededError:
            log.error("webhook_max_retries_exceeded", url=url, event=event)
            return {"status": "FAILED", "error": str(exc)}
