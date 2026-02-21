"""API dependencies for dependency injection."""

from typing import Annotated, Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.security import decode_token, is_token_revoked
from src.domain.models.user import User
from src.infrastructure.database import get_db
from src.infrastructure.monitoring.azure_monitor import track_metric

# Security scheme - auto_error=False allows optional auth
security = HTTPBearer()
optional_security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """Get the current authenticated user from JWT token."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    token = credentials.credentials
    payload = decode_token(token)

    if payload is None:
        track_metric("auth.failure", 1)
        raise credentials_exception

    jti = payload.get("jti")
    if jti and await is_token_revoked(jti, db):
        track_metric("auth.failure", 1)
        raise credentials_exception

    user_id_raw = payload.get("sub")
    if user_id_raw is None:
        track_metric("auth.failure", 1)
        raise credentials_exception
    user_id: str = str(user_id_raw)

    # Get user from database with roles eagerly loaded
    from sqlalchemy.orm import selectinload

    result = await db.execute(
        select(User).where(User.id == int(user_id)).options(selectinload(User.roles))
    )
    user = result.scalar_one_or_none()

    if user is None:
        track_metric("auth.failure", 1)
        raise credentials_exception

    if not user.is_active:
        track_metric("auth.failure", 1)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled",
        )

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

    return permission_checker


async def get_optional_current_user(
    credentials: Annotated[
        Optional[HTTPAuthorizationCredentials], Depends(optional_security)
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Optional[User]:
    """Get the current user if valid token provided, otherwise return None.

    This allows endpoints to be accessed without authentication while still
    supporting authenticated access for additional permissions.
    Used by portal users who authenticate via Azure AD (tokens not validated here)
    but can still filter by their email address.
    """
    if credentials is None:
        return None

    token = credentials.credentials
    payload = decode_token(token)

    if payload is None:
        return None

    jti = payload.get("jti")
    if jti and await is_token_revoked(jti, db):
        return None

    user_id_raw = payload.get("sub")
    if user_id_raw is None:
        return None
    user_id: str = str(user_id_raw)

    # Get user from database with roles eagerly loaded
    from sqlalchemy.orm import selectinload

    result = await db.execute(
        select(User).where(User.id == int(user_id)).options(selectinload(User.roles))
    )
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        return None

    return user


# Type aliases for cleaner route signatures
CurrentUser = Annotated[User, Depends(get_current_user)]
CurrentActiveUser = Annotated[User, Depends(get_current_active_user)]
CurrentSuperuser = Annotated[User, Depends(get_current_superuser)]
OptionalCurrentUser = Annotated[Optional[User], Depends(get_optional_current_user)]
DbSession = Annotated[AsyncSession, Depends(get_db)]

# Tenant isolation – imported after CurrentUser is defined to avoid circular imports
from src.api.dependencies.tenant import verify_tenant_access  # noqa: E402
