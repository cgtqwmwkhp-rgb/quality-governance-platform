"""AI Services API response schemas."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class AIInsightResponse(BaseModel):
    """Response model for AI insight."""

    insight_type: str
    title: str
    description: str
    confidence: float
    recommendations: list[str] = []


class AIPredictionResponse(BaseModel):
    """Response model for AI prediction."""

    entity_type: str
    prediction: str
    probability: float
    factors: list[str] = []


class AuditSuggestionResponse(BaseModel):
    """Response model for audit suggestion."""

    field: str
    suggested_value: str
    confidence: float
    reasoning: str
