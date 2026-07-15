"""Partner API token lifecycle — create, list, revoke (R6)."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.partner_api_token import PARTNER_API_SCOPES, PartnerApiToken

_TOKEN_PREFIX = "qgp_pt_"


def hash_partner_token(raw_token: str) -> str:
    """Return SHA-256 hex digest of a partner API token."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def verify_partner_token(raw_token: str, stored_hash: str) -> bool:
    """Constant-time compare of raw token against stored hash."""
    return hmac.compare_digest(hash_partner_token(raw_token), stored_hash)


def generate_partner_token() -> tuple[str, str, str]:
    """Return (raw_token, secret_hash, token_prefix) for persistence."""
    raw_token = f"{_TOKEN_PREFIX}{secrets.token_urlsafe(32)}"
    return raw_token, hash_partner_token(raw_token), raw_token[:16]


class PartnerAuthService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_token(
        self,
        *,
        tenant_id: int,
        scopes: list[str],
        name: Optional[str] = None,
    ) -> tuple[PartnerApiToken, str]:
        invalid = [scope for scope in scopes if scope not in PARTNER_API_SCOPES]
        if invalid:
            allowed = ", ".join(PARTNER_API_SCOPES)
            raise ValueError(f"Unsupported scope(s): {', '.join(invalid)}. Allowed: {allowed}")
        if not scopes:
            raise ValueError("At least one scope is required")

        raw_token, secret_hash, token_prefix = generate_partner_token()
        token = PartnerApiToken(
            tenant_id=tenant_id,
            name=name,
            token_prefix=token_prefix,
            secret_hash=secret_hash,
            scopes=scopes,
            is_active=True,
        )
        self.db.add(token)
        await self.db.flush()
        return token, raw_token

    async def list_tokens(self, tenant_id: int, *, include_revoked: bool = False) -> list[PartnerApiToken]:
        query = select(PartnerApiToken).where(PartnerApiToken.tenant_id == tenant_id)
        if not include_revoked:
            query = query.where(PartnerApiToken.is_active.is_(True))
        result = await self.db.execute(query.order_by(PartnerApiToken.id.desc()))
        return list(result.scalars().all())

    async def get_token(self, tenant_id: int, token_id: int) -> Optional[PartnerApiToken]:
        result = await self.db.execute(
            select(PartnerApiToken).where(
                PartnerApiToken.id == token_id,
                PartnerApiToken.tenant_id == tenant_id,
            )
        )
        return result.scalar_one_or_none()

    async def revoke_token(self, token: PartnerApiToken) -> PartnerApiToken:
        if not token.is_active:
            return token
        now = datetime.now(timezone.utc)
        token.is_active = False
        token.revoked_at = now
        await self.db.flush()
        return token
