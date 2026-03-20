"""Driver Profile domain model.

Links QGP user accounts to PAMS driver data, enabling driver
accountability for vehicle checks, defect acknowledgement, and
compliance scoring.
"""

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.domain.models.base import CaseInsensitiveEnum, TimestampMixin
from src.infrastructure.database import Base


class AcknowledgementStatus(str, enum.Enum):
    PENDING = "pending"
    ACKNOWLEDGED = "acknowledged"
    REFUSED = "refused"


class DriverProfile(Base, TimestampMixin):
    """Links a QGP user to their PAMS driver identity."""

    __tablename__ = "driver_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False, index=True
    )

    pams_driver_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    licence_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    licence_expiry: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    allocated_vehicle_reg: Mapped[Optional[str]] = mapped_column(
        String(20), ForeignKey("vehicle_registry.vehicle_reg", ondelete="SET NULL"), nullable=True, index=True
    )

    compliance_score: Mapped[float] = mapped_column(Float, default=100.0, nullable=False)
    last_check_completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active_driver: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    tenant_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("tenants.id"), nullable=True, index=True
    )

    def __repr__(self) -> str:
        return (
            f"<DriverProfile(id={self.id}, user_id={self.user_id}, "
            f"pams_name='{self.pams_driver_name}', vehicle='{self.allocated_vehicle_reg}')>"
        )


class DriverAcknowledgement(Base, TimestampMixin):
    """Records a driver's acknowledgement of a defect or vehicle assignment."""

    __tablename__ = "driver_acknowledgements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    driver_profile_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("driver_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )

    entity_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    status: Mapped[AcknowledgementStatus] = mapped_column(
        CaseInsensitiveEnum(AcknowledgementStatus),
        default=AcknowledgementStatus.PENDING,
        nullable=False,
        index=True,
    )
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    tenant_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("tenants.id"), nullable=True, index=True
    )

    def __repr__(self) -> str:
        return (
            f"<DriverAcknowledgement(id={self.id}, driver={self.driver_profile_id}, "
            f"entity={self.entity_type}/{self.entity_id}, status={self.status})>"
        )
