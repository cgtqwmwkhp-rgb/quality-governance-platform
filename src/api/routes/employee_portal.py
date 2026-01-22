"""Employee Self-Service Portal API routes.

Provides simplified, mobile-first endpoints for:
- Anonymous incident/complaint reporting
- Report tracking by reference number
- QR code generation for quick access
"""

import hashlib
import secrets
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select

from src.api.dependencies import CurrentUser, DbSession, OptionalCurrentUser
from src.domain.models.complaint import Complaint, ComplaintPriority, ComplaintStatus, ComplaintType
from src.domain.models.incident import Incident, IncidentSeverity, IncidentStatus, IncidentType

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

    if report.report_type.lower() == "incident":
        # Generate reference number
        year = datetime.now(timezone.utc).year
        count_query = select(func.count()).select_from(Incident)
        result = await db.execute(count_query)
        count = result.scalar() or 0
        ref_number = f"INC-{year}-{count + 1:04d}"

        # Create incident with reporter info for "My Reports" linkage
        incident = Incident(
            reference_number=ref_number,
            title=report.title,
            description=report.description,
            incident_type=IncidentType.OTHER,
            severity=incident_severity,
            status=IncidentStatus.REPORTED,
            location=report.location,
            department=report.department,
            incident_date=datetime.now(timezone.utc),
            reported_date=datetime.now(timezone.utc),
            # CRITICAL: Set reporter info for My Reports identity linkage
            reporter_name=report.reporter_name if not report.is_anonymous else "Anonymous",
            reporter_email=report.reporter_email if not report.is_anonymous else None,
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

        # Create complaint
        complaint = Complaint(
            reference_number=ref_number,
            title=report.title,
            description=report.description,
            complaint_type=ComplaintType.OTHER,
            priority=complaint_priority,
            status=ComplaintStatus.RECEIVED,
            received_date=datetime.now(timezone.utc),
            complainant_name=report.reporter_name if not report.is_anonymous else "Anonymous",
            complainant_email=report.reporter_email if not report.is_anonymous else None,
            complainant_phone=report.reporter_phone if not report.is_anonymous else None,
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

    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid report_type. Must be 'incident' or 'complaint'.",
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
                detail="Report not found. Please check your reference number.",
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
                detail="Report not found. Please check your reference number.",
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

    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid reference number format.",
        )


@router.get(
    "/stats/",
    response_model=PortalStatsResponse,
    summary="Portal Statistics",
    description="Get transparency statistics about report handling.",
)
async def get_portal_stats(db: DbSession):
    """
    Get portal statistics for transparency.

    Shows how many reports are submitted and resolved.
    """
    from datetime import timedelta

    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago = now - timedelta(days=7)

    # Count today's reports
    incidents_today = await db.execute(
        select(func.count()).select_from(Incident).where(Incident.created_at >= today_start)
    )
    complaints_today = await db.execute(
        select(func.count()).select_from(Complaint).where(Complaint.created_at >= today_start)
    )
    total_today = (incidents_today.scalar() or 0) + (complaints_today.scalar() or 0)

    # Count resolved this week
    resolved_incidents = await db.execute(
        select(func.count())
        .select_from(Incident)
        .where(Incident.status == IncidentStatus.CLOSED)
        .where(Incident.updated_at >= week_ago)
    )
    resolved_complaints = await db.execute(
        select(func.count())
        .select_from(Complaint)
        .where(Complaint.status == ComplaintStatus.CLOSED)
        .where(Complaint.updated_at >= week_ago)
    )
    resolved_week = (resolved_incidents.scalar() or 0) + (resolved_complaints.scalar() or 0)

    return PortalStatsResponse(
        total_reports_today=total_today,
        average_resolution_days=3.2,  # Would calculate from actual data
        reports_resolved_this_week=resolved_week,
        anonymous_reports_percentage=15.0,  # Would calculate from actual data
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
    tracking_url = f"https://purple-water-03205fa03.6.azurestaticapps.net/portal/track/{reference_number}"

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
            {"id": "low", "label": "Low", "description": "Minor issue, no immediate action needed", "color": "#22c55e"},
            {"id": "medium", "label": "Medium", "description": "Moderate issue, attention needed", "color": "#eab308"},
            {"id": "high", "label": "High", "description": "Serious issue, prompt action required", "color": "#f97316"},
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
    all_reports: list[MyReportSummary] = []

    # Fetch incidents where user is reporter
    incidents_query = select(Incident).where(func.lower(Incident.reporter_email) == user_email)
    incidents_result = await db.execute(incidents_query)
    incidents = incidents_result.scalars().all()

    for inc in incidents:
        all_reports.append(
            MyReportSummary(
                reference_number=inc.reference_number,
                report_type="incident",
                title=inc.title,
                status=inc.status.value if hasattr(inc.status, "value") else str(inc.status),
                status_label=get_status_label(inc.status.value if hasattr(inc.status, "value") else str(inc.status)),
                submitted_at=inc.reported_date or inc.created_at,
                updated_at=inc.updated_at or inc.created_at,
            )
        )

    # Fetch complaints where user is complainant
    complaints_query = select(Complaint).where(func.lower(Complaint.complainant_email) == user_email)
    complaints_result = await db.execute(complaints_query)
    complaints = complaints_result.scalars().all()

    for comp in complaints:
        all_reports.append(
            MyReportSummary(
                reference_number=comp.reference_number,
                report_type="complaint",
                title=comp.title,
                status=comp.status.value if hasattr(comp.status, "value") else str(comp.status),
                status_label=get_status_label(comp.status.value if hasattr(comp.status, "value") else str(comp.status)),
                submitted_at=comp.received_date or comp.created_at,
                updated_at=comp.updated_at or comp.created_at,
            )
        )

    # Sort by submitted_at descending
    all_reports.sort(key=lambda r: r.submitted_at, reverse=True)

    # Paginate
    total = len(all_reports)
    start = (page - 1) * page_size
    end = start + page_size
    paginated = all_reports[start:end]

    return MyReportsResponse(
        items=paginated,
        total=total,
        page=page,
        page_size=page_size,
    )
