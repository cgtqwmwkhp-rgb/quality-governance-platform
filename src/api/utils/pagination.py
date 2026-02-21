"""Shared pagination utilities for API routes."""

from typing import Any, Generic, TypeVar

from fastapi import Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

T = TypeVar("T")


class PaginationParams:
    """Standard pagination parameters as a FastAPI dependency."""

    def __init__(
        self,
        page: int = Query(1, ge=1, description="Page number"),
        page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    ):
        self.page = page
        self.page_size = page_size
        self.offset = (page - 1) * page_size


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
    params: PaginationParams,
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
