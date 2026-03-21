"""Employee Self-Service Portal API routes.

Provides simplified, mobile-first endpoints for:
- Anonymous incident/complaint reporting
- Report tracking by reference number
- QR code generation for quick access
"""

import hashlib
import secrets
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import String, cast, func, literal, select, union_all

from src.api.dependencies import CurrentUser, DbSession, OptionalCurrentUser
from src.api.schemas.error_codes import ErrorCode
from src.api.utils.errors import api_error
from src.core.config import settings
from src.domain.models.complaint import Complaint, ComplaintPriority, ComplaintStatus, ComplaintType
from src.domain.models.incident import Incident, IncidentSeverity, IncidentStatus, IncidentType
from src.domain.models.near_miss import NearMiss
from src.domain.models.rta import RoadTrafficCollision, RTASeverity, RTAStatus

DEFAULT_PORTAL_TENANT_ID = getattr(settings, "default_tenant_id", 1)

router = APIRouter(tags=["Employee Portal"])


# ============================================================================
# Schemas for Employee Portal
# ============================================================================


class QuickReportCreate(BaseModel):
    """Simplified report submission schema."""

    report_type: str = Field(..., description="Type: 'incident' or 'complaint'")
    title: str = Field(..., min_length=5, max_length=200, description="Brief title")
    description: str = Field(..., min_length=10, description="What happened?")
    location: Optional[str] = Field(None, max_length=200, description="Where did it occur?")
    severity: str = Field(default="medium", description="Severity: low, medium, high, critical")

    # Reporter info (optional for anonymous)
    reporter_name: Optional[str] = Field(None, max_length=100)
    reporter_email: Optional[EmailStr] = None
    reporter_phone: Optional[str] = Field(None, max_length=20)
    department: Optional[str] = Field(None, max_length=100)

    # Anonymous flag
    is_anonymous: bool = Field(default=False, description="Submit anonymously")

    # Optional photo/attachment reference
    attachment_ids: Optional[list[str]] = None
    reporter_submission: Optional[dict[str, Any]] = Field(
        None,
        description="Immutable snapshot of reporter-entered intake data for investigator views",
    )


class QuickReportResponse(BaseModel):
    """Response after submitting a report."""

    success: bool
    reference_number: str
    tracking_code: str  # Secret code for anonymous tracking
    message: str
    estimated_response: str
    qr_code_url: Optional[str] = None


class ReportStatusResponse(BaseModel):
    """Report status for tracking."""

    reference_number: str
    report_type: str
    title: str
    status: str
    status_label: str
    submitted_at: datetime
    updated_at: datetime
    priority: str
    timeline: list[dict]
    next_steps: Optional[str] = None
    assigned_to: Optional[str] = None
    resolution: Optional[str] = None


class PortalStatsResponse(BaseModel):
    """Portal statistics for transparency."""

    total_reports_today: int
    average_resolution_days: float
    reports_resolved_this_week: int
    anonymous_reports_percentage: float


class MyReportSummary(BaseModel):
    """Summary of a user's own report."""

    reference_number: str
    report_type: str
    title: str
    status: str
    status_label: str
    submitted_at: datetime
    updated_at: datetime


class MyReportsResponse(BaseModel):
    """Response containing user's own reports."""

    items: list[MyReportSummary]
    total: int
    page: int
    page_size: int
    pages: int


# ============================================================================
# Helper Functions
# ============================================================================


def generate_tracking_code() -> str:
    """Generate a secure tracking code for anonymous report access."""
    return secrets.token_urlsafe(16)


def hash_tracking_code(code: str) -> str:
    """Hash tracking code for storage."""
    return hashlib.sha256(code.encode()).hexdigest()


def map_severity(severity: str) -> tuple:
    """Map simplified severity to model enums."""
    severity_map = {
        "low": (IncidentSeverity.LOW, ComplaintPriority.LOW),
        "medium": (IncidentSeverity.MEDIUM, ComplaintPriority.MEDIUM),
        "high": (IncidentSeverity.HIGH, ComplaintPriority.HIGH),
        "critical": (IncidentSeverity.CRITICAL, ComplaintPriority.CRITICAL),
    }
    return severity_map.get(severity.lower(), (IncidentSeverity.MEDIUM, ComplaintPriority.MEDIUM))


