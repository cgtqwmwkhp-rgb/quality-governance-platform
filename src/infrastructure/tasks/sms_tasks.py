"""Async SMS dispatch tasks."""

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


def _mask_phone(phone_number: str) -> str:
    """Mask a phone number for logs and task results."""
    if len(phone_number) > 4:
        return "***" + phone_number[-4:]
    return "***"


@celery_app.task(
    name="src.infrastructure.tasks.sms_tasks.send_sms",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    queue="notifications",
)
def send_sms(self, phone_number: str, message: str) -> dict:
    """Send an SMS asynchronously with retry logic.

    Fail-closed: without a configured provider this returns ``skipped``
    (never ``sent``). Soft provider failures return ``failed``; hard
    exceptions enter the Celery retry/DLQ path.
    """
    masked_to = _mask_phone(phone_number)
    try:
        from src.domain.services.sms_service import SMSService

        sms_service = SMSService()

        if not sms_service.enabled:
            # Do not log phone-derived values (CodeQL clear-text logging).
            logger.warning("SMS service not configured — skipping send")
            return {
                "status": "skipped",
                "to": masked_to,
                "reason": "SMS service not configured",
            }

        result = _run_async(sms_service.send_sms(to=phone_number, message=message))
        if result.success:
            logger.info("SMS sent successfully")
            return {
                "status": "sent",
                "to": masked_to,
                "message_sid": result.message_sid,
            }

        error = result.error_message or "SMS delivery failed"
        logger.error("SMS delivery failed")
        return {"status": "failed", "to": masked_to, "error": error}
    except Exception as exc:
        logger.error("SMS send failed: %s", exc)
        raise self.retry(exc=exc)
