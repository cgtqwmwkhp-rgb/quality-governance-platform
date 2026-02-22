"""Executive Dashboard API response schemas."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class ExecutiveMetricResponse(BaseModel):
    """Response model for executive metric."""

    name: str
    value: float
    change: Optional[float] = None
    trend: Optional[str] = None
    period: str


class ExecutiveDashboardResponse(BaseModel):
    """Response model for executive dashboard."""

    metrics: list[ExecutiveMetricResponse] = []
    charts: list[dict[str, Any]] = []
    summary: Optional[str] = None