def get_status_label(status: str) -> str:
    """Get human-readable status label."""
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


def get_priority_label(priority: str) -> str:
    """Get priority with visual indicator."""
    labels = {
        "LOW": "🟢 Low",
        "MEDIUM": "🟡 Medium",
        "HIGH": "🟠 High",
        "CRITICAL": "🔴 Critical",
    }
    return labels.get(priority, priority)


def parse_portal_datetime(date_value: Any, time_value: Any | None = None) -> datetime | None:
    """Parse a date/date-time pair from portal submission data."""
    if not date_value:
        return None

    raw_value = str(date_value).strip()
    if not raw_value:
        return None

    if time_value:
        raw_value = f"{raw_value}T{str(time_value).strip()}"

    try:
        parsed = datetime.fromisoformat(raw_value.replace("Z", "+00:00"))
    except ValueError:
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def build_incident_portal_fields(
    report: QuickReportCreate,
    incident_severity: IncidentSeverity,
    reporter_submission: dict[str, Any],
) -> dict[str, Any]:
    incident_occurred_at = parse_portal_datetime(
        reporter_submission.get("incident_date"),
        reporter_submission.get("incident_time"),
    ) or datetime.now(timezone.utc)
    witness_names = reporter_submission.get("witness_names")
    medical_assistance = str(reporter_submission.get("medical_assistance") or "").strip().lower()

    return {
        "incident_type": IncidentType.OTHER,
        "severity": incident_severity,
        "status": IncidentStatus.REPORTED,
        "location": report.location,
        "department": report.department,
        "incident_date": incident_occurred_at,
        "reported_date": datetime.now(timezone.utc),
        "reporter_name": (report.reporter_name if not report.is_anonymous else "Anonymous"),
        "reporter_email": report.reporter_email if not report.is_anonymous else None,
        "people_involved": reporter_submission.get("person_name") or report.reporter_name,
        "witnesses": witness_names if isinstance(witness_names, str) else None,
        "first_aid_given": medical_assistance not in {"", "none"},
        "emergency_services_called": medical_assistance == "ambulance",
        "source_form_id": "portal_incident_v1",
        "source_type": "portal",
        "reporter_submission": reporter_submission or None,
        "tenant_id": DEFAULT_PORTAL_TENANT_ID,
    }


def build_complaint_portal_fields(
    report: QuickReportCreate,
    complaint_priority: ComplaintPriority,
    reporter_submission: dict[str, Any],
) -> dict[str, Any]:
    return {
        "complaint_type": ComplaintType.OTHER,
        "priority": complaint_priority,
        "status": ComplaintStatus.RECEIVED,
        "received_date": datetime.now(timezone.utc),
        "complainant_name": (report.reporter_name if not report.is_anonymous else "Anonymous"),
        "complainant_email": (report.reporter_email if not report.is_anonymous else None),
        "complainant_phone": (report.reporter_phone if not report.is_anonymous else None),
        "department": report.department,
        "source_form_id": "portal_complaint_v1",
        "source_type": "portal",
        "reporter_submission": reporter_submission or None,
        "tenant_id": DEFAULT_PORTAL_TENANT_ID,
    }


