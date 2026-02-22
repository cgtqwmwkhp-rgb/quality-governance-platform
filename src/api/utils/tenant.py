"""Tenant scoping utilities for query filtering."""

from sqlalchemy import Select


def tenant_scope(stmt: Select, model, tenant_id: int) -> Select:
    """Apply tenant isolation filter to a SQLAlchemy select statement.
    
    Args:
        stmt: SQLAlchemy Select statement
        model: SQLAlchemy model class with tenant_id column
        tenant_id: The tenant ID to filter by
    
    Returns:
        Filtered Select statement
    """
    return stmt.where(model.tenant_id == tenant_id)
