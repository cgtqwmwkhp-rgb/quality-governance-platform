"""Monitoring tasks for Celery queue depth and metrics."""

import logging

from src.infrastructure.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    name="src.infrastructure.tasks.monitor_tasks.log_task_queue_depth",
    queue="default",
)
def log_task_queue_depth() -> dict:
    """Log/track Celery task queue depth. Runs every 5 minutes via beat.

    Reports active (in progress) and reserved (waiting) task counts from workers.
    Note: reserved only reflects prefetched tasks; for Redis, queue depth may be higher.
    """
    try:
        inspect = celery_app.control.inspect(timeout=2.0)
        active = inspect.active() or {}
        reserved = inspect.reserved() or {}

        active_count = sum(len(tasks) for tasks in active.values())
        reserved_count = sum(len(tasks) for tasks in reserved.values())
        total = active_count + reserved_count

        logger.info(
            "Celery task queue depth",
            extra={
                "active": active_count,
                "reserved": reserved_count,
                "total": total,
                "workers": len(active) or len(reserved) or 0,
            },
        )

        return {"active": active_count, "reserved": reserved_count, "total": total}
    except Exception as e:
        logger.warning("Failed to get Celery queue depth: %s", e, exc_info=True)
        return {"error": str(e)}
