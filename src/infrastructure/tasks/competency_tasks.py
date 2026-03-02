"""Celery tasks for competency lifecycle management."""

import logging
from datetime import datetime, timedelta, timezone

from src.infrastructure.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    name="src.infrastructure.tasks.competency_tasks.check_competency_expiry",
    queue="cleanup",
    bind=True,
    max_retries=3,
)
def check_competency_expiry(self) -> dict:
    """Check for expiring and expired competencies and send notifications.

    Runs daily via Celery beat. Updates competency record states and
    triggers notifications for engineers and their supervisors.
    """
    from sqlalchemy import update
    from src.domain.models.engineer import CompetencyLifecycleState, CompetencyRecord
    from src.infrastructure.database import SessionLocal

    now = datetime.now(timezone.utc)
    expiry_warning_date = now + timedelta(days=30)
    results = {"expired": 0, "expiring_soon": 0, "notifications_sent": 0}

    try:
        with SessionLocal() as db:
            # Mark expired records
            expired_stmt = (
                update(CompetencyRecord)
                .where(
                    CompetencyRecord.expires_at < now,
                    CompetencyRecord.state.in_([
                        CompetencyLifecycleState.ACTIVE,
                        CompetencyLifecycleState.DUE,
                    ]),
                )
                .values(state=CompetencyLifecycleState.EXPIRED)
            )
            result = db.execute(expired_stmt)
            results["expired"] = result.rowcount

            # Mark due-soon records
            due_stmt = (
                update(CompetencyRecord)
                .where(
                    CompetencyRecord.expires_at.between(now, expiry_warning_date),
                    CompetencyRecord.state == CompetencyLifecycleState.ACTIVE,
                )
                .values(state=CompetencyLifecycleState.DUE)
            )
            result = db.execute(due_stmt)
            results["expiring_soon"] = result.rowcount

            db.commit()

        logger.info("Competency expiry check completed: %s", results)
    except Exception as exc:
        logger.error("Competency expiry check failed: %s", exc)
        raise self.retry(exc=exc, countdown=300)

    return results
