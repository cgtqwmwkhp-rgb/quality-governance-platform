"""Allocation Compliance Gate Service.

Enforces compliance rules before a vehicle can be allocated to a driver
or dispatched. Checks fleet status, open defects, check currency, expiry
dates, and linked / child Safety Assets (AM-VAN).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.domain.models.asset import Asset, AssetCategory, AssetStatus
from src.domain.models.vehicle_defect import VehicleDefect
from src.domain.models.vehicle_registry import FleetStatus, VehicleRegistry

logger = logging.getLogger(__name__)

OPEN_STATUSES = ["open", "auto_detected", "acknowledged", "action_assigned"]

# Asset statuses that must block dispatch when linked to a vehicle.
BLOCKING_ASSET_STATUSES = {AssetStatus.VOR, AssetStatus.QUARANTINED}

FIRE_EXTINGUISHER_TYPE_HINTS = ("fire extinguisher", "extinguisher")
TOOLING_TYPE_HINTS = ("engineer tool", "tooling", "calibration")
KIT_TYPE_HINTS = FIRE_EXTINGUISHER_TYPE_HINTS + TOOLING_TYPE_HINTS + ("first aid",)


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


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _type_name(asset: Asset) -> str:
    if getattr(asset, "asset_type", None) is not None:
        return (asset.asset_type.name or "").strip()
    return ""


def _matches_hints(name: str, hints: tuple[str, ...]) -> bool:
    lowered = name.lower()
    return any(hint in lowered for hint in hints)


def pick_kit_asset_expiry(assets: list[Asset], hints: tuple[str, ...]) -> datetime | None:
    """Prefer the soonest expiry among child assets matching type name hints."""
    candidates: list[datetime] = []
    for asset in assets:
        if not _matches_hints(_type_name(asset), hints):
            continue
        expiry = _as_utc(asset.expiry_date)
        if expiry is not None:
            candidates.append(expiry)
    if not candidates:
        return None
    return min(candidates)


def dual_read_expiry(
    registry_expiry: datetime | None,
    child_assets: list[Asset],
    hints: tuple[str, ...],
) -> tuple[datetime | None, str]:
    """Prefer child-asset expiry when present; else fall back to vehicle_registry."""
    child_expiry = pick_kit_asset_expiry(child_assets, hints)
    if child_expiry is not None:
        return child_expiry, "asset"
    registry = _as_utc(registry_expiry)
    if registry is not None:
        return registry, "registry"
    return None, "none"


def expiry_band(expiry: datetime | None, now: datetime) -> str:
    """Return overdue | due_30 | in_date | unknown for UI / gate messaging."""
    expiry_utc = _as_utc(expiry)
    if expiry_utc is None:
        return "unknown"
    if expiry_utc < now:
        return "overdue"
    if (expiry_utc - now).days <= 30:
        return "due_30"
    return "in_date"


async def load_vehicle_kit_assets(
    db: AsyncSession,
    vehicle_reg: str,
    tenant_id: Optional[int] = None,
) -> list[Asset]:
    """Load safety (and other) assets assigned to a vehicle_reg."""
    query = select(Asset).options(selectinload(Asset.asset_type)).where(Asset.vehicle_reg.ilike(vehicle_reg.strip()))
    if tenant_id is not None:
        query = query.where(or_(Asset.tenant_id == tenant_id, Asset.tenant_id.is_(None)))
    result = await db.execute(query.order_by(Asset.asset_number))
    return list(result.scalars().all())


async def load_linked_asset(
    db: AsyncSession,
    asset_id: int | None,
    tenant_id: Optional[int] = None,
) -> Asset | None:
    if asset_id is None:
        return None
    query = select(Asset).options(selectinload(Asset.asset_type)).where(Asset.id == asset_id)
    if tenant_id is not None:
        query = query.where(or_(Asset.tenant_id == tenant_id, Asset.tenant_id.is_(None)))
    result = await db.execute(query)
    return result.scalar_one_or_none()


def _consult_asset_status(
    asset: Asset,
    *,
    reasons: list[str],
    expiry_warnings: list[str],
    now: datetime,
    label: str,
) -> None:
    status = asset.status
    if isinstance(status, AssetStatus):
        status_value = status
    else:
        try:
            status_value = AssetStatus(str(status).lower())
        except ValueError:
            status_value = None

    if status_value in BLOCKING_ASSET_STATUSES:
        reasons.append(
            f"{label} '{asset.asset_number}' status is '{status_value.value}' — vehicle must not be dispatched"
        )
    elif status_value == AssetStatus.MAINTENANCE:
        expiry_warnings.append(f"{label} '{asset.asset_number}' is in maintenance")

    band = expiry_band(asset.expiry_date, now)
    if band == "overdue":
        reasons.append(f"{label} '{asset.asset_number}' expiry is overdue")
    elif band == "due_30":
        expiry = _as_utc(asset.expiry_date)
        days = (expiry - now).days if expiry is not None else 0
        expiry_warnings.append(f"{label} '{asset.asset_number}' expires in {days} days")


def build_kit_compliance_payload(
    vehicle: VehicleRegistry,
    child_assets: list[Asset],
    linked_asset: Asset | None = None,
) -> dict[str, Any]:
    """Serialize van kit dual-read expiry + child assets for the compliance panel API."""
    now = datetime.now(timezone.utc)
    fire_expiry, fire_source = dual_read_expiry(
        vehicle.fire_extinguisher_expiry, child_assets, FIRE_EXTINGUISHER_TYPE_HINTS
    )
    tool_expiry, tool_source = dual_read_expiry(vehicle.tooling_calibration_expiry, child_assets, TOOLING_TYPE_HINTS)

    items: list[dict[str, Any]] = []
    for asset in child_assets:
        type_name = _type_name(asset)
        category = None
        if getattr(asset, "asset_type", None) is not None:
            cat = asset.asset_type.category
            category = cat.value if isinstance(cat, AssetCategory) else str(cat)
        status_val = asset.status.value if isinstance(asset.status, AssetStatus) else str(asset.status)
        items.append(
            {
                "id": asset.id,
                "asset_number": asset.asset_number,
                "name": asset.name,
                "asset_type_id": asset.asset_type_id,
                "asset_type_name": type_name or None,
                "category": category,
                "status": status_val,
                "expiry_date": _as_utc(asset.expiry_date),
                "expiry_status": expiry_band(asset.expiry_date, now),
                "is_kit_asset": _matches_hints(type_name, KIT_TYPE_HINTS)
                or (category == AssetCategory.SAFETY.value if category else False),
            }
        )

    return {
        "vehicle_reg": vehicle.vehicle_reg,
        "asset_id": vehicle.asset_id,
        "linked_asset_id": linked_asset.id if linked_asset else vehicle.asset_id,
        "linked_asset_status": (
            (linked_asset.status.value if isinstance(linked_asset.status, AssetStatus) else str(linked_asset.status))
            if linked_asset
            else None
        ),
        "assets": items,
        "fire_extinguisher_expiry": fire_expiry,
        "fire_extinguisher_expiry_source": fire_source,
        "fire_extinguisher_expiry_status": expiry_band(fire_expiry, now),
        "tooling_calibration_expiry": tool_expiry,
        "tooling_calibration_expiry_source": tool_source,
        "tooling_calibration_expiry_status": expiry_band(tool_expiry, now),
        "registry_fire_extinguisher_expiry": _as_utc(vehicle.fire_extinguisher_expiry),
        "registry_tooling_calibration_expiry": _as_utc(vehicle.tooling_calibration_expiry),
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
        last_check = _as_utc(vehicle.last_daily_check_at)
        hours_since = (now - last_check).total_seconds() / 3600 if last_check is not None else 0
        if hours_since > 24:
            checks_current = False
            reasons.append("Daily check overdue (>24h)")
    else:
        checks_current = False
        reasons.append("No daily check recorded")

    road_tax = _as_utc(vehicle.road_tax_expiry)
    if road_tax is not None and road_tax < now:
        reasons.append("Road tax expired")
    elif road_tax is not None and (road_tax - now).days <= 30:
        expiry_warnings.append(
            f"Road tax expires in {(road_tax - now).days} days"
        )

    # AM-VAN: consult linked vehicle Asset + child kit assets
    child_assets = await load_vehicle_kit_assets(db, vehicle_reg, tenant_id)
    linked_asset = await load_linked_asset(db, vehicle.asset_id, tenant_id)

    if linked_asset is not None:
        _consult_asset_status(
            linked_asset,
            reasons=reasons,
            expiry_warnings=expiry_warnings,
            now=now,
            label="Linked vehicle asset",
        )

    for asset in child_assets:
        _consult_asset_status(
            asset,
            reasons=reasons,
            expiry_warnings=expiry_warnings,
            now=now,
            label="Kit asset",
        )

    # Dual-read kit expiries: prefer child-asset expiry when present.
    # Child assets are already consulted above; registry fallbacks apply only when
    # no matching child asset expiry exists (keeps legacy PAMS columns live).
    fire_expiry, fire_source = dual_read_expiry(
        vehicle.fire_extinguisher_expiry, child_assets, FIRE_EXTINGUISHER_TYPE_HINTS
    )
    if fire_source == "registry" and fire_expiry is not None:
        if fire_expiry < now:
            reasons.append("Fire extinguisher expired")
        elif (fire_expiry - now).days <= 30:
            expiry_warnings.append(f"Fire extinguisher expires in {(fire_expiry - now).days} days")

    tool_expiry, tool_source = dual_read_expiry(vehicle.tooling_calibration_expiry, child_assets, TOOLING_TYPE_HINTS)
    if tool_source == "registry" and tool_expiry is not None and tool_expiry < now:
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
        "message": f"Vehicle {vehicle_reg} allocated to driver {driver_profile_id}" + (" (forced)" if force else ""),
        "warnings": gate.expiry_warnings,
    }
