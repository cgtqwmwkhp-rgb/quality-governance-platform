"""Shared pagination schemas and utilities.

Defines the canonical response envelope for list endpoints:
- Paginated collections: {"data": [...], "meta": {"total", "page", "per_page", "total_pages"}}
- Non-paginated collections: {"data": [...]}
"""

from typing import Generic, TypeVar

from fastapi import Query
from pydantic import BaseModel

T = TypeVar("T")


class PaginationParams:
    """Dependency for extracting pagination parameters."""
    def __init__(
        self,
        page: int = Query(1, ge=1, description="Page number"),
        per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    ):
        self.page = page
        self.per_page = per_page
        self.offset = (page - 1) * per_page


class PaginationMeta(BaseModel):
    """Pagination metadata for list responses."""
    total: int
    page: int
    per_page: int
    total_pages: int


class PaginatedResponse(BaseModel, Generic[T]):
    """Standardized paginated response."""
    data: list
    meta: PaginationMeta


class DataListResponse(BaseModel, Generic[T]):
    """Standardized wrapper for non-paginated list responses."""
    data: list
