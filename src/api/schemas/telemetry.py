"""Pydantic response schemas for Telemetry API."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel


class ReceiveEventResponse(BaseModel):
    """Response after receiving a single telemetry event."""

    status: str


class ReceiveBatchEventResponse(BaseModel):
    """Response after receiving a batch of telemetry events."""

    status: str
    count: int


class GetExperimentMetricsResponse(BaseModel):
    """Aggregated experiment metrics returned to evaluators."""

    experimentId: str
    collectionStart: Optional[str] = None
    collectionEnd: Optional[str] = None
    samples: int
    events: dict[str, Any]
    dimensions: dict[str, Any]
    metrics: Optional[dict[str, Any]] = None


class ResetMetricsResponse(BaseModel):
    """Response after resetting experiment metrics."""

    status: str
