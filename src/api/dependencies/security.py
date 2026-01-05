"""
Security dependencies for RBAC enforcement.
"""

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.domain.models.user import User


async def require_permission(
    permission_name: str,
    current_user: User,
    session: AsyncSession,
) -> None:
    """
    Check if the current user has the required permission.

    Raises HTTPException 403 if the user does not have the permission.
    """
    # Superusers have all permissions
    if current_user.is_superuser:
        return

    # Load user with roles eagerly
    stmt = select(User).where(User.id == current_user.id).options(selectinload(User.roles))
    result = await session.execute(stmt)
    user_with_roles = result.scalar_one_or_none()

    if not user_with_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User not found",
        )

    # Check if any of the user's roles have the required permission
    for role in user_with_roles.roles:
        if role.permissions and permission_name in role.permissions:
            return  # Permission granted

    # Permission denied
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=f"Permission denied: {permission_name} required",
    )
