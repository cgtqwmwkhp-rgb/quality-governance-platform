"""Partner API tokens — scoped bearer credentials for partner integrations (R6)."""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from src.domain.models.base import Base, TimestampMixin

PARTNER_API_SCOPES: tuple[str, ...] = (
    "webhooks:manage",
    "inspections:read",
    "documents:read",
    "search:read",
    "policies:read",
)

# Partner scopes → the platform RBAC tokens a partner caller holding that scope
# satisfies, so the ``require_permission`` dependencies already on the gated
# routes keep being the thing that decides.
#
# A scope absent from this mapping grants no RBAC permission at all. That is the
# fail-closed half of the design and it is load-bearing for two scopes:
# ``search:read`` gates only the routes that opt in by name, and
# ``policies:read`` is allowlisted so a token can be minted for a future policy
# surface but reaches nothing until one opts in. Mapping either of them here
# would hand a partner token a permission on every route that already checks it.
PARTNER_SCOPE_TO_PERMISSIONS: dict[str, frozenset[str]] = {
    "documents:read": frozenset({"document:read"}),
}


class PartnerApiToken(Base, TimestampMixin):
    """Tenant-scoped partner API token (secret stored as SHA-256 hash only)."""

    __tablename__ = "partner_api_tokens"
    __table_args__ = (
        Index("ix_partner_api_tokens_tenant_active", "tenant_id", "is_active"),
        Index("ix_partner_api_tokens_prefix", "token_prefix"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    token_prefix: Mapped[str] = mapped_column(String(16), nullable=False)
    secret_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    scopes: Mapped[list[str]] = mapped_column(JSON().with_variant(JSONB, "postgresql"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<PartnerApiToken(id={self.id}, tenant_id={self.tenant_id}, prefix={self.token_prefix!r})>"
