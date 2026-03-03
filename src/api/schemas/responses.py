"""Standardized API response models."""

from datetime import datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class ErrorDetail(BaseModel):
    """Structured error detail for field-level errors."""

    field: str | None = None
    message: str
    code: str | None = None


class ErrorEnvelope(BaseModel):
    """Inner error object matching the actual handler output."""

    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
    request_id: str | None = None


class ErrorResponse(BaseModel):
    """Standard error response wrapper — matches handler output exactly."""

    error: ErrorEnvelope


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
    total_pages: int
    has_next: bool
    has_prev: bool


class PaginatedResponse(BaseModel, Generic[T]):
    """Standard paginated response."""

    items: list[Any]
    meta: PaginatedMeta
    _links: dict[str, str] | None = None


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    version: str | None = None
    uptime_seconds: float | None = None
    checks: dict[str, str] | None = None
