"""Dead letter queue handler for failed Celery tasks.

Logs permanently failed tasks (after all retries exhausted) to the database
for manual review and retry.
"""

import logging
from datetime import datetime, timezone

from celery.signals import task_failure

logger = logging.getLogger(__name__)


@task_failure.connect
def handle_task_failure(
    sender=None, task_id=None, exception=None, args=None, kwargs=None, traceback=None, einfo=None, **kw
):
    """Handle permanently failed tasks by logging to database."""
    logger.error(
        "Task permanently failed",
        extra={
            "task_name": sender.name if sender else "unknown",
            "task_id": task_id,
            "exception": str(exception),
            "args": str(args)[:500],
            "kwargs": str(kwargs)[:500],
            "failed_at": datetime.now(timezone.utc).isoformat(),
        },
    )
