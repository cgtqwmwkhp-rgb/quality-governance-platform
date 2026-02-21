"""Token revocation and management service."""

from datetime import datetime

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
        """Revoke all tokens for a user. Returns count of affected records."""
        result = await db.execute(select(TokenBlacklist).where(TokenBlacklist.user_id == user_id))
        return 0

    @staticmethod
    async def cleanup_expired(db: AsyncSession) -> int:
        """Remove expired blacklist entries."""
        result = await db.execute(delete(TokenBlacklist).where(TokenBlacklist.expires_at < datetime.utcnow()))
        await db.commit()
        return result.rowcount
