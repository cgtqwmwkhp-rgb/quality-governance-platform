"""Partner bearer authentication dependencies (fail-closed inbound API).

JWT session callers keep using :func:`get_current_user` /
:func:`require_permission`. Partner ``qgp_pt_`` tokens are **rejected** by
those helpers so authenticated-only routes stay closed to partners.

Partner-callable routes must opt in via
:func:`require_auth_or_partner_scope` or
:func:`require_permission_or_partner_scope`.
"""

from __future__ import annotations

from typing import Annotated, Union

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import (
    _bind_tenant_rls_guc,
    _credentials_exception,
    _enforce_access_token_not_revoked,
    _resolve_user_tenant_context,
    get_current_user,
    security,
)
from src.domain.authz.census import AUTHENTICATION_KIND_ATTR, AuthenticationKind
from src.domain.authz.extraction import REQUIRED_PERMISSION_ATTR
from src.domain.models.user import User
from src.domain.services.partner_auth_service import (
    PARTNER_SCOPES_ATTR,
    PartnerAuthService,
    PartnerPrincipal,
    is_partner_bearer_token,
)
from src.infrastructure.database import get_db

PartnerCaller = Union[User, PartnerPrincipal]


def _partner_scope_forbidden(scope: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=f"Partner scope '{scope}' required",
    )


async def _authenticate_partner_principal(
    raw_token: str,
    db: AsyncSession,
) -> PartnerPrincipal:
    service = PartnerAuthService(db)
    token = await service.authenticate(raw_token)
    if token is None:
        raise _credentials_exception()
    principal = PartnerPrincipal(token)
    await _bind_tenant_rls_guc(db, principal)  # type: ignore[arg-type]
    return principal


async def _authenticate_jwt_user(
    raw_token: str,
    db: AsyncSession,
) -> User:
    from src.core.security import decode_token
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    credentials_exception = _credentials_exception()
    payload = decode_token(raw_token)
    if payload is None:
        raise credentials_exception
    if payload.get("type") != "access":
        raise credentials_exception
    await _enforce_access_token_not_revoked(payload, db)
    user_id_raw = payload.get("sub")
    if user_id_raw is None:
        raise credentials_exception
    result = await db.execute(
        select(User).where(User.id == int(user_id_raw)).options(selectinload(User.roles))
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise credentials_exception
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled",
        )
    await _resolve_user_tenant_context(db, user)
    await _bind_tenant_rls_guc(db, user)
    return user


def require_auth_or_partner_scope(partner_scope: str):
    """JWT session (unchanged) **or** partner bearer with ``partner_scope``.

    Does not attach a RBAC permission token — use on authenticated-only routes
    so census posture stays AUTHENTICATED_ONLY.
    """

    async def checker(
        credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
        db: Annotated[AsyncSession, Depends(get_db)],
    ) -> PartnerCaller:
        raw = credentials.credentials
        if is_partner_bearer_token(raw):
            principal = await _authenticate_partner_principal(raw, db)
            if not principal.has_partner_scope(partner_scope):
                raise _partner_scope_forbidden(partner_scope)
            return principal
        return await _authenticate_jwt_user(raw, db)

    setattr(checker, AUTHENTICATION_KIND_ATTR, AuthenticationKind.REQUIRED.value)
    return checker


def require_permission_or_partner_scope(permission: str, partner_scope: str):
    """JWT caller needs ``permission``; partner bearer needs ``partner_scope``.

    Stamps :data:`REQUIRED_PERMISSION_ATTR` so the permission catalogue still
    walks the JWT side of the gate.
    """

    async def checker(
        credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
        db: Annotated[AsyncSession, Depends(get_db)],
    ) -> PartnerCaller:
        raw = credentials.credentials
        if is_partner_bearer_token(raw):
            principal = await _authenticate_partner_principal(raw, db)
            if not principal.has_partner_scope(partner_scope):
                raise _partner_scope_forbidden(partner_scope)
            return principal
        user = await _authenticate_jwt_user(raw, db)
        if not user.has_permission(permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission '{permission}' required",
            )
        return user

    setattr(checker, REQUIRED_PERMISSION_ATTR, permission)
    setattr(checker, AUTHENTICATION_KIND_ATTR, AuthenticationKind.REQUIRED.value)
    return checker


def is_partner_caller(user: object) -> bool:
    """True when ``user`` was established by a partner API token."""
    return getattr(user, PARTNER_SCOPES_ATTR, None) is not None


# Re-export get_current_user for tests that patch the JWT path alongside partner deps.
__all__ = [
    "PartnerCaller",
    "is_partner_caller",
    "require_auth_or_partner_scope",
    "require_permission_or_partner_scope",
    "get_current_user",
]
