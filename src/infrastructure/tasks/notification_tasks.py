"""Push notification batch tasks."""

import json
import logging
import os
from typing import Optional

from src.infrastructure.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

VAPID_PRIVATE_KEY = os.getenv("VAPID_PRIVATE_KEY", "")
VAPID_CLAIMS_EMAIL = os.getenv("VAPID_CLAIMS_EMAIL", "mailto:admin@qgp.plantexpand.com")


def _send_webpush(endpoint: str, p256dh: str, auth: str, payload: str) -> bool:
    """Send a single Web Push notification via pywebpush."""
    try:
        from pywebpush import webpush

        webpush(
            subscription_info={
                "endpoint": endpoint,
                "keys": {"p256dh": p256dh, "auth": auth},
            },
            data=payload,
            vapid_private_key=VAPID_PRIVATE_KEY,
            vapid_claims={"sub": VAPID_CLAIMS_EMAIL},
        )
        return True
    except ImportError:
        logger.warning("pywebpush not installed — push notifications disabled")
        return False
    except Exception as exc:
        logger.error("Web push delivery failed to %s...: %s", endpoint[:40], exc)
        return False


@celery_app.task(
    name="src.infrastructure.tasks.notification_tasks.send_push_notification",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    queue="notifications",
)
def send_push_notification(self, user_id: int, title: str, body: str, data: Optional[dict] = None) -> dict:
    """Send a push notification to a user via Web Push (VAPID)."""
    from sqlalchemy import select

    from src.infrastructure.database import SessionLocal

    if not VAPID_PRIVATE_KEY:
        logger.warning("VAPID_PRIVATE_KEY not set — skipping push for user %d", user_id)
        return {"status": "skipped", "user_id": user_id, "reason": "no_vapid_key"}

    payload = json.dumps({"title": title, "body": body, "data": data or {}})
    sent = 0
    failed = 0

    try:
        from src.api.routes.push_notifications import PushSubscription

        with SessionLocal() as session:
            subs = (
                session.execute(
                    select(PushSubscription).where(
                        PushSubscription.user_id == user_id,
                        PushSubscription.is_active.is_(True),
                    )
                )
                .scalars()
                .all()
            )

            for sub in subs:
                ok = _send_webpush(sub.endpoint, sub.p256dh_key, sub.auth_key, payload)
                if ok:
                    sent += 1
                else:
                    failed += 1

        logger.info("Push notification for user %d: %d sent, %d failed", user_id, sent, failed)
        return {"status": "sent", "user_id": user_id, "sent": sent, "failed": failed}
    except Exception as exc:
        logger.error("Push notification failed for user %d: %s", user_id, exc)
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
