"""Durable API idempotency keys (PX-001).

Redis middleware caches full HTTP responses when available. This table stores
key → entity_id for create endpoints so timeout retries return the same record
even when Redis is unavailable or the first response has not been cached yet.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from src.domain.models.base import Base


class ApiIdempotencyKey(Base):
    """Tenant-scoped idempotency claim for mutating creates."""

    __tablename__ = "api_idempotency_keys"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "scope",
            "idempotency_key",
            name="uq_api_idempotency_tenant_scope_key",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    # 0 = no tenant (superuser / system); never NULL so unique constraint is reliable.
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True, default=0)
    scope: Mapped[str] = mapped_column(String(64), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    # processing | completed
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="processing")
    entity_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    entity_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
