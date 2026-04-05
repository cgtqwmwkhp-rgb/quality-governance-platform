"""Compliance automation service backed by persisted platform data."""

import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.exceptions import NotFoundError
from src.domain.models.compliance_automation import Certificate, GapAnalysis, RegulatoryUpdate, ScheduledAudit
from src.domain.models.compliance_evidence import ComplianceEvidenceLink
from src.domain.models.standard import Clause, Standard

logger = logging.getLogger(__name__)


def _to_iso(value: Optional[datetime]) -> Optional[str]:
    return value.isoformat() if value else None


def _utc_naive() -> datetime:
    """Naive UTC for TIMESTAMP WITHOUT TIME ZONE columns (asyncpg rejects tz-aware binds)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _normalize_standard_text(*values: Optional[str]) -> str:
    return " ".join(value or "" for value in values).lower()


def _extract_standard_tokens(*values: Optional[str]) -> set[str]:
    tokens: set[str] = set()
    for value in values:
        if not value:
            continue
        normalized = "".join(ch.lower() for ch in value if ch.isalnum())
        if normalized:
            tokens.add(normalized)
        tokens.update(re.findall(r"\d{4,5}", value))
    return tokens


def _build_standard_match_clause(raw_value: str):
    normalized = "".join(ch.lower() for ch in raw_value if ch.isalnum())
    digit_tokens = re.findall(r"\d{4,5}", raw_value)
    checks = [
        Standard.code.ilike(f"%{raw_value}%"),
        Standard.name.ilike(f"%{raw_value}%"),
        Standard.full_name.ilike(f"%{raw_value}%"),
    ]
    if normalized:
        checks.extend(
            [
                Standard.code.ilike(f"%{normalized}%"),
                Standard.name.ilike(f"%{normalized}%"),
                Standard.full_name.ilike(f"%{normalized}%"),
            ]
        )
    for token in digit_tokens:
        checks.extend(
            [
                Standard.code.ilike(f"%{token}%"),
                Standard.name.ilike(f"%{token}%"),
                Standard.full_name.ilike(f"%{token}%"),
            ]
        )
    return or_(*checks)


class ComplianceAutomationService:
    """Persisted compliance automation service."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def _resolve_standard(
        self,
        *,
        tenant_id: int,
        raw_value: Optional[str],
    ) -> Optional[Standard]:
        if not raw_value:
            return None

        result = await self.db.execute(
            select(Standard).where(
                or_(Standard.tenant_id == tenant_id, Standard.tenant_id.is_(None)),
                Standard.is_active == True,  # noqa: E712
                _build_standard_match_clause(raw_value),
            )
        )
        return result.scalars().first()

    async def _count_standard_coverage(
        self,
        *,
        tenant_id: int,
        standard: Standard,
    ) -> int:
        clause_count_result = await self.db.execute(
            select(func.count(func.distinct(ComplianceEvidenceLink.clause_id))).where(
                ComplianceEvidenceLink.tenant_id == tenant_id,
                ComplianceEvidenceLink.deleted_at.is_(None),
            )
        )
        all_clause_ids = clause_count_result.scalar()
        if all_clause_ids is None:
            return 0

        tokens = _extract_standard_tokens(standard.code, standard.name, standard.full_name)
        if not tokens:
            return 0

        clause_patterns = []
        for token in tokens:
            clause_patterns.extend(
                [
                    ComplianceEvidenceLink.clause_id.ilike(f"{token}-%"),
                    ComplianceEvidenceLink.clause_id.ilike(f"{token}:%"),
                    ComplianceEvidenceLink.clause_id.ilike(f"{token}/%"),
                    ComplianceEvidenceLink.clause_id.ilike(f"%{token} clause %"),
                ]
            )

        result = await self.db.execute(
            select(func.count(func.distinct(ComplianceEvidenceLink.clause_id))).where(
                ComplianceEvidenceLink.tenant_id == tenant_id,
                ComplianceEvidenceLink.deleted_at.is_(None),
                or_(*clause_patterns),
            )
        )
        return int(result.scalar() or 0)

    async def get_regulatory_updates(
        self,
        *,
        tenant_id: int,
        source: Optional[str] = None,
        since: Optional[datetime] = None,
        impact: Optional[str] = None,
        reviewed: Optional[bool] = None,
    ) -> list[dict[str, Any]]:
        query = select(RegulatoryUpdate).where(
            or_(RegulatoryUpdate.tenant_id == tenant_id, RegulatoryUpdate.tenant_id.is_(None))
        )
        if source:
            query = query.where(RegulatoryUpdate.source == source)
        if since:
            since_cmp = since
            if since_cmp.tzinfo is not None:
                since_cmp = since_cmp.astimezone(timezone.utc).replace(tzinfo=None)
            query = query.where(RegulatoryUpdate.published_date >= since_cmp)
        if impact:
            query = query.where(RegulatoryUpdate.impact == impact)
        if reviewed is not None:
            query = query.where(RegulatoryUpdate.is_reviewed == reviewed)

        result = await self.db.execute(query.order_by(RegulatoryUpdate.published_date.desc()))
        return [
            {
                "id": row.id,
                "source": row.source,
                "source_reference": row.source_reference,
                "source_url": row.source_url,
                "title": row.title,
                "summary": row.summary,
                "category": row.category,
                "subcategory": row.subcategory,
                "impact": row.impact,
                "affected_standards": row.affected_standards or [],
                "affected_clauses": row.affected_clauses or [],
                "published_date": _to_iso(row.published_date),
                "effective_date": _to_iso(row.effective_date),
                "detected_at": _to_iso(row.detected_at),
                "is_reviewed": row.is_reviewed,
                "reviewed_by": row.reviewed_by,
                "reviewed_at": _to_iso(row.reviewed_at),
                "requires_action": row.requires_action,
                "action_notes": row.action_notes,
            }
            for row in result.scalars().all()
        ]

    async def mark_update_reviewed(
        self,
        *,
        tenant_id: int,
        update_id: int,
        reviewed_by: int,
        requires_action: bool,
        action_notes: Optional[str] = None,
    ) -> dict[str, Any]:
        result = await self.db.execute(
            select(RegulatoryUpdate).where(
                RegulatoryUpdate.id == update_id,
                or_(RegulatoryUpdate.tenant_id == tenant_id, RegulatoryUpdate.tenant_id.is_(None)),
            )
        )
        update = result.scalar_one_or_none()
        if update is None:
            raise NotFoundError(f"RegulatoryUpdate {update_id} not found")

        update.is_reviewed = True
        update.reviewed_by = reviewed_by
        update.reviewed_at = _utc_naive()
        update.requires_action = requires_action
        update.action_notes = action_notes
        await self.db.flush()
        return {
            "id": update.id,
            "is_reviewed": update.is_reviewed,
            "reviewed_by": update.reviewed_by,
            "reviewed_at": _to_iso(update.reviewed_at),
            "requires_action": update.requires_action,
            "action_notes": update.action_notes,
        }

    async def run_gap_analysis(
        self,
        *,
        tenant_id: int,
        regulatory_update_id: Optional[int] = None,
        standard_id: Optional[int] = None,
        actor_user_id: Optional[int] = None,
    ) -> dict[str, Any]:
        standard = None
        if standard_id is not None:
            standard_result = await self.db.execute(
                select(Standard).where(
                    Standard.id == standard_id,
                    or_(Standard.tenant_id == tenant_id, Standard.tenant_id.is_(None)),
                )
            )
            standard = standard_result.scalar_one_or_none()

        update = None
        if regulatory_update_id is not None:
            update_result = await self.db.execute(
                select(RegulatoryUpdate).where(
                    RegulatoryUpdate.id == regulatory_update_id,
                    or_(RegulatoryUpdate.tenant_id == tenant_id, RegulatoryUpdate.tenant_id.is_(None)),
                )
            )
            update = update_result.scalar_one_or_none()

        if standard is None and update and update.affected_standards:
            standard = await self._resolve_standard(
                tenant_id=tenant_id,
                raw_value=update.affected_standards[0],
            )

        total_clauses = 0
        covered_clauses = 0
        title_scope = "organization"
        if standard is not None:
            title_scope = standard.name
            total_clause_result = await self.db.execute(
                select(func.count(Clause.id)).where(
                    Clause.standard_id == standard.id,
                    Clause.is_active == True,  # noqa: E712
                    or_(Clause.tenant_id == tenant_id, Clause.tenant_id.is_(None)),
                )
            )
            total_clauses = int(total_clause_result.scalar() or 0)

            covered_clauses = await self._count_standard_coverage(
                tenant_id=tenant_id,
                standard=standard,
            )

        uncovered = max(total_clauses - covered_clauses, 0)
        overall_compliance = round((covered_clauses / total_clauses) * 100, 1) if total_clauses else 0.0
        gaps = {
            "covered_clauses": covered_clauses,
            "uncovered_clauses": uncovered,
            "regulatory_update_id": regulatory_update_id,
        }

        analysis = GapAnalysis(
            tenant_id=tenant_id,
            regulatory_update_id=regulatory_update_id,
            standard_id=standard.id if standard is not None else None,
            title=f"Gap analysis for {title_scope}",
            description="Generated from standards coverage and persisted evidence links.",
            gaps=gaps,
            total_gaps=uncovered,
            critical_gaps=uncovered if overall_compliance < 50 else 0,
            high_gaps=uncovered if 50 <= overall_compliance < 80 else 0,
            recommendations={
                "recommended_actions": [
                    "Upload missing evidence",
                    "Link audit findings to uncovered clauses",
                    "Review certificates against affected standards",
                ]
            },
            estimated_effort_hours=max(uncovered * 2, 4) if uncovered else 2,
            status="completed",
            assigned_to=actor_user_id,
            completed_at=_utc_naive(),
        )
        self.db.add(analysis)
        await self.db.flush()
        return {
            "id": analysis.id,
            "title": analysis.title,
            "gaps": analysis.gaps,
            "total": analysis.total_gaps,
            "total_gaps": analysis.total_gaps,
            "overall_compliance": overall_compliance,
            "critical_gaps": analysis.critical_gaps,
            "high_gaps": analysis.high_gaps,
            "status": analysis.status,
            "recommendations": analysis.recommendations or {},
            "estimated_effort_hours": analysis.estimated_effort_hours,
        }

    async def get_gap_analyses(
        self,
        *,
        tenant_id: int,
        status: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        query = select(GapAnalysis).where(or_(GapAnalysis.tenant_id == tenant_id, GapAnalysis.tenant_id.is_(None)))
        if status:
            query = query.where(GapAnalysis.status == status)
        result = await self.db.execute(query.order_by(GapAnalysis.created_at.desc()))
        return [
            {
                "id": analysis.id,
                "regulatory_update_id": analysis.regulatory_update_id,
                "standard_id": analysis.standard_id,
                "title": analysis.title,
                "description": analysis.description,
                "gaps": analysis.gaps,
                "total_gaps": analysis.total_gaps,
                "critical_gaps": analysis.critical_gaps,
                "high_gaps": analysis.high_gaps,
                "recommendations": analysis.recommendations,
                "estimated_effort_hours": analysis.estimated_effort_hours,
                "status": analysis.status,
                "assigned_to": analysis.assigned_to,
                "created_at": _to_iso(analysis.created_at),
                "completed_at": _to_iso(analysis.completed_at),
            }
            for analysis in result.scalars().all()
        ]

    async def get_certificates(
        self,
        *,
        tenant_id: int,
        certificate_type: Optional[str] = None,
        entity_type: Optional[str] = None,
        status: Optional[str] = None,
        expiring_within_days: Optional[int] = None,
    ) -> list[dict[str, Any]]:
        query = select(Certificate).where(or_(Certificate.tenant_id == tenant_id, Certificate.tenant_id.is_(None)))
        if certificate_type:
            query = query.where(Certificate.certificate_type == certificate_type)
        if entity_type:
            query = query.where(Certificate.entity_type == entity_type)
        if status:
            query = query.where(Certificate.status == status)
        if expiring_within_days is not None:
            query = query.where(Certificate.expiry_date <= _utc_naive() + timedelta(days=expiring_within_days))

        result = await self.db.execute(query.order_by(Certificate.expiry_date.asc()))
        return [
            {
                "id": certificate.id,
                "name": certificate.name,
                "certificate_type": certificate.certificate_type,
                "reference_number": certificate.reference_number,
                "entity_type": certificate.entity_type,
                "entity_id": certificate.entity_id,
                "entity_name": certificate.entity_name,
                "issuing_body": certificate.issuing_body,
                "issue_date": _to_iso(certificate.issue_date),
                "expiry_date": _to_iso(certificate.expiry_date),
                "reminder_days": certificate.reminder_days,
                "reminder_sent": certificate.reminder_sent,
                "status": certificate.status,
                "is_critical": certificate.is_critical,
                "primary_evidence_asset_id": certificate.primary_evidence_asset_id,
                "document_url": certificate.document_url,
                "notes": certificate.notes,
            }
            for certificate in result.scalars().all()
        ]

    async def get_expiring_certificates_summary(self, *, tenant_id: int) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        d7 = now + timedelta(days=7)
        d30 = now + timedelta(days=30)
        d90 = now + timedelta(days=90)
        result = await self.db.execute(
            select(Certificate).where(or_(Certificate.tenant_id == tenant_id, Certificate.tenant_id.is_(None)))
        )
        rows = result.scalars().all()

        def _expiry_aware(row: Certificate) -> datetime:
            ed = row.expiry_date
            if ed.tzinfo is None:
                return ed.replace(tzinfo=timezone.utc)
            return ed

        expired = [row for row in rows if _expiry_aware(row) < now]
        expiring_7 = [row for row in rows if now <= _expiry_aware(row) <= d7]
        expiring_30 = [row for row in rows if now <= _expiry_aware(row) <= d30]
        expiring_90 = [row for row in rows if now <= _expiry_aware(row) <= d90]
        expiring_soon = expiring_30
        categories: dict[str, int] = {}
        for row in rows:
            categories[row.certificate_type] = categories.get(row.certificate_type, 0) + 1
        return {
            "expired": len(expired),
            "expiring_7_days": len(expiring_7),
            "expiring_30_days": len(expiring_30),
            "expiring_90_days": len(expiring_90),
            "expiring_soon": len(expiring_soon),
            "by_type": dict(sorted(categories.items())),
            "categories": [{"certificate_type": key, "count": value} for key, value in sorted(categories.items())],
        }

    async def get_scheduled_audits(
        self,
        *,
        tenant_id: int,
        upcoming_days: Optional[int] = None,
        overdue: Optional[bool] = None,
    ) -> list[dict[str, Any]]:
        query = select(ScheduledAudit).where(
            and_(
                or_(ScheduledAudit.tenant_id == tenant_id, ScheduledAudit.tenant_id.is_(None)),
                ScheduledAudit.is_active == True,  # noqa: E712
            )
        )
        now_aware = datetime.now(timezone.utc)
        now_sql = _utc_naive()
        if upcoming_days is not None:
            query = query.where(ScheduledAudit.next_due_date <= now_sql + timedelta(days=upcoming_days))
        if overdue is True:
            query = query.where(ScheduledAudit.next_due_date < now_sql)
        elif overdue is False:
            query = query.where(ScheduledAudit.next_due_date >= now_sql)

        result = await self.db.execute(query.order_by(ScheduledAudit.next_due_date.asc()))
        rows = []
        for audit in result.scalars().all():
            nd = audit.next_due_date
            if nd is None:
                st = "scheduled"
            else:
                nd_aware = nd.replace(tzinfo=timezone.utc) if nd.tzinfo is None else nd
                st = "overdue" if nd_aware < now_aware else "scheduled"
            rows.append(
                {
                    "id": audit.id,
                    "name": audit.name,
                    "description": audit.description,
                    "audit_type": audit.audit_type,
                    "template_id": audit.template_id,
                    "frequency": audit.frequency,
                    "schedule_config": audit.schedule_config,
                    "next_due_date": _to_iso(audit.next_due_date),
                    "last_completed_date": _to_iso(audit.last_completed_date),
                    "assigned_to": audit.assigned_to,
                    "department": audit.department,
                    "standard_ids": audit.standard_ids or [],
                    "reminder_days_before": audit.reminder_days_before,
                    "reminder_sent": audit.reminder_sent,
                    "created_at": _to_iso(audit.created_at),
                    "status": st,
                }
            )
        return rows

    async def calculate_compliance_score(
        self,
        *,
        tenant_id: int,
        scope_type: str = "organization",
        scope_id: Optional[str] = None,
    ) -> dict[str, Any]:
        standards_result = await self.db.execute(
            select(Standard).where(
                Standard.is_active == True,  # noqa: E712
                or_(Standard.tenant_id == tenant_id, Standard.tenant_id.is_(None)),
            )
        )
        standards = standards_result.scalars().all()
        categories: dict[str, float] = {}
        total_clauses = 0
        total_covered = 0

        for standard in standards:
            clause_count_result = await self.db.execute(
                select(func.count(Clause.id)).where(
                    Clause.standard_id == standard.id,
                    Clause.is_active == True,  # noqa: E712
                    or_(Clause.tenant_id == tenant_id, Clause.tenant_id.is_(None)),
                )
            )
            clause_count = int(clause_count_result.scalar() or 0)
            covered = await self._count_standard_coverage(
                tenant_id=tenant_id,
                standard=standard,
            )
            total_clauses += clause_count
            total_covered += min(covered, clause_count)
            categories[standard.code] = round((covered / clause_count) * 100, 1) if clause_count else 0.0

        overall_score = round((total_covered / total_clauses) * 100, 1) if total_clauses else 0.0
        breakdown = {code: {"score": pct} for code, pct in categories.items()}
        key_gaps: list[str] = []
        recommendations: list[str] = []
        if overall_score < 80:
            key_gaps.append("Evidence coverage below target for one or more active standards")
            recommendations.append("Upload and link evidence for standards with the lowest scores in breakdown")
        return {
            "scope_type": scope_type,
            "scope_id": scope_id,
            "overall_score": overall_score,
            "categories": categories,
            "breakdown": breakdown,
            "key_gaps": key_gaps,
            "recommendations": recommendations,
            "trend": "improving" if overall_score >= 75 else "attention_required",
        }

    async def get_compliance_trend(
        self,
        *,
        tenant_id: int,
        scope_type: str = "organization",
        months: int = 12,
    ) -> list[dict[str, Any]]:
        result = await self.db.execute(
            select(GapAnalysis).where(or_(GapAnalysis.tenant_id == tenant_id, GapAnalysis.tenant_id.is_(None)))
        )
        analyses = result.scalars().all()
        trend = []
        for month_offset in range(months - 1, -1, -1):
            bucket_start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            bucket_start = bucket_start - timedelta(days=month_offset * 30)
            bucket_label = bucket_start.strftime("%Y-%m")
            month_analyses = [
                analysis for analysis in analyses if analysis.created_at.strftime("%Y-%m") == bucket_label
            ]
            if month_analyses:
                score = round(
                    sum(max(0, 100 - (analysis.total_gaps * 5)) for analysis in month_analyses) / len(month_analyses),
                    1,
                )
            else:
                score = 0.0
            trend.append(
                {
                    "period": bucket_label,
                    "score": score,
                    "overall_score": score,
                    "scope_type": scope_type,
                }
            )
        return trend

    # ==================== RIDDOR Automation ====================

    def check_riddor_required(self, incident_data: Dict[str, Any]) -> Dict[str, Any]:
        """Check if an incident requires RIDDOR reporting."""
        riddor_types = []

        if incident_data.get("fatality"):
            riddor_types.append("death")

        if incident_data.get("injury_type") in [
            "fracture",
            "amputation",
            "dislocation",
            "loss_of_sight",
        ]:
            riddor_types.append("specified_injury")

        if incident_data.get("days_off_work", 0) > 7:
            riddor_types.append("over_7_day_incapacitation")

        if incident_data.get("dangerous_occurrence"):
            riddor_types.append("dangerous_occurrence")

        if incident_data.get("occupational_disease"):
            riddor_types.append("occupational_disease")

        is_riddor = len(riddor_types) > 0
        deadline = None
        if is_riddor:
            if "death" in riddor_types or "specified_injury" in riddor_types:
                deadline = datetime.now(timezone.utc) + timedelta(days=10)
            else:
                deadline = datetime.now(timezone.utc) + timedelta(days=15)

        return {
            "is_riddor": is_riddor,
            "riddor_types": riddor_types,
            "deadline": deadline.isoformat() if deadline else None,
            "submission_url": ("https://www.hse.gov.uk/riddor/report.htm" if is_riddor else None),
        }

    def prepare_riddor_submission(
        self,
        incident_id: int,
        riddor_type: str,
    ) -> Dict[str, Any]:
        """Prepare RIDDOR submission data."""
        deadline = datetime.now(timezone.utc) + timedelta(days=10)
        return {
            "incident_id": incident_id,
            "riddor_type": riddor_type,
            "submission_data": {
                "report_type": riddor_type,
                "date_of_incident": "",
                "time_of_incident": "",
                "location": "",
                "injured_person": {
                    "name": "",
                    "occupation": "",
                    "employment_status": "",
                },
                "injury_details": {
                    "type": "",
                    "body_part": "",
                    "severity": "",
                },
                "incident_description": "",
                "immediate_actions": "",
                "preventive_measures": "",
                "reporter": {
                    "name": "",
                    "position": "",
                    "contact": "",
                },
            },
            "deadline": deadline.isoformat(),
            "status": "ready_to_submit",
        }

    def submit_riddor(
        self,
        incident_id: int,
        submitted_by: int,
    ) -> Dict[str, Any]:
        """Submit RIDDOR report to HSE."""
        submitted_at = datetime.now(timezone.utc)
        hse_reference = f"RIDDOR-{incident_id:06d}-{submitted_at.strftime('%Y%m%d%H%M%S')}"
        return {
            "incident_id": incident_id,
            "status": "submitted",
            "hse_reference": hse_reference,
            "submitted_at": submitted_at.isoformat(),
            "submitted_by": submitted_by,
            "confirmation": "Acknowledged by HSE submission stub (integrate production gateway separately)",
        }
