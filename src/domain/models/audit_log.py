"""Audit Log models for system-wide events."""

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.database import Base


class AuditEvent(Base):
    """System-wide audit event log."""

    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    entity_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)

    # Event details
    before_value: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    after_value: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)

    # Metadata
    actor_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    request_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    def __repr__(self) -> str:
        return f"<AuditEvent(id={self.id}, type='{self.event_type}')>"
