"""Data retention and cleanup tasks."""

import logging
from dataclasses import dataclass

from src.core.retention_config import DEFAULT_RETENTION_POLICIES
from src.infrastructure.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RetentionRule:
    """One purge target, and where its horizon comes from.

    The horizon is deliberately *not* a number written here. It was, and the copy drifted
    to a seventh of the declared statutory period without anything noticing, because the
    two lists had no relationship beyond a human keeping them in step.

    ``policy_key`` names an entry in ``DEFAULT_RETENTION_POLICIES``, which then owns both
    the horizon and whether a hard ``DELETE`` is permissible at all. ``operational_days``
    is the alternative for tables no retention policy governs -- expired tokens and push
    logs are plumbing, not records. Exactly one must be given: a rule that supplies
    neither has no defensible horizon, and one that supplies both re-creates the very
    divergence this type exists to prevent.
    """

    table: str
    date_column: str
    policy_key: str | None = None
    operational_days: int | None = None

    def __post_init__(self) -> None:
        if (self.policy_key is None) == (self.operational_days is None):
            raise ValueError(f"{self.table}: give exactly one of policy_key or operational_days")
        if self.policy_key is not None and self.policy_key not in DEFAULT_RETENTION_POLICIES:
            raise ValueError(f"{self.table}: unknown retention policy {self.policy_key!r}")

    @property
    def retention_days(self) -> int:
        if self.policy_key is not None:
            return DEFAULT_RETENTION_POLICIES[self.policy_key].retention_days
        assert self.operational_days is not None  # nosec B101 - guaranteed by __post_init__
        return self.operational_days

    @property
    def may_hard_delete(self) -> bool:
        """Whether this sweep is allowed to issue a ``DELETE`` for the target.

        A policy carrying ``soft_delete_first`` is a statement that rows are withdrawn
        before they are destroyed. This sweep has no soft-delete phase, so for those
        tables it is not the right instrument and must not act -- irreversibly, at 02:00,
        with nobody watching. Being held here is the intended outcome, not a failure.
        """
        if self.policy_key is None:
            return True
        return not DEFAULT_RETENTION_POLICIES[self.policy_key].soft_delete_first


#: Purge targets per docs/privacy/data-retention-policy.md.
#:
#: Module level so the suite can check every target against the declared schema without
#: running a sweep. ``notification_log`` (singular) sat here for as long as it did because
#: nothing short of a live PostgreSQL run could see that the name was wrong.
#:
#: Two former entries are deliberately absent rather than corrected:
#:   * ``investigations`` -- no such table exists. The models declare ``investigation_runs``
#:     among several others, and which of them a retention horizon covers is a records
#:     decision, not a rename.
#:   * ``road_traffic_collisions`` -- a statutory record with no entry in
#:     ``DEFAULT_RETENTION_POLICIES``, so there is no declared horizon to honour. Inventing
#:     one here is how the original 365 got in.
RETENTION_RULES: tuple[RetentionRule, ...] = (
    RetentionRule("token_blacklist", "expires_at", operational_days=0),
    RetentionRule("notification_logs", "created_at", operational_days=90),
    RetentionRule("audit_log_entries", "timestamp", policy_key="audit_logs"),
    RetentionRule("incidents", "created_at", policy_key="incidents"),
    RetentionRule("complaints", "created_at", policy_key="complaints"),
    RetentionRule("near_misses", "created_at", policy_key="near_misses"),
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
    held: dict[str, str] = {}
    engine = engine_ref
    now = datetime.utcnow()

    try:
        with engine.begin() as conn:
            for rule in RETENTION_RULES:
                table, date_col = rule.table, rule.date_column
                if not rule.may_hard_delete:
                    # Checked before any SQL is built, so a policy-governed table cannot be
                    # destroyed by a later refactor of the statement below.
                    held[table] = f"{rule.policy_key} requires soft delete first"
                    logger.info(
                        "Retention: %s held, policy %s requires soft delete first (%d day horizon)",
                        table,
                        rule.policy_key,
                        rule.retention_days,
                    )
                    continue

                cutoff = now - timedelta(days=rule.retention_days)
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

        logger.info("Data retention sweep complete: purged=%s held=%s", results, held)
        return {"status": "completed", "purged": results, "held": held}

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
