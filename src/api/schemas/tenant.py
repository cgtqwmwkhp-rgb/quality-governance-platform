"""Tenant API response schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel

# ============================================================================
# User Management
# ============================================================================


class TenantUserItem(BaseModel):
    id: int
    user_id: int
    role: str
    is_active: bool
    joined_at: Optional[datetime] = None


class TenantUserListResponse(BaseModel):
    items: list[TenantUserItem] = []


class AddUserToTenantResponse(BaseModel):
    id: int
    role: str


class RemoveUserFromTenantResponse(BaseModel):
    status: str


# ============================================================================
# Invitations
# ============================================================================


class CreateInvitationResponse(BaseModel):
    id: int
    email: str
    token: str
    expires_at: datetime


class AcceptInvitationResponse(BaseModel):
    status: str
    tenant_id: int


# ============================================================================
# Features
# ============================================================================


class TenantFeaturesResponse(BaseModel):
    model_config = {"extra": "allow"}


class ToggleFeatureResponse(BaseModel):
    feature: str
    enabled: bool


# ============================================================================
# Limits
# ============================================================================


class LimitDetail(BaseModel):
    current: int
    max: int


class TenantLimitsResponse(BaseModel):
    users: LimitDetail
    storage_gb: LimitDetail
