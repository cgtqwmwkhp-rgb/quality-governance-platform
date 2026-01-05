'''Shared helper functions for API routes.'''

from typing import Any, Dict, Tuple

from fastapi import Query

DEFAULT_PAGE = 1
DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 100


def pagination_params(
    page: int = Query(DEFAULT_PAGE, ge=1, description="Page number"),
    page_size: int = Query(
        DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE, description="Items per page"
    ),
) -> Tuple[int, int]:
    """
    Returns a tuple of (page, page_size) for use in endpoint signatures.
    """
    return (page, page_size)


def apply_pagination(query: Any, page: int, page_size: int) -> Any:
    """
    Applies limit and offset to a SQLAlchemy query based on pagination parameters.
    """
    return query.limit(page_size).offset((page - 1) * page_size)
