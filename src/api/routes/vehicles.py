"""Vehicle Registry API routes — fleet governance.

Provides fleet management endpoints: list vehicles, inspect individual
vehicles with defect history, compliance gate checks, fleet health analytics,
and vehicle status updates.
"""

import logging
import math
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import CurrentUser, DbSession
from pydantic import BaseModel

from src.api.schemas.vehicle_registry import (
    ComplianceGateResponse,
    FleetHealthResponse,
    VehicleDefectSummary,
    VehicleDetailResponse,
    VehicleListResponse,
    VehicleRegistryResponse,
    VehicleRegistryUpdate,
)
from src.domain.models.vehicle_defect import VehicleDefect
from src.domain.models.vehicle_registry import ComplianceStatus, FleetStatus, VehicleRegistry

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/", response_model=VehicleListResponse)
async def list_vehicles(
    db: DbSession,
    user: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=500),
    fleet_status: Optional[str] = None,
    compliance_status: Optional[str] = None,
    search: Optional[str] = None,
):
    """List fleet vehicles with optional filters and pagination."""
    query = select(VehicleRegistry)
    count_query = select(func.count(VehicleRegistry.id))

    if user.tenant_id:
        query = query.where(VehicleRegistry.tenant_id == user.tenant_id)
        count_query = count_query.where(VehicleRegistry.tenant_id == user.tenant_id)

    if fleet_status:
        try:
            fs = FleetStatus(fleet_status.lower())
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid fleet_status: {fleet_status}")
        query = query.where(VehicleRegistry.fleet_status == fs)
        count_query = count_query.where(VehicleRegistry.fleet_status == fs)

    if compliance_status:
        try:
            cs = ComplianceStatus(compliance_status.lower())
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid compliance_status: {compliance_status}")
        query = query.where(VehicleRegistry.compliance_status == cs)
        count_query = count_query.where(VehicleRegistry.compliance_status == cs)

    if search:
        pattern = f"%{search}%"
        query = query.where(VehicleRegistry.vehicle_reg.ilike(pattern))
        count_query = count_query.where(VehicleRegistry.vehicle_reg.ilike(pattern))

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    offset = (page - 1) * page_size
    query = query.order_by(VehicleRegistry.vehicle_reg).offset(offset).limit(page_size)
    result = await db.execute(query)
    vehicles = result.scalars().all()

    return VehicleListResponse(
        items=[VehicleRegistryResponse.model_validate(v) for v in vehicles],
        total=total,
        page=page,
        page_size=page_size,
        pages=max(1, math.ceil(total / page_size)),
    )


@router.get("/analytics/fleet-health", response_model=FleetHealthResponse)
async def fleet_health(db: DbSession, user: CurrentUser):
    """Fleet health summary — counts by fleet status and compliance status."""
    base = select(VehicleRegistry)
    if user.tenant_id:
        base = base.where(VehicleRegistry.tenant_id == user.tenant_id)

    total_q = select(func.count(VehicleRegistry.id))
    if user.tenant_id:
        total_q = total_q.where(VehicleRegistry.tenant_id == user.tenant_id)

    total = (await db.execute(total_q)).scalar() or 0

    fleet_counts_q = (
        select(
            VehicleRegistry.fleet_status,
            func.count(VehicleRegistry.id).label("cnt"),
        )
        .group_by(VehicleRegistry.fleet_status)
    )
    if user.tenant_id:
        fleet_counts_q = fleet_counts_q.where(VehicleRegistry.tenant_id == user.tenant_id)
    fleet_rows = (await db.execute(fleet_counts_q)).all()
    fleet_map = {str(r[0].value if hasattr(r[0], "value") else r[0]): r[1] for r in fleet_rows}

    comp_counts_q = (
        select(
            VehicleRegistry.compliance_status,
            func.count(VehicleRegistry.id).label("cnt"),
        )
        .group_by(VehicleRegistry.compliance_status)
    )
    if user.tenant_id:
        comp_counts_q = comp_counts_q.where(VehicleRegistry.tenant_id == user.tenant_id)
    comp_rows = (await db.execute(comp_counts_q)).all()
    comp_map = {str(r[0].value if hasattr(r[0], "value") else r[0]): r[1] for r in comp_rows}

    compliant_count = comp_map.get("compliant", 0)
    compliance_rate = (compliant_count / total * 100) if total > 0 else 100.0

    return FleetHealthResponse(
        total_vehicles=total,
        active=fleet_map.get("active", 0),
        vor=fleet_map.get("vor", 0),
        maintenance=fleet_map.get("maintenance", 0),
        decommissioned=fleet_map.get("decommissioned", 0),
        compliant=compliant_count,
        non_compliant=comp_map.get("non_compliant", 0),
        overdue_check=comp_map.get("overdue_check", 0),
        suspended=comp_map.get("suspended", 0),
        compliance_rate=round(compliance_rate, 1),
    )


