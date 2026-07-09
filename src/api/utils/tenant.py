"""Tenant filtering utilities for multi-tenant queries."""

from typing import Any, Optional

from fastapi import HTTPException, status
from sqlalchemy import false

from src.api.schemas.error_codes import ErrorCode
from src.api.utils.errors import api_error


def require_tenant_id(tenant_id: Optional[int], *, message: str = "User has no tenant membership") -> int:
    """Require an explicit tenant id; fail closed with 403 when missing."""
    if tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=api_error(
                ErrorCode.TENANT_ACCESS_DENIED.value,
                message,
            ),
        )
    return tenant_id


def apply_tenant_filter(query: Any, model: Any, tenant_id: Optional[int]) -> Any:
    """Apply fail-closed tenant filter: exact tenant match only (NULL rows excluded).

    When ``tenant_id`` is missing, the query matches nothing so callers cannot
    accidentally return cross-tenant or unscoped rows.
    """
    if tenant_id is None:
        return query.where(false())
    return query.where(model.tenant_id == tenant_id)
