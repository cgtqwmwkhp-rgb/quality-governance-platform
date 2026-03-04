"""Pydantic schemas for Feature Flag API."""

from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class FeatureFlagCreate(BaseModel):
    """Schema for creating a feature flag."""

    key: str = Field(..., min_length=1, max_length=100, pattern=r"^[a-z0-9_.-]+$")
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    enabled: bool = False
    rollout_percentage: int = Field(default=0, ge=0, le=100)
    tenant_overrides: Optional[Dict[str, bool]] = None
    metadata_: Optional[Dict[str, Any]] = Field(None, alias="metadata")


class FeatureFlagUpdate(BaseModel):
    """Schema for updating a feature flag."""

    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    enabled: Optional[bool] = None
    rollout_percentage: Optional[int] = Field(None, ge=0, le=100)
    tenant_overrides: Optional[Dict[str, bool]] = None
    metadata_: Optional[Dict[str, Any]] = Field(None, alias="metadata")


class FeatureFlagResponse(BaseModel):
    """Schema for feature flag response."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    key: str
    name: str
    description: Optional[str] = None
    enabled: bool
    rollout_percentage: int
    tenant_overrides: Optional[Dict[str, bool]] = None
    metadata_: Optional[Dict[str, Any]] = Field(None, alias="metadata")
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    created_by: Optional[str] = None


class FeatureFlagEvaluateRequest(BaseModel):
    """Schema for evaluating a feature flag."""

    tenant_id: Optional[str] = None
    user_id: Optional[str] = None


class FeatureFlagEvaluateResponse(BaseModel):
    """Schema for feature flag evaluation result."""

    key: str
    enabled: bool


class FeatureFlagListResponse(BaseModel):
    """Schema for listing feature flags."""

    items: list[FeatureFlagResponse]
    total: int