@router.get("/{reg}", response_model=VehicleDetailResponse)
async def get_vehicle(reg: str, db: DbSession, user: CurrentUser):
    """Single vehicle detail with open defect history."""
    query = select(VehicleRegistry).where(VehicleRegistry.vehicle_reg == reg)
    if user.tenant_id:
        query = query.where(VehicleRegistry.tenant_id == user.tenant_id)
    result = await db.execute(query)
    vehicle = result.scalar_one_or_none()

    if vehicle is None:
        raise HTTPException(status_code=404, detail=f"Vehicle '{reg}' not found")

    defect_q = (
        select(VehicleDefect)
        .where(VehicleDefect.vehicle_reg == reg)
        .order_by(VehicleDefect.created_at.desc())
        .limit(50)
    )
    defect_result = await db.execute(defect_q)
    defects = defect_result.scalars().all()

    total_defect_q = select(func.count(VehicleDefect.id)).where(VehicleDefect.vehicle_reg == reg)
    total_defects = (await db.execute(total_defect_q)).scalar() or 0

    return VehicleDetailResponse(
        vehicle=VehicleRegistryResponse.model_validate(vehicle),
        open_defects=[VehicleDefectSummary.model_validate(d) for d in defects],
        total_defects=total_defects,
    )


@router.get("/{reg}/compliance", response_model=ComplianceGateResponse)
async def compliance_gate(reg: str, db: DbSession, user: CurrentUser):
    """Compliance gate check — can this vehicle be dispatched?"""
    query = select(VehicleRegistry).where(VehicleRegistry.vehicle_reg == reg)
    if user.tenant_id:
        query = query.where(VehicleRegistry.tenant_id == user.tenant_id)
    result = await db.execute(query)
    vehicle = result.scalar_one_or_none()

    if vehicle is None:
        raise HTTPException(status_code=404, detail=f"Vehicle '{reg}' not found")

    open_statuses = ["open", "auto_detected", "acknowledged", "action_assigned"]

    p1_q = select(func.count(VehicleDefect.id)).where(
        VehicleDefect.vehicle_reg == reg,
        VehicleDefect.priority == "P1",
        VehicleDefect.status.in_(open_statuses),
    )
    p2_q = select(func.count(VehicleDefect.id)).where(
        VehicleDefect.vehicle_reg == reg,
        VehicleDefect.priority == "P2",
        VehicleDefect.status.in_(open_statuses),
    )
    open_p1 = (await db.execute(p1_q)).scalar() or 0
    open_p2 = (await db.execute(p2_q)).scalar() or 0

    now = datetime.now(timezone.utc)
    checks_current = True
    if vehicle.last_daily_check_at:
        hours_since = (now - vehicle.last_daily_check_at).total_seconds() / 3600
        if hours_since > 24:
            checks_current = False
    else:
        checks_current = False

    compliant = (
        vehicle.compliance_status == ComplianceStatus.COMPLIANT
        and vehicle.fleet_status == FleetStatus.ACTIVE
        and open_p1 == 0
        and checks_current
    )

    reasons = []
    if vehicle.fleet_status != FleetStatus.ACTIVE:
        reasons.append(f"Fleet status: {vehicle.fleet_status.value}")
    if open_p1 > 0:
        reasons.append(f"{open_p1} open P1 defect(s)")
    if open_p2 > 0:
        reasons.append(f"{open_p2} open P2 defect(s)")
    if not checks_current:
        reasons.append("Daily check overdue")

    message = "Vehicle cleared for dispatch" if compliant else "; ".join(reasons)

    return ComplianceGateResponse(
        vehicle_reg=reg,
        compliant=compliant,
        compliance_status=vehicle.compliance_status.value,
        fleet_status=vehicle.fleet_status.value,
        open_p1_count=open_p1,
        open_p2_count=open_p2,
        checks_current=checks_current,
        message=message,
    )


