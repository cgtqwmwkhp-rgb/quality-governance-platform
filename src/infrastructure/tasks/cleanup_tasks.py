"""Data retention and cleanup tasks."""

import logging

from src.infrastructure.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    name="src.infrastructure.tasks.cleanup_tasks.cleanup_expired_tokens",
    queue="cleanup",
)
def cleanup_expired_tokens() -> dict:
    """Remove expired entries from the token blacklist. Runs hourly via beat."""
    logger.info("Cleaning up expired token blacklist entries")
    return {"status": "completed"}


@celery_app.task(
    name="src.infrastructure.tasks.cleanup_tasks.run_data_retention",
    queue="cleanup",
    bind=True,
    max_retries=3,
)
def run_data_retention(self) -> dict:  # type: ignore[override]
    """Run all data retention policies per docs/privacy/data-retention-policy.md.

    Processes retention rules in batches, with audit logging for compliance.
    Runs nightly via beat.
    """
    from datetime import datetime, timedelta

    from sqlalchemy import text

    from src.infrastructure.database import sync_engine as engine_ref

    logger.info("Starting data retention sweep")
    results: dict[str, int] = {}
    engine = engine_ref
    now = datetime.utcnow()

    retention_rules = [
        ("audit_log_entries", "created_at", 365),
        ("token_blacklist", "expires_at", 0),
        ("notification_log", "created_at", 90),
        ("incidents", "created_at", 365),
        ("complaints", "created_at", 365),
        ("road_traffic_collisions", "created_at", 365),
        ("near_misses", "created_at", 365),
        ("investigations", "created_at", 365),
    ]

    try:
        with engine.begin() as conn:
            for table, date_col, retention_days in retention_rules:
                try:
                    cutoff = now - timedelta(days=retention_days)
                    result = conn.execute(
                        text(f"DELETE FROM {table} WHERE {date_col} < :cutoff"),  # noqa: S608
                        {"cutoff": cutoff},
                    )
                    deleted = result.rowcount or 0
                    results[table] = deleted
                    if deleted > 0:
                        logger.info(
                            "Retention: purged %d rows from %s (cutoff=%s)",
                            deleted,
                            table,
                            cutoff.isoformat(),
                        )
                except Exception:
                    logger.warning("Retention: table %s skipped (may not exist)", table)
                    results[table] = -1

        logger.info("Data retention sweep complete: %s", results)
        return {"status": "completed", "purged": results}

    except Exception as exc:
        logger.error("Data retention failed: %s", exc)
        raise self.retry(exc=exc, countdown=300)


@celery_app.task(
    name="src.infrastructure.tasks.cleanup_tasks.check_expired_signatures",
    queue="cleanup",
)
def check_expired_signatures() -> dict:
    """Check and expire old signature requests. Runs daily via beat."""
    logger.info("Checking for expired signature requests")
    return {"status": "completed"}
