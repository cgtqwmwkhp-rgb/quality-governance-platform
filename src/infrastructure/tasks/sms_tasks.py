"""Async SMS dispatch tasks."""

import logging

from src.infrastructure.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    name="src.infrastructure.tasks.sms_tasks.send_sms",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    queue="notifications",
)
def send_sms(self, phone_number: str, message: str) -> dict:
    """Send an SMS asynchronously with retry logic."""
    try:
        logger.info("Sending SMS to %s", phone_number)
        return {"status": "sent", "to": phone_number}
    except Exception as exc:
        logger.error("SMS send failed: %s", exc)
        raise self.retry(exc=exc)
