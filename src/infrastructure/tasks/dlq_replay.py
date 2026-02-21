"""Automated DLQ replay task.

Periodically retries failed tasks from the dead-letter queue.  Each entry is
retried at most once; after the retry is dispatched the entry is marked with
``retried=True`` and a ``retried_at`` timestamp.
"""

import ast
import logging
from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.infrastructure.tasks.celery_app import celery_app
from src.infrastructure.tasks.dlq import _get_sync_database_url

logger = logging.getLogger(__name__)


def _parse_args(raw: str | None) -> tuple:
    if not raw:
        return ()
    try:
        val = ast.literal_eval(raw)
        return tuple(val) if isinstance(val, (list, tuple)) else (val,)
    except Exception:
        return ()


def _parse_kwargs(raw: str | None) -> dict:
    if not raw:
        return {}
    try:
        val = ast.literal_eval(raw)
        return val if isinstance(val, dict) else {}
    except Exception:
        return {}


@celery_app.task(
    name="src.infrastructure.tasks.dlq_replay.replay_failed_tasks",
    queue="default",
)
def replay_failed_tasks() -> dict:
    """Re-send un-retried DLQ entries and mark them as retried."""
    sync_url = _get_sync_database_url()
    if not sync_url:
        logger.warning("DATABASE_URL not set; skipping DLQ replay")
        return {"replayed": 0, "errors": 0}

    from src.domain.models.failed_task import FailedTask

    engine = create_engine(sync_url)
    replayed = 0
    errors = 0

    with Session(engine) as session:
        entries = session.query(FailedTask).filter(FailedTask.retried.is_(False)).all()

        for entry in entries:
            try:
                args = _parse_args(entry.args)
                kwargs = _parse_kwargs(entry.kwargs)

                celery_app.send_task(entry.task_name, args=args, kwargs=kwargs)

                entry.retried = True
                entry.retried_at = datetime.now(timezone.utc)
                session.commit()

                logger.info(
                    "Replayed DLQ entry",
                    extra={
                        "task_name": entry.task_name,
                        "task_id": entry.task_id,
                        "dlq_id": entry.id,
                    },
                )
                replayed += 1
            except Exception:
                session.rollback()
                logger.exception(
                    "Failed to replay DLQ entry",
                    extra={
                        "task_name": entry.task_name,
                        "task_id": entry.task_id,
                        "dlq_id": entry.id,
                    },
                )
                errors += 1

    logger.info("DLQ replay complete", extra={"replayed": replayed, "errors": errors})
    return {"replayed": replayed, "errors": errors}
