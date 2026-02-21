"""Employee portal domain service.

Extracts report submission, tracking, stats, and "my reports" logic
from the employee_portal route module.
"""

import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.complaint import Complaint, ComplaintPriority, ComplaintStatus, ComplaintType
from src.domain.models.incident import Incident, IncidentSeverity, IncidentStatus, IncidentType
from src.domain.models.near_miss import NearMiss
from src.domain.models.rta import RoadTrafficCollision, RTASeverity, RTAStatus
from src.domain.services.reference_number import ReferenceNumberService
from src.infrastructure.monitoring.azure_monitor import track_metric

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _generate_tracking_code() -> str:
    return secrets.token_urlsafe(16)


def _hash_tracking_code(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()


def _map_severity(severity: str) -> tuple:
    severity_map = {
        "low": (IncidentSeverity.LOW, ComplaintPriority.LOW),
        "medium": (IncidentSeverity.MEDIUM, ComplaintPriority.MEDIUM),
        "high": (IncidentSeverity.HIGH, ComplaintPriority.HIGH),
        "critical": (IncidentSeverity.CRITICAL, ComplaintPriority.CRITICAL),
    }
    return severity_map.get(severity.lower(), (IncidentSeverity.MEDIUM, ComplaintPriority.MEDIUM))


def _get_status_label(status: str) -> str:
    labels = {
        "REPORTED": "📋 Submitted",
        "OPEN": "📋 Open",
        "UNDER_INVESTIGATION": "🔍 Under Investigation",
        "IN_PROGRESS": "⚙️ In Progress",
        "PENDING_REVIEW": "👀 Pending Review",
        "RESOLVED": "✅ Resolved",
        "CLOSED": "🏁 Closed",
        "REJECTED": "❌ Rejected",
    }
    return labels.get(status, status)


def _get_priority_label(priority: str) -> str:
    labels = {
        "LOW": "🟢 Low",
        "MEDIUM": "🟡 Medium",
        "HIGH": "🟠 High",
        "CRITICAL": "🔴 Critical",
    }
    return labels.get(priority, priority)


class PortalService:
    """Handles employee portal report submission, tracking, and statistics."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ------------------------------------------------------------------
    # Submit quick report
    # ------------------------------------------------------------------

    async def submit_report(self, report_data: BaseModel) -> dict[str, Any]:
        """Submit a quick report (incident, complaint, rta, or near_miss).

        Raises:
            ValueError: If the report type is unsupported.
        """
        data = report_data.model_dump()
        report_type = data["report_type"].lower()
        track_metric("portal.submission", 1, {"report_type": report_type})
        track_metric("portal.reports_submitted", 1)

        tracking_code = _generate_tracking_code()
        _ = _hash_tracking_code(tracking_code)  # noqa: F841

        incident_severity, complaint_priority = _map_severity(data.get("severity", "medium"))
        is_anonymous = data.get("is_anonymous", False)

        if report_type == "incident":
            return await self._submit_incident(data, incident_severity, is_anonymous, tracking_code)
        elif report_type == "complaint":
            return await self._submit_complaint(data, complaint_priority, is_anonymous, tracking_code)
        elif report_type == "rta":
            return await self._submit_rta(data, is_anonymous, tracking_code)
        elif report_type == "near_miss":
            return await self._submit_near_miss(data, is_anonymous, tracking_code)
        else:
            raise ValueError(f"Unsupported report type: {report_type}")

    async def _submit_incident(
        self, data: dict, severity: IncidentSeverity, is_anonymous: bool, tracking_code: str
    ) -> dict[str, Any]:
        ref_number = await ReferenceNumberService.generate(self.db, "incident", Incident)
        incident = Incident(
            reference_number=ref_number,
            title=data["title"],
            description=data["description"],
            incident_type=IncidentType.OTHER,
            severity=severity,
            status=IncidentStatus.REPORTED,
            location=data.get("location"),
            department=data.get("department"),
            incident_date=datetime.now(timezone.utc),
            reported_date=datetime.now(timezone.utc),
            tenant_id=1,
            reporter_name=data.get("reporter_name") if not is_anonymous else "Anonymous",
            reporter_email=data.get("reporter_email") if not is_anonymous else None,
            source_form_id="portal_incident_v1",
            source_type="portal",
        )
        self.db.add(incident)
        await self.db.commit()
        await self.db.refresh(incident)

        return {
            "success": True,
            "reference_number": ref_number,
            "tracking_code": tracking_code,
            "message": "Your incident report has been submitted successfully.",
            "estimated_response": "You will receive an update within 24-48 hours.",
            "qr_code_url": f"/api/v1/portal/qr/{ref_number}",
        }

    async def _submit_complaint(
        self, data: dict, priority: ComplaintPriority, is_anonymous: bool, tracking_code: str
    ) -> dict[str, Any]:
        ref_number = await ReferenceNumberService.generate(self.db, "complaint", Complaint)
        complaint = Complaint(
            reference_number=ref_number,
            title=data["title"],
            description=data["description"],
            complaint_type=ComplaintType.OTHER,
            priority=priority,
            status=ComplaintStatus.RECEIVED,
            received_date=datetime.now(timezone.utc),
            tenant_id=1,
            complainant_name=data.get("reporter_name") if not is_anonymous else "Anonymous",
            complainant_email=data.get("reporter_email") if not is_anonymous else None,
            complainant_phone=data.get("reporter_phone") if not is_anonymous else None,
            source_form_id="portal_complaint_v1",
            source_type="portal",
        )
        self.db.add(complaint)
        await self.db.commit()
        await self.db.refresh(complaint)

        return {
            "success": True,
            "reference_number": ref_number,
            "tracking_code": tracking_code,
            "message": "Your complaint has been submitted successfully.",
            "estimated_response": "A case manager will review your complaint within 24 hours.",
            "qr_code_url": f"/api/v1/portal/qr/{ref_number}",
        }

    async def _submit_rta(self, data: dict, is_anonymous: bool, tracking_code: str) -> dict[str, Any]:
        ref_number = await ReferenceNumberService.generate(self.db, "rta", RoadTrafficCollision)
        rta_severity_map = {
            "low": RTASeverity.DAMAGE_ONLY,
            "medium": RTASeverity.MINOR_INJURY,
            "high": RTASeverity.SERIOUS_INJURY,
            "critical": RTASeverity.FATAL,
        }
        rta_severity = rta_severity_map.get(data.get("severity", "low").lower(), RTASeverity.DAMAGE_ONLY)

        rta = RoadTrafficCollision(
            reference_number=ref_number,
            title=data["title"],
            description=data["description"],
            severity=rta_severity,
            status=RTAStatus.REPORTED,
            location=data.get("location") or "Not specified",
            collision_date=datetime.now(timezone.utc),
            reported_date=datetime.now(timezone.utc),
            tenant_id=1,
            reporter_name=data.get("reporter_name") if not is_anonymous else "Anonymous",
            reporter_email=data.get("reporter_email") if not is_anonymous else None,
            driver_name=data.get("reporter_name") if not is_anonymous else "Anonymous",
            source_form_id="portal_rta_v1",
        )
        self.db.add(rta)
        await self.db.commit()
        await self.db.refresh(rta)

        return {
            "success": True,
            "reference_number": ref_number,
            "tracking_code": tracking_code,
            "message": "Your RTA report has been submitted successfully.",
            "estimated_response": "A fleet manager will review your report within 24 hours.",
            "qr_code_url": f"/api/v1/portal/qr/{ref_number}",
        }

    async def _submit_near_miss(self, data: dict, is_anonymous: bool, tracking_code: str) -> dict[str, Any]:
        ref_number = await ReferenceNumberService.generate(self.db, "near_miss", NearMiss)
        priority_map = {"low": "LOW", "medium": "MEDIUM", "high": "HIGH", "critical": "CRITICAL"}
        priority = priority_map.get(data.get("severity", "medium").lower(), "MEDIUM")

        near_miss = NearMiss(
            reference_number=ref_number,
            reporter_name=data.get("reporter_name") if not is_anonymous else "Anonymous",
            reporter_email=data.get("reporter_email") if not is_anonymous else None,
            contract=data.get("department") or "Not specified",
            location=data.get("location") or "Not specified",
            event_date=datetime.now(timezone.utc),
            description=data["description"],
            potential_severity=data.get("severity", "medium").lower(),
            status="REPORTED",
            priority=priority,
            tenant_id=1,
            source_form_id="portal_near_miss_v1",
        )
        self.db.add(near_miss)
        await self.db.commit()
        await self.db.refresh(near_miss)

        return {
            "success": True,
            "reference_number": ref_number,
            "tracking_code": tracking_code,
            "message": "Your near miss report has been submitted successfully.",
            "estimated_response": "A safety manager will review your report within 24 hours.",
            "qr_code_url": f"/api/v1/portal/qr/{ref_number}",
        }

    # ------------------------------------------------------------------
    # Track report
    # ------------------------------------------------------------------

    async def track_report(self, reference_number: str) -> dict[str, Any]:
        """Look up a report by its reference number and return status info.

        Raises:
            LookupError: If the report is not found.
            ValueError: If the reference number prefix is unrecognised.
        """
        if reference_number.startswith("INC-"):
            return await self._track_incident(reference_number)
        elif reference_number.startswith("COMP-"):
            return await self._track_complaint(reference_number)
        elif reference_number.startswith("RTA-"):
            return await self._track_rta(reference_number)
        elif reference_number.startswith("NM-"):
            return await self._track_near_miss(reference_number)
        else:
            raise ValueError(f"Unrecognised reference number prefix: {reference_number}")

    async def _track_incident(self, reference_number: str) -> dict[str, Any]:
        result = await self.db.execute(select(Incident).where(Incident.reference_number == reference_number))
        incident = result.scalar_one_or_none()
        if not incident:
            raise LookupError(f"Report {reference_number} not found")

        timeline = [{"date": incident.created_at.isoformat(), "event": "Report Submitted", "icon": "📋"}]
        if incident.status != IncidentStatus.REPORTED:
            timeline.append(
                {
                    "date": incident.updated_at.isoformat(),
                    "event": f"Status changed to {_get_status_label(incident.status.value)}",
                    "icon": "🔄",
                }
            )

        return {
            "reference_number": incident.reference_number,
            "report_type": "Incident",
            "title": incident.title,
            "status": incident.status.value,
            "status_label": _get_status_label(incident.status.value),
            "submitted_at": incident.created_at,
            "updated_at": incident.updated_at,
            "priority": _get_priority_label(incident.severity.value),
            "timeline": timeline,
            "next_steps": "Our team is reviewing your report.",
        }

    async def _track_complaint(self, reference_number: str) -> dict[str, Any]:
        result = await self.db.execute(select(Complaint).where(Complaint.reference_number == reference_number))
        complaint = result.scalar_one_or_none()
        if not complaint:
            raise LookupError(f"Report {reference_number} not found")

        timeline = [{"date": complaint.created_at.isoformat(), "event": "Complaint Submitted", "icon": "📋"}]
        if complaint.status != ComplaintStatus.RECEIVED:
            timeline.append(
                {
                    "date": complaint.updated_at.isoformat(),
                    "event": f"Status changed to {_get_status_label(complaint.status.value)}",
                    "icon": "🔄",
                }
            )

        return {
            "reference_number": complaint.reference_number,
            "report_type": "Complaint",
            "title": complaint.title,
            "status": complaint.status.value,
            "status_label": _get_status_label(complaint.status.value),
            "submitted_at": complaint.created_at,
            "updated_at": complaint.updated_at,
            "priority": _get_priority_label(complaint.priority.value),
            "timeline": timeline,
            "next_steps": "A case manager will contact you soon.",
            "resolution": complaint.resolution_summary,
        }

    async def _track_rta(self, reference_number: str) -> dict[str, Any]:
        result = await self.db.execute(
            select(RoadTrafficCollision).where(RoadTrafficCollision.reference_number == reference_number)
        )
        rta = result.scalar_one_or_none()
        if not rta:
            raise LookupError(f"Report {reference_number} not found")

        timeline = [{"date": rta.created_at.isoformat(), "event": "RTA Report Submitted", "icon": "🚗"}]
        if rta.status != RTAStatus.REPORTED:
            timeline.append(
                {
                    "date": rta.updated_at.isoformat(),
                    "event": f"Status changed to {_get_status_label(rta.status.value)}",
                    "icon": "🔄",
                }
            )

        return {
            "reference_number": rta.reference_number,
            "report_type": "Road Traffic Collision",
            "title": rta.title,
            "status": rta.status.value,
            "status_label": _get_status_label(rta.status.value),
            "submitted_at": rta.created_at,
            "updated_at": rta.updated_at,
            "priority": _get_priority_label(rta.severity.value.upper()),
            "timeline": timeline,
            "next_steps": "A fleet manager will review your report.",
        }

    async def _track_near_miss(self, reference_number: str) -> dict[str, Any]:
        result = await self.db.execute(select(NearMiss).where(NearMiss.reference_number == reference_number))
        near_miss = result.scalar_one_or_none()
        if not near_miss:
            raise LookupError(f"Report {reference_number} not found")

        timeline = [{"date": near_miss.created_at.isoformat(), "event": "Near Miss Reported", "icon": "⚠️"}]
        if near_miss.status != "REPORTED":
            timeline.append(
                {
                    "date": near_miss.updated_at.isoformat(),
                    "event": f"Status changed to {_get_status_label(near_miss.status)}",
                    "icon": "🔄",
                }
            )

        return {
            "reference_number": near_miss.reference_number,
            "report_type": "Near Miss",
            "title": f"Near Miss - {near_miss.contract}",
            "status": near_miss.status,
            "status_label": _get_status_label(near_miss.status),
            "submitted_at": near_miss.created_at,
            "updated_at": near_miss.updated_at,
            "priority": _get_priority_label(near_miss.priority),
            "timeline": timeline,
            "next_steps": "A safety manager will review your report.",
        }

    # ------------------------------------------------------------------
    # Portal stats
    # ------------------------------------------------------------------

    async def get_stats(self) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_ago = now - timedelta(days=7)

        incidents_today = await self.db.execute(
            select(func.count()).select_from(Incident).where(Incident.created_at >= today_start)
        )
        complaints_today = await self.db.execute(
            select(func.count()).select_from(Complaint).where(Complaint.created_at >= today_start)
        )
        total_today = (incidents_today.scalar() or 0) + (complaints_today.scalar() or 0)

        resolved_incidents = await self.db.execute(
            select(func.count())
            .select_from(Incident)
            .where(Incident.status == IncidentStatus.CLOSED)
            .where(Incident.updated_at >= week_ago)
        )
        resolved_complaints = await self.db.execute(
            select(func.count())
            .select_from(Complaint)
            .where(Complaint.status == ComplaintStatus.CLOSED)
            .where(Complaint.updated_at >= week_ago)
        )
        resolved_week = (resolved_incidents.scalar() or 0) + (resolved_complaints.scalar() or 0)

        return {
            "total_reports_today": total_today,
            "average_resolution_days": 3.2,
            "reports_resolved_this_week": resolved_week,
            "anonymous_reports_percentage": 15.0,
        }

    # ------------------------------------------------------------------
    # My reports
    # ------------------------------------------------------------------

    async def get_my_reports(
        self,
        user_email: str,
        *,
        page: int = 1,
        page_size: int = 20,
    ) -> dict[str, Any]:
        """Fetch all reports submitted by a given email address.

        Returns:
            Dict with items, total, page, page_size.
        """
        email_lower = user_email.lower()
        all_reports: list[dict[str, Any]] = []

        # Incidents
        incidents_result = await self.db.execute(
            select(Incident).where(func.lower(Incident.reporter_email) == email_lower)
        )
        for inc in incidents_result.scalars().all():
            status_val = inc.status.value if hasattr(inc.status, "value") else str(inc.status)
            all_reports.append(
                {
                    "reference_number": inc.reference_number,
                    "report_type": "incident",
                    "title": inc.title,
                    "status": status_val,
                    "status_label": _get_status_label(status_val),
                    "submitted_at": inc.reported_date or inc.created_at,
                    "updated_at": inc.updated_at or inc.created_at,
                }
            )

        # Complaints
        complaints_result = await self.db.execute(
            select(Complaint).where(func.lower(Complaint.complainant_email) == email_lower)
        )
        for comp in complaints_result.scalars().all():
            status_val = comp.status.value if hasattr(comp.status, "value") else str(comp.status)
            all_reports.append(
                {
                    "reference_number": comp.reference_number,
                    "report_type": "complaint",
                    "title": comp.title,
                    "status": status_val,
                    "status_label": _get_status_label(status_val),
                    "submitted_at": comp.received_date or comp.created_at,
                    "updated_at": comp.updated_at or comp.created_at,
                }
            )

        # RTAs
        rtas_result = await self.db.execute(
            select(RoadTrafficCollision).where(func.lower(RoadTrafficCollision.reporter_email) == email_lower)
        )
        for rta in rtas_result.scalars().all():
            status_val = rta.status.value if hasattr(rta.status, "value") else str(rta.status)
            all_reports.append(
                {
                    "reference_number": rta.reference_number,
                    "report_type": "rta",
                    "title": rta.title,
                    "status": status_val,
                    "status_label": _get_status_label(status_val),
                    "submitted_at": rta.reported_date or rta.created_at,
                    "updated_at": rta.updated_at or rta.created_at,
                }
            )

        # Near misses
        nm_result = await self.db.execute(select(NearMiss).where(func.lower(NearMiss.reporter_email) == email_lower))
        for nm in nm_result.scalars().all():
            all_reports.append(
                {
                    "reference_number": nm.reference_number,
                    "report_type": "near_miss",
                    "title": f"Near Miss - {nm.contract}",
                    "status": nm.status,
                    "status_label": _get_status_label(nm.status),
                    "submitted_at": nm.event_date or nm.created_at,
                    "updated_at": nm.updated_at or nm.created_at,
                }
            )

        all_reports.sort(key=lambda r: r["submitted_at"], reverse=True)

        total = len(all_reports)
        start = (page - 1) * page_size
        end = start + page_size
        paginated = all_reports[start:end]

        return {
            "items": paginated,
            "total": total,
            "page": page,
            "page_size": page_size,
        }
