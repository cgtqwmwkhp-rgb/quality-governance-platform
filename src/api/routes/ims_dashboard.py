"""
IMS (Integrated Management System) Dashboard API Route

Aggregates data from multiple management system modules:
- Standards Library (compliance scores per standard)
- ISO 27001 ISMS (assets, controls, risks, incidents, suppliers)
- UVDB Achilles Verify B2 (audit status, scores)
- Planet Mark Carbon Management (emissions, certification)
- Compliance Evidence (coverage statistics)

Each sub-query is wrapped in try/except so one failing module
doesn't break the entire dashboard response.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError, ProgrammingError, SQLAlchemyError

from fastapi import Depends

from src.api.dependencies import CurrentUser, DbSession
from src.api.dependencies.request_context import get_request_id
from src.infrastructure.monitoring.azure_monitor import track_metric

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ims", tags=["IMS Dashboard"])


class IMSDashboardResponse(BaseModel):
    model_config = {"extra": "allow"}

    generated_at: str
    overall_compliance: float = 0


async def _get_standards_compliance(db: Any) -> list[dict]:
    """Query compliance scores for all active standards."""
    from src.domain.models.standard import Clause, Control, Standard

    result = await db.execute(select(Standard).where(Standard.is_active == True).order_by(Standard.code))
    standards = list(result.scalars().all())

    scores = []
    for std in standards:
        control_query = (
            select(Control)
            .join(Clause, Control.clause_id == Clause.id)
            .where(Clause.standard_id == std.id)
            .where(Control.is_active == True)
            .where(Control.is_applicable == True)
        )
        control_result = await db.execute(control_query)
        controls = list(control_result.scalars().all())

        total = len(controls)
        implemented = sum(1 for c in controls if c.implementation_status == "implemented")
        partial = sum(1 for c in controls if c.implementation_status == "partial")
        not_impl = total - implemented - partial

        scores.append(
            {
                "standard_id": std.id,
                "standard_code": std.code,
                "standard_name": std.name,
                "full_name": std.full_name,
                "version": std.version,
                "total_controls": total,
                "implemented_count": implemented,
                "partial_count": partial,
                "not_implemented_count": not_impl,
                "compliance_percentage": round(((implemented + partial * 0.5) / max(total, 1)) * 100, 1),
                "setup_required": total == 0,
            }
        )

    return scores


async def _get_isms_data(db: Any) -> dict:
    """Query ISO 27001 ISMS dashboard data."""
    from src.domain.models.iso27001 import (
        InformationAsset,
        InformationSecurityRisk,
        ISO27001Control,
        SecurityIncident,
        SupplierSecurityAssessment,
    )

    total_assets = (
        await db.scalar(
            select(func.count()).select_from(
                select(InformationAsset).where(InformationAsset.is_active == True).subquery()
            )
        )
        or 0
    )
    critical_assets = (
        await db.scalar(
            select(func.count()).select_from(
                select(InformationAsset)
                .where(
                    InformationAsset.is_active == True,
                    InformationAsset.criticality == "critical",
                )
                .subquery()
            )
        )
        or 0
    )

    total_controls = await db.scalar(select(func.count()).select_from(ISO27001Control)) or 0
    applicable_controls = (
        await db.scalar(
            select(func.count()).select_from(
                select(ISO27001Control).where(ISO27001Control.is_applicable == True).subquery()
            )
        )
        or 0
    )
    implemented_controls = (
        await db.scalar(
            select(func.count()).select_from(
                select(ISO27001Control).where(ISO27001Control.implementation_status == "implemented").subquery()
            )
        )
        or 0
    )

    open_risks = (
        await db.scalar(
            select(func.count()).select_from(
                select(InformationSecurityRisk).where(InformationSecurityRisk.status != "closed").subquery()
            )
        )
        or 0
    )
    high_risks = (
        await db.scalar(
            select(func.count()).select_from(
                select(InformationSecurityRisk)
                .where(
                    InformationSecurityRisk.residual_risk_score > 16,
                    InformationSecurityRisk.status != "closed",
                )
                .subquery()
            )
        )
        or 0
    )

    open_incidents = (
        await db.scalar(
            select(func.count()).select_from(
                select(SecurityIncident).where(SecurityIncident.status == "open").subquery()
            )
        )
        or 0
    )
    incidents_30d = (
        await db.scalar(
            select(func.count()).select_from(
                select(SecurityIncident)
                .where(SecurityIncident.detected_date >= datetime.now(timezone.utc) - timedelta(days=30))
                .subquery()
            )
        )
        or 0
    )

    high_risk_suppliers = (
        await db.scalar(
            select(func.count()).select_from(
                select(SupplierSecurityAssessment)
                .where(
                    SupplierSecurityAssessment.risk_level == "high",
                    SupplierSecurityAssessment.status == "active",
                )
                .subquery()
            )
        )
        or 0
    )

    # Annex A domain breakdown
    domains = []
    domain_names_result = await db.execute(select(ISO27001Control.domain).distinct())
    for (domain_name,) in domain_names_result:
        d_name = domain_name or "Unknown"
        d_total = (
            await db.scalar(
                select(func.count()).select_from(
                    select(ISO27001Control).where(ISO27001Control.domain == domain_name).subquery()
                )
            )
            or 0
        )
        d_impl = (
            await db.scalar(
                select(func.count()).select_from(
                    select(ISO27001Control)
                    .where(
                        ISO27001Control.domain == domain_name,
                        ISO27001Control.implementation_status == "implemented",
                    )
                    .subquery()
                )
            )
            or 0
        )
        domains.append(
            {
                "domain": d_name,
                "total": d_total,
                "implemented": d_impl,
                "percentage": round((d_impl / max(d_total, 1)) * 100, 1),
            }
        )

    # Recent security incidents
    incident_result = await db.execute(
        select(SecurityIncident)
        .where(SecurityIncident.detected_date >= datetime.now(timezone.utc) - timedelta(days=30))
        .order_by(SecurityIncident.detected_date.desc())
        .limit(10)
    )
    recent_incidents = []
    for inc in incident_result.scalars().all():
        recent_incidents.append(
            {
                "id": inc.incident_id,
                "title": inc.title,
                "incident_type": inc.incident_type,
                "severity": inc.severity,
                "status": inc.status,
                "date": inc.detected_date.isoformat() if inc.detected_date else None,
            }
        )

    return {
        "assets": {"total": total_assets, "critical": critical_assets},
        "controls": {
            "total": total_controls,
            "applicable": applicable_controls,
            "implemented": implemented_controls,
            "implementation_percentage": round((implemented_controls / max(applicable_controls, 1)) * 100, 1),
        },
        "risks": {"open": open_risks, "high_critical": high_risks},
        "incidents": {"open": open_incidents, "last_30_days": incidents_30d},
        "suppliers": {"high_risk": high_risk_suppliers},
        "compliance_score": round((implemented_controls / max(applicable_controls, 1)) * 100, 1),
        "domains": domains,
        "recent_incidents": recent_incidents,
    }


async def _get_uvdb_data(db: Any) -> dict:
    """Query UVDB dashboard summary."""
    from src.domain.models.uvdb_achilles import UVDBAudit

    total_audits = await db.scalar(select(func.count()).select_from(UVDBAudit)) or 0

    active_audits = (
        await db.scalar(
            select(func.count()).select_from(
                select(UVDBAudit).where(UVDBAudit.status.in_(["scheduled", "in_progress"])).subquery()
            )
        )
        or 0
    )

    completed_result = await db.execute(
        select(UVDBAudit).where(UVDBAudit.status == "completed", UVDBAudit.percentage_score.isnot(None))
    )
    completed = list(completed_result.scalars().all())

    avg_score = 0.0
    latest_score = None
    if completed:
        avg_score = sum(a.percentage_score for a in completed) / len(completed)
        latest = sorted(completed, key=lambda a: a.created_at or datetime.min, reverse=True)
        latest_score = latest[0].percentage_score if latest else None

    return {
        "total_audits": total_audits,
        "active_audits": active_audits,
        "completed_audits": len(completed),
        "average_score": round(avg_score, 1),
        "latest_score": latest_score,
        "status": ("active" if active_audits > 0 else ("completed" if completed else "not_started")),
    }


async def _get_planet_mark_data(db: Any) -> dict:
    """Query Planet Mark carbon dashboard summary."""
    from sqlalchemy import desc

    from src.domain.models.planet_mark import CarbonReportingYear

    result = await db.execute(select(CarbonReportingYear).order_by(desc(CarbonReportingYear.year_number)).limit(2))
    years = list(result.scalars().all())

    if not years:
        return {
            "status": "not_configured",
            "current_year": None,
            "total_emissions": None,
            "certification_status": None,
            "reduction_vs_previous": None,
        }

    current = years[0]
    total_emissions = (current.scope1_total or 0) + (current.scope2_total or 0) + (current.scope3_total or 0)

    reduction = None
    if len(years) >= 2:
        prev = years[1]
        prev_total = (prev.scope1_total or 0) + (prev.scope2_total or 0) + (prev.scope3_total or 0)
        if prev_total > 0:
            reduction = round(((prev_total - total_emissions) / prev_total) * 100, 1)

    return {
        "status": "active",
        "current_year": current.year_number,
        "total_emissions": round(total_emissions, 2),
        "certification_status": current.certification_status or "pending",
        "reduction_vs_previous": reduction,
        "scope1": round(current.scope1_total or 0, 2),
        "scope2": round(current.scope2_total or 0, 2),
        "scope3": round(current.scope3_total or 0, 2),
    }


async def _get_compliance_coverage(db: Any) -> dict:
    """Query compliance evidence coverage."""
    from src.domain.models.compliance_evidence import ComplianceEvidenceLink
    from src.domain.services.iso_compliance_service import iso_compliance_service

    result = await db.execute(select(ComplianceEvidenceLink))
    links_raw = list(result.scalars().all())

    from src.domain.services.iso_compliance_service import EvidenceLink

    links = [
        EvidenceLink(
            id=str(lnk.id),
            entity_type=lnk.entity_type,
            entity_id=lnk.entity_id,
            clause_id=lnk.clause_id,
            linked_by=lnk.linked_by or "manual",
            confidence=lnk.confidence,
        )
        for lnk in links_raw
    ]

    coverage = iso_compliance_service.calculate_compliance_coverage(links, None)
    return {
        "total_clauses": coverage.get("total_clauses", 0),
        "covered_clauses": coverage.get("covered_clauses", 0),
        "coverage_percentage": coverage.get("coverage_percentage", 0),
        "gaps": coverage.get("gaps", 0),
        "total_evidence_links": len(links),
    }


async def _get_audit_schedule(db: Any) -> list[dict]:
    """Query upcoming audits from the audit system."""
    from src.domain.models.audit import AuditRun

    result = await db.execute(
        select(AuditRun)
        .where(AuditRun.status.in_(["draft", "scheduled", "in_progress"]))
        .order_by(AuditRun.scheduled_date.asc().nulls_last())
        .limit(10)
    )
    audits = []
    for run in result.scalars().all():
        audits.append(
            {
                "id": run.id,
                "reference_number": run.reference_number,
                "title": run.title,
                "status": run.status,
                "scheduled_date": (run.scheduled_date.isoformat() if run.scheduled_date else None),
                "due_date": run.due_date.isoformat() if run.due_date else None,
            }
        )
    return audits


@router.get("/dashboard", response_model=IMSDashboardResponse)
async def get_ims_dashboard(
    db: DbSession,
    current_user: CurrentUser,
    request_id: str = Depends(get_request_id),
) -> dict[str, Any]:
    """
    Get unified IMS dashboard aggregating data from all management system modules.

    Returns compliance scores, ISMS data, UVDB audit status, Planet Mark carbon data,
    compliance evidence coverage, and upcoming audit schedule.
    """
    track_metric("ims_dashboard.loaded")
    response: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    # Standards compliance scores
    try:
        response["standards"] = await _get_standards_compliance(db)
    except SQLAlchemyError as e:
        logger.warning(
            "IMS dashboard: standards query failed [request_id=%s]: %s",
            request_id,
            type(e).__name__,
            exc_info=True,
        )
        response["standards"] = []
        response["standards_error"] = "Unable to load standards data"

    # Overall compliance (average across standards with data)
    standards_with_data = [s for s in response.get("standards", []) if not s.get("setup_required")]
    if standards_with_data:
        response["overall_compliance"] = round(
            sum(s["compliance_percentage"] for s in standards_with_data) / len(standards_with_data),
            1,
        )
    else:
        response["overall_compliance"] = 0

    # ISO 27001 ISMS
    try:
        response["isms"] = await _get_isms_data(db)
    except (ProgrammingError, OperationalError) as e:
        logger.warning(
            "IMS dashboard: ISMS tables not available [request_id=%s]: %s",
            request_id,
            type(e).__name__,
            exc_info=True,
        )
        response["isms"] = None
        response["isms_error"] = "ISO 27001 module not configured"
    except SQLAlchemyError as e:
        logger.warning(
            "IMS dashboard: ISMS query failed [request_id=%s]: %s",
            request_id,
            type(e).__name__,
            exc_info=True,
        )
        response["isms"] = None
        response["isms_error"] = "Unable to load ISMS data"

    # UVDB Achilles
    try:
        response["uvdb"] = await _get_uvdb_data(db)
    except (ProgrammingError, OperationalError) as e:
        logger.warning(
            "IMS dashboard: UVDB tables not available [request_id=%s]: %s",
            request_id,
            type(e).__name__,
            exc_info=True,
        )
        response["uvdb"] = None
        response["uvdb_error"] = "UVDB module not configured"
    except SQLAlchemyError as e:
        logger.warning(
            "IMS dashboard: UVDB query failed [request_id=%s]: %s",
            request_id,
            type(e).__name__,
            exc_info=True,
        )
        response["uvdb"] = None
        response["uvdb_error"] = "Unable to load UVDB data"

    # Planet Mark
    try:
        response["planet_mark"] = await _get_planet_mark_data(db)
    except (ProgrammingError, OperationalError) as e:
        logger.warning(
            "IMS dashboard: Planet Mark tables not available [request_id=%s]: %s",
            request_id,
            type(e).__name__,
            exc_info=True,
        )
        response["planet_mark"] = None
        response["planet_mark_error"] = "Planet Mark module not configured"
    except SQLAlchemyError as e:
        logger.warning(
            "IMS dashboard: Planet Mark query failed [request_id=%s]: %s",
            request_id,
            type(e).__name__,
            exc_info=True,
        )
        response["planet_mark"] = None
        response["planet_mark_error"] = "Unable to load Planet Mark data"

    # Compliance coverage
    try:
        response["compliance_coverage"] = await _get_compliance_coverage(db)
    except SQLAlchemyError as e:
        logger.warning(
            "IMS dashboard: compliance coverage failed [request_id=%s]: %s",
            request_id,
            type(e).__name__,
            exc_info=True,
        )
        response["compliance_coverage"] = None
        response["compliance_coverage_error"] = "Unable to load compliance data"

    # Audit schedule
    try:
        response["audit_schedule"] = await _get_audit_schedule(db)
    except SQLAlchemyError as e:
        logger.warning(
            "IMS dashboard: audit schedule failed [request_id=%s]: %s",
            request_id,
            type(e).__name__,
            exc_info=True,
        )
        response["audit_schedule"] = []
        response["audit_schedule_error"] = "Unable to load audit schedule"

    return response
