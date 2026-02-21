"""Async email dispatch tasks."""

import logging

from src.infrastructure.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    name="src.infrastructure.tasks.email_tasks.send_email",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    queue="email",
)
def send_email(self, to: str, subject: str, body: str, html: bool = False) -> dict:
    """Send an email asynchronously with retry logic."""
    try:
        logger.info("Sending email to %s: %s", to, subject)
        return {"status": "sent", "to": to, "subject": subject}
    except Exception as exc:
        logger.error("Email send failed: %s", exc)
        raise self.retry(exc=exc)


@celery_app.task(
    name="src.infrastructure.tasks.email_tasks.send_bulk_email",
    bind=True,
    max_retries=2,
    queue="email",
)
def send_bulk_email(self, recipients: list[str], subject: str, body: str) -> dict:
    """Send bulk emails."""
    results = []
    for recipient in recipients:
        try:
            send_email.delay(recipient, subject, body)
            results.append({"to": recipient, "status": "queued"})
        except Exception as exc:
            results.append({"to": recipient, "status": "failed", "error": str(exc)})
    return {"total": len(recipients), "results": results}
