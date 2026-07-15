"""Pydantic schemas for Partner Webhook API (Wave5 scaffold)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

from src.domain.models.partner_webhook import PARTNER_WEBHOOK_EVENTS


class WebhookSubscriptionCreate(BaseModel):
    """Create a partner webhook subscription."""

    name: Optional[str] = Field(None, max_length=200)
    url: HttpUrl
    secret: str = Field(..., min_length=16, max_length=255)
    events: list[str] = Field(..., min_length=1)
    is_active: bool = True

    @field_validator("events")
    @classmethod
    def validate_events(cls, events: list[str]) -> list[str]:
        invalid = [event for event in events if event not in PARTNER_WEBHOOK_EVENTS]
        if invalid:
            allowed = ", ".join(PARTNER_WEBHOOK_EVENTS)
            raise ValueError(f"Unsupported event(s): {', '.join(invalid)}. Allowed: {allowed}")
        return events


class WebhookSubscriptionUpdate(BaseModel):
    """Update a partner webhook subscription."""

    name: Optional[str] = Field(None, max_length=200)
    url: Optional[HttpUrl] = None
    secret: Optional[str] = Field(None, min_length=16, max_length=255)
    events: Optional[list[str]] = Field(None, min_length=1)
    is_active: Optional[bool] = None

    @field_validator("events")
    @classmethod
    def validate_events(cls, events: Optional[list[str]]) -> Optional[list[str]]:
        if events is None:
            return events
        invalid = [event for event in events if event not in PARTNER_WEBHOOK_EVENTS]
        if invalid:
            allowed = ", ".join(PARTNER_WEBHOOK_EVENTS)
            raise ValueError(f"Unsupported event(s): {', '.join(invalid)}. Allowed: {allowed}")
        return events


class WebhookSubscriptionResponse(BaseModel):
    """Partner webhook subscription response (secret omitted)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    name: Optional[str] = None
    url: str
    events: list[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime


class WebhookSubscriptionListResponse(BaseModel):
    """Paginated subscription list."""

    items: list[WebhookSubscriptionResponse]
    total: int


class WebhookDeliveryLogResponse(BaseModel):
    """Delivery log entry."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    subscription_id: int
    tenant_id: int
    event_type: str
    payload: dict[str, Any]
    status: str
    http_status: Optional[int] = None
    error_message: Optional[str] = None
    signature: Optional[str] = None
    created_at: datetime
    delivered_at: Optional[datetime] = None


class WebhookDeliveryLogListResponse(BaseModel):
    """Paginated delivery log list."""

    items: list[WebhookDeliveryLogResponse]
    total: int


class PartnerWebhookEventCatalogResponse(BaseModel):
    """Supported partner webhook event types."""

    events: list[str]
