"""Partner API token lifecycle — create, list, revoke, authenticate (R6+)."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from collections.abc import Iterable
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.partner_api_token import (
    PARTNER_API_SCOPES,
    PARTNER_SCOPE_TO_PERMISSIONS,
    PartnerApiToken,
)

_TOKEN_PREFIX = "qgp_pt_"

#: Characters of the raw token stored as ``token_prefix`` for candidate lookup.
#: Matches the ``String(16)`` column, and must match what
#: :func:`generate_partner_token` persists or no inbound token would ever be
#: found by :meth:`PartnerAuthService.authenticate`.
_TOKEN_PREFIX_LENGTH = 16

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
    return raw_token, hash_partner_token(raw_token), raw_token[:_TOKEN_PREFIX_LENGTH]


def is_partner_bearer_token(raw_token: str) -> bool:
    """True when the bearer credential uses the partner API token prefix."""
    return bool(raw_token) and raw_token.startswith(_TOKEN_PREFIX)


def partner_effective_permissions(scopes: Iterable[str]) -> frozenset[str]:
    """Map partner scopes onto the platform RBAC tokens they satisfy.

    Normalised to lower case on the way out so the comparison in
    :meth:`PartnerPrincipal.has_permission` cannot be defeated by the casing of
    a token someone adds to the mapping later.
    """
    effective: set[str] = set()
    for scope in scopes:
        effective.update(PARTNER_SCOPE_TO_PERMISSIONS.get(scope, ()))
    return frozenset(token.strip().lower() for token in effective)


class PartnerPrincipal:
    """The caller a verified partner API token establishes.

    Deliberately *not* a ``User`` row and deliberately not a subclass of one.
    It carries only the attributes the handlers it can reach actually read, so
    an attribute nobody thought about raises ``AttributeError`` (``__slots__``)
    rather than being answered with a plausible-looking lie.

    ``id`` is ``None``: there is no user behind this caller, and both audit
    tables it reaches (``library_document_access_logs``,
    ``document_search_logs``) have a nullable ``user_id``. A synthetic id would
    have to point at a real ``users`` row to satisfy the FK, and inventing one
    is how a partner integration ends up indistinguishable from a person in the
    audit trail.

    ``is_superuser`` is ``False`` unconditionally, so every superuser exemption
    in the library — including the cross-tenant by-id read in
    ``_get_document_or_404`` — stays shut. Everything the token can do comes
    from :data:`PARTNER_SCOPE_TO_PERMISSIONS`.

    Every field is copied off the ORM row in ``__init__`` rather than read
    through it later: the row belongs to the request session, and a caller that
    commits mid-request would otherwise expire it and turn an attribute read
    into implicit IO from a context that cannot await.
    """

    __slots__ = (
        "id",
        "email",
        "full_name",
        "is_active",
        "is_superuser",
        "tenant_id",
        "roles",
        PARTNER_SCOPES_ATTR,
        PARTNER_TOKEN_ID_ATTR,
    )

    def __init__(self, token: PartnerApiToken):
        self.id = None
        # .invalid is reserved by RFC 6761 and can never be a deliverable
        # address, so a surface that filters by email matches nothing rather
        # than colliding with a real account.
        self.email = f"partner-token-{token.id}@qgp.invalid"
        self.full_name = f"Partner: {token.name}" if token.name else f"Partner token {token.id}"
        self.is_active = True
        self.is_superuser = False
        self.tenant_id = token.tenant_id
        self.roles: list = []
        setattr(self, PARTNER_SCOPES_ATTR, frozenset(token.scopes or ()))
        setattr(self, PARTNER_TOKEN_ID_ATTR, token.id)

    @property
    def partner_scopes(self) -> frozenset[str]:
        scopes: frozenset[str] = getattr(self, PARTNER_SCOPES_ATTR, frozenset())
        return scopes

    @property
    def partner_token_id(self) -> Optional[int]:
        token_id: Optional[int] = getattr(self, PARTNER_TOKEN_ID_ATTR, None)
        return token_id

    def has_permission(self, permission: str) -> bool:
        """Satisfy the RBAC tokens this token's scopes map to, and nothing else."""
        return permission.strip().lower() in partner_effective_permissions(self.partner_scopes)

    def has_partner_scope(self, scope: str) -> bool:
        return scope in self.partner_scopes


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
        """Return the active token this bearer credential proves, or ``None``.

        A pure read: nothing is written here, so authentication cannot fail on a
        write and cannot leave the request session dirty. Usage is recorded
        separately by :meth:`touch_last_used`.

        The prefix narrows the candidate set; the decision is always the
        constant-time hash comparison, so a token whose prefix collides with
        another tenant's is refused rather than confused with it. The tenant is
        then read off the matched row — a partner bearer names its own tenant,
        which is why there is no tenant filter to apply here and why
        ``PartnerPrincipal`` binds ``tenant_id`` from the row and never from the
        request.

        ``is_active`` is the revocation check: ``revoke_token`` clears it in the
        same flush that stamps ``revoked_at``, so a revoked token has no active
        row to match and fails closed.
        """
        if not is_partner_bearer_token(raw_token):
            return None
        prefix = raw_token[:_TOKEN_PREFIX_LENGTH]
        result = await self.db.execute(
            select(PartnerApiToken).where(
                PartnerApiToken.token_prefix == prefix,
                PartnerApiToken.is_active.is_(True),
            )
        )
        for token in result.scalars().all():
            if verify_partner_token(raw_token, token.secret_hash):
                return token
        return None

    async def touch_last_used(self, token_id: int) -> None:
        """Record that a token was used, best-effort.

        Issued as an UPDATE rather than an ORM attribute write so it cannot
        expire the row the caller has already read its scopes from, and left for
        the request's own transaction to commit rather than committed here: a
        commit inside authentication would end the transaction the tenant RLS
        GUC is local to, and a failed one would turn a telemetry write into a
        401. The consequence is honest and deliberate — on a request that never
        commits, ``last_used_at`` does not advance. It is credential-hygiene
        telemetry, not an authorisation input.
        """
        await self.db.execute(
            update(PartnerApiToken)
            .where(PartnerApiToken.id == token_id)
            .values(last_used_at=datetime.now(timezone.utc))
        )

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