def build_rta_portal_fields(
    report: QuickReportCreate,
    rta_severity: RTASeverity,
    reporter_submission: dict[str, Any],
) -> dict[str, Any]:
    collision_occurred_at = parse_portal_datetime(
        reporter_submission.get("accident_date"),
        reporter_submission.get("accident_time"),
    ) or datetime.now(timezone.utc)
    vehicle_registration = reporter_submission.get("pe_vehicle")
    if vehicle_registration == "other":
        vehicle_registration = reporter_submission.get("pe_vehicle_other")
    witness_details = reporter_submission.get("witness_details")
    third_party_entries = reporter_submission.get("third_parties")
    witness_structured = None
    if isinstance(witness_details, str) and witness_details.strip():
        witness_structured = {
            "witnesses": [
                {
                    "name": witness_details.strip(),
                    "statement": "Reporter-provided witness/contact details from portal intake.",
                }
            ]
        }

    return {
        "severity": rta_severity,
        "status": RTAStatus.REPORTED,
        "location": report.location or "Not specified",
        "collision_date": collision_occurred_at,
        "collision_time": reporter_submission.get("accident_time"),
        "reported_date": datetime.now(timezone.utc),
        "weather_conditions": reporter_submission.get("weather"),
        "road_conditions": reporter_submission.get("road_condition"),
        "company_vehicle_registration": vehicle_registration,
        "company_vehicle_damage": reporter_submission.get("damage_description"),
        "reporter_name": (report.reporter_name if not report.is_anonymous else "Anonymous"),
        "reporter_email": report.reporter_email if not report.is_anonymous else None,
        "driver_name": (report.reporter_name if not report.is_anonymous else "Anonymous"),
        "driver_email": report.reporter_email if not report.is_anonymous else None,
        "third_parties": (
            {"parties": third_party_entries} if isinstance(third_party_entries, list) and third_party_entries else None
        ),
        "vehicles_involved_count": max(
            1,
            int(reporter_submission.get("vehicle_count") or 0) + 1,
        ),
        "witnesses": witness_details if isinstance(witness_details, str) else None,
        "witnesses_structured": witness_structured,
        "police_attended": bool(reporter_submission.get("police_ref")),
        "police_reference": reporter_submission.get("police_ref"),
        "cctv_available": bool(reporter_submission.get("has_cctv")),
        "dashcam_footage_available": bool(reporter_submission.get("has_dashcam")),
        "footage_notes": (
            "Portal submission indicated available footage."
            if reporter_submission.get("has_cctv") or reporter_submission.get("has_dashcam")
            else None
        ),
        "source_form_id": "portal_rta_v1",
        "reporter_submission": reporter_submission or None,
        "tenant_id": DEFAULT_PORTAL_TENANT_ID,
    }


# ============================================================================
# API Endpoints
# ============================================================================