@router.patch("/{reg}", response_model=VehicleRegistryResponse)
async def update_vehicle(
    reg: str,
    body: VehicleRegistryUpdate,
    db: DbSession,
    user: CurrentUser,
):
    """Update fleet status or assign a driver to a vehicle."""
    query = select(VehicleRegistry).where(VehicleRegistry.vehicle_reg == reg)
    if user.tenant_id:
        query = query.where(VehicleRegistry.tenant_id == user.tenant_id)
    result = await db.execute(query)
    vehicle = result.scalar_one_or_none()

    if vehicle is None:
        raise HTTPException(status_code=404, detail=f"Vehicle '{reg}' not found")

    if body.fleet_status is not None:
        try:
            vehicle.fleet_status = FleetStatus(body.fleet_status.lower())
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid fleet_status: {body.fleet_status}")

    if body.assigned_driver_id is not None:
        vehicle.assigned_driver_id = body.assigned_driver_id

    if body.asset_id is not None:
        vehicle.asset_id = body.asset_id

    await db.commit()
    await db.refresh(vehicle)

    return VehicleRegistryResponse.model_validate(vehicle)


# --- CAPA Pipeline ---


class DefectCAPARequest(BaseModel):
    defect_id: int


class DefectCAPAResponse(BaseModel):
    capa_id: int
    reference_number: str
    priority: str
    sla_days: int
    due_date: str


@router.post("/defects/create-capa", response_model=DefectCAPAResponse, status_code=status.HTTP_201_CREATED)
async def create_capa_from_defect(
    body: DefectCAPARequest,
    db: DbSession,
    user: CurrentUser,
):
    """Manually create a CAPA action from a vehicle defect."""
    defect_q = select(VehicleDefect).where(VehicleDefect.id == body.defect_id)
    defect_result = await db.execute(defect_q)
    defect = defect_result.scalar_one_or_none()

    if defect is None:
        raise HTTPException(status_code=404, detail=f"Defect {body.defect_id} not found")

    from src.domain.services.vehicle_capa_pipeline import create_capa_from_defect_async

    result = await create_capa_from_defect_async(
        defect_id=defect.id,
        defect_priority=defect.priority.value if hasattr(defect.priority, "value") else str(defect.priority),
        vehicle_reg=defect.vehicle_reg or "",
        check_field=defect.check_field,
        check_value=defect.check_value or "",
        user_id=user.id,
        tenant_id=user.tenant_id,
        db=db,
    )

    if result is None:
        raise HTTPException(status_code=409, detail="CAPA already exists for this defect")

    return DefectCAPAResponse(**result)


# --- Allocation Gate ---


class AllocationRequest(BaseModel):
    vehicle_reg: str
    driver_profile_id: int
    force: bool = False


@router.post("/allocate")
async def allocate_vehicle(
    body: AllocationRequest,
    db: DbSession,
    user: CurrentUser,
):
    """Allocate a vehicle to a driver with compliance gate enforcement.

    Set force=True to bypass the gate (admin override).
    """
    from src.domain.services.allocation_gate import allocate_vehicle_to_driver

    result = await allocate_vehicle_to_driver(
        db=db,
        vehicle_reg=body.vehicle_reg,
        driver_profile_id=body.driver_profile_id,
        tenant_id=user.tenant_id,
        force=body.force,
    )
    if not result["allocated"]:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=result,
        )
    return result


class BatchGateRequest(BaseModel):
    vehicle_regs: list[str]


@router.post("/compliance/batch")
async def batch_compliance_check(
    body: BatchGateRequest,
    db: DbSession,
    user: CurrentUser,
):
    """Check compliance gate for multiple vehicles at once."""
    from src.domain.services.allocation_gate import check_allocation

    results = []
    for reg in body.vehicle_regs[:50]:
        decision = await check_allocation(db, reg, user.tenant_id)
        results.append(decision.to_dict())
    return {"results": results, "total": len(results)}
