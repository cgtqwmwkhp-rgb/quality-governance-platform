"""IMS Dashboard service – aggregates data from all management system modules.

Extracts database operations from the API route layer into a reusable
service class that can be consumed by routes, CLI commands, or background
tasks without coupling to FastAPI / HTTP concerns.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class IMSDashboardService:
    """Reads cross-module IMS data from the database."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ------------------------------------------------------------------
    # Standards compliance
    # ------------------------------------------------------------------

    async def get_standards_compliance(self) -> list[dict[str, Any]]:
        """Return compliance scores for every active standard."""
        from src.domain.models.standard import Clause, Control, Standard

        result = await self._db.execute(
            select(Standard).where(Standard.is_active == True).order_by(Standard.code)
        )
        standards = list(result.scalars().all())

        scores: list[dict[str, Any]] = []
        for std in standards:
            control_query = (
                select(Control)
                .join(Clause, Control.clause_id == Clause.id)
                .where(Clause.standard_id == std.id)
                .where(Control.is_active == True)
                .where(Control.is_applicable == True)
            )
            control_result = await self._db.execute(control_query)
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
                    "compliance_percentage": round(
                        ((implemented + partial * 0.5) / max(total, 1)) * 100, 1
                    ),
                    "setup_required": total == 0,
                }
            )

        return scores

    # ------------------------------------------------------------------
    # ISO 27001 ISMS
    # ------------------------------------------------------------------

    async def get_isms_data(self) -> dict[str, Any]:
        """Return ISO 27001 ISMS dashboard data."""
        from src.domain.models.iso27001 import (
            InformationAsset,
            InformationSecurityRisk,
            ISO27001Control,
            SecurityIncident,
            SupplierSecurityAssessment,
        )

        total_assets = await self._count(
            select(InformationAsset).where(InformationAsset.is_active == True)
        )
        critical_assets = await self._count(
            select(InformationAsset).where(
                InformationAsset.is_active == True,
                InformationAsset.criticality == "critical",
            )
        )

        total_controls = await self._count(select(ISO27001Control))
        applicable_controls = await self._count(
            select(ISO27001Control).where(ISO27001Control.is_applicable == True)
        )
        implemented_controls = await self._count(
            select(ISO27001Control).where(
                ISO27001Control.implementation_status == "implemented"
            )
        )

        open_risks = await self._count(
            select(InformationSecurityRisk).where(
                InformationSecurityRisk.status != "closed"
            )
        )
        high_risks = await self._count(
            select(InformationSecurityRisk).where(
                InformationSecurityRisk.residual_risk_score > 16,
                InformationSecurityRisk.status != "closed",
            )
        )

        open_incidents = await self._count(
            select(SecurityIncident).where(SecurityIncident.status == "open")
        )
        incidents_30d = await self._count(
            select(SecurityIncident).where(
                SecurityIncident.detected_date >= datetime.utcnow() - timedelta(days=30)
            )
        )

        high_risk_suppliers = await self._count(
            select(SupplierSecurityAssessment).where(
                SupplierSecurityAssessment.risk_level == "high",
                SupplierSecurityAssessment.status == "active",
            )
        )

        domains = await self._get_annex_a_domains(ISO27001Control)
        recent_incidents = await self._get_recent_incidents(SecurityIncident)

        return {
            "assets": {"total": total_assets, "critical": critical_assets},
            "controls": {
                "total": total_controls,
                "applicable": applicable_controls,
                "implemented": implemented_controls,
                "implementation_percentage": round(
                    (implemented_controls / max(applicable_controls, 1)) * 100, 1
                ),
            },
            "risks": {"open": open_risks, "high_critical": high_risks},
            "incidents": {"open": open_incidents, "last_30_days": incidents_30d},
            "suppliers": {"high_risk": high_risk_suppliers},
            "compliance_score": round(
                (implemented_controls / max(applicable_controls, 1)) * 100, 1
            ),
            "domains": domains,
            "recent_incidents": recent_incidents,
        }

    async def _get_annex_a_domains(self, control_model: Any) -> list[dict[str, Any]]:
        domain_names_result = await self._db.execute(
            select(control_model.domain).distinct()
        )
        domains: list[dict[str, Any]] = []
        for (domain_name,) in domain_names_result:
            d_name = domain_name or "Unknown"
            d_total = await self._count(
                select(control_model).where(control_model.domain == domain_name)
            )
            d_impl = await self._count(
                select(control_model).where(
                    control_model.domain == domain_name,
                    control_model.implementation_status == "implemented",
                )
            )
            domains.append(
                {
                    "domain": d_name,
                    "total": d_total,
                    "implemented": d_impl,
                    "percentage": round((d_impl / max(d_total, 1)) * 100, 1),
                }
            )
        return domains

    async def _get_recent_incidents(self, incident_model: Any) -> list[dict[str, Any]]:
        result = await self._db.execute(
            select(incident_model)
            .where(
                incident_model.detected_date
                >= datetime.utcnow() - timedelta(days=30)
            )
            .order_by(incident_model.detected_date.desc())
            .limit(10)
        )
        return [
            {
                "id": inc.incident_id,
                "title": inc.title,
                "incident_type": inc.incident_type,
                "severity": inc.severity,
                "status": inc.status,
                "date": inc.detected_date.isoformat() if inc.detected_date else None,
            }
            for inc in result.scalars().all()
        ]

    # ------------------------------------------------------------------
    # UVDB Achilles
    # ------------------------------------------------------------------

    async def get_uvdb_data(self) -> dict[str, Any]:
        """Return UVDB audit dashboard summary."""
        from src.domain.models.uvdb_achilles import UVDBAudit

        total_audits = await self._count(select(UVDBAudit))
        active_audits = await self._count(
            select(UVDBAudit).where(
                UVDBAudit.status.in_(["scheduled", "in_progress"])
            )
        )

        completed_result = await self._db.execute(
            select(UVDBAudit).where(
                UVDBAudit.status == "completed",
                UVDBAudit.percentage_score.isnot(None),
            )
        )
        completed = list(completed_result.scalars().all())

        avg_score = 0.0
        latest_score = None
        if completed:
            avg_score = sum(a.percentage_score for a in completed) / len(completed)
            latest = sorted(
                completed,
                key=lambda a: a.created_at or datetime.min,
                reverse=True,
            )
            latest_score = latest[0].percentage_score if latest else None

        return {
            "total_audits": total_audits,
            "active_audits": active_audits,
            "completed_audits": len(completed),
            "average_score": round(avg_score, 1),
            "latest_score": latest_score,
            "status": (
                "active"
                if active_audits > 0
                else ("completed" if completed else "not_started")
            ),
        }

    # ------------------------------------------------------------------
    # Planet Mark carbon
    # ------------------------------------------------------------------

    async def get_planet_mark_data(self) -> dict[str, Any]:
        """Return Planet Mark carbon dashboard summary."""
        from src.domain.models.planet_mark import CarbonReportingYear

        result = await self._db.execute(
            select(CarbonReportingYear)
            .order_by(desc(CarbonReportingYear.year_number))
            .limit(2)
        )
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
        total_emissions = (
            (current.scope1_total or 0)
            + (current.scope2_total or 0)
            + (current.scope3_total or 0)
        )

        reduction = None
        if len(years) >= 2:
            prev = years[1]
            prev_total = (
                (prev.scope1_total or 0)
                + (prev.scope2_total or 0)
                + (prev.scope3_total or 0)
            )
            if prev_total > 0:
                reduction = round(
                    ((prev_total - total_emissions) / prev_total) * 100, 1
                )

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

    # ------------------------------------------------------------------
    # Compliance evidence coverage
    # ------------------------------------------------------------------

    async def get_compliance_coverage(self) -> dict[str, Any]:
        """Return compliance evidence coverage statistics."""
        from src.domain.models.compliance_evidence import ComplianceEvidenceLink
        from src.domain.services.iso_compliance_service import (
            EvidenceLink,
            iso_compliance_service,
        )

        result = await self._db.execute(select(ComplianceEvidenceLink))
        links_raw = list(result.scalars().all())

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

    # ------------------------------------------------------------------
    # Audit schedule
    # ------------------------------------------------------------------

    async def get_audit_schedule(self) -> list[dict[str, Any]]:
        """Return upcoming/active audits."""
        from src.domain.models.audit import AuditRun

        result = await self._db.execute(
            select(AuditRun)
            .where(AuditRun.status.in_(["draft", "scheduled", "in_progress"]))
            .order_by(AuditRun.scheduled_date.asc().nulls_last())
            .limit(10)
        )
        return [
            {
                "id": run.id,
                "reference_number": run.reference_number,
                "title": run.title,
                "status": run.status,
                "scheduled_date": (
                    run.scheduled_date.isoformat() if run.scheduled_date else None
                ),
                "due_date": run.due_date.isoformat() if run.due_date else None,
            }
            for run in result.scalars().all()
        ]

    # ------------------------------------------------------------------
    # Full dashboard aggregate
    # ------------------------------------------------------------------

    async def get_dashboard(self) -> dict[str, Any]:
        """Build the complete IMS dashboard response.

        Each sub-query is wrapped in try/except so one failing module
        doesn't break the entire dashboard.
        """
        from sqlalchemy.exc import (
            OperationalError,
            ProgrammingError,
            SQLAlchemyError,
        )

        response: dict[str, Any] = {
            "generated_at": datetime.utcnow().isoformat(),
        }

        # Standards compliance
        try:
            response["standards"] = await self.get_standards_compliance()
        except SQLAlchemyError:
            logger.warning("IMS dashboard: standards query failed", exc_info=True)
            response["standards"] = []
            response["standards_error"] = "Unable to load standards data"

        standards_with_data = [
            s for s in response.get("standards", []) if not s.get("setup_required")
        ]
        if standards_with_data:
            response["overall_compliance"] = round(
                sum(s["compliance_percentage"] for s in standards_with_data)
                / len(standards_with_data),
                1,
            )
        else:
            response["overall_compliance"] = 0

        # ISO 27001 ISMS
        try:
            response["isms"] = await self.get_isms_data()
        except (ProgrammingError, OperationalError):
            logger.warning("IMS dashboard: ISMS tables not available", exc_info=True)
            response["isms"] = None
            response["isms_error"] = "ISO 27001 module not configured"
        except SQLAlchemyError:
            logger.warning("IMS dashboard: ISMS query failed", exc_info=True)
            response["isms"] = None
            response["isms_error"] = "Unable to load ISMS data"

        # UVDB Achilles
        try:
            response["uvdb"] = await self.get_uvdb_data()
        except (ProgrammingError, OperationalError):
            logger.warning("IMS dashboard: UVDB tables not available", exc_info=True)
            response["uvdb"] = None
            response["uvdb_error"] = "UVDB module not configured"
        except SQLAlchemyError:
            logger.warning("IMS dashboard: UVDB query failed", exc_info=True)
            response["uvdb"] = None
            response["uvdb_error"] = "Unable to load UVDB data"

        # Planet Mark
        try:
            response["planet_mark"] = await self.get_planet_mark_data()
        except (ProgrammingError, OperationalError):
            logger.warning(
                "IMS dashboard: Planet Mark tables not available", exc_info=True
            )
            response["planet_mark"] = None
            response["planet_mark_error"] = "Planet Mark module not configured"
        except SQLAlchemyError:
            logger.warning("IMS dashboard: Planet Mark query failed", exc_info=True)
            response["planet_mark"] = None
            response["planet_mark_error"] = "Unable to load Planet Mark data"

        # Compliance coverage
        try:
            response["compliance_coverage"] = await self.get_compliance_coverage()
        except SQLAlchemyError:
            logger.warning(
                "IMS dashboard: compliance coverage failed", exc_info=True
            )
            response["compliance_coverage"] = None
            response["compliance_coverage_error"] = "Unable to load compliance data"

        # Audit schedule
        try:
            response["audit_schedule"] = await self.get_audit_schedule()
        except SQLAlchemyError:
            logger.warning("IMS dashboard: audit schedule failed", exc_info=True)
            response["audit_schedule"] = []
            response["audit_schedule_error"] = "Unable to load audit schedule"

        return response

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _count(self, sub_select: Any) -> int:
        """Execute ``SELECT count(*) FROM (<sub_select>)``."""
        value = await self._db.scalar(
            select(func.count()).select_from(sub_select.subquery())
        )
        return value or 0