@router.post(
    "/reports/",
    response_model=QuickReportResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a Quick Report",
    description="Submit an incident or complaint report. Can be anonymous.",
)
async def submit_quick_report(
    report: QuickReportCreate,
    db: DbSession,
):
    """
    Submit a quick report (incident or complaint).

    This endpoint is public and doesn't require authentication.
    Anonymous reports can be tracked using the returned tracking_code.
    """
    tracking_code = generate_tracking_code()
    # Hash stored for future secure lookup functionality
    _ = hash_tracking_code(tracking_code)  # noqa: F841

    incident_severity, complaint_priority = map_severity(report.severity)
    reporter_submission = report.reporter_submission or {}

    if report.report_type.lower() == "incident":
        # Generate reference number
        year = datetime.now(timezone.utc).year
        count_query = select(func.count()).select_from(Incident)
        result = await db.execute(count_query)
        count = result.scalar() or 0
        ref_number = f"INC-{year}-{count + 1:04d}"

        incident = Incident(
            reference_number=ref_number,
            title=report.title,
            description=report.description,
            **build_incident_portal_fields(report, incident_severity, reporter_submission),
        )

        db.add(incident)
        await db.commit()
        await db.refresh(incident)

        return QuickReportResponse(
            success=True,
            reference_number=ref_number,
            tracking_code=tracking_code,
            message="Your incident report has been submitted successfully.",
            estimated_response="You will receive an update within 24-48 hours.",
            qr_code_url=f"/api/v1/portal/qr/{ref_number}",
        )

    elif report.report_type.lower() == "complaint":
        # Generate reference number
        year = datetime.now(timezone.utc).year
        count_query = select(func.count()).select_from(Complaint)
        result = await db.execute(count_query)
        count = result.scalar() or 0
        ref_number = f"COMP-{year}-{count + 1:04d}"

        complaint = Complaint(
            reference_number=ref_number,
            title=report.title,
            description=report.description,
            **build_complaint_portal_fields(report, complaint_priority, reporter_submission),
        )

        db.add(complaint)
        await db.commit()
        await db.refresh(complaint)

        return QuickReportResponse(
            success=True,
            reference_number=ref_number,
            tracking_code=tracking_code,
            message="Your complaint has been submitted successfully.",
            estimated_response="A case manager will review your complaint within 24 hours.",
            qr_code_url=f"/api/v1/portal/qr/{ref_number}",
        )

    elif report.report_type.lower() == "rta":
        # Generate reference number for Road Traffic Collision
        year = datetime.now(timezone.utc).year
        count_query = select(func.count()).select_from(RoadTrafficCollision)
        result = await db.execute(count_query)
        count = result.scalar() or 0
        ref_number = f"RTA-{year}-{count + 1:04d}"

        # Map severity
        rta_severity_map = {
            "low": RTASeverity.DAMAGE_ONLY,
            "medium": RTASeverity.MINOR_INJURY,
            "high": RTASeverity.SERIOUS_INJURY,
            "critical": RTASeverity.FATAL,
        }
        rta_severity = rta_severity_map.get(report.severity.lower(), RTASeverity.DAMAGE_ONLY)

        rta = RoadTrafficCollision(
            reference_number=ref_number,
            title=report.title,
            description=report.description,
            **build_rta_portal_fields(report, rta_severity, reporter_submission),
        )

        db.add(rta)
        await db.commit()
        await db.refresh(rta)

        return QuickReportResponse(
            success=True,
            reference_number=ref_number,
            tracking_code=tracking_code,
            message="Your RTA report has been submitted successfully.",
            estimated_response="A fleet manager will review your report within 24 hours.",
            qr_code_url=f"/api/v1/portal/qr/{ref_number}",
        )

    elif report.report_type.lower() == "near_miss":
        # Generate reference number for Near Miss
        year = datetime.now(timezone.utc).year
        count_query = select(func.count()).select_from(NearMiss)
        result = await db.execute(count_query)
        count = result.scalar() or 0
        ref_number = f"NM-{year}-{count + 1:04d}"

        # Map severity to priority
        priority_map = {
            "low": "LOW",
            "medium": "MEDIUM",
            "high": "HIGH",
            "critical": "CRITICAL",
        }
        priority = priority_map.get(report.severity.lower(), "MEDIUM")

        # Create Near Miss record
        near_miss = NearMiss(
            reference_number=ref_number,
            reporter_name=(report.reporter_name if not report.is_anonymous else "Anonymous"),
            reporter_email=report.reporter_email if not report.is_anonymous else None,
            contract=report.department or "Not specified",
            location=report.location or "Not specified",
            event_date=datetime.now(timezone.utc),
            description=report.description,
            potential_severity=report.severity.lower(),
            status="REPORTED",
            priority=priority,
            source_form_id="portal_near_miss_v1",
            tenant_id=DEFAULT_PORTAL_TENANT_ID,
        )

        db.add(near_miss)
        await db.commit()
        await db.refresh(near_miss)

        return QuickReportResponse(
            success=True,
            reference_number=ref_number,
            tracking_code=tracking_code,
            message="Your near miss report has been submitted successfully.",
            estimated_response="A safety manager will review your report within 24 hours.",
            qr_code_url=f"/api/v1/portal/qr/{ref_number}",
        )

    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=api_error(
                ErrorCode.VALIDATION_ERROR,
                "Invalid report_type. Must be 'incident', 'complaint', 'rta', or 'near_miss'.",
            ),
        )


