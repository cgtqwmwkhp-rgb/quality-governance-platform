"""Tenant-scoped matter legal holds.

This is the durable record of a hold instruction.  It deliberately uses a
generic ``matter_reference`` because QGP has no canonical legal-matter model.
Creating or releasing a hold does not by itself wire every retention worker;
that enforcement boundary is disclosed by the privacy API.
"""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from src.domain.models.base import Base, CaseInsensitiveEnum, TimestampMixin


class LegalHoldStatus(str, enum.Enum):
    ACTIVE = "active"
    RELEASED = "released"


class MatterLegalHold(Base, TimestampMixin):
    """A durable hold instruction for records associated with one matter."""

    __tablename__ = "matter_legal_holds"
    __table_args__ = (
        CheckConstraint(
            "length(trim(matter_reference)) > 0",
            name="ck_matter_legal_holds_matter_ref",
        ),
        Index("ix_matter_legal_holds_tenant_matter", "tenant_id", "matter_reference"),
        Index("ix_matter_legal_holds_tenant_status", "tenant_id", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    matter_reference: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[LegalHoldStatus] = mapped_column(
        CaseInsensitiveEnum(LegalHoldStatus), nullable=False, default=LegalHoldStatus.ACTIVE
    )
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    released_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    released_by_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
