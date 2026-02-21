"""Shared entity lookup utilities for API routes."""

from typing import Any, Type, TypeVar

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

T = TypeVar("T")


async def get_or_404(
    db: AsyncSession,
    model: Type[T],
    entity_id: int,
    detail: str | None = None,
    tenant_id: int | None = None,
) -> T:
    """Fetch an entity by primary key or raise 404.

    When *tenant_id* is provided the query also filters by
    ``model.tenant_id`` so rows belonging to other tenants are
    treated as not-found.
    """
    model_any: Any = model
    stmt = select(model).where(model_any.id == entity_id)
    if tenant_id is not None:
        stmt = stmt.where(model_any.tenant_id == tenant_id)
    result = await db.execute(stmt)
    entity = result.scalar_one_or_none()
    if entity is None:
        model_name = model.__name__
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=detail or f"{model_name} with ID {entity_id} not found",
        )
    return entity