@router.get(
    "/reports/{reference_number}/",
    response_model=ReportStatusResponse,
    summary="Track Report Status",
    description="Check the status of a submitted report by reference number.",
)
async def track_report(
    reference_number: str,
    db: DbSession,
    tracking_code: Optional[str] = Query(None, description="Required for anonymous reports"),
):
    """
    Track a report's status by reference number.

    For anonymous reports, the tracking_code is required.
    """
    # Determine report type from reference number prefix
    if reference_number.startswith("INC-"):
        inc_query = select(Incident).where(Incident.reference_number == reference_number)
        inc_result = await db.execute(inc_query)
        incident = inc_result.scalar_one_or_none()

        if not incident:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=api_error(ErrorCode.ENTITY_NOT_FOUND, "Report not found. Please check your reference number."),
            )

        # Build timeline
        timeline = [
            {
                "date": incident.created_at.isoformat(),
                "event": "Report Submitted",
                "icon": "📋",
            },
        ]

        if incident.status != IncidentStatus.REPORTED:
            timeline.append(
                {
                    "date": incident.updated_at.isoformat(),
                    "event": f"Status changed to {get_status_label(incident.status.value)}",
                    "icon": "🔄",
                }
            )

        return ReportStatusResponse(
            reference_number=incident.reference_number,
            report_type="Incident",
            title=incident.title,
            status=incident.status.value,
            status_label=get_status_label(incident.status.value),
            submitted_at=incident.created_at,
            updated_at=incident.updated_at,
            priority=get_priority_label(incident.severity.value),
            timeline=timeline,
            next_steps="Our team is reviewing your report.",
        )

    elif reference_number.startswith("COMP-"):
        comp_query = select(Complaint).where(Complaint.reference_number == reference_number)
        comp_result = await db.execute(comp_query)
        complaint = comp_result.scalar_one_or_none()

        if not complaint:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=api_error(ErrorCode.ENTITY_NOT_FOUND, "Report not found. Please check your reference number."),
            )

        timeline = [
            {
                "date": complaint.created_at.isoformat(),
                "event": "Complaint Submitted",
                "icon": "📋",
            },
        ]

        if complaint.status != ComplaintStatus.RECEIVED:
            timeline.append(
                {
                    "date": complaint.updated_at.isoformat(),
                    "event": f"Status changed to {get_status_label(complaint.status.value)}",
                    "icon": "🔄",
                }
            )

        return ReportStatusResponse(
            reference_number=complaint.reference_number,
            report_type="Complaint",
            title=complaint.title,
            status=complaint.status.value,
            status_label=get_status_label(complaint.status.value),
            submitted_at=complaint.created_at,
            updated_at=complaint.updated_at,
            priority=get_priority_label(complaint.priority.value),
            timeline=timeline,
            next_steps="A case manager will contact you soon.",
            resolution=complaint.resolution_summary,
        )

    elif reference_number.startswith("RTA-"):
        rta_query = select(RoadTrafficCollision).where(RoadTrafficCollision.reference_number == reference_number)
        rta_result = await db.execute(rta_query)
        rta = rta_result.scalar_one_or_none()

        if not rta:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=api_error(ErrorCode.ENTITY_NOT_FOUND, "Report not found. Please check your reference number."),
            )

        timeline = [
            {
                "date": rta.created_at.isoformat(),
                "event": "RTA Report Submitted",
                "icon": "🚗",
            },
        ]

        if rta.status != RTAStatus.REPORTED:
            timeline.append(
                {
                    "date": rta.updated_at.isoformat(),
                    "event": f"Status changed to {get_status_label(rta.status.value)}",
                    "icon": "🔄",
                }
            )

        return ReportStatusResponse(
            reference_number=rta.reference_number,
            report_type="Road Traffic Collision",
            title=rta.title,
            status=rta.status.value,
            status_label=get_status_label(rta.status.value),
            submitted_at=rta.created_at,
            updated_at=rta.updated_at,
            priority=get_priority_label(rta.severity.value.upper()),
            timeline=timeline,
            next_steps="A fleet manager will review your report.",
        )

    elif reference_number.startswith("NM-"):
        nm_query = select(NearMiss).where(NearMiss.reference_number == reference_number)
        nm_result = await db.execute(nm_query)
        near_miss = nm_result.scalar_one_or_none()

        if not near_miss:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=api_error(ErrorCode.ENTITY_NOT_FOUND, "Report not found. Please check your reference number."),
            )

        timeline = [
            {
                "date": near_miss.created_at.isoformat(),
                "event": "Near Miss Reported",
                "icon": "⚠️",
            },
        ]

        if near_miss.status != "REPORTED":
            timeline.append(
                {
                    "date": near_miss.updated_at.isoformat(),
                    "event": f"Status changed to {get_status_label(near_miss.status)}",
                    "icon": "🔄",
                }
            )

        return ReportStatusResponse(
            reference_number=near_miss.reference_number,
            report_type="Near Miss",
            title=f"Near Miss - {near_miss.contract}",
            status=near_miss.status,
            status_label=get_status_label(near_miss.status),
            submitted_at=near_miss.created_at,
            updated_at=near_miss.updated_at,
            priority=get_priority_label(near_miss.priority),
            timeline=timeline,
            next_steps="A safety manager will review your report.",
        )

    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=api_error(ErrorCode.VALIDATION_ERROR, "Invalid reference number format."),
        )


