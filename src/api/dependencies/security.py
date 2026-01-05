"""Security-related dependencies for RBAC."""

from functools import wraps

from fastapi import Depends, HTTPException, status

from src.api.dependencies import CurrentUser
from src.domain.models.user import User


def require_permission(permission: str):
    """Dependency that checks if the current user has the required permission."""

    async def dependency(current_user: User = Depends(CurrentUser)) -> User:
        # In a real application, you would check the user's roles and permissions
        # against the required permission. For this scaffold, we'll use a simple check.
        if not current_user.is_superuser:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="The user does not have the required permission",
            )
        return current_user

    return dependency
