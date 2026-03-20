"""Vehicle Registry domain model.

Gives every PAMS vehicle a first-class identity in QGP, tracking fleet
status, compliance posture, check timestamps, and driver assignment.
Auto-populated during PAMS sync; governance data lives in QGP PostgreSQL.
"""

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from src.domain.models.base import CaseInsensitiveEnum, TimestampMixin
from src.infrastructure.database import Base


class FleetStatus(str, enum.Enum):
    ACTIVE = "active"
    VOR = "vor"
    MAINTENANCE = "maintenance"
    DECOMMISSIONED = "decommissioned"


class ComplianceStatus(str, enum.Enum):
    COMPLIANT = "compliant"
    NON_COMPLIANT = "non_compliant"
    OVERDUE_CHECK = "overdue_check"
    SUSPENDED = "suspended"


class VehicleRegistry(Base, TimestampMixin):
    """A vehicle (van) with first-class identity in QGP."""

    __tablename__ = "vehicle_registry"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    vehicle_reg: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    pams_van_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    asset_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("assets.id", ondelete="SET NULL"), nullable=True
    )

    fleet_status: Mapped[FleetStatus] = mapped_column(
        CaseInsensitiveEnum(FleetStatus), default=FleetStatus.ACTIVE, nullable=False, index=True
    )
    compliance_status: Mapped[ComplianceStatus] = mapped_column(
        CaseInsensitiveEnum(ComplianceStatus), default=ComplianceStatus.COMPLIANT, nullable=False, index=True
    )

    last_daily_check_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_monthly_check_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_daily_check_pass: Mapped[Optional[bool]] = mapped_column(nullable=True)

    road_tax_expiry: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    fire_extinguisher_expiry: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    tooling_calibration_expiry: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    assigned_driver_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )

    tenant_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("tenants.id"), nullable=True, index=True
    )

    def __repr__(self) -> str:
        return (
            f"<VehicleRegistry(id={self.id}, reg='{self.vehicle_reg}', "
            f"fleet={self.fleet_status}, compliance={self.compliance_status})>"
        )
