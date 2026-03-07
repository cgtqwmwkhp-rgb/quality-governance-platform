"""API-layer pagination utilities.

Re-exports core pagination and adds FastAPI-specific PaginationParams
(uses Query() defaults).
"""

from fastapi import Query

from src.core.pagination import PaginatedResponse, PaginationInput, paginate

__all__ = ["PaginatedResponse", "PaginationParams", "paginate"]


class PaginationParams(PaginationInput):
    """FastAPI dependency that binds page/page_size from query-string."""

    def __init__(
        self,
        page: int = Query(1, ge=1, description="Page number"),
        page_size: int = Query(20, ge=1, le=500, description="Items per page"),
    ):
        super().__init__(page=page, page_size=page_size)
