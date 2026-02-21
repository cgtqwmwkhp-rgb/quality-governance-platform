"""Automated data retention and cleanup service."""

from datetime import datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.token_blacklist import TokenBlacklist


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
        result = await db.execute(
            delete(TokenBlacklist).where(
                TokenBlacklist.expires_at < datetime.utcnow()
            )
        )
        await db.commit()
        return result.rowcount

    @staticmethod
    async def run_all_policies(db: AsyncSession) -> dict[str, int]:
        """Run all retention policies and return cleanup counts."""
        results = {}
        results["token_blacklist"] = await DataRetentionService.cleanup_expired_tokens(db)
        return results
