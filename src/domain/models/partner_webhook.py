"""Partner webhook subscriptions and delivery log — Wave5 cash-in-wall scaffold."""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from src.domain.models.base import Base, CaseInsensitiveEnum, TimestampMixin

# Event catalog — v1 partner webhook surface
PARTNER_WEBHOOK_EVENTS: tuple[str, ...] = (
    "inspection.started",
    "inspection.completed",
    "finding.created",
    "finding.updated",
    "capa.created",
    "capa.status_changed",
)


class WebhookDeliveryStatus(str, enum.Enum):
    PENDING = "pending"
    STUBBED = "stubbed"
    DELIVERED = "delivered"
    FAILED = "failed"


class WebhookSubscription(Base, TimestampMixin):
    """Outbound partner webhook subscription (tenant-scoped)."""

    __tablename__ = "webhook_subscriptions"
    __table_args__ = (Index("ix_webhook_subscriptions_tenant_active", "tenant_id", "is_active"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    secret: Mapped[str] = mapped_column(String(255), nullable=False)
    events: Mapped[list[str]] = mapped_column(JSON().with_variant(JSONB, "postgresql"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    def __repr__(self) -> str:
        return f"<WebhookSubscription(id={self.id}, tenant_id={self.tenant_id}, url={self.url!r})>"


class WebhookDeliveryLog(Base):
    """Immutable delivery attempt log for partner webhooks."""

    __tablename__ = "webhook_delivery_logs"
    __table_args__ = (
        Index("ix_webhook_delivery_logs_tenant_created", "tenant_id", "created_at"),
        Index("ix_webhook_delivery_logs_subscription", "subscription_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    subscription_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("webhook_subscriptions.id", ondelete="CASCADE"), nullable=False
    )
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON().with_variant(JSONB, "postgresql"), nullable=False)
    status: Mapped[WebhookDeliveryStatus] = mapped_column(
        CaseInsensitiveEnum(WebhookDeliveryStatus),
        default=WebhookDeliveryStatus.PENDING,
        nullable=False,
    )
    http_status: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    signature: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    delivered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<WebhookDeliveryLog(id={self.id}, event_type={self.event_type!r}, status={self.status})>"
