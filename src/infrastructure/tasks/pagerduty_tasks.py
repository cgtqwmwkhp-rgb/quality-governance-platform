"""Celery tasks for PagerDuty Events API v2 paging (Path-to-10 S12 Ops)."""

from __future__ import annotations

import logging
from typing import Any, Optional

from src.infrastructure.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    name="src.infrastructure.tasks.pagerduty_tasks.trigger_pagerduty_alert",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    queue="notifications",
)
def trigger_pagerduty_alert(
    self,
    summary: str,
    severity: str = "error",
    dedup_key: Optional[str] = None,
    source: str = "quality-governance-platform",
    custom_details: Optional[dict[str, Any]] = None,
) -> dict:
    """Enqueue a PagerDuty Events API v2 trigger.

    Fail-closed:
    - No routing key → ``not_configured`` (honest skip; never fake ``enqueued``).
    - Routing key set but send fails → raise (Celery retry / DLQ).
    """
    from src.infrastructure.alerting.pagerduty_client import PagerDutySendError, enqueue_event, is_enabled

    if not is_enabled():
        logger.info("PagerDuty alert skipped: PAGERDUTY_ENABLED is not set")
        return {
            "status": "skipped",
            "reason": "PAGERDUTY_ENABLED is not true",
        }

    try:
        result = enqueue_event(
            summary=summary,
            severity=severity,
            source=source,
            dedup_key=dedup_key,
            custom_details=custom_details,
        )
    except PagerDutySendError as exc:
        logger.error("PagerDuty alert enqueue failed: %s", exc)
        raise self.retry(exc=exc) from exc

    if result.get("status") == "not_configured":
        logger.warning("PagerDuty enabled but routing key missing — alert not sent (fail-closed honesty)")
    return result
