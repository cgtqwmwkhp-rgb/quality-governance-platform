"""ISO 27001 Information Security business logic.

Encapsulates risk score calculation, SoA compliance percentage,
control implementation percentage computation, and all ISMS
data operations (assets, controls, risks, incidents, suppliers, dashboard).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.utils.pagination import PaginationParams, paginate
from src.domain.exceptions import NotFoundError
from src.domain.models.iso27001 import (
    InformationAsset,
    InformationSecurityRisk,
    ISO27001Control,
    SecurityIncident,
    StatementOfApplicability,
    SupplierSecurityAssessment,
)
from src.infrastructure.monitoring.azure_monitor import track_metric


async def _get_entity(db: AsyncSession, model: type, entity_id: int, *, tenant_id: int | None = None) -> Any:
    """Fetch entity by PK or raise ``NotFoundError``."""
    stmt = select(model).where(model.id == entity_id)  # type: ignore[attr-defined]
    if tenant_id is not None:
        stmt = stmt.where(model.tenant_id == tenant_id)  # type: ignore[attr-defined]
    result = await db.execute(stmt)
    entity = result.scalar_one_or_none()
    if entity is None:
        raise NotFoundError(f"{model.__name__} with ID {entity_id} not found")
    return entity


class ISO27001Service:
    """Business logic and data operations for ISO 27001 ISMS."""

    # ---- Pure calculations (no DB) ----

    @staticmethod
    def calculate_risk_scores(likelihood: int, impact: int) -> tuple[int, int]:
        """Calculate inherent and residual risk scores.

        Returns *(inherent_score, residual_score)* where residual assumes
        one level of mitigation on both likelihood and impact axes.
        """
        inherent = likelihood * impact
        residual = max((likelihood - 1) * (impact - 1), 1)
        return inherent, residual

    @staticmethod
    def calculate_soa_compliance_percentage(implemented: int, applicable: int) -> float:
        """Percentage of applicable controls that are fully implemented."""
        return round((implemented / max(applicable, 1)) * 100, 1)

    @staticmethod
    def calculate_implementation_percentage(implemented: int, total: int, excluded: int) -> float:
        """Percentage of non-excluded controls that are implemented."""
        denominator = max(total - excluded, 1)
        return round((implemented / denominator) * 100, 1)

    # ---- Asset operations ----

    @staticmethod
    async def generate_asset_id(db: AsyncSession) -> str:
        """Generate next sequential asset ID (ASSET-NNNNN)."""
        result = await db.execute(select(func.count()).select_from(InformationAsset))
        count = result.scalar_one()
        return f"ASSET-{(count + 1):05d}"

    @staticmethod
    async def list_assets(
        db: AsyncSession,
        tenant_id: int,
        params: PaginationParams,
        *,
        asset_type: str | None = None,
        classification: str | None = None,
        department: str | None = None,
        criticality: str | None = None,
    ) -> dict[str, Any]:
        stmt = select(InformationAsset).where(
            InformationAsset.is_active == True,  # noqa: E712
            InformationAsset.tenant_id == tenant_id,
        )
        if asset_type:
            stmt = stmt.where(InformationAsset.asset_type == asset_type)
        if classification:
            stmt = stmt.where(InformationAsset.classification == classification)
        if department:
            stmt = stmt.where(InformationAsset.department == department)
        if criticality:
            stmt = stmt.where(InformationAsset.criticality == criticality)

        query = stmt.order_by(InformationAsset.criticality.desc())
        paginated = await paginate(db, query, params)

        return {
            "total": paginated.total,
            "page": paginated.page,
            "page_size": paginated.page_size,
            "pages": paginated.pages,
            "assets": [
                {
                    "id": a.id,
                    "asset_id": a.asset_id,
                    "name": a.name,
                    "asset_type": a.asset_type,
                    "classification": a.classification,
                    "criticality": a.criticality,
                    "owner_name": a.owner_name,
                    "department": a.department,
                    "cia_score": (
                        int(a.confidentiality_requirement or 0)
                        + int(a.integrity_requirement or 0)
                        + int(a.availability_requirement or 0)
                    ),
                }
                for a in paginated.items
            ],
        }

    @staticmethod
    async def create_asset(
        db: AsyncSession,
        tenant_id: int,
        asset_data: dict[str, Any],
    ) -> dict[str, Any]:
        asset_id = await ISO27001Service.generate_asset_id(db)
        asset = InformationAsset(
            asset_id=asset_id,
            next_review_date=datetime.now(timezone.utc) + timedelta(days=365),
            tenant_id=tenant_id,
            **asset_data,
        )
        db.add(asset)
        await db.commit()
        await db.refresh(asset)
        track_metric("iso27001.assets_created", 1)
        return {"id": asset.id, "asset_id": asset_id, "message": "Asset created"}

    @staticmethod
    async def get_asset(
        db: AsyncSession,
        asset_id: int,
        tenant_id: int,
    ) -> dict[str, Any]:
        asset = await _get_entity(db, InformationAsset, asset_id, tenant_id=tenant_id)
        return {
            "id": asset.id,
            "asset_id": asset.asset_id,
            "name": asset.name,
            "description": asset.description,
            "asset_type": asset.asset_type,
            "classification": asset.classification,
            "handling_requirements": asset.handling_requirements,
            "owner_name": asset.owner_name,
            "custodian_name": asset.custodian_name,
            "department": asset.department,
            "location": asset.location,
            "physical_location": asset.physical_location,
            "logical_location": asset.logical_location,
            "criticality": asset.criticality,
            "business_value": asset.business_value,
            "confidentiality_requirement": asset.confidentiality_requirement,
            "integrity_requirement": asset.integrity_requirement,
            "availability_requirement": asset.availability_requirement,
            "cia_score": (
                int(asset.confidentiality_requirement or 0)
                + int(asset.integrity_requirement or 0)
                + int(asset.availability_requirement or 0)
            ),
            "dependencies": asset.dependencies,
            "dependent_processes": asset.dependent_processes,
            "applied_controls": asset.applied_controls,
            "status": asset.status,
            "last_review_date": asset.last_review_date.isoformat() if asset.last_review_date else None,
            "next_review_date": asset.next_review_date.isoformat() if asset.next_review_date else None,
        }

    # ---- Controls ----

    @staticmethod
    async def list_controls(
        db: AsyncSession,
        params: PaginationParams,
        *,
        domain: str | None = None,
        implementation_status: str | None = None,
        is_applicable: bool | None = None,
    ) -> dict[str, Any]:
        stmt = select(ISO27001Control)
        if domain:
            stmt = stmt.where(ISO27001Control.domain == domain)
        if implementation_status:
            stmt = stmt.where(ISO27001Control.implementation_status == implementation_status)
        if is_applicable is not None:
            stmt = stmt.where(ISO27001Control.is_applicable == is_applicable)

        query = stmt.order_by(ISO27001Control.control_id)
        paginated = await paginate(db, query, params)
        track_metric("iso27001.controls_accessed")

        result = await db.execute(
            select(func.count())
            .select_from(ISO27001Control)
            .where(ISO27001Control.implementation_status == "implemented")
        )
        implemented = result.scalar_one()

        result = await db.execute(
            select(func.count()).select_from(ISO27001Control).where(ISO27001Control.implementation_status == "partial")
        )
        partial = result.scalar_one()

        result = await db.execute(
            select(func.count())
            .select_from(ISO27001Control)
            .where(ISO27001Control.implementation_status == "not_implemented")
        )
        not_impl = result.scalar_one()

        result = await db.execute(
            select(func.count())
            .select_from(ISO27001Control)
            .where(ISO27001Control.is_applicable == False)  # noqa: E712
        )
        excluded = result.scalar_one()

        return {
            "total": paginated.total,
            "page": paginated.page,
            "page_size": paginated.page_size,
            "pages": paginated.pages,
            "summary": {
                "implemented": implemented,
                "partially_implemented": partial,
                "not_implemented": not_impl,
                "excluded": excluded,
                "implementation_percentage": ISO27001Service.calculate_implementation_percentage(
                    int(implemented), int(paginated.total), int(excluded)
                ),
            },
            "controls": [
                {
                    "id": c.id,
                    "control_id": c.control_id,
                    "control_name": c.control_name,
                    "domain": c.domain,
                    "category": c.category,
                    "implementation_status": c.implementation_status,
                    "is_applicable": c.is_applicable,
                    "effectiveness_rating": c.effectiveness_rating,
                    "control_owner_name": c.control_owner_name,
                }
                for c in paginated.items
            ],
        }

    @staticmethod
    async def update_control(
        db: AsyncSession,
        control_id: int,
        updates: dict[str, Any],
    ) -> dict[str, Any]:
        control = await _get_entity(db, ISO27001Control, control_id)
        for key, value in updates.items():
            setattr(control, key, value)
        if hasattr(control, "updated_at"):
            control.updated_at = datetime.now(timezone.utc)
        if updates.get("implementation_status") == "implemented":
            control.implementation_date = datetime.now(timezone.utc)
        if updates.get("effectiveness_rating"):
            control.last_effectiveness_review = datetime.now(timezone.utc)
        await db.commit()
        return {"message": "Control updated", "id": control.id}

    # ---- Statement of Applicability ----

    @staticmethod
    async def get_current_soa(db: AsyncSession) -> dict[str, Any]:
        result = await db.execute(
            select(StatementOfApplicability).where(StatementOfApplicability.is_current == True)  # noqa: E712
        )
        soa = result.scalar_one_or_none()

        if not soa:
            result = await db.execute(select(func.count()).select_from(ISO27001Control))
            total = result.scalar_one()

            result = await db.execute(
                select(func.count())
                .select_from(ISO27001Control)
                .where(ISO27001Control.is_applicable == True)  # noqa: E712
            )
            applicable = result.scalar_one()

            result = await db.execute(
                select(func.count())
                .select_from(ISO27001Control)
                .where(
                    ISO27001Control.is_applicable == True,  # noqa: E712
                    ISO27001Control.implementation_status == "implemented",
                )
            )
            implemented = result.scalar_one()

            return {
                "version": "N/A",
                "status": "not_created",
                "total_controls": total,
                "applicable_controls": applicable,
                "excluded_controls": int(total) - int(applicable),
                "implemented_controls": implemented,
                "implementation_percentage": ISO27001Service.calculate_soa_compliance_percentage(
                    int(implemented), int(applicable)
                ),
            }

        return {
            "id": soa.id,
            "version": soa.version,
            "effective_date": soa.effective_date.isoformat() if soa.effective_date else None,
            "approved_by": soa.approved_by,
            "approved_date": soa.approved_date.isoformat() if soa.approved_date else None,
            "scope_description": soa.scope_description,
            "total_controls": soa.total_controls,
            "applicable_controls": soa.applicable_controls,
            "excluded_controls": soa.excluded_controls,
            "implemented_controls": soa.implemented_controls,
            "partially_implemented": soa.partially_implemented,
            "not_implemented": soa.not_implemented,
            "implementation_percentage": ISO27001Service.calculate_soa_compliance_percentage(
                int(soa.implemented_controls or 0), int(soa.applicable_controls or 0)
            ),
            "status": soa.status,
            "document_link": soa.document_link,
        }

    # ---- Risks ----

    @staticmethod
    async def list_security_risks(
        db: AsyncSession,
        tenant_id: int,
        params: PaginationParams,
        *,
        risk_status: str | None = None,
        treatment_option: str | None = None,
        min_score: int | None = None,
    ) -> dict[str, Any]:
        stmt = select(InformationSecurityRisk).where(
            InformationSecurityRisk.status != "closed",
            InformationSecurityRisk.tenant_id == tenant_id,
        )
        if risk_status:
            stmt = stmt.where(InformationSecurityRisk.status == risk_status)
        if treatment_option:
            stmt = stmt.where(InformationSecurityRisk.treatment_option == treatment_option)
        if min_score:
            stmt = stmt.where(InformationSecurityRisk.residual_risk_score >= min_score)

        query = stmt.order_by(InformationSecurityRisk.residual_risk_score.desc())
        paginated = await paginate(db, query, params)

        return {
            "total": paginated.total,
            "page": paginated.page,
            "page_size": paginated.page_size,
            "pages": paginated.pages,
            "risks": [
                {
                    "id": r.id,
                    "risk_id": r.risk_id,
                    "title": r.title,
                    "threat_source": r.threat_source,
                    "inherent_risk_score": r.inherent_risk_score,
                    "residual_risk_score": r.residual_risk_score,
                    "treatment_option": r.treatment_option,
                    "treatment_status": r.treatment_status,
                    "risk_owner_name": r.risk_owner_name,
                    "status": r.status,
                }
                for r in paginated.items
            ],
        }

    @staticmethod
    async def create_security_risk(
        db: AsyncSession,
        tenant_id: int,
        risk_data: dict[str, Any],
    ) -> dict[str, Any]:
        result = await db.execute(select(func.count()).select_from(InformationSecurityRisk))
        count = result.scalar_one()
        risk_id = f"ISR-{(count + 1):04d}"

        likelihood = risk_data.get("likelihood", 3)
        impact = risk_data.get("impact", 3)
        inherent_score, residual_score = ISO27001Service.calculate_risk_scores(likelihood, impact)

        risk = InformationSecurityRisk(
            risk_id=risk_id,
            inherent_risk_score=inherent_score,
            residual_risk_score=residual_score,
            next_review_date=datetime.now(timezone.utc) + timedelta(days=90),
            tenant_id=tenant_id,
            **risk_data,
        )
        db.add(risk)
        await db.commit()
        await db.refresh(risk)
        return {"id": risk.id, "risk_id": risk_id, "message": "Security risk created"}

    # ---- Incidents ----

    @staticmethod
    async def list_security_incidents(
        db: AsyncSession,
        tenant_id: int,
        params: PaginationParams,
        *,
        incident_status: str | None = None,
        severity: str | None = None,
        incident_type: str | None = None,
    ) -> dict[str, Any]:
        stmt = select(SecurityIncident).where(
            SecurityIncident.tenant_id == tenant_id,
        )
        if incident_status:
            stmt = stmt.where(SecurityIncident.status == incident_status)
        if severity:
            stmt = stmt.where(SecurityIncident.severity == severity)
        if incident_type:
            stmt = stmt.where(SecurityIncident.incident_type == incident_type)

        query = stmt.order_by(SecurityIncident.detected_date.desc())
        paginated = await paginate(db, query, params)

        result = await db.execute(
            select(func.count())
            .select_from(SecurityIncident)
            .where(SecurityIncident.tenant_id == tenant_id, SecurityIncident.status == "open")
        )
        open_count = result.scalar_one()

        result = await db.execute(
            select(func.count())
            .select_from(SecurityIncident)
            .where(SecurityIncident.tenant_id == tenant_id, SecurityIncident.severity == "critical")
        )
        critical_count = result.scalar_one()

        return {
            "total": paginated.total,
            "page": paginated.page,
            "page_size": paginated.page_size,
            "pages": paginated.pages,
            "open_incidents": open_count,
            "critical_incidents": critical_count,
            "incidents": [
                {
                    "id": i.id,
                    "incident_id": i.incident_id,
                    "title": i.title,
                    "incident_type": i.incident_type,
                    "severity": i.severity,
                    "status": i.status,
                    "detected_date": i.detected_date.isoformat() if i.detected_date else None,
                    "assigned_to_name": i.assigned_to_name,
                    "data_compromised": i.data_compromised,
                }
                for i in paginated.items
            ],
        }

    @staticmethod
    async def create_security_incident(
        db: AsyncSession,
        tenant_id: int,
        incident_data: dict[str, Any],
    ) -> dict[str, Any]:
        result = await db.execute(select(func.count()).select_from(SecurityIncident))
        count = result.scalar_one()
        incident_id = f"SEC-{(count + 1):05d}"

        incident = SecurityIncident(
            incident_id=incident_id,
            status="open",
            tenant_id=tenant_id,
            **incident_data,
        )
        db.add(incident)
        await db.commit()
        await db.refresh(incident)
        return {"id": incident.id, "incident_id": incident_id, "message": "Security incident created"}

    @staticmethod
    async def update_incident(
        db: AsyncSession,
        incident_id: int,
        tenant_id: int,
        updates: dict[str, Any],
    ) -> dict[str, Any]:
        incident = await _get_entity(db, SecurityIncident, incident_id, tenant_id=tenant_id)
        for key, value in updates.items():
            setattr(incident, key, value)
        if hasattr(incident, "updated_at"):
            incident.updated_at = datetime.now(timezone.utc)
        if updates.get("status") == "contained" and not incident.contained_date:
            incident.contained_date = datetime.now(timezone.utc)
        if updates.get("status") == "closed" and not incident.resolved_date:
            incident.resolved_date = datetime.now(timezone.utc)
        await db.commit()
        return {"message": "Incident updated", "id": incident.id}

    # ---- Suppliers ----

    @staticmethod
    async def list_supplier_assessments(
        db: AsyncSession,
        tenant_id: int,
        params: PaginationParams,
        *,
        rating: str | None = None,
        risk_level: str | None = None,
    ) -> dict[str, Any]:
        stmt = select(SupplierSecurityAssessment).where(
            SupplierSecurityAssessment.status == "active",
            SupplierSecurityAssessment.tenant_id == tenant_id,
        )
        if rating:
            stmt = stmt.where(SupplierSecurityAssessment.overall_rating == rating)
        if risk_level:
            stmt = stmt.where(SupplierSecurityAssessment.risk_level == risk_level)

        query = stmt.order_by(SupplierSecurityAssessment.next_assessment_date)
        paginated = await paginate(db, query, params)

        return {
            "total": paginated.total,
            "page": paginated.page,
            "page_size": paginated.page_size,
            "pages": paginated.pages,
            "suppliers": [
                {
                    "id": s.id,
                    "supplier_name": s.supplier_name,
                    "supplier_type": s.supplier_type,
                    "data_access_level": s.data_access_level,
                    "overall_rating": s.overall_rating,
                    "security_score": s.security_score,
                    "iso27001_certified": s.iso27001_certified,
                    "soc2_certified": s.soc2_certified,
                    "risk_level": s.risk_level,
                    "next_assessment_date": (s.next_assessment_date.isoformat() if s.next_assessment_date else None),
                }
                for s in paginated.items
            ],
        }

    @staticmethod
    async def create_supplier_assessment(
        db: AsyncSession,
        tenant_id: int,
        assessment_data: dict[str, Any],
    ) -> dict[str, Any]:
        assessment = SupplierSecurityAssessment(
            assessment_date=datetime.now(timezone.utc),
            tenant_id=tenant_id,
            next_assessment_date=datetime.now(timezone.utc)
            + timedelta(days=int(assessment_data.pop("assessment_frequency_months", None) or 365)),
            **assessment_data,
        )
        db.add(assessment)
        await db.commit()
        await db.refresh(assessment)
        return {"id": assessment.id, "message": "Supplier assessment created"}

    # ---- Dashboard ----

    @staticmethod
    async def get_isms_dashboard(
        db: AsyncSession,
        tenant_id: int,
    ) -> dict[str, Any]:
        # Assets
        result = await db.execute(
            select(func.count())
            .select_from(InformationAsset)
            .where(
                InformationAsset.is_active == True,  # noqa: E712
                InformationAsset.tenant_id == tenant_id,
            )
        )
        total_assets = result.scalar_one()

        result = await db.execute(
            select(func.count())
            .select_from(InformationAsset)
            .where(
                InformationAsset.is_active == True,  # noqa: E712
                InformationAsset.tenant_id == tenant_id,
                InformationAsset.criticality == "critical",
            )
        )
        critical_assets = result.scalar_one()

        # Controls
        result = await db.execute(select(func.count()).select_from(ISO27001Control))
        total_controls = result.scalar_one()

        result = await db.execute(
            select(func.count())
            .select_from(ISO27001Control)
            .where(ISO27001Control.implementation_status == "implemented")
        )
        implemented_controls = result.scalar_one()

        result = await db.execute(
            select(func.count()).select_from(ISO27001Control).where(ISO27001Control.is_applicable == True)  # noqa: E712
        )
        applicable_controls = result.scalar_one()

        # Risks
        result = await db.execute(
            select(func.count())
            .select_from(InformationSecurityRisk)
            .where(
                InformationSecurityRisk.tenant_id == tenant_id,
                InformationSecurityRisk.status != "closed",
            )
        )
        open_risks = result.scalar_one()

        result = await db.execute(
            select(func.count())
            .select_from(InformationSecurityRisk)
            .where(
                InformationSecurityRisk.tenant_id == tenant_id,
                InformationSecurityRisk.residual_risk_score > 16,
                InformationSecurityRisk.status != "closed",
            )
        )
        high_risks = result.scalar_one()

        # Incidents
        result = await db.execute(
            select(func.count())
            .select_from(SecurityIncident)
            .where(
                SecurityIncident.tenant_id == tenant_id,
                SecurityIncident.status == "open",
            )
        )
        open_incidents = result.scalar_one()

        result = await db.execute(
            select(func.count())
            .select_from(SecurityIncident)
            .where(
                SecurityIncident.tenant_id == tenant_id,
                SecurityIncident.detected_date >= datetime.now(timezone.utc) - timedelta(days=30),
            )
        )
        incidents_30d = result.scalar_one()

        # Suppliers
        result = await db.execute(
            select(func.count())
            .select_from(SupplierSecurityAssessment)
            .where(
                SupplierSecurityAssessment.tenant_id == tenant_id,
                SupplierSecurityAssessment.risk_level == "high",
                SupplierSecurityAssessment.status == "active",
            )
        )
        high_risk_suppliers = result.scalar_one()

        compliance_pct = ISO27001Service.calculate_soa_compliance_percentage(
            int(implemented_controls), int(applicable_controls)
        )

        return {
            "assets": {
                "total": total_assets,
                "critical": critical_assets,
            },
            "controls": {
                "total": total_controls,
                "applicable": applicable_controls,
                "implemented": implemented_controls,
                "implementation_percentage": compliance_pct,
            },
            "risks": {
                "open": open_risks,
                "high_critical": high_risks,
            },
            "incidents": {
                "open": open_incidents,
                "last_30_days": incidents_30d,
            },
            "suppliers": {
                "high_risk": high_risk_suppliers,
            },
            "compliance_score": compliance_pct,
        }