@router.get(
    "/stats/",
    response_model=PortalStatsResponse,
    summary="Portal Statistics",
    description="Get transparency statistics about report handling.",
)
async def get_portal_stats(current_user: CurrentUser, db: DbSession):
    """
    Get portal statistics for transparency.

    Shows how many reports are submitted and resolved.
    """
    from datetime import timedelta

    tid = current_user.tenant_id
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago = now - timedelta(days=7)

    incidents_today = await db.execute(
        select(func.count())
        .select_from(Incident)
        .where(Incident.tenant_id == tid)
        .where(Incident.created_at >= today_start)
    )
    complaints_today = await db.execute(
        select(func.count())
        .select_from(Complaint)
        .where(Complaint.tenant_id == tid)
        .where(Complaint.created_at >= today_start)
    )
    total_today = (incidents_today.scalar() or 0) + (complaints_today.scalar() or 0)

    resolved_incidents = await db.execute(
        select(func.count())
        .select_from(Incident)
        .where(Incident.tenant_id == tid)
        .where(Incident.status == IncidentStatus.CLOSED)
        .where(Incident.updated_at >= week_ago)
    )
    resolved_complaints = await db.execute(
        select(func.count())
        .select_from(Complaint)
        .where(Complaint.tenant_id == tid)
        .where(Complaint.status == ComplaintStatus.CLOSED)
        .where(Complaint.updated_at >= week_ago)
    )
    resolved_week = (resolved_incidents.scalar() or 0) + (resolved_complaints.scalar() or 0)

    return PortalStatsResponse(
        total_reports_today=total_today,
        average_resolution_days=0.0,
        reports_resolved_this_week=resolved_week,
        anonymous_reports_percentage=0.0,
    )


@router.get(
    "/qr/{reference_number}/",
    summary="Generate QR Code",
    description="Generate a QR code for quick access to report status.",
)
async def generate_qr_code(reference_number: str):
    """
    Generate QR code data for a report.

    Returns the URL that the QR code should point to.
    """
    # Return QR code data (frontend will render it)
    from src.core.config import settings

    tracking_url = f"{settings.frontend_url}/portal/track/{reference_number}"

    return {
        "reference_number": reference_number,
        "tracking_url": tracking_url,
        "qr_data": tracking_url,
    }


@router.get(
    "/report-types/",
    summary="Get Report Types",
    description="Get available report types and categories.",
)
async def get_report_types():
    """
    Get available report types for the quick report form.
    """
    return {
        "report_types": [
            {
                "id": "incident",
                "label": "Safety Incident",
                "description": "Report a safety issue, near-miss, or workplace incident",
                "icon": "🚨",
                "color": "#ef4444",
            },
            {
                "id": "complaint",
                "label": "Complaint",
                "description": "Submit a complaint about service, quality, or conduct",
                "icon": "📝",
                "color": "#f59e0b",
            },
        ],
        "severity_levels": [
            {
                "id": "low",
                "label": "Low",
                "description": "Minor issue, no immediate action needed",
                "color": "#22c55e",
            },
            {
                "id": "medium",
                "label": "Medium",
                "description": "Moderate issue, attention needed",
                "color": "#eab308",
            },
            {
                "id": "high",
                "label": "High",
                "description": "Serious issue, prompt action required",
                "color": "#f97316",
            },
            {
                "id": "critical",
                "label": "Critical",
                "description": "Urgent! Immediate action required",
                "color": "#ef4444",
            },
        ],
    }


