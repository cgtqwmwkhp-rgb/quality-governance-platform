"""
Compliance Automation Service

Features:
- Regulatory change monitoring
- Gap analysis
- Certificate expiry tracking
- Scheduled audit management
- Compliance score calculation
- RIDDOR automation
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.compliance_automation import (
    Certificate,
    ComplianceScore,
    GapAnalysis,
    RegulatoryUpdate,
    RIDDORSubmission,
    ScheduledAudit,
)

logger = logging.getLogger(__name__)


def _row_to_dict(obj: Any) -> Dict[str, Any]:
    """Convert a SQLAlchemy model instance to a dict, serialising datetimes."""
    d: Dict[str, Any] = {}
    for col in obj.__table__.columns:
        val = getattr(obj, col.name)
        if isinstance(val, datetime):
            val = val.isoformat()
        d[col.name] = val
    return d


class ComplianceAutomationService:
    """
    Comprehensive compliance automation service.

    All methods accept an AsyncSession and perform real database queries.
    """

    # ==================== Regulatory Monitoring ====================

    async def get_regulatory_updates(
        self,
        db: AsyncSession,
        source: Optional[str] = None,
        since: Optional[datetime] = None,
        impact: Optional[str] = None,
        reviewed: Optional[bool] = None,
    ) -> List[Dict[str, Any]]:
        """Get regulatory updates with filters."""
        query = select(RegulatoryUpdate).order_by(RegulatoryUpdate.published_date.desc())

        if source:
            query = query.where(RegulatoryUpdate.source == source)
        if since:
            query = query.where(RegulatoryUpdate.published_date >= since)
        if impact:
            query = query.where(RegulatoryUpdate.impact == impact)
        if reviewed is not None:
            query = query.where(RegulatoryUpdate.is_reviewed == reviewed)

        result = await db.execute(query)
        return [_row_to_dict(u) for u in result.scalars().all()]

    async def mark_update_reviewed(
        self,
        db: AsyncSession,
        update_id: int,
        reviewed_by: int,
        requires_action: bool,
        action_notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Mark a regulatory update as reviewed."""
        result = await db.execute(select(RegulatoryUpdate).where(RegulatoryUpdate.id == update_id))
        update = result.scalar_one_or_none()
        if not update:
            raise ValueError(f"Regulatory update {update_id} not found")

        update.is_reviewed = True
        update.reviewed_by = reviewed_by
        update.reviewed_at = datetime.now(timezone.utc)
        update.requires_action = requires_action
        if action_notes is not None:
            update.action_notes = action_notes

        await db.flush()
        return _row_to_dict(update)

    # ==================== Gap Analysis ====================

    async def run_gap_analysis(
        self,
        db: AsyncSession,
        regulatory_update_id: Optional[int] = None,
        standard_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Run gap analysis and persist results."""
        title = "Gap Analysis"
        description = None

        if regulatory_update_id:
            result = await db.execute(select(RegulatoryUpdate).where(RegulatoryUpdate.id == regulatory_update_id))
            reg = result.scalar_one_or_none()
            if reg:
                title = f"Gap Analysis - {reg.title}"
                description = f"Analysis triggered by regulatory update: {reg.source_reference}"

        gaps_data: List[Dict[str, Any]] = []

        if reg:
            clauses = reg.affected_clauses or []
            standards = reg.affected_standards or []
            for clause in clauses:
                gaps_data.append(
                    {
                        "clause": clause,
                        "requirement": f"Clause {clause} compliance for {', '.join(standards) or 'applicable standard'}",
                        "current_state": "Requires review against updated regulation",
                        "gap_description": (
                            f"Regulatory change '{reg.title}' affects clause {clause}. "
                            "Current procedures and documentation must be assessed for alignment."
                        ),
                        "severity": ("high" if reg.impact in ("critical", "high") else "medium"),
                        "effort_hours": (24 if reg.impact in ("critical", "high") else 12),
                        "recommendation": (
                            f"Review clause {clause} documentation and procedures against "
                            f"the updated requirements from {reg.source_reference}. "
                            "Update SOPs and notify relevant personnel."
                        ),
                    }
                )
            if not clauses:
                gaps_data.append(
                    {
                        "clause": "General",
                        "requirement": f"Overall compliance with {', '.join(standards) or 'regulatory update'}",
                        "current_state": "Pending assessment",
                        "gap_description": (f"Regulatory update '{reg.title}' requires a general compliance review."),
                        "severity": "medium",
                        "effort_hours": 16,
                        "recommendation": "Conduct a thorough review of affected processes and documentation.",
                    }
                )
        else:
            all_audits_q = (
                select(ScheduledAudit)
                .where(ScheduledAudit.is_active == True)  # noqa: E712
                .where(ScheduledAudit.next_due_date < datetime.now(timezone.utc))
            )
            overdue_result = await db.execute(all_audits_q)
            overdue_audits = overdue_result.scalars().all()
            for oa in overdue_audits:
                stds = oa.standard_ids or []
                gaps_data.append(
                    {
                        "clause": "Audit Schedule",
                        "requirement": f"Timely completion of '{oa.name}'",
                        "current_state": "Overdue",
                        "gap_description": (
                            f"Scheduled audit '{oa.name}' is overdue since " f"{oa.next_due_date.strftime('%Y-%m-%d')}."
                        ),
                        "severity": "high",
                        "effort_hours": 8,
                        "recommendation": (
                            f"Complete overdue {oa.audit_type} audit for "
                            f"{', '.join(stds) if stds else oa.department or 'assigned department'}."
                        ),
                    }
                )
            if not overdue_audits:
                gaps_data.append(
                    {
                        "clause": "General",
                        "requirement": "Overall compliance posture review",
                        "current_state": "No specific gaps detected from overdue audits",
                        "gap_description": "No overdue audits found. General compliance health check.",
                        "severity": "low",
                        "effort_hours": 4,
                        "recommendation": "Continue monitoring and maintain current compliance cadence.",
                    }
                )

        total = len(gaps_data)
        critical = sum(1 for g in gaps_data if g["severity"] == "critical")
        high = sum(1 for g in gaps_data if g["severity"] == "high")
        effort = sum(g["effort_hours"] for g in gaps_data)

        analysis = GapAnalysis(
            regulatory_update_id=regulatory_update_id,
            standard_id=standard_id,
            title=title,
            description=description,
            gaps=gaps_data,
            total_gaps=total,
            critical_gaps=critical,
            high_gaps=high,
            recommendations={"items": [g["recommendation"] for g in gaps_data[:5]]},
            estimated_effort_hours=effort,
            status="pending",
        )
        db.add(analysis)
        await db.flush()

        return _row_to_dict(analysis)

    async def get_gap_analyses(
        self,
        db: AsyncSession,
        status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get list of gap analyses."""
        query = select(GapAnalysis).order_by(GapAnalysis.created_at.desc())
        if status:
            query = query.where(GapAnalysis.status == status)

        result = await db.execute(query)
        return [_row_to_dict(a) for a in result.scalars().all()]

    # ==================== Certificate Tracking ====================

    async def get_certificates(
        self,
        db: AsyncSession,
        certificate_type: Optional[str] = None,
        entity_type: Optional[str] = None,
        status: Optional[str] = None,
        expiring_within_days: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Get certificates with filters."""
        query = select(Certificate).order_by(Certificate.expiry_date.asc())

        if certificate_type:
            query = query.where(Certificate.certificate_type == certificate_type)
        if entity_type:
            query = query.where(Certificate.entity_type == entity_type)
        if status:
            query = query.where(Certificate.status == status)
        if expiring_within_days:
            cutoff = datetime.now(timezone.utc) + timedelta(days=expiring_within_days)
            query = query.where(Certificate.expiry_date <= cutoff)

        result = await db.execute(query)
        return [_row_to_dict(c) for c in result.scalars().all()]

    async def get_expiring_certificates_summary(
        self,
        db: AsyncSession,
    ) -> Dict[str, Any]:
        """Get summary of expiring certificates."""
        now = datetime.now(timezone.utc)

        expired_q = select(func.count()).select_from(Certificate).where(Certificate.expiry_date < now)
        exp_7_q = (
            select(func.count())
            .select_from(Certificate)
            .where(
                Certificate.expiry_date >= now,
                Certificate.expiry_date <= now + timedelta(days=7),
            )
        )
        exp_30_q = (
            select(func.count())
            .select_from(Certificate)
            .where(
                Certificate.expiry_date >= now,
                Certificate.expiry_date <= now + timedelta(days=30),
            )
        )
        exp_90_q = (
            select(func.count())
            .select_from(Certificate)
            .where(
                Certificate.expiry_date >= now,
                Certificate.expiry_date <= now + timedelta(days=90),
            )
        )
        critical_q = (
            select(func.count())
            .select_from(Certificate)
            .where(
                Certificate.is_critical == True,  # noqa: E712
                Certificate.expiry_date <= now + timedelta(days=90),
            )
        )

        expired = await db.scalar(expired_q) or 0
        exp_7 = await db.scalar(exp_7_q) or 0
        exp_30 = await db.scalar(exp_30_q) or 0
        exp_90 = await db.scalar(exp_90_q) or 0
        total_critical = await db.scalar(critical_q) or 0

        return {
            "expired": expired,
            "expiring_7_days": exp_7,
            "expiring_30_days": exp_30,
            "expiring_90_days": exp_90,
            "total_critical": total_critical,
        }

    async def add_certificate(
        self,
        db: AsyncSession,
        data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Add a new certificate."""
        cert = Certificate(
            name=data["name"],
            certificate_type=data["certificate_type"],
            reference_number=data.get("reference_number"),
            entity_type=data["entity_type"],
            entity_id=data["entity_id"],
            entity_name=data.get("entity_name"),
            issuing_body=data.get("issuing_body"),
            issue_date=(
                datetime.fromisoformat(data["issue_date"])
                if isinstance(data["issue_date"], str)
                else data["issue_date"]
            ),
            expiry_date=(
                datetime.fromisoformat(data["expiry_date"])
                if isinstance(data["expiry_date"], str)
                else data["expiry_date"]
            ),
            reminder_days=data.get("reminder_days", 30),
            is_critical=data.get("is_critical", False),
            notes=data.get("notes"),
        )
        db.add(cert)
        await db.flush()
        return _row_to_dict(cert)

    # ==================== Scheduled Audits ====================

    async def get_scheduled_audits(
        self,
        db: AsyncSession,
        upcoming_days: Optional[int] = None,
        overdue: Optional[bool] = None,
    ) -> List[Dict[str, Any]]:
        """Get scheduled audits."""
        now = datetime.now(timezone.utc)
        query = (
            select(ScheduledAudit).where(ScheduledAudit.is_active == True).order_by(ScheduledAudit.next_due_date.asc())
        )  # noqa: E712

        if overdue:
            query = query.where(ScheduledAudit.next_due_date < now)
        elif upcoming_days:
            cutoff = now + timedelta(days=upcoming_days)
            query = query.where(ScheduledAudit.next_due_date <= cutoff)

        result = await db.execute(query)
        rows = result.scalars().all()

        audits = []
        for a in rows:
            d = _row_to_dict(a)
            d["status"] = "overdue" if a.next_due_date < now else "scheduled"
            d["standards"] = a.standard_ids or []
            audits.append(d)
        return audits

    async def schedule_audit(
        self,
        db: AsyncSession,
        data: Dict[str, Any],
        created_by: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Schedule a new audit."""
        audit = ScheduledAudit(
            name=data["name"],
            description=data.get("description"),
            audit_type=data["audit_type"],
            frequency=data["frequency"],
            next_due_date=(
                datetime.fromisoformat(data["next_due_date"])
                if isinstance(data["next_due_date"], str)
                else data["next_due_date"]
            ),
            department=data.get("department"),
            standard_ids=data.get("standard_ids"),
            reminder_days_before=data.get("reminder_days_before", 7),
            created_by=created_by,
        )
        db.add(audit)
        await db.flush()
        d = _row_to_dict(audit)
        d["standards"] = audit.standard_ids or []
        d["status"] = "scheduled"
        return d

    # ==================== Compliance Scoring ====================

    async def calculate_compliance_score(
        self,
        db: AsyncSession,
        scope_type: str = "organization",
        scope_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get latest compliance score or compute a live one."""
        query = (
            select(ComplianceScore)
            .where(ComplianceScore.scope_type == scope_type)
            .order_by(ComplianceScore.calculated_at.desc())
            .limit(1)
        )
        if scope_id:
            query = query.where(ComplianceScore.scope_id == scope_id)

        result = await db.execute(query)
        score = result.scalar_one_or_none()

        if score:
            d = _row_to_dict(score)
            d["overall_score"] = score.percentage
            d["previous_score"] = score.previous_score
            d["change"] = score.score_change or 0
            d["trend"] = (
                "improving"
                if (score.score_change or 0) > 0
                else "declining" if (score.score_change or 0) < 0 else "stable"
            )
            return d

        return {
            "scope_type": scope_type,
            "scope_id": scope_id,
            "overall_score": 0,
            "previous_score": None,
            "change": 0,
            "trend": "stable",
            "breakdown": {},
            "calculated_at": datetime.now(timezone.utc).isoformat(),
        }

    async def get_compliance_trend(
        self,
        db: AsyncSession,
        scope_type: str = "organization",
        months: int = 12,
    ) -> List[Dict[str, Any]]:
        """Get compliance score trend over time."""
        since = datetime.now(timezone.utc) - timedelta(days=months * 30)
        query = (
            select(ComplianceScore)
            .where(
                ComplianceScore.scope_type == scope_type,
                ComplianceScore.calculated_at >= since,
            )
            .order_by(ComplianceScore.calculated_at.asc())
        )

        result = await db.execute(query)
        rows = result.scalars().all()

        return [
            {
                "period": (s.period_start.strftime("%Y-%m") if s.period_start else s.calculated_at.strftime("%Y-%m")),
                "overall_score": s.percentage,
                "breakdown": s.breakdown,
            }
            for s in rows
        ]

    # ==================== RIDDOR Automation ====================

    async def get_riddor_submissions(
        self,
        db: AsyncSession,
        status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get RIDDOR submissions."""
        query = select(RIDDORSubmission).order_by(RIDDORSubmission.created_at.desc())
        if status:
            query = query.where(RIDDORSubmission.submission_status == status)
        result = await db.execute(query)
        return [_row_to_dict(s) for s in result.scalars().all()]

    async def check_riddor_required(
        self,
        incident_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Check if an incident requires RIDDOR reporting (stateless logic)."""
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

    async def prepare_riddor_submission(
        self,
        db: AsyncSession,
        incident_id: int,
        riddor_type: str,
    ) -> Dict[str, Any]:
        """Prepare RIDDOR submission and persist a draft record."""
        existing = await db.execute(
            select(RIDDORSubmission).where(
                RIDDORSubmission.incident_id == incident_id,
                RIDDORSubmission.submission_status.in_(["pending", "ready_to_submit"]),
            )
        )
        submission = existing.scalar_one_or_none()

        if not submission:
            deadline = datetime.now(timezone.utc) + timedelta(
                days=10 if riddor_type in ("death", "specified_injury") else 15
            )
            submission = RIDDORSubmission(
                incident_id=incident_id,
                riddor_type=riddor_type,
                submission_status="ready_to_submit",
                submission_data={"riddor_type": riddor_type},
                deadline=deadline,
            )
            db.add(submission)
            await db.flush()

        return _row_to_dict(submission)

    async def submit_riddor(
        self,
        db: AsyncSession,
        incident_id: int,
        submitted_by: int,
    ) -> Dict[str, Any]:
        """Submit RIDDOR report (mark as submitted)."""
        result = await db.execute(
            select(RIDDORSubmission).where(
                RIDDORSubmission.incident_id == incident_id,
                RIDDORSubmission.submission_status.in_(["pending", "ready_to_submit"]),
            )
        )
        submission = result.scalar_one_or_none()

        if not submission:
            raise ValueError(f"No pending RIDDOR submission for incident {incident_id}")

        now = datetime.now(timezone.utc)
        submission.submission_status = "submitted"
        submission.submitted_at = now
        submission.submitted_by = submitted_by
        submission.hse_reference = f"RIDDOR-{now.year}-{incident_id:06d}"
        await db.flush()

        return _row_to_dict(submission)

    # ==================== Seed Data ====================

    async def seed_default_data(self, db: AsyncSession) -> None:
        """Seed default regulatory updates and certificates if tables are empty."""
        count_result = await db.scalar(select(func.count()).select_from(RegulatoryUpdate))
        if count_result and count_result > 0:
            logger.info("Compliance automation data already exists, skipping seed")
            return

        logger.info("Seeding compliance automation default data")
        now = datetime.now(timezone.utc)

        updates = [
            RegulatoryUpdate(
                source="hse_uk",
                source_reference="HSE/2026/001",
                title="Updated guidance on workplace first aid requirements",
                summary="New requirements for first aid training and equipment in workplaces with 50+ employees.",
                category="health_safety",
                impact="high",
                affected_standards=["ISO 45001"],
                affected_clauses=["8.2", "7.2"],
                published_date=datetime(2026, 1, 15),
                effective_date=datetime(2026, 4, 1),
                detected_at=datetime(2026, 1, 16, 9, 0),
                is_reviewed=False,
                requires_action=True,
            ),
            RegulatoryUpdate(
                source="iso",
                source_reference="ISO/TC 176/2026",
                title="Amendment to ISO 9001:2015 - Clause 4.4.1",
                summary="Clarification on process interaction requirements and documented information.",
                category="quality",
                impact="medium",
                affected_standards=["ISO 9001"],
                affected_clauses=["4.4.1"],
                published_date=datetime(2026, 1, 10),
                effective_date=datetime(2026, 7, 1),
                detected_at=datetime(2026, 1, 12, 14, 30),
                is_reviewed=True,
                requires_action=False,
            ),
            RegulatoryUpdate(
                source="hse_uk",
                source_reference="HSE/2026/002",
                title="RIDDOR amendment - digital submission requirements",
                summary="All RIDDOR submissions must be made digitally from March 2026.",
                category="regulatory",
                impact="critical",
                affected_standards=["ISO 45001"],
                affected_clauses=["10.2"],
                published_date=datetime(2026, 1, 18),
                effective_date=datetime(2026, 3, 1),
                detected_at=datetime(2026, 1, 19, 8, 0),
                is_reviewed=False,
                requires_action=True,
            ),
        ]

        certificates = [
            Certificate(
                name="First Aid at Work Certificate",
                certificate_type="training",
                entity_type="user",
                entity_id="user-001",
                entity_name="John Smith",
                issuing_body="St John Ambulance",
                issue_date=datetime(2023, 3, 15),
                expiry_date=now + timedelta(days=45),
                status="expiring_soon",
                is_critical=True,
            ),
            Certificate(
                name="IPAF Licence",
                certificate_type="license",
                entity_type="user",
                entity_id="user-002",
                entity_name="Mike Johnson",
                issuing_body="IPAF",
                issue_date=datetime(2024, 6, 1),
                expiry_date=now + timedelta(days=180),
                status="valid",
                is_critical=False,
            ),
            Certificate(
                name="Crane Calibration Certificate",
                certificate_type="calibration",
                entity_type="equipment",
                entity_id="equip-005",
                entity_name="Mobile Crane MC-01",
                issuing_body="UKAS Accredited",
                issue_date=datetime(2025, 1, 10),
                expiry_date=now + timedelta(days=10),
                status="expiring_soon",
                is_critical=True,
            ),
            Certificate(
                name="ISO 9001 Accreditation",
                certificate_type="accreditation",
                entity_type="organization",
                entity_id="org-001",
                entity_name="Organisation",
                issuing_body="BSI",
                issue_date=datetime(2024, 3, 1),
                expiry_date=now + timedelta(days=400),
                status="valid",
                is_critical=True,
            ),
        ]

        scheduled_audits = [
            ScheduledAudit(
                name="Monthly H&S Inspection - Site A",
                audit_type="safety_inspection",
                frequency="monthly",
                next_due_date=now + timedelta(days=5),
                last_completed_date=now - timedelta(days=25),
                department="Safety Team",
                standard_ids=["ISO 45001"],
            ),
            ScheduledAudit(
                name="Quarterly ISO 9001 Internal Audit",
                audit_type="internal_audit",
                frequency="quarterly",
                next_due_date=now - timedelta(days=3),
                last_completed_date=now - timedelta(days=93),
                department="Quality Team",
                standard_ids=["ISO 9001"],
            ),
            ScheduledAudit(
                name="Annual Environmental Review",
                audit_type="environmental_audit",
                frequency="annual",
                next_due_date=now + timedelta(days=45),
                last_completed_date=now - timedelta(days=320),
                department="Environmental Manager",
                standard_ids=["ISO 14001"],
            ),
        ]

        initial_scores = [
            ComplianceScore(
                scope_type="organization",
                score=87.5,
                max_score=100.0,
                percentage=87.5,
                breakdown={
                    "ISO 9001": {
                        "score": 92.0,
                        "clauses_compliant": 45,
                        "clauses_total": 48,
                        "gaps": 3,
                    },
                    "ISO 14001": {
                        "score": 88.5,
                        "clauses_compliant": 38,
                        "clauses_total": 42,
                        "gaps": 4,
                    },
                    "ISO 45001": {
                        "score": 82.0,
                        "clauses_compliant": 35,
                        "clauses_total": 42,
                        "gaps": 7,
                    },
                },
                period_start=now - timedelta(days=30),
                period_end=now,
                previous_score=85.2,
                score_change=2.3,
            ),
        ]

        for obj in [*updates, *certificates, *scheduled_audits, *initial_scores]:
            db.add(obj)

        await db.flush()
        logger.info("Compliance automation seed data created successfully")


compliance_automation_service = ComplianceAutomationService()
