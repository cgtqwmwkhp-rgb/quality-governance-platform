"""API dependencies for dependency injection."""

import logging
from typing import Annotated, Optional, Union, cast

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.api.dependencies.partner import (
    is_partner_bearer_token,
    required_partner_scope,
    resolve_partner_principal,
)
from src.api.schemas.error_codes import ErrorCode
from src.api.utils.errors import api_error
from src.core.config import settings
from src.core.security import decode_token, ensure_access_token_not_revoked
from src.domain.authz.census import AUTHENTICATION_KIND_ATTR, AuthenticationKind
from src.domain.authz.extraction import REQUIRED_PERMISSION_ATTR
from src.domain.exceptions import TokenRevokedError
from src.domain.models.tenant import Tenant, TenantUser
from src.domain.models.user import User
from src.domain.services.partner_auth_service import PartnerPrincipal
from src.infrastructure.database import get_db
from src.infrastructure.middleware.tenant_context import apply_tenant_guc, set_request_tenant_id

logger = logging.getLogger(__name__)

# Security scheme - auto_error=False allows optional auth
security = HTTPBearer()
optional_security = HTTPBearer(auto_error=False)


def _credentials_exception() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


def _token_revoked_exception(message: str = "Access token has been revoked") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=api_error(ErrorCode.TOKEN_REVOKED.value, message),
        headers={"WWW-Authenticate": "Bearer"},
    )


async def _enforce_access_token_not_revoked(payload: dict, db: AsyncSession) -> None:
    """Raise 401 TOKEN_REVOKED (or credentials error) when the access token is unusable."""
    try:
        await ensure_access_token_not_revoked(payload, db)
    except TokenRevokedError as exc:
        raise _token_revoked_exception(str(exc)) from exc
    except ValueError as exc:
        raise _credentials_exception() from exc


async def _bind_tenant_rls_guc(db: AsyncSession, user: Union[User, PartnerPrincipal]) -> None:
    """Bind tenant GUC on the request session after tenant resolution.

    Sets ContextVar + ``set_config`` for any caller with a tenant_id (including
    app superusers and partner principals) so FORCE RLS policies match.
    Cross-tenant admin requires a DB role with BYPASSRLS.
    """
    if user.tenant_id is None:
        return
    set_request_tenant_id(user.tenant_id)
    await apply_tenant_guc(db, user.tenant_id)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
    db: Annotated[AsyncSession, Depends(get_db)],
    partner_scope: Annotated[Optional[str], Depends(required_partner_scope)] = None,
) -> User:
    """Get the current authenticated caller from the bearer credential.

    Two kinds of credential reach this. A JWT access token resolves to the
    ``User`` row it names, unchanged. A ``qgp_pt_`` partner API token resolves to
    a :class:`PartnerPrincipal`, but only on a route that opted in by declaring
    the scope it requires — see :mod:`src.api.dependencies.partner`. Everywhere
    else a partner token is refused, which is also what it got before this path
    existed, because ``decode_token`` cannot read one.

    ``partner_scope`` defaults to ``None`` so that calling this function directly
    (as the dependency unit tests do) refuses partner tokens rather than
    silently accepting them with no route to read a scope from.

    The return type is ``User`` for the benefit of the several hundred routes
    annotated ``CurrentUser``. A ``PartnerPrincipal`` is not one and is not a
    subclass of one — deliberately, since ``User`` is a mapped class — so it is
    cast at the boundary. What makes that safe is not the cast: it is that the
    principal answers ``has_permission`` from its scopes and reports
    ``is_superuser`` as ``False``, so the authorisation and tenancy checks
    downstream reach their own conclusions about it rather than trusting it.
    """
    credentials_exception = _credentials_exception()

    token = credentials.credentials

    if is_partner_bearer_token(token):
        principal = await resolve_partner_principal(token, db, required_scope=partner_scope)
        await _bind_tenant_rls_guc(db, principal)
        return cast(User, principal)

    payload = decode_token(token)

    if payload is None:
        raise credentials_exception

    if payload.get("type") != "access":
        raise credentials_exception

    await _enforce_access_token_not_revoked(payload, db)

    user_id_raw = payload.get("sub")
    if user_id_raw is None:
        raise credentials_exception
    user_id: str = str(user_id_raw)

    result = await db.execute(select(User).where(User.id == int(user_id)).options(selectinload(User.roles)))
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


async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Get the current active user."""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user",
        )
    return current_user


async def get_current_superuser(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Get the current superuser."""
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions",
        )
    return current_user


def require_permission(permission: str):
    """Dependency factory for permission checking."""

    async def permission_checker(
        current_user: Annotated[User, Depends(get_current_user)],
    ) -> User:
        if not current_user.has_permission(permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission '{permission}' required",
            )
        return current_user

    # Record the token so the permission-catalogue test can walk the app's routes
    # and read it back. Deliberately not left to closure introspection: a closure
    # variable read by name goes quietly to None the day someone renames the
    # parameter, and the catalogue test would then pass while checking nothing.
    setattr(permission_checker, REQUIRED_PERMISSION_ATTR, permission)
    return permission_checker


