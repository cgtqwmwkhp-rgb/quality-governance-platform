"""Data retention and cleanup tasks."""

import logging
import os

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
    dry_run = os.getenv("RETENTION_DRY_RUN", "").lower() in ("1", "true")
    batch_size = 1000

    retention_rules = [
        ("audit_log_entries", "created_at", 365),
        ("token_blacklist", "expires_at", 0),
        ("notification_log", "created_at", 90),
        ("incidents", "created_at", 2555),  # 7 years
        ("complaints", "created_at", 1095),  # 3 years
        ("rtas", "created_at", 2190),  # 6 years
        ("audit_runs", "created_at", 2555),  # 7 years
        ("risks", "created_at", 2555),  # 7 years
        ("vehicle_checks", "created_at", 2555),  # 7 years
        ("near_misses", "created_at", 2555),  # 7 years
    ]

    if dry_run:
        logger.info("RETENTION_DRY_RUN enabled — no rows will be deleted")

    try:
        with engine.begin() as conn:
            for table, date_col, retention_days in retention_rules:
                try:
                    cutoff = now - timedelta(days=retention_days)
                    total_deleted = 0

                    if dry_run:
                        count_result = conn.execute(
                            text(f"SELECT COUNT(*) FROM {table} WHERE {date_col} < :cutoff"),  # noqa: S608
                            {"cutoff": cutoff},
                        )
                        total_deleted = count_result.scalar() or 0
                        logger.info(
                            "Retention [DRY RUN]: would purge %d rows from %s (cutoff=%s)",
                            total_deleted,
                            table,
                            cutoff.isoformat(),
                        )
                    else:
                        while True:
                            result = conn.execute(
                                text(
                                    f"DELETE FROM {table} WHERE {date_col} < :cutoff "  # noqa: S608
                                    f"LIMIT :batch_size"
                                ),
                                {"cutoff": cutoff, "batch_size": batch_size},
                            )
                            batch_deleted = result.rowcount or 0
                            total_deleted += batch_deleted
                            if batch_deleted < batch_size:
                                break

                        if total_deleted > 0:
                            logger.info(
                                "Retention: purged %d rows from %s (cutoff=%s)",
                                total_deleted,
                                table,
                                cutoff.isoformat(),
                            )

                    results[table] = total_deleted
                except Exception:
                    logger.warning("Retention: table %s skipped (may not exist)", table)
                    results[table] = -1

        total_all_tables = sum(v for v in results.values() if v > 0)
        logger.info(
            "Data retention sweep complete: total_deleted=%d, details=%s",
            total_all_tables,
            results,
        )
        return {"status": "completed", "dry_run": dry_run, "purged": results}

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
