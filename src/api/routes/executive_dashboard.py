"""Executive Dashboard API Routes.

Provides endpoints for executive-level KPI dashboards,
real-time metrics, and organizational health scoring.
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_current_user, get_db
from src.api.schemas.executive_dashboard import (
    DashboardSummaryResponse,
    ExecutiveDashboardResponse,
    VehicleGovernanceSummary,
)
from src.services.executive_dashboard import ExecutiveDashboardService

router = APIRouter(prefix="/executive-dashboard", tags=["Executive Dashboard"])


@router.get("", response_model=ExecutiveDashboardResponse)
async def get_executive_dashboard(
    period_days: int = Query(30, ge=7, le=365, description="Period in days for metrics"),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get complete executive dashboard with all KPIs.

    Returns a comprehensive view of organizational performance including:
    - Overall health score (0-100)
    - Module-specific summaries (incidents, near-misses, complaints, RTAs, risks)
    - KRI performance metrics
    - Policy compliance status
    - SLA performance
    - Trend data for charts
    - Active alerts requiring attention
    """
    service = ExecutiveDashboardService(db)
    dashboard = await service.get_full_dashboard(period_days)
    return dashboard


@router.get("/summary", response_model=DashboardSummaryResponse)
async def get_dashboard_summary(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get simplified dashboard summary for quick overview.

    Suitable for widgets or mobile views.
    """
    service = ExecutiveDashboardService(db)
    dashboard = await service.get_full_dashboard(30)

    # Calculate pending actions
    pending_actions = dashboard["incidents"]["open"] + dashboard["complaints"]["open"]

    # Calculate overdue items
    overdue_items = dashboard["compliance"]["overdue"]

    return DashboardSummaryResponse(
        health_score=dashboard["health_score"]["score"],
        health_status=dashboard["health_score"]["status"],
        open_incidents=dashboard["incidents"]["open"],
        pending_actions=pending_actions,
        overdue_items=overdue_items,
        kri_alerts=dashboard["kris"]["pending_alerts"],
    )


@router.get("/incidents")
async def get_incident_dashboard(
    period_days: int = Query(30, ge=7, le=365),
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get incident-specific dashboard data."""
    service = ExecutiveDashboardService(db)
    from datetime import datetime, timedelta, timezone

    cutoff = datetime.now(timezone.utc) - timedelta(days=period_days)

    summary = await service._get_incident_summary(cutoff)
    trends = await service._get_trends(period_days)

    return {
        "period_days": period_days,
        "summary": summary,
        "trends": trends.get("incidents_weekly", []),
    }


@router.get("/risks")
async def get_risk_dashboard(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get risk-specific dashboard data."""
    service = ExecutiveDashboardService(db)

    summary = await service._get_risk_summary()
    kri_summary = await service._get_kri_summary()

    return {
        "risks": summary,
        "kris": kri_summary,
    }


@router.get("/compliance")
async def get_compliance_dashboard(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get compliance-specific dashboard data."""
    service = ExecutiveDashboardService(db)

    compliance_summary = await service._get_compliance_summary()
    sla_summary = await service._get_sla_summary()

    return {
        "policy_acknowledgments": compliance_summary,
        "sla_performance": sla_summary,
    }


@router.get("/alerts")
async def get_active_alerts(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get all active alerts requiring attention."""
    service = ExecutiveDashboardService(db)
    alerts = await service._get_active_alerts()

    return {
        "total": len(alerts),
        "alerts": alerts,
    }


@router.get("/health-score")
async def get_health_score(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get current organizational health score."""
    service = ExecutiveDashboardService(db)
    dashboard = await service.get_full_dashboard(30)

    return dashboard["health_score"]


@router.get("/vehicle-governance", response_model=VehicleGovernanceSummary)
async def get_vehicle_governance(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Vehicle governance KPIs for the executive dashboard.

    Returns fleet compliance rates, defect counts, driver accountability
    metrics, and CAPA pipeline status.
    """
    from sqlalchemy import func, select

    from src.domain.models.capa import CAPAAction, CAPASource, CAPAStatus
    from src.domain.models.driver_profile import AcknowledgementStatus, DriverAcknowledgement, DriverProfile
    from src.domain.models.vehicle_defect import VehicleDefect
    from src.domain.models.vehicle_registry import ComplianceStatus, FleetStatus, VehicleRegistry

    total_q = select(func.count(VehicleRegistry.id))
    total = (await db.execute(total_q)).scalar() or 0

    active_q = select(func.count(VehicleRegistry.id)).where(VehicleRegistry.fleet_status == FleetStatus.ACTIVE)
    active = (await db.execute(active_q)).scalar() or 0

    compliant_q = select(func.count(VehicleRegistry.id)).where(
        VehicleRegistry.compliance_status == ComplianceStatus.COMPLIANT
    )
    compliant = (await db.execute(compliant_q)).scalar() or 0

    non_compliant_q = select(func.count(VehicleRegistry.id)).where(
        VehicleRegistry.compliance_status != ComplianceStatus.COMPLIANT
    )
    non_compliant = (await db.execute(non_compliant_q)).scalar() or 0

    compliance_rate = (compliant / total * 100) if total > 0 else 100.0

    open_statuses = ["open", "auto_detected", "acknowledged", "action_assigned"]
    open_defects_q = select(func.count(VehicleDefect.id)).where(VehicleDefect.status.in_(open_statuses))
    open_defects = (await db.execute(open_defects_q)).scalar() or 0

    p1_q = select(func.count(VehicleDefect.id)).where(
        VehicleDefect.priority == "P1",
        VehicleDefect.status.in_(open_statuses),
    )
    open_p1 = (await db.execute(p1_q)).scalar() or 0

    p2_q = select(func.count(VehicleDefect.id)).where(
        VehicleDefect.priority == "P2",
        VehicleDefect.status.in_(open_statuses),
    )
    open_p2 = (await db.execute(p2_q)).scalar() or 0

    overdue_q = select(func.count(VehicleRegistry.id)).where(
        VehicleRegistry.compliance_status == ComplianceStatus.OVERDUE_CHECK
    )
    overdue_checks = (await db.execute(overdue_q)).scalar() or 0

    active_drivers_q = select(func.count(DriverProfile.id)).where(DriverProfile.is_active_driver == True)  # noqa: E712
    active_drivers = (await db.execute(active_drivers_q)).scalar() or 0

    pending_ack_q = select(func.count(DriverAcknowledgement.id)).where(
        DriverAcknowledgement.status == AcknowledgementStatus.PENDING
    )
    pending_acks = (await db.execute(pending_ack_q)).scalar() or 0

    vehicle_capas_q = select(func.count(CAPAAction.id)).where(
        CAPAAction.source_type == CAPASource.VEHICLE_DEFECT.value,
        CAPAAction.status.in_([CAPAStatus.OPEN.value, CAPAStatus.IN_PROGRESS.value]),
    )
    open_vehicle_capas = (await db.execute(vehicle_capas_q)).scalar() or 0

    return VehicleGovernanceSummary(
        total_vehicles=total,
        active_vehicles=active,
        compliant_vehicles=compliant,
        non_compliant_vehicles=non_compliant,
        compliance_rate=round(compliance_rate, 1),
        open_defects=open_defects,
        open_p1_defects=open_p1,
        open_p2_defects=open_p2,
        overdue_checks=overdue_checks,
        active_drivers=active_drivers,
        pending_acknowledgements=pending_acks,
        open_vehicle_capas=open_vehicle_capas,
    )
