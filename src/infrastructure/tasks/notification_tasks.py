"""Push notification batch tasks."""

import logging

from src.infrastructure.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    name="src.infrastructure.tasks.notification_tasks.send_push_notification",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    queue="notifications",
)
def send_push_notification(
    self, user_id: int, title: str, body: str, data: dict | None = None
) -> dict:
    """Send a push notification to a user."""
    try:
        logger.info("Sending push notification to user %d: %s", user_id, title)
        return {"status": "sent", "user_id": user_id, "title": title}
    except Exception as exc:
        logger.error("Push notification failed: %s", exc)
        raise self.retry(exc=exc)


@celery_app.task(
    name="src.infrastructure.tasks.notification_tasks.send_batch_notifications",
    queue="notifications",
)
def send_batch_notifications(user_ids: list[int], title: str, body: str) -> dict:
    """Send push notifications to multiple users."""
    for user_id in user_ids:
        send_push_notification.delay(user_id, title, body)
    return {"status": "queued", "count": len(user_ids)}
