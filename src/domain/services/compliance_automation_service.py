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
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ComplianceAutomationService:
    """
    Comprehensive compliance automation service.

    Monitors regulatory changes, tracks certificates,
    manages scheduled audits, and automates RIDDOR submissions.
    """

    def __init__(self) -> None:
        pass

    # ==================== Regulatory Monitoring ====================

    def get_regulatory_updates(
        self,
        source: Optional[str] = None,
        since: Optional[datetime] = None,
        impact: Optional[str] = None,
        reviewed: Optional[bool] = None,
    ) -> List[Dict[str, Any]]:
        """Get regulatory updates with filters."""
        # Mock data representing HSE and ISO updates
        updates = [
            {
                "id": 1,
                "source": "hse_uk",
                "source_reference": "HSE/2026/001",
                "title": "Updated guidance on workplace first aid requirements",
                "summary": "New requirements for first aid training and equipment in workplaces with 50+ employees.",
                "category": "health_safety",
                "impact": "high",
                "affected_standards": ["ISO 45001"],
                "affected_clauses": ["8.2", "7.2"],
                "published_date": "2026-01-15T00:00:00Z",
                "effective_date": "2026-04-01T00:00:00Z",
                "detected_at": "2026-01-16T09:00:00Z",
                "is_reviewed": False,
                "requires_action": True,
            },
            {
                "id": 2,
                "source": "iso",
                "source_reference": "ISO/TC 176/2026",
                "title": "Amendment to ISO 9001:2015 - Clause 4.4.1",
                "summary": "Clarification on process interaction requirements and documented information.",
                "category": "quality",
                "impact": "medium",
                "affected_standards": ["ISO 9001"],
                "affected_clauses": ["4.4.1"],
                "published_date": "2026-01-10T00:00:00Z",
                "effective_date": "2026-07-01T00:00:00Z",
                "detected_at": "2026-01-12T14:30:00Z",
                "is_reviewed": True,
                "requires_action": False,
            },
            {
                "id": 3,
                "source": "hse_uk",
                "source_reference": "HSE/2026/002",
                "title": "RIDDOR amendment - digital submission requirements",
                "summary": "All RIDDOR submissions must be made digitally from March 2026.",
                "category": "regulatory",
                "impact": "critical",
                "affected_standards": ["ISO 45001"],
                "affected_clauses": ["10.2"],
                "published_date": "2026-01-18T00:00:00Z",
                "effective_date": "2026-03-01T00:00:00Z",
                "detected_at": "2026-01-19T08:00:00Z",
                "is_reviewed": False,
                "requires_action": True,
            },
        ]

        # Apply filters
        if source:
            updates = [u for u in updates if u["source"] == source]
        if impact:
            updates = [u for u in updates if u["impact"] == impact]
        if reviewed is not None:
            updates = [u for u in updates if u["is_reviewed"] == reviewed]

        return updates

    def mark_update_reviewed(
        self,
        update_id: int,
        reviewed_by: int,
        requires_action: bool,
        action_notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Mark a regulatory update as reviewed."""
        return {
            "id": update_id,
            "is_reviewed": True,
            "reviewed_by": reviewed_by,
            "reviewed_at": datetime.utcnow().isoformat(),
            "requires_action": requires_action,
            "action_notes": action_notes,
        }

    # ==================== Gap Analysis ====================

    def run_gap_analysis(
        self,
        regulatory_update_id: Optional[int] = None,
        standard_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Run automated gap analysis."""
        now = datetime.utcnow()

        # Mock gap analysis results
        gaps = [
            {
                "id": 1,
                "clause": "8.2",
                "requirement": "First aid training for all staff",
                "current_state": "60% of staff trained",
                "gap_description": "40% of staff require first aid training",
                "severity": "high",
                "effort_hours": 40,
                "recommendation": "Schedule training sessions for remaining staff",
            },
            {
                "id": 2,
                "clause": "7.2",
                "requirement": "First aid equipment audit",
                "current_state": "Last audit was 18 months ago",
                "gap_description": "First aid equipment audit overdue",
                "severity": "medium",
                "effort_hours": 8,
                "recommendation": "Conduct immediate equipment audit",
            },
        ]

        return {
            "id": f"GA-{now.strftime('%Y%m%d%H%M%S')}",
            "regulatory_update_id": regulatory_update_id,
            "standard_id": standard_id,
            "title": "Gap Analysis - First Aid Requirements Update",
            "created_at": now.isoformat(),
            "total_gaps": len(gaps),
            "critical_gaps": sum(1 for g in gaps if g["severity"] == "critical"),
            "high_gaps": sum(1 for g in gaps if g["severity"] == "high"),
            "estimated_effort_hours": sum(g["effort_hours"] for g in gaps),
            "gaps": gaps,
            "recommendations": [
                "Prioritize high-severity gaps first",
                "Create CAPA for each identified gap",
                "Schedule follow-up audit in 3 months",
            ],
        }

    def get_gap_analyses(
        self,
        status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get list of gap analyses."""
        analyses = [
            {
                "id": "GA-20260119001",
                "title": "Gap Analysis - First Aid Requirements Update",
                "total_gaps": 2,
                "high_gaps": 1,
                "status": "pending",
                "created_at": "2026-01-19T10:00:00Z",
            },
            {
                "id": "GA-20260115001",
                "title": "ISO 9001 Clause 4.4.1 Amendment Review",
                "total_gaps": 1,
                "high_gaps": 0,
                "status": "completed",
                "created_at": "2026-01-15T14:00:00Z",
            },
        ]

        if status:
            analyses = [a for a in analyses if a["status"] == status]

        return analyses

    # ==================== Certificate Tracking ====================

    def get_certificates(
        self,
        certificate_type: Optional[str] = None,
        entity_type: Optional[str] = None,
        status: Optional[str] = None,
        expiring_within_days: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Get certificates with filters."""
        now = datetime.utcnow()

        certificates = [
            {
                "id": 1,
                "name": "First Aid at Work Certificate",
                "certificate_type": "training",
                "entity_type": "user",
                "entity_id": "user-001",
                "entity_name": "John Smith",
                "issuing_body": "St John Ambulance",
                "issue_date": "2023-03-15",
                "expiry_date": (now + timedelta(days=45)).strftime("%Y-%m-%d"),
                "status": "expiring_soon",
                "is_critical": True,
            },
            {
                "id": 2,
                "name": "IPAF Licence",
                "certificate_type": "license",
                "entity_type": "user",
                "entity_id": "user-002",
                "entity_name": "Mike Johnson",
                "issuing_body": "IPAF",
                "issue_date": "2024-06-01",
                "expiry_date": (now + timedelta(days=180)).strftime("%Y-%m-%d"),
                "status": "valid",
                "is_critical": False,
            },
            {
                "id": 3,
                "name": "Crane Calibration Certificate",
                "certificate_type": "calibration",
                "entity_type": "equipment",
                "entity_id": "equip-005",
                "entity_name": "Mobile Crane MC-01",
                "issuing_body": "UKAS Accredited",
                "issue_date": "2025-01-10",
                "expiry_date": (now + timedelta(days=10)).strftime("%Y-%m-%d"),
                "status": "expiring_soon",
                "is_critical": True,
            },
            {
                "id": 4,
                "name": "ISO 9001 Accreditation",
                "certificate_type": "accreditation",
                "entity_type": "organization",
                "entity_id": "org-001",
                "entity_name": "Plantexpand Ltd",
                "issuing_body": "BSI",
                "issue_date": "2024-03-01",
                "expiry_date": (now + timedelta(days=400)).strftime("%Y-%m-%d"),
                "status": "valid",
                "is_critical": True,
            },
        ]

        # Apply filters
        if certificate_type:
            certificates = [c for c in certificates if c["certificate_type"] == certificate_type]
        if entity_type:
            certificates = [c for c in certificates if c["entity_type"] == entity_type]
        if status:
            certificates = [c for c in certificates if c["status"] == status]
        if expiring_within_days:
            cutoff = now + timedelta(days=expiring_within_days)
            certificates = [c for c in certificates if datetime.strptime(c["expiry_date"], "%Y-%m-%d") <= cutoff]

        return certificates

    def get_expiring_certificates_summary(self) -> Dict[str, Any]:
        """Get summary of expiring certificates."""
        return {
            "expired": 2,
            "expiring_7_days": 1,
            "expiring_30_days": 3,
            "expiring_90_days": 8,
            "total_critical": 4,
            "by_type": {
                "training": {"expired": 1, "expiring_30": 2},
                "equipment": {"expired": 0, "expiring_30": 1},
                "license": {"expired": 1, "expiring_30": 0},
                "calibration": {"expired": 0, "expiring_30": 0},
            },
        }

    # ==================== Scheduled Audits ====================

    def get_scheduled_audits(
        self,
        upcoming_days: Optional[int] = None,
        overdue: Optional[bool] = None,
    ) -> List[Dict[str, Any]]:
        """Get scheduled audits."""
        now = datetime.utcnow()

        audits = [
            {
                "id": 1,
                "name": "Monthly H&S Inspection - Site A",
                "audit_type": "safety_inspection",
                "frequency": "monthly",
                "next_due_date": (now + timedelta(days=5)).strftime("%Y-%m-%d"),
                "last_completed": (now - timedelta(days=25)).strftime("%Y-%m-%d"),
                "assigned_to": "Safety Team",
                "status": "scheduled",
                "standards": ["ISO 45001"],
            },
            {
                "id": 2,
                "name": "Quarterly ISO 9001 Internal Audit",
                "audit_type": "internal_audit",
                "frequency": "quarterly",
                "next_due_date": (now - timedelta(days=3)).strftime("%Y-%m-%d"),
                "last_completed": (now - timedelta(days=93)).strftime("%Y-%m-%d"),
                "assigned_to": "Quality Team",
                "status": "overdue",
                "standards": ["ISO 9001"],
            },
            {
                "id": 3,
                "name": "Annual Environmental Review",
                "audit_type": "environmental_audit",
                "frequency": "annual",
                "next_due_date": (now + timedelta(days=45)).strftime("%Y-%m-%d"),
                "last_completed": (now - timedelta(days=320)).strftime("%Y-%m-%d"),
                "assigned_to": "Environmental Manager",
                "status": "scheduled",
                "standards": ["ISO 14001"],
            },
        ]

        if overdue:
            audits = [a for a in audits if a["status"] == "overdue"]
        elif upcoming_days:
            cutoff = now + timedelta(days=upcoming_days)
            audits = [a for a in audits if datetime.strptime(a["next_due_date"], "%Y-%m-%d") <= cutoff]

        return audits

    # ==================== Compliance Scoring ====================

    def calculate_compliance_score(
        self,
        scope_type: str = "organization",
        scope_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Calculate compliance score."""
        # Mock comprehensive scoring
        return {
            "scope_type": scope_type,
            "scope_id": scope_id,
            "overall_score": 87.5,
            "previous_score": 85.2,
            "change": 2.3,
            "trend": "improving",
            "calculated_at": datetime.utcnow().isoformat(),
            "breakdown": {
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
            "key_gaps": [
                {"standard": "ISO 45001", "clause": "8.2", "description": "First aid training gaps"},
                {"standard": "ISO 14001", "clause": "6.1", "description": "Environmental risk register outdated"},
                {"standard": "ISO 9001", "clause": "10.2", "description": "NCR closure rate below target"},
            ],
            "recommendations": [
                "Focus on ISO 45001 clause 8.2 improvements",
                "Update environmental risk assessments",
                "Accelerate NCR closure process",
            ],
        }

    def get_compliance_trend(
        self,
        scope_type: str = "organization",
        months: int = 12,
    ) -> List[Dict[str, Any]]:
        """Get compliance score trend over time."""
        now = datetime.utcnow()
        trend = []

        for i in range(months, 0, -1):
            date = now - timedelta(days=i * 30)
            # Simulated gradual improvement
            base_score = 75 + (12 - i) * 1.2 + (i % 3) * 0.5
            trend.append(
                {
                    "period": date.strftime("%Y-%m"),
                    "overall_score": round(min(base_score, 95), 1),
                    "iso_9001": round(min(base_score + 4, 98), 1),
                    "iso_14001": round(min(base_score + 1, 95), 1),
                    "iso_45001": round(min(base_score - 3, 92), 1),
                }
            )

        return trend

    # ==================== RIDDOR Automation ====================

    def check_riddor_required(self, incident_data: Dict[str, Any]) -> Dict[str, Any]:
        """Check if an incident requires RIDDOR reporting."""
        riddor_types = []

        # Death
        if incident_data.get("fatality"):
            riddor_types.append("death")

        # Major injury
        if incident_data.get("injury_type") in ["fracture", "amputation", "dislocation", "loss_of_sight"]:
            riddor_types.append("specified_injury")

        # Over 7 day incapacitation
        if incident_data.get("days_off_work", 0) > 7:
            riddor_types.append("over_7_day_incapacitation")

        # Dangerous occurrence
        if incident_data.get("dangerous_occurrence"):
            riddor_types.append("dangerous_occurrence")

        # Occupational disease
        if incident_data.get("occupational_disease"):
            riddor_types.append("occupational_disease")

        is_riddor = len(riddor_types) > 0
        deadline = None
        if is_riddor:
            # Deaths and specified injuries: immediately (within 10 days for written)
            # Over 7 day: within 15 days
            if "death" in riddor_types or "specified_injury" in riddor_types:
                deadline = datetime.utcnow() + timedelta(days=10)
            else:
                deadline = datetime.utcnow() + timedelta(days=15)

        return {
            "is_riddor": is_riddor,
            "riddor_types": riddor_types,
            "deadline": deadline.isoformat() if deadline else None,
            "submission_url": "https://www.hse.gov.uk/riddor/report.htm" if is_riddor else None,
        }

    def prepare_riddor_submission(
        self,
        incident_id: int,
        riddor_type: str,
    ) -> Dict[str, Any]:
        """Prepare RIDDOR submission data."""
        # In production, would pull actual incident data
        return {
            "incident_id": incident_id,
            "riddor_type": riddor_type,
            "submission_data": {
                "report_type": riddor_type,
                "date_of_incident": "2026-01-19",
                "time_of_incident": "14:30",
                "location": "Site A, Warehouse 3",
                "injured_person": {
                    "name": "John Smith",
                    "occupation": "Warehouse Operative",
                    "employment_status": "employee",
                },
                "injury_details": {
                    "type": "fracture",
                    "body_part": "right_arm",
                    "severity": "specified_injury",
                },
                "incident_description": "Worker fell from ladder while accessing high shelving.",
                "immediate_actions": "First aid administered, ambulance called, area secured.",
                "preventive_measures": "Ladder inspection protocol to be reviewed, additional training scheduled.",
                "reporter": {
                    "name": "Safety Manager",
                    "position": "H&S Manager",
                    "contact": "safety@plantexpand.com",
                },
            },
            "deadline": (datetime.utcnow() + timedelta(days=10)).isoformat(),
            "status": "ready_to_submit",
        }

    def submit_riddor(
        self,
        incident_id: int,
        submitted_by: int,
    ) -> Dict[str, Any]:
        """Submit RIDDOR report to HSE."""
        # In production, would integrate with HSE API
        return {
            "incident_id": incident_id,
            "status": "submitted",
            "hse_reference": f"RIDDOR-2026-{incident_id:06d}",
            "submitted_at": datetime.utcnow().isoformat(),
            "submitted_by": submitted_by,
            "confirmation": "Report successfully submitted to HSE. Reference number provided.",
        }


# Singleton instance
compliance_automation_service = ComplianceAutomationService()
