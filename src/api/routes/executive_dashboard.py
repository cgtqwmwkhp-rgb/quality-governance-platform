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
    from datetime import datetime, timedelta

    cutoff = datetime.utcnow() - timedelta(days=period_days)

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
