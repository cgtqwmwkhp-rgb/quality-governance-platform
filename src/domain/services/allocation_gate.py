"""Allocation Compliance Gate Service.

Enforces compliance rules before a vehicle can be allocated to a driver
or dispatched. Checks fleet status, open defects, check currency, and
expiry dates.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.vehicle_defect import VehicleDefect
from src.domain.models.vehicle_registry import ComplianceStatus, FleetStatus, VehicleRegistry

logger = logging.getLogger(__name__)

OPEN_STATUSES = ["open", "auto_detected", "acknowledged", "action_assigned"]


class AllocationDecision:
    """Result of an allocation compliance check."""

    def __init__(
        self,
        vehicle_reg: str,
        allowed: bool,
        reasons: list[str],
        open_p1: int = 0,
        open_p2: int = 0,
        checks_current: bool = True,
        expiry_warnings: list[str] | None = None,
    ):
        self.vehicle_reg = vehicle_reg
        self.allowed = allowed
        self.reasons = reasons
        self.open_p1 = open_p1
        self.open_p2 = open_p2
        self.checks_current = checks_current
        self.expiry_warnings = expiry_warnings or []

    def to_dict(self) -> dict:
        return {
            "vehicle_reg": self.vehicle_reg,
            "allowed": self.allowed,
            "reasons": self.reasons,
            "open_p1": self.open_p1,
            "open_p2": self.open_p2,
            "checks_current": self.checks_current,
            "expiry_warnings": self.expiry_warnings,
        }


async def check_allocation(
    db: AsyncSession,
    vehicle_reg: str,
    tenant_id: Optional[int] = None,
) -> AllocationDecision:
    """Run a full compliance gate check for allocating a vehicle."""
    query = select(VehicleRegistry).where(VehicleRegistry.vehicle_reg == vehicle_reg)
    if tenant_id:
        query = query.where(VehicleRegistry.tenant_id == tenant_id)
    result = await db.execute(query)
    vehicle = result.scalar_one_or_none()

    if vehicle is None:
        return AllocationDecision(
            vehicle_reg=vehicle_reg,
            allowed=False,
            reasons=[f"Vehicle '{vehicle_reg}' not found in registry"],
        )

    reasons: list[str] = []
    expiry_warnings: list[str] = []

    if vehicle.fleet_status != FleetStatus.ACTIVE:
        reasons.append(f"Fleet status is '{vehicle.fleet_status.value}' (must be 'active')")

    p1_q = select(func.count(VehicleDefect.id)).where(
        VehicleDefect.vehicle_reg == vehicle_reg,
        VehicleDefect.priority == "P1",
        VehicleDefect.status.in_(OPEN_STATUSES),
    )
    p2_q = select(func.count(VehicleDefect.id)).where(
        VehicleDefect.vehicle_reg == vehicle_reg,
        VehicleDefect.priority == "P2",
        VehicleDefect.status.in_(OPEN_STATUSES),
    )
    open_p1 = (await db.execute(p1_q)).scalar() or 0
    open_p2 = (await db.execute(p2_q)).scalar() or 0

    if open_p1 > 0:
        reasons.append(f"{open_p1} open P1 defect(s) — vehicle must not be dispatched")

    now = datetime.now(timezone.utc)
    checks_current = True
    if vehicle.last_daily_check_at:
        hours_since = (now - vehicle.last_daily_check_at).total_seconds() / 3600
        if hours_since > 24:
            checks_current = False
            reasons.append("Daily check overdue (>24h)")
    else:
        checks_current = False
        reasons.append("No daily check recorded")

    if vehicle.road_tax_expiry and vehicle.road_tax_expiry < now:
        reasons.append("Road tax expired")
    elif vehicle.road_tax_expiry and (vehicle.road_tax_expiry - now).days <= 30:
        expiry_warnings.append(f"Road tax expires in {(vehicle.road_tax_expiry - now).days} days")

    if vehicle.fire_extinguisher_expiry and vehicle.fire_extinguisher_expiry < now:
        reasons.append("Fire extinguisher expired")
    elif vehicle.fire_extinguisher_expiry and (vehicle.fire_extinguisher_expiry - now).days <= 30:
        expiry_warnings.append(f"Fire extinguisher expires in {(vehicle.fire_extinguisher_expiry - now).days} days")

    if vehicle.tooling_calibration_expiry and vehicle.tooling_calibration_expiry < now:
        expiry_warnings.append("Tooling calibration expired")

    allowed = len(reasons) == 0

    return AllocationDecision(
        vehicle_reg=vehicle_reg,
        allowed=allowed,
        reasons=reasons if reasons else ["Vehicle cleared for allocation"],
        open_p1=open_p1,
        open_p2=open_p2,
        checks_current=checks_current,
        expiry_warnings=expiry_warnings,
    )


async def allocate_vehicle_to_driver(
    db: AsyncSession,
    vehicle_reg: str,
    driver_profile_id: int,
    tenant_id: Optional[int] = None,
    force: bool = False,
) -> dict:
    """Allocate a vehicle to a driver with compliance gate enforcement.

    If force=True, bypasses compliance gate (requires admin).
    Returns allocation result dict.
    """
    from src.domain.models.driver_profile import DriverProfile

    gate = await check_allocation(db, vehicle_reg, tenant_id)

    if not gate.allowed and not force:
        return {
            "allocated": False,
            "gate": gate.to_dict(),
            "message": "Allocation blocked by compliance gate",
        }

    vehicle_q = select(VehicleRegistry).where(VehicleRegistry.vehicle_reg == vehicle_reg)
    if tenant_id:
        vehicle_q = vehicle_q.where(VehicleRegistry.tenant_id == tenant_id)
    vehicle = (await db.execute(vehicle_q)).scalar_one_or_none()
    if not vehicle:
        return {"allocated": False, "gate": gate.to_dict(), "message": "Vehicle not found"}

    driver_q = select(DriverProfile).where(DriverProfile.id == driver_profile_id)
    if tenant_id:
        driver_q = driver_q.where(DriverProfile.tenant_id == tenant_id)
    driver = (await db.execute(driver_q)).scalar_one_or_none()
    if not driver:
        return {"allocated": False, "gate": gate.to_dict(), "message": "Driver profile not found"}

    driver.allocated_vehicle_reg = vehicle_reg
    vehicle.assigned_driver_id = driver.user_id

    await db.commit()

    return {
        "allocated": True,
        "gate": gate.to_dict(),
        "message": f"Vehicle {vehicle_reg} allocated to driver {driver_profile_id}"
        + (" (forced)" if force else ""),
        "warnings": gate.expiry_warnings,
    }
