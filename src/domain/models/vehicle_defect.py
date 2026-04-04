"""Vehicle Defect domain model.

Stores governance assessments of defects found in PAMS Van Checklists.
The PAMS database is read-only; all governance data lives here in QGP PostgreSQL.
"""

from datetime import datetime, timezone
from enum import Enum as PyEnum
from typing import Optional

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.domain.models.base import Base


class DefectPriority(str, PyEnum):
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"


class DefectStatus(str, PyEnum):
    OPEN = "open"
    AUTO_DETECTED = "auto_detected"
    ACKNOWLEDGED = "acknowledged"
    ACTION_ASSIGNED = "action_assigned"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


class VehicleDefect(Base):
    """A defect flagged against a PAMS van checklist item."""

    __tablename__ = "vehicle_defects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)

    pams_table: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    pams_record_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    check_field: Mapped[str] = mapped_column(String(255), nullable=False)
    check_value: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    priority: Mapped[DefectPriority] = mapped_column(Enum(DefectPriority), nullable=False, index=True)
    status: Mapped[DefectStatus] = mapped_column(
        Enum(DefectStatus), default=DefectStatus.OPEN, nullable=False, index=True
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    vehicle_reg: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, index=True)

    created_by_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    assigned_to_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
    )

    def __repr__(self) -> str:
        return (
            f"<VehicleDefect(id={self.id}, priority={self.priority}, "
            f"vehicle={self.vehicle_reg}, field={self.check_field})>"
        )
