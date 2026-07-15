"""Pydantic schemas for Partner API token management (R6)."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.domain.models.partner_api_token import PARTNER_API_SCOPES


class PartnerApiTokenCreate(BaseModel):
    """Create a scoped partner API token."""

    name: Optional[str] = Field(None, max_length=200)
    scopes: list[str] = Field(..., min_length=1)

    @field_validator("scopes")
    @classmethod
    def validate_scopes(cls, scopes: list[str]) -> list[str]:
        invalid = [scope for scope in scopes if scope not in PARTNER_API_SCOPES]
        if invalid:
            allowed = ", ".join(PARTNER_API_SCOPES)
            raise ValueError(f"Unsupported scope(s): {', '.join(invalid)}. Allowed: {allowed}")
        return scopes


class PartnerApiTokenResponse(BaseModel):
    """Partner API token metadata (secret never returned after create)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    name: Optional[str] = None
    token_prefix: str
    scopes: list[str]
    is_active: bool
    last_used_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class PartnerApiTokenCreateResponse(PartnerApiTokenResponse):
    """One-time plaintext token returned only on create."""

    token: str


class PartnerApiTokenListResponse(BaseModel):
    """Paginated partner API token list."""

    items: list[PartnerApiTokenResponse]
    total: int
