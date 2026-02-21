"""Tenant isolation verification dependency."""

from fastapi import HTTPException, status

from src.api.dependencies import CurrentUser


async def verify_tenant_access(
    tenant_id: int,
    current_user: CurrentUser,
) -> int:
    """Verify the current user has access to the specified tenant.

    Superusers can access any tenant. Regular users can only access
    their own tenant.

    Returns the verified tenant_id.
    """
    if hasattr(current_user, "is_superuser") and current_user.is_superuser:
        return tenant_id

    user_tenant_id = getattr(current_user, "tenant_id", None)
    if user_tenant_id is None or user_tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: you do not belong to this tenant",
        )
    return tenant_id
