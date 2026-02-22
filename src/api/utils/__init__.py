"""Shared API utility functions."""

from src.api.utils.entity import get_or_404
from src.api.utils.pagination import PaginatedResponse, PaginationParams, paginate
from src.api.utils.tenant import tenant_scope
from src.api.utils.update import apply_updates

__all__ = [
    "get_or_404",
    "PaginatedResponse",
    "PaginationParams",
    "paginate",
    "tenant_scope",
    "apply_updates",
]
