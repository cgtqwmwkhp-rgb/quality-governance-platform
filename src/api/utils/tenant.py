"""Tenant filtering utilities for multi-tenant queries."""

from typing import Any, Optional

from sqlalchemy import or_


def apply_tenant_filter(query: Any, model: Any, tenant_id: Optional[int]) -> Any:
    """Apply tenant filter to query: tenant_id matches or tenant_id is NULL."""
    if tenant_id is not None:
        return query.where(
            or_(
                model.tenant_id == tenant_id,
                model.tenant_id.is_(None),
            )
        )
    return query
