"""Shared pagination primitives — no FastAPI dependency.

Domain services can import from here safely without creating
an api→domain circular dependency.
"""

from typing import Any

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select


class PaginationInput:
    """Framework-agnostic pagination input (no FastAPI Query)."""

    def __init__(self, page: int = 1, page_size: int = 20):
        self.page = max(1, page)
        self.page_size = max(1, min(page_size, 500))
        self.offset = (self.page - 1) * self.page_size


class PaginatedResponse(BaseModel):
    """Standard paginated response envelope."""

    items: list[Any]
    total: int
    page: int
    page_size: int
    pages: int


async def paginate(
    db: AsyncSession,
    query: Select,
    params: PaginationInput,
) -> PaginatedResponse:
    """Execute a query with pagination and return a PaginatedResponse."""
    count_query = select(func.count()).select_from(query.subquery())
    count_result = await db.execute(count_query)
    total = count_result.scalar_one()

    result = await db.execute(query.offset(params.offset).limit(params.page_size))
    items = result.scalars().all()

    pages = (total + params.page_size - 1) // params.page_size if total > 0 else 0

    return PaginatedResponse(
        items=list(items),
        total=total,
        page=params.page,
        page_size=params.page_size,
        pages=pages,
    )
