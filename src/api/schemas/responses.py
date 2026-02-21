"""Standardized API response models."""

from datetime import datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class ErrorDetail(BaseModel):
    """Structured error detail."""
    field: str | None = None
    message: str
    code: str | None = None


class ErrorResponse(BaseModel):
    """Standard error response format."""
    error: str
    message: str
    details: list[ErrorDetail] | None = None
    request_id: str | None = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class SuccessResponse(BaseModel):
    """Standard success response wrapper."""
    data: Any
    message: str | None = None
    meta: dict[str, Any] | None = None


class PaginatedMeta(BaseModel):
    """Pagination metadata."""
    total: int
    page: int
    page_size: int
    pages: int
    has_next: bool
    has_prev: bool


class PaginatedResponse(BaseModel):
    """Standard paginated response."""
    items: list[Any]
    meta: PaginatedMeta


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    version: str | None = None
    uptime_seconds: float | None = None
    checks: dict[str, str] | None = None
