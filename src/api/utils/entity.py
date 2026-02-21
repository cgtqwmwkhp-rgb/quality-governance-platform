"""Shared entity lookup utilities for API routes."""

from typing import Type, TypeVar

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

T = TypeVar("T")


async def get_or_404(
    db: AsyncSession,
    model: Type[T],
    entity_id: int,
    detail: str | None = None,
) -> T:
    """Fetch an entity by primary key or raise 404."""
    result = await db.execute(select(model).where(model.id == entity_id))
    entity = result.scalar_one_or_none()
    if entity is None:
        model_name = model.__name__
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=detail or f"{model_name} with ID {entity_id} not found",
        )
    return entity
