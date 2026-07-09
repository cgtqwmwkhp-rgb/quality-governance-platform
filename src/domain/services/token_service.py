"""Token revocation and management service."""

from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.token_blacklist import TokenBlacklist


class TokenService:
    @staticmethod
    async def revoke_token(
        db: AsyncSession,
        jti: str,
        user_id: int | None,
        expires_at: datetime,
        reason: str = "logout",
    ) -> None:
        # TIMESTAMP WITHOUT TIME ZONE columns require naive UTC.
        if expires_at.tzinfo is not None:
            expires_at = expires_at.astimezone(timezone.utc).replace(tzinfo=None)
        entry = TokenBlacklist(
            jti=jti,
            user_id=user_id,
            expires_at=expires_at,
            reason=reason,
        )
        db.add(entry)
        await db.commit()

    @staticmethod
    async def is_revoked(db: AsyncSession, jti: str) -> bool:
        result = await db.execute(select(TokenBlacklist.id).where(TokenBlacklist.jti == jti))
        return result.scalar_one_or_none() is not None

    @staticmethod
    async def revoke_all_user_tokens(
        db: AsyncSession,
        user_id: int,
        reason: str = "admin_revoke",
    ) -> int:
        """Update reason on existing blacklist rows for a user.

        NOTE: This does **not** revoke active (not-yet-blacklisted) tokens. A
        proper "revoke all sessions" needs a ``token_version`` (or similar)
        claim checked at validation time. Prefer presenting tokens to
        ``revoke_token`` / logout until that exists.
        """
        from sqlalchemy import update

        result = await db.execute(update(TokenBlacklist).where(TokenBlacklist.user_id == user_id).values(reason=reason))
        await db.commit()
        return result.rowcount

    @staticmethod
    async def cleanup_expired(db: AsyncSession) -> int:
        """Remove expired blacklist entries."""
        result = await db.execute(
            delete(TokenBlacklist).where(TokenBlacklist.expires_at < datetime.now(timezone.utc).replace(tzinfo=None))
        )
        await db.commit()
        return result.rowcount
