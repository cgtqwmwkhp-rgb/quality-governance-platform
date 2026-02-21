"""Dead letter queue handler for failed Celery tasks.

Logs permanently failed tasks (after all retries exhausted) to the database
for manual review and retry.
"""

import logging
import os
from datetime import datetime, timezone

from celery.signals import task_failure
from sqlalchemy import create_engine, func
from sqlalchemy.orm import Session

from src.infrastructure.monitoring.azure_monitor import track_metric

logger = logging.getLogger(__name__)


def _get_sync_database_url() -> str | None:
    """Derive a synchronous database URL from the async one."""
    url = os.getenv("DATABASE_URL", "")
    if not url:
        return None
    return url.replace("+asyncpg", "").replace("+aiosqlite", "+pysqlite")


def _persist_failed_task(
    task_name: str,
    task_id: str,
    exception_str: str,
    args_str: str | None,
    kwargs_str: str | None,
) -> None:
    """Write a FailedTask record using a sync session."""
    sync_url = _get_sync_database_url()
    if not sync_url:
        logger.warning("DATABASE_URL not set; skipping DLQ persistence")
        return

    try:
        from src.domain.models.failed_task import FailedTask

        engine = create_engine(sync_url)
        with Session(engine) as session:
            record = FailedTask(
                task_name=task_name,
                task_id=task_id,
                exception=exception_str,
                args=args_str,
                kwargs=kwargs_str,
                failed_at=datetime.now(timezone.utc),
            )
            session.add(record)
            session.commit()

            count = session.query(func.count(FailedTask.id)).scalar()
            track_metric("dlq.size", count)
    except Exception:
        logger.exception("Failed to persist task to DLQ table")


@task_failure.connect
def handle_task_failure(
    sender=None, task_id=None, exception=None, args=None, kwargs=None, traceback=None, einfo=None, **kw
):
    """Handle permanently failed tasks by logging to database."""
    task_name = sender.name if sender else "unknown"
    exception_str = str(exception)
    args_str = str(args)[:500] if args else None
    kwargs_str = str(kwargs)[:500] if kwargs else None

    logger.error(
        "Task permanently failed",
        extra={
            "task_name": task_name,
            "task_id": task_id,
            "exception": exception_str,
            "args": args_str,
            "kwargs": kwargs_str,
            "failed_at": datetime.now(timezone.utc).isoformat(),
        },
    )

    _persist_failed_task(task_name, task_id, exception_str, args_str, kwargs_str)