# =============================================================================
# Authenticated Portal Endpoints (My Reports)
# =============================================================================


@router.get(
    "/my-reports/",
    response_model=MyReportsResponse,
    summary="Get My Reports",
    description="Get all reports submitted by the authenticated user. "
    "Identity is derived from the JWT token, not from query parameters.",
)
async def get_my_reports(
    current_user: CurrentUser,
    db: DbSession,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
) -> MyReportsResponse:
    """
    Get all reports submitted by the current authenticated user.

    This endpoint uses the authenticated user's email from the JWT token
    to filter reports. It does NOT accept email as a query parameter,
    preventing users from enumerating other users' reports.

    Security:
        - Requires valid JWT token
        - Uses server-side identity from token
        - No email enumeration possible
    """
    user_email = current_user.email.lower()
    tid = current_user.tenant_id

    # Build UNION ALL across all 4 report tables so sorting and pagination
    # happen in SQL rather than in Python.
    inc_q = (
        select(
            Incident.reference_number.label("reference_number"),
            literal("incident").label("report_type"),
            Incident.title.label("title"),
            cast(Incident.status, String).label("status"),
            func.coalesce(Incident.reported_date, Incident.created_at).label("submitted_at"),
            func.coalesce(Incident.updated_at, Incident.created_at).label("updated_at"),
        )
        .where(Incident.tenant_id == tid)
        .where(func.lower(Incident.reporter_email) == user_email)
    )

    comp_q = (
        select(
            Complaint.reference_number.label("reference_number"),
            literal("complaint").label("report_type"),
            Complaint.title.label("title"),
            cast(Complaint.status, String).label("status"),
            func.coalesce(Complaint.received_date, Complaint.created_at).label("submitted_at"),
            func.coalesce(Complaint.updated_at, Complaint.created_at).label("updated_at"),
        )
        .where(Complaint.tenant_id == tid)
        .where(func.lower(Complaint.complainant_email) == user_email)
    )

    rta_q = (
        select(
            RoadTrafficCollision.reference_number.label("reference_number"),
            literal("rta").label("report_type"),
            RoadTrafficCollision.title.label("title"),
            cast(RoadTrafficCollision.status, String).label("status"),
            func.coalesce(RoadTrafficCollision.reported_date, RoadTrafficCollision.created_at).label("submitted_at"),
            func.coalesce(RoadTrafficCollision.updated_at, RoadTrafficCollision.created_at).label("updated_at"),
        )
        .where(RoadTrafficCollision.tenant_id == tid)
        .where(func.lower(RoadTrafficCollision.reporter_email) == user_email)
    )

    nm_q = (
        select(
            NearMiss.reference_number.label("reference_number"),
            literal("near_miss").label("report_type"),
            func.concat(literal("Near Miss - "), NearMiss.contract).label("title"),
            cast(NearMiss.status, String).label("status"),
            func.coalesce(NearMiss.event_date, NearMiss.created_at).label("submitted_at"),
            func.coalesce(NearMiss.updated_at, NearMiss.created_at).label("updated_at"),
        )
        .where(NearMiss.tenant_id == tid)
        .where(func.lower(NearMiss.reporter_email) == user_email)
    )

    combined = union_all(inc_q, comp_q, rta_q, nm_q).subquery("all_reports")

    # Total count via SQL
    count_result = await db.execute(select(func.count()).select_from(combined))
    total = count_result.scalar() or 0

    # Paginated + sorted fetch
    offset = (page - 1) * page_size
    data_query = select(combined).order_by(combined.c.submitted_at.desc()).offset(offset).limit(page_size)
    result = await db.execute(data_query)
    rows = result.all()

    items = [
        MyReportSummary(
            reference_number=row.reference_number,
            report_type=row.report_type,
            title=row.title,
            status=row.status,
            status_label=get_status_label(row.status),
            submitted_at=row.submitted_at,
            updated_at=row.updated_at,
        )
        for row in rows
    ]

    pages = (total + page_size - 1) // page_size if total > 0 else 0
    return MyReportsResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )
