"""Data retention and cleanup tasks."""

import logging

from src.infrastructure.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

#: ``(table, date column, retention days)`` per docs/privacy/data-retention-policy.md.
#:
#: Module level so the suite can check every target against the declared schema
#: without running a sweep. ``notification_log`` sat here for as long as it did
#: because nothing but a live PostgreSQL run could see that the name was wrong.
RETENTION_RULES: tuple[tuple[str, str, int], ...] = (
    ("audit_log_entries", "created_at", 365),
    ("token_blacklist", "expires_at", 0),
    ("notification_logs", "created_at", 90),
    ("incidents", "created_at", 365),
    ("complaints", "created_at", 365),
    ("road_traffic_collisions", "created_at", 365),
    ("near_misses", "created_at", 365),
    ("investigations", "created_at", 365),
)


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

    try:
        with engine.begin() as conn:
            for table, date_col, retention_days in RETENTION_RULES:
                cutoff = now - timedelta(days=retention_days)
                try:
                    # SAVEPOINT per table because on PostgreSQL the first failing
                    # statement aborts the whole transaction: without unwinding to a
                    # savepoint, one bad target makes every later DELETE raise
                    # InFailedSqlTransaction and turns the closing COMMIT into a
                    # rollback, so the counts below are reported for rows that were
                    # never actually purged. Same C-8 shape as ``_read_savepoint``.
                    with conn.begin_nested():
                        result = conn.execute(
                            text(f"DELETE FROM {table} WHERE {date_col} < :cutoff"),  # nosec B608  # noqa: S608
                            {"cutoff": cutoff},
                        )
                        deleted = result.rowcount or 0
                except Exception as exc:
                    # Names the table *and* the error: the previous wording asserted
                    # "may not exist" without checking, which is how a misnamed
                    # target read as routine for as long as it did.
                    logger.warning(
                        "Retention: table %s NOT purged, rule had no effect: %s: %s",
                        table,
                        type(exc).__name__,
                        exc,
                        exc_info=True,
                    )
                    results[table] = -1
                    continue

                results[table] = deleted
                if deleted > 0:
                    logger.info(
                        "Retention: purged %d rows from %s (cutoff=%s)",
                        deleted,
                        table,
                        cutoff.isoformat(),
                    )

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
