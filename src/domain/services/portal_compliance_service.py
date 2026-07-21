"""Person-scoped tool + van compliance for the employee portal."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.domain.models.asset import Asset, AssetStatus
from src.domain.models.driver_profile import DriverProfile
from src.domain.models.vehicle_defect import VehicleDefect
from src.domain.models.vehicle_registry import VehicleRegistry
from src.domain.services.allocation_gate import OPEN_STATUSES, load_vehicle_kit_assets

ClearState = Literal["clear", "attention", "blocked"]
ToolBand = Literal["overdue", "due_30", "due_60", "due_90", "in_date", "none", "quarantined", "decommissioned"]


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def exclusive_expiry_band(expiry: datetime | None, *, now: datetime | None = None) -> ToolBand:
    """Exclusive windows matching Safety Asset Register board helpers."""
    now_utc = _as_utc(now) or datetime.now(timezone.utc)
    expiry_utc = _as_utc(expiry)
    if expiry_utc is None:
        return "none"
    days = (expiry_utc.date() - now_utc.date()).days
    if days < 0:
        return "overdue"
    if days <= 30:
        return "due_30"
    if days <= 60:
        return "due_60"
    if days <= 90:
        return "due_90"
    return "in_date"


def tool_display_band(asset: Asset, *, now: datetime | None = None) -> ToolBand:
    status = (getattr(asset.status, "value", asset.status) or "").lower()
    if status == AssetStatus.QUARANTINED.value:
        return "quarantined"
    if status == AssetStatus.DECOMMISSIONED.value:
        return "decommissioned"
    return exclusive_expiry_band(asset.expiry_date, now=now)


def derive_clear_state(
    *,
    overdue: int,
    quarantined: int,
    due_30: int,
    open_p1: int,
    open_other_defects: int,
) -> ClearState:
    if quarantined > 0 or open_p1 > 0:
        return "blocked"
    if overdue > 0 or due_30 > 0 or open_other_defects > 0:
        return "attention"
    return "clear"


class PortalComplianceService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def _resolve_van(
        self, *, user_id: int, tenant_id: int
    ) -> tuple[DriverProfile | None, VehicleRegistry | None, str | None, bool, list[str]]:
        """Return profile, vehicle, empty_reason, assignment_conflict, conflicting_regs."""
        profile = (
            await self.db.execute(
                select(DriverProfile).where(
                    DriverProfile.user_id == user_id,
                    or_(DriverProfile.tenant_id == tenant_id, DriverProfile.tenant_id.is_(None)),
                )
            )
        ).scalar_one_or_none()

        claimed = list(
            (
                await self.db.execute(
                    select(VehicleRegistry).where(
                        VehicleRegistry.assigned_driver_id == user_id,
                        or_(VehicleRegistry.tenant_id == tenant_id, VehicleRegistry.tenant_id.is_(None)),
                    )
                )
            )
            .scalars()
            .all()
        )
        claimed_regs = [v.vehicle_reg for v in claimed]

        if profile is None:
            if len(claimed) == 1:
                return None, claimed[0], None, True, claimed_regs
            if len(claimed) > 1:
                return None, None, "multiple_assigned", True, claimed_regs
            return None, None, "no_driver_profile", False, []

        allocated = (profile.allocated_vehicle_reg or "").strip() or None
        if not allocated:
            if len(claimed) == 1:
                return profile, claimed[0], None, True, claimed_regs
            if len(claimed) > 1:
                return profile, None, "multiple_assigned", True, claimed_regs
            return profile, None, "no_van", False, []

        vehicle = (
            await self.db.execute(
                select(VehicleRegistry).where(
                    VehicleRegistry.vehicle_reg == allocated,
                    or_(VehicleRegistry.tenant_id == tenant_id, VehicleRegistry.tenant_id.is_(None)),
                )
            )
        ).scalar_one_or_none()
        if vehicle is None:
            return profile, None, "no_van", False, claimed_regs

        conflict = vehicle.assigned_driver_id not in (None, user_id) or (
            len(claimed) > 0 and allocated not in claimed_regs
        )
        if conflict and vehicle.assigned_driver_id not in (None, user_id):
            return profile, None, "assignment_conflict", True, claimed_regs
        if len(claimed) > 1:
            return profile, None, "multiple_assigned", True, claimed_regs
        return profile, vehicle, None, bool(conflict), claimed_regs

    async def _owned_assets(self, *, user_id: int, tenant_id: int) -> list[Asset]:
        return list(
            (
                await self.db.execute(
                    select(Asset)
                    .options(selectinload(Asset.asset_type))
                    .where(
                        Asset.owner_user_id == user_id,
                        or_(Asset.tenant_id == tenant_id, Asset.tenant_id.is_(None)),
                    )
                    .order_by(Asset.name)
                )
            )
            .scalars()
            .all()
        )

    async def _open_defects(self, *, vehicle_reg: str, tenant_id: int) -> list[VehicleDefect]:
        return list(
            (
                await self.db.execute(
                    select(VehicleDefect)
                    .where(
                        VehicleDefect.vehicle_reg == vehicle_reg,
                        or_(VehicleDefect.tenant_id == tenant_id, VehicleDefect.tenant_id.is_(None)),
                        VehicleDefect.status.in_(OPEN_STATUSES),
                    )
                    .order_by(VehicleDefect.created_at.desc())
                    .limit(50)
                )
            )
            .scalars()
            .all()
        )

    def _serialize_tool(
        self,
        asset: Asset,
        *,
        why: str,
        now: datetime,
    ) -> dict[str, Any]:
        band = tool_display_band(asset, now=now)
        type_name = asset.asset_type.name if asset.asset_type is not None else None
        type_pending = bool(
            asset.asset_type is not None
            and (
                not getattr(asset.asset_type, "is_active", True)
                or getattr(asset.asset_type, "approval_status", "approved") == "pending"
            )
        )
        return {
            "id": asset.id,
            "name": asset.name,
            "asset_number": asset.asset_number,
            "serial_number": asset.serial_number,
            "status": getattr(asset.status, "value", asset.status),
            "expiry_date": asset.expiry_date.isoformat() if asset.expiry_date else None,
            "band": band,
            "vehicle_reg": asset.vehicle_reg,
            "owner_user_id": asset.owner_user_id,
            "asset_type_name": type_name,
            "type_pending": type_pending,
            "why_shown": why,
        }

    async def my_driver(self, *, user_id: int, tenant_id: int) -> dict[str, Any]:
        profile, vehicle, empty_reason, conflict, claimed_regs = await self._resolve_van(
            user_id=user_id, tenant_id=tenant_id
        )
        return {
            "linked": profile is not None,
            "driver_profile_id": profile.id if profile else None,
            "pams_driver_name": profile.pams_driver_name if profile else None,
            "allocated_vehicle_reg": profile.allocated_vehicle_reg if profile else None,
            "vehicle_reg": vehicle.vehicle_reg if vehicle else None,
            "assignment_conflict": conflict,
            "conflicting_regs": claimed_regs,
            "empty_reason": empty_reason,
        }

    async def my_tools(self, *, user_id: int, tenant_id: int) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        _profile, vehicle, van_empty, _conflict, _regs = await self._resolve_van(user_id=user_id, tenant_id=tenant_id)
        owned = await self._owned_assets(user_id=user_id, tenant_id=tenant_id)
        van_kit: list[Asset] = []
        if vehicle is not None:
            van_kit = await load_vehicle_kit_assets(self.db, vehicle.vehicle_reg, tenant_id)

        by_id: dict[int, dict[str, Any]] = {}
        for asset in owned:
            why = "Assigned to me"
            if vehicle and asset.vehicle_reg and asset.vehicle_reg.upper() == vehicle.vehicle_reg.upper():
                why = "Assigned to me · on van"
            by_id[asset.id] = self._serialize_tool(asset, why=why, now=now)
        for asset in van_kit:
            if asset.id in by_id:
                continue
            by_id[asset.id] = self._serialize_tool(asset, why="On my van", now=now)

        items = list(by_id.values())
        band_rank = {
            "quarantined": 0,
            "overdue": 1,
            "due_30": 2,
            "due_60": 3,
            "due_90": 4,
            "in_date": 5,
            "none": 6,
            "decommissioned": 7,
        }
        items.sort(key=lambda row: (band_rank.get(row["band"], 9), (row["name"] or "").lower()))

        summary = {
            "total": len(items),
            "overdue": sum(1 for i in items if i["band"] == "overdue"),
            "due_30": sum(1 for i in items if i["band"] == "due_30"),
            "due_60": sum(1 for i in items if i["band"] == "due_60"),
            "due_90": sum(1 for i in items if i["band"] == "due_90"),
            "in_date": sum(1 for i in items if i["band"] == "in_date"),
            "quarantined": sum(1 for i in items if i["band"] == "quarantined"),
            "mine": len(owned),
            "on_van": len(van_kit),
        }
        empty_reason = None
        if not items:
            empty_reason = "no_tools" if van_empty != "no_driver_profile" else "no_tools"
        return {"items": items, "summary": summary, "empty_reason": empty_reason}

    async def my_van_status(self, *, user_id: int, tenant_id: int) -> dict[str, Any]:
        profile, vehicle, empty_reason, conflict, claimed_regs = await self._resolve_van(
            user_id=user_id, tenant_id=tenant_id
        )
        if vehicle is None:
            return {
                "linked_driver": profile is not None,
                "vehicle_reg": None,
                "assignment_conflict": conflict,
                "conflicting_regs": claimed_regs,
                "empty_reason": empty_reason or "no_van",
                "daily_last_at": None,
                "daily_pass": None,
                "monthly_last_at": None,
                "open_defects": [],
                "defect_counts": {"p1": 0, "p2": 0, "p3": 0, "total": 0},
                "fleet_status": None,
                "compliance_status": None,
            }

        defects = await self._open_defects(vehicle_reg=vehicle.vehicle_reg, tenant_id=tenant_id)

        def _priority(d: VehicleDefect) -> str:
            return str(getattr(d.priority, "value", d.priority) or "").upper()

        def _status(d: VehicleDefect) -> str:
            return str(getattr(d.status, "value", d.status) or "")

        p1 = sum(1 for d in defects if _priority(d) == "P1")
        p2 = sum(1 for d in defects if _priority(d) == "P2")
        p3 = sum(1 for d in defects if _priority(d) == "P3")
        return {
            "linked_driver": profile is not None,
            "vehicle_reg": vehicle.vehicle_reg,
            "assignment_conflict": conflict,
            "conflicting_regs": claimed_regs,
            "empty_reason": None,
            "daily_last_at": vehicle.last_daily_check_at.isoformat() if vehicle.last_daily_check_at else None,
            "daily_pass": vehicle.last_daily_check_pass,
            "monthly_last_at": (vehicle.last_monthly_check_at.isoformat() if vehicle.last_monthly_check_at else None),
            "open_defects": [
                {
                    "id": d.id,
                    "priority": _priority(d),
                    "status": _status(d),
                    "check_field": d.check_field,
                    "check_value": d.check_value,
                    "notes": d.notes,
                    "created_at": d.created_at.isoformat() if d.created_at else None,
                }
                for d in defects
            ],
            "defect_counts": {"p1": p1, "p2": p2, "p3": p3, "total": len(defects)},
            "fleet_status": getattr(vehicle.fleet_status, "value", vehicle.fleet_status),
            "compliance_status": getattr(vehicle.compliance_status, "value", vehicle.compliance_status),
        }

    async def my_compliance(self, *, user_id: int, tenant_id: int) -> dict[str, Any]:
        tools = await self.my_tools(user_id=user_id, tenant_id=tenant_id)
        van = await self.my_van_status(user_id=user_id, tenant_id=tenant_id)
        summary = tools["summary"]
        counts = van["defect_counts"]
        clear_state = derive_clear_state(
            overdue=summary["overdue"],
            quarantined=summary["quarantined"],
            due_30=summary["due_30"],
            open_p1=counts["p1"],
            open_other_defects=counts["p2"] + counts["p3"],
        )
        tool_badge = summary["overdue"] + summary["quarantined"] + summary["due_30"]
        van_badge = counts["total"]
        return {
            "clear_state": clear_state,
            "tool_summary": summary,
            "tool_badge": tool_badge,
            "van_summary": {
                "vehicle_reg": van["vehicle_reg"],
                "daily_last_at": van["daily_last_at"],
                "daily_pass": van["daily_pass"],
                "monthly_last_at": van["monthly_last_at"],
                "defect_counts": counts,
                "empty_reason": van["empty_reason"],
                "assignment_conflict": van["assignment_conflict"],
            },
            "van_badge": van_badge,
            "tools_empty_reason": tools["empty_reason"],
        }
