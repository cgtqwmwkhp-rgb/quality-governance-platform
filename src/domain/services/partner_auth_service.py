"""Partner API token lifecycle — create, list, revoke, authenticate (R6+)."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.partner_api_token import (
    PARTNER_API_SCOPES,
    PARTNER_SCOPE_TO_PERMISSIONS,
    PartnerApiToken,
)

_TOKEN_PREFIX = "qgp_pt_"
PARTNER_SCOPES_ATTR = "_partner_scopes"
PARTNER_TOKEN_ID_ATTR = "_partner_token_id"


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


def is_partner_bearer_token(raw_token: str) -> bool:
    """True when the bearer credential uses the partner API token prefix."""
    return bool(raw_token) and raw_token.startswith(_TOKEN_PREFIX)


def partner_effective_permissions(scopes: list[str] | tuple[str, ...] | set[str]) -> frozenset[str]:
    """Map partner scopes onto platform RBAC permission tokens."""
    effective: set[str] = set()
    for scope in scopes:
        effective.update(PARTNER_SCOPE_TO_PERMISSIONS.get(scope, ()))
    return frozenset(effective)


class PartnerPrincipal:
    """Duck-typed caller established by a verified partner API token.

    Not an ORM ``User`` row — ``id`` is always ``None`` so access logs and
    search logs omit a user FK. Fail-closed for RBAC except permissions
    granted by :data:`PARTNER_SCOPE_TO_PERMISSIONS`.
    """

    __slots__ = (
        "id",
        "email",
        "first_name",
        "last_name",
        "hashed_password",
        "is_active",
        "is_superuser",
        "tenant_id",
        "roles",
        PARTNER_SCOPES_ATTR,
        PARTNER_TOKEN_ID_ATTR,
    )

    def __init__(self, token: PartnerApiToken):
        scopes = list(token.scopes or [])
        self.id = None
        self.email = f"partner-token-{token.id}@qgp.invalid"
        self.first_name = "Partner"
        self.last_name = (token.name or f"Token {token.id}")[:100]
        self.hashed_password = "!"
        self.is_active = True
        self.is_superuser = False
        self.tenant_id = token.tenant_id
        self.roles = []
        setattr(self, PARTNER_SCOPES_ATTR, frozenset(scopes))
        setattr(self, PARTNER_TOKEN_ID_ATTR, token.id)

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    def has_permission(self, permission: str) -> bool:
        scopes = getattr(self, PARTNER_SCOPES_ATTR, frozenset())
        return permission.strip().lower() in {
            p.lower() for p in partner_effective_permissions(scopes)
        }

    def has_partner_scope(self, scope: str) -> bool:
        scopes = getattr(self, PARTNER_SCOPES_ATTR, frozenset())
        return scope in scopes


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

    async def authenticate(self, raw_token: str) -> Optional[PartnerApiToken]:
        """Verify an active partner bearer token; update ``last_used_at`` on hit."""
        if not is_partner_bearer_token(raw_token):
            return None
        prefix = raw_token[:16]
        result = await self.db.execute(
            select(PartnerApiToken).where(
                PartnerApiToken.token_prefix == prefix,
                PartnerApiToken.is_active.is_(True),
            )
        )
        for token in result.scalars().all():
            if verify_partner_token(raw_token, token.secret_hash):
                token.last_used_at = datetime.now(timezone.utc)
                await self.db.flush()
                return token
        return None

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
