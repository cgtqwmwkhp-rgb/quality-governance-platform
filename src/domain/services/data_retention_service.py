"""Automated data retention and cleanup service."""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.token_blacklist import TokenBlacklist

logger = logging.getLogger(__name__)


class DataRetentionService:
    """Handles automated cleanup of expired and stale data."""

    RETENTION_POLICIES = {
        "token_blacklist": 7,
        "audit_trail_entries": 365,
        "telemetry_events": 90,
        "notification_history": 180,
    }

    @staticmethod
    async def cleanup_expired_tokens(db: AsyncSession) -> int:
        result = await db.execute(delete(TokenBlacklist).where(TokenBlacklist.expires_at < datetime.now(timezone.utc)))
        await db.commit()
        return result.rowcount

    @staticmethod
    async def cleanup_old_audit_entries(db: AsyncSession) -> int:
        """Delete AuditLogEntry records older than 365 days."""
        from src.domain.models.audit_log import AuditLogEntry

        cutoff = datetime.now(timezone.utc) - timedelta(
            days=DataRetentionService.RETENTION_POLICIES["audit_trail_entries"]
        )
        result = await db.execute(delete(AuditLogEntry).where(AuditLogEntry.timestamp < cutoff))
        await db.commit()
        logger.info("Cleaned up %d audit log entries older than 365 days", result.rowcount)
        return result.rowcount

    @staticmethod
    async def cleanup_old_telemetry(db: AsyncSession) -> int:
        """Intentional no-op: telemetry retention is deferred.

        Telemetry data is currently exported directly to Azure Monitor via
        OpenTelemetry and is not persisted in the application database.
        Retention cleanup will be implemented once a TelemetryEvent model is
        created for local telemetry storage.  This is an acceptable gap —
        the 90-day retention policy defined in RETENTION_POLICIES is reserved
        for future use and does not represent missing functionality.
        """
        logger.warning(
            "Telemetry cleanup skipped: no TelemetryEvent model exists yet. "
            "Retention is deferred until local telemetry storage is implemented."
        )
        return 0

    @staticmethod
    async def cleanup_old_notifications(db: AsyncSession) -> int:
        """Delete Notification records older than 180 days."""
        from src.domain.models.notification import Notification

        cutoff = datetime.now(timezone.utc) - timedelta(
            days=DataRetentionService.RETENTION_POLICIES["notification_history"]
        )
        result = await db.execute(delete(Notification).where(Notification.created_at < cutoff))
        await db.commit()
        logger.info("Cleaned up %d notifications older than 180 days", result.rowcount)
        return result.rowcount

    @staticmethod
    async def run_all_policies(db: AsyncSession) -> dict[str, int]:
        """Run all retention policies and return cleanup counts."""
        results = {}
        results["token_blacklist"] = await DataRetentionService.cleanup_expired_tokens(db)
        results["audit_trail_entries"] = await DataRetentionService.cleanup_old_audit_entries(db)
        results["telemetry_events"] = await DataRetentionService.cleanup_old_telemetry(db)
        results["notification_history"] = await DataRetentionService.cleanup_old_notifications(db)
        logger.info("Data retention cleanup complete: %s", results)
        return results