async def get_optional_current_user(
    credentials: Annotated[Optional[HTTPAuthorizationCredentials], Depends(optional_security)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Optional[User]:
    """Get the current user if valid token provided, otherwise return None.

    This allows endpoints to be accessed without authentication while still
    supporting authenticated access for additional permissions.
    Used by portal users who authenticate via Azure AD (tokens not validated here)
    but can still filter by their email address.

    A presented but revoked access token is rejected with 401 TOKEN_REVOKED
    (same contract as :func:`get_current_user`).
    """
    if credentials is None:
        return None

    token = credentials.credentials

    # Partner bearers establish no user here. Stated rather than left to
    # ``decode_token`` failing on the string: these routes serve the anonymous
    # caller anyway, so the difference is only whether the next reader can tell
    # that partner tokens were considered and refused.
    if is_partner_bearer_token(token):
        return None

    payload = decode_token(token)

    if payload is None:
        # Invalid token - return None instead of raising error
        return None

    if payload.get("type") != "access":
        return None

    await _enforce_access_token_not_revoked(payload, db)

    user_id_raw = payload.get("sub")
    if user_id_raw is None:
        return None
    user_id: str = str(user_id_raw)

    result = await db.execute(select(User).where(User.id == int(user_id)).options(selectinload(User.roles)))
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        return None

    await _resolve_user_tenant_context(db, user)
    await _bind_tenant_rls_guc(db, user)
    return user


async def _resolve_user_tenant_context(db: AsyncSession, user: User) -> None:
    """Backfill in-request tenant context from active tenant membership.

    In production, users without an explicit tenant membership fail closed —
    no silent first-tenant assignment and no auto-created
    ``Default Organisation``.
    """
    if user.tenant_id is not None:
        return

    membership_result = await db.execute(
        select(TenantUser)
        .where(
            TenantUser.user_id == user.id,
            TenantUser.is_active == True,
        )
        .order_by(TenantUser.is_primary.desc(), TenantUser.id.asc())
    )
    membership = membership_result.scalars().first()
    if membership is not None:
        user.tenant_id = membership.tenant_id
        await db.flush()
        logger.info(
            "Persisted tenant_id=%s on user %s from TenantUser membership",
            membership.tenant_id,
            user.id,
        )
        return

    if settings.is_production:
        logger.warning(
            "User %s has no tenant membership in production — refusing auto-bootstrap",
            user.id,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=api_error(
                ErrorCode.TENANT_ACCESS_DENIED.value,
                "User has no tenant membership",
            ),
        )

    tenant_result = await db.execute(select(Tenant).where(Tenant.is_active == True).order_by(Tenant.id.asc()).limit(1))
    tenant = tenant_result.scalar_one_or_none()
    if tenant is None:
        tenant = Tenant(
            name="Default Organisation",
            slug="default",
            admin_email="admin@qgp.local",
            is_active=True,
            subscription_tier="enterprise",
        )
        db.add(tenant)
        await db.flush()
        logger.warning("Bootstrapped default tenant id=%s for user %s (no tenants existed)", tenant.id, user.id)

    user.tenant_id = tenant.id
    db.add(
        TenantUser(
            tenant_id=tenant.id,
            user_id=user.id,
            is_active=True,
            is_primary=True,
            role="user",
        )
    )
    await db.flush()
    logger.info(
        "Auto-assigned tenant_id=%s to existing user %s (no prior membership)",
        tenant.id,
        user.id,
    )


# Tag each authentication dependency with what it establishes about the caller,
# so src.domain.authz.census can classify a route without matching on function
# names. A name match would silently reclassify every route beneath a renamed
# dependency; an untagged one classifies as UNAUTHENTICATED instead, which is the
# posture that has to be declared route by route and so cannot pass quietly.
setattr(get_current_user, AUTHENTICATION_KIND_ATTR, AuthenticationKind.REQUIRED.value)
setattr(get_current_active_user, AUTHENTICATION_KIND_ATTR, AuthenticationKind.REQUIRED.value)
setattr(get_current_superuser, AUTHENTICATION_KIND_ATTR, AuthenticationKind.SUPERUSER.value)
setattr(get_optional_current_user, AUTHENTICATION_KIND_ATTR, AuthenticationKind.OPTIONAL.value)


# Type aliases for cleaner route signatures
CurrentUser = Annotated[User, Depends(get_current_user)]
CurrentActiveUser = Annotated[User, Depends(get_current_active_user)]
CurrentSuperuser = Annotated[User, Depends(get_current_superuser)]
OptionalCurrentUser = Annotated[Optional[User], Depends(get_optional_current_user)]
DbSession = Annotated[AsyncSession, Depends(get_db)]
