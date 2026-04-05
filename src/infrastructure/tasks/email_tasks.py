"""Async email dispatch tasks."""

import asyncio
import logging

from src.infrastructure.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


def _run_async(coro):
    """Run an async coroutine from a synchronous Celery task."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as pool:
                return pool.submit(asyncio.run, coro).result()
        return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


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
        from src.domain.services.email_service import email_service

        masked_to = to[:3] + "***" if len(to) > 3 else "***"

        if not email_service.enabled:
            logger.warning("Email service not configured — skipping send to %s", masked_to)
            return {"status": "skipped", "to": masked_to, "subject": subject}

        success = _run_async(
            email_service.send_email(to=[to], subject=subject, html_content=body if html else f"<pre>{body}</pre>")
        )
        send_status = "sent" if success else "failed"
        logger.info("Email %s to %s: %s", send_status, masked_to, subject[:30])
        return {"status": send_status, "to": masked_to, "subject": subject}
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
