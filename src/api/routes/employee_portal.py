"""Employee Self-Service Portal API routes.

Provides simplified, mobile-first endpoints for:
- Anonymous incident/complaint reporting
- Report tracking by reference number
- QR code generation for quick access
"""

import hashlib
import hmac
import secrets
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import String, cast, func, literal, select, union_all
from sqlalchemy.exc import OperationalError, ProgrammingError

from src.api.dependencies import CurrentUser, DbSession, OptionalCurrentUser
from src.api.schemas.error_codes import ErrorCode
from src.api.utils.errors import api_error
from src.core.config import settings
from src.domain.exceptions import BadRequestError, NotFoundError
from src.domain.models.complaint import Complaint, ComplaintPriority, ComplaintStatus, ComplaintType
from src.domain.models.incident import Incident, IncidentSeverity, IncidentStatus, IncidentType
from src.domain.models.near_miss import NearMiss
from src.domain.models.rta import RoadTrafficCollision, RTASeverity, RTAStatus
from src.domain.services.portal_triage_service import assign_and_notify_portal_intake

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

    # Reporter info (optional for anonymous). complainant_name is accepted as an alias
    # for complaint intake clients that use the staff-schema field name.
    reporter_name: Optional[str] = Field(None, max_length=100)
    complainant_name: Optional[str] = Field(
        None,
        max_length=200,
        description="Alias for reporter_name on complaint submissions",
    )
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


def resolve_portal_display_name(
    report: "QuickReportCreate",
    reporter_submission: Optional[dict[str, Any]] = None,
) -> Optional[str]:
    """Resolve a non-null display name for portal intake entities.

    Anonymous submissions always map to ``Anonymous``. Non-anonymous submissions
    accept ``reporter_name``, ``complainant_name``, or common snapshot keys.
    """
    if report.is_anonymous:
        return "Anonymous"
    snapshot = reporter_submission if isinstance(reporter_submission, dict) else {}
    candidates = (
        report.reporter_name,
        report.complainant_name,
        snapshot.get("reporter_name"),
        snapshot.get("complainant_name"),
        snapshot.get("person_name"),
        snapshot.get("employee_name"),
    )
    for value in candidates:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def require_portal_display_name(
    report: "QuickReportCreate",
    reporter_submission: Optional[dict[str, Any]] = None,
) -> str:
    """Return a display name or raise 422 when a non-anonymous name is missing."""
    name = resolve_portal_display_name(report, reporter_submission)
    if name:
        return name
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=api_error(
            ErrorCode.VALIDATION_ERROR,
            "reporter_name is required unless is_anonymous=true "
            "(complainant_name is also accepted for complaint submissions)",
            details={
                "fields": ["reporter_name", "complainant_name"],
                "report_type": report.report_type,
            },
        ),
    )


class QuickReportResponse(BaseModel):
    """Response after submitting a report."""

    success: bool
    reference_number: str
    tracking_code: str  # Secret code for anonymous tracking
    message: str
    estimated_response: str
    qr_code_url: Optional[str] = None
    # Golden-thread fields — only populated when submitter may open staff record
    entity_id: Optional[int] = None
    entity_type: Optional[str] = None
    staff_href: Optional[str] = None
    can_open_staff_record: bool = False
    triage_assigned: bool = False


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


def generate_tracking_code(reference_number: str) -> str:
    """Generate a deterministic tracking code tied to a reference number."""
    message = f"portal-track:{reference_number}"
    return hmac.new(settings.secret_key.encode(), message.encode(), hashlib.sha256).hexdigest()[:24]


def generate_portal_reference(prefix: str) -> str:
    """Generate a collision-resistant portal reference number."""
    year = datetime.now(timezone.utc).year
    return f"{prefix}-{year}-{secrets.token_hex(4).upper()}"


def hash_tracking_code(code: str) -> str:
    """Hash tracking code for storage."""
    return hashlib.sha256(code.encode()).hexdigest()


def validate_tracking_code(reference_number: str, provided_code: Optional[str]) -> bool:
    """Validate a tracking code without storing sensitive portal state."""
    if not provided_code:
        return False
    expected_code = generate_tracking_code(reference_number)
    return hmac.compare_digest(expected_code, provided_code)


_STAFF_HREF_BY_TYPE = {
    "incident": "/incidents/{id}",
    "near_miss": "/near-misses/{id}",
    "complaint": "/complaints/{id}",
    "rta": "/rtas/{id}",
}


def staff_golden_thread_fields(
    current_user: Optional[Any],
    *,
    entity_type: str,
    entity_id: int,
) -> dict[str, Any]:
    """Return staff deep-link fields when the submitter may open the staff record.

    Anonymous / portal-only submitters get tracking_code only — no staff_href.
    Authenticated platform users (OptionalCurrentUser present) get a staff deep-link.
    """
    if current_user is None:
        return {
            "entity_id": None,
            "entity_type": None,
            "staff_href": None,
            "can_open_staff_record": False,
        }
    href_tmpl = _STAFF_HREF_BY_TYPE.get(entity_type)
    if not href_tmpl:
        return {
            "entity_id": None,
            "entity_type": None,
            "staff_href": None,
            "can_open_staff_record": False,
        }
    return {
        "entity_id": entity_id,
        "entity_type": entity_type,
        "staff_href": href_tmpl.format(id=entity_id),
        "can_open_staff_record": True,
    }


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


def get_default_portal_tenant_id() -> int:
    """Resolve the tenant used for unauthenticated portal intake.

    Fail closed when the portal tenant is not configured so public submissions
    cannot silently land in tenant ``1`` / Default Organisation.
    """
    tenant_id = settings.default_tenant_id
    if tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=api_error(
                ErrorCode.CONFIGURATION_ERROR,
                "Portal intake tenant is not configured.",
            ),
        )
    return tenant_id


def build_incident_portal_fields(
    report: QuickReportCreate,
    incident_severity: IncidentSeverity,
    reporter_submission: dict[str, Any],
    tenant_id: Optional[int] = None,
) -> dict[str, Any]:
    resolved_tenant_id = tenant_id if tenant_id is not None else get_default_portal_tenant_id()
    incident_occurred_at = parse_portal_datetime(
        reporter_submission.get("incident_date"),
        reporter_submission.get("incident_time"),
    ) or datetime.now(timezone.utc)
    witness_names = reporter_submission.get("witness_names")
    display_name = require_portal_display_name(report, reporter_submission)
    from src.domain.services.incident_care_fields import care_fields_from_submission
    from src.domain.services.incident_injury_promote import promote_injury_fields_from_submission

    injury_fields = promote_injury_fields_from_submission(reporter_submission)
    care_fields = care_fields_from_submission(reporter_submission)

    return {
        "incident_type": IncidentType.OTHER,
        "severity": incident_severity,
        "status": IncidentStatus.REPORTED,
        "location": report.location,
        "department": report.department,
        "incident_date": incident_occurred_at,
        "reported_date": datetime.now(timezone.utc),
        "reporter_name": display_name,
        "reporter_email": report.reporter_email if not report.is_anonymous else None,
        "people_involved": reporter_submission.get("person_name") or display_name,
        "witnesses": witness_names if isinstance(witness_names, str) else None,
        "first_aid_given": care_fields["first_aid_given"],
        "emergency_services_called": care_fields["emergency_services_called"],
        "medical_assistance": care_fields["medical_assistance"],
        "emergency_services": care_fields["emergency_services"],
        "is_injury": injury_fields["is_injury"],
        "body_parts": injury_fields["body_parts"],
        "source_form_id": "portal_incident_v1",
        "source_type": "portal",
        "reporter_submission": reporter_submission or None,
        "tenant_id": resolved_tenant_id,
    }


def build_complaint_portal_fields(
    report: QuickReportCreate,
    complaint_priority: ComplaintPriority,
    reporter_submission: dict[str, Any],
    tenant_id: Optional[int] = None,
) -> dict[str, Any]:
    resolved_tenant_id = tenant_id if tenant_id is not None else get_default_portal_tenant_id()
    display_name = require_portal_display_name(report, reporter_submission)
    return {
        "complaint_type": ComplaintType.OTHER,
        "priority": complaint_priority,
        "status": ComplaintStatus.RECEIVED,
        "received_date": datetime.now(timezone.utc),
        "complainant_name": display_name,
        "complainant_email": (report.reporter_email if not report.is_anonymous else None),
        "complainant_phone": (report.reporter_phone if not report.is_anonymous else None),
        "department": report.department,
        "source_form_id": "portal_complaint_v1",
        "source_type": "portal",
        "reporter_submission": reporter_submission or None,
        "tenant_id": resolved_tenant_id,
    }


def build_rta_portal_fields(
    report: QuickReportCreate,
    rta_severity: RTASeverity,
    reporter_submission: dict[str, Any],
    tenant_id: Optional[int] = None,
) -> dict[str, Any]:
    resolved_tenant_id = tenant_id if tenant_id is not None else get_default_portal_tenant_id()
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

    display_name = require_portal_display_name(report, reporter_submission)
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
        "reporter_name": display_name,
        "reporter_email": report.reporter_email if not report.is_anonymous else None,
        "driver_name": display_name,
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
        "tenant_id": resolved_tenant_id,
    }


async def commit_portal_record(db: DbSession, record_label: str) -> None:
    """Persist a portal record with an explicit configuration failure on schema drift."""
    from sqlalchemy.exc import IntegrityError

    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        # NOT NULL / FK violations must never surface as INTERNAL_ERROR 500.
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=api_error(
                ErrorCode.VALIDATION_ERROR,
                f"Portal {record_label} submission failed validation "
                "(required identity fields such as reporter_name/complainant_name).",
            ),
        ) from exc
    except (ProgrammingError, OperationalError) as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=api_error(
                ErrorCode.CONFIGURATION_ERROR,
                f"Portal {record_label} intake is not available until the latest database schema is applied.",
            ),
        ) from exc


async def complete_portal_intake_triage(
    db: DbSession,
    *,
    entity: Any,
    entity_type: str,
    reference_number: str,
    tenant_id: int,
    current_user: Optional[Any],
) -> bool:
    """Assign case owner and notify after portal submit; never blocks the 201 response."""
    owner_id = await assign_and_notify_portal_intake(
        db,
        entity=entity,
        entity_type=entity_type,
        reference=reference_number,
        tenant_id=tenant_id,
        submitter=current_user,
    )
    return owner_id is not None


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
    current_user: OptionalCurrentUser = None,
):
    """
    Submit a quick report (incident or complaint).

    This endpoint is public and doesn't require authentication.
    Anonymous reports can be tracked using the returned tracking_code.
    Authenticated staff receive a golden-thread staff_href when role allows.
    """
    incident_severity, complaint_priority = map_severity(report.severity)
    reporter_submission = report.reporter_submission or {}
    portal_tenant_id = get_default_portal_tenant_id()

    if report.report_type.lower() == "incident":
        ref_number = generate_portal_reference("INC")
        tracking_code = generate_tracking_code(ref_number)

        from src.domain.services.contract_resolve import resolve_contract_id_by_code

        portal_fields = build_incident_portal_fields(report, incident_severity, reporter_submission, portal_tenant_id)
        customer_code = reporter_submission.get("contract") or report.department
        contract_id = await resolve_contract_id_by_code(
            db, tenant_id=portal_tenant_id, code=str(customer_code) if customer_code else None
        )
        if contract_id is not None:
            portal_fields["contract_id"] = contract_id

        incident = Incident(
            reference_number=ref_number,
            title=report.title,
            description=report.description,
            **portal_fields,
        )

        db.add(incident)
        await commit_portal_record(db, "incident")
        await db.refresh(incident)
        triage_assigned = await complete_portal_intake_triage(
            db,
            entity=incident,
            entity_type="incident",
            reference_number=ref_number,
            tenant_id=portal_tenant_id,
            current_user=current_user,
        )

        return QuickReportResponse(
            success=True,
            reference_number=ref_number,
            tracking_code=tracking_code,
            message="Your incident report has been submitted successfully.",
            estimated_response="You will receive an update within 24-48 hours.",
            qr_code_url=f"/api/v1/portal/qr/{ref_number}",
            triage_assigned=triage_assigned,
            **staff_golden_thread_fields(current_user, entity_type="incident", entity_id=incident.id),
        )

    elif report.report_type.lower() == "complaint":
        ref_number = generate_portal_reference("COMP")
        tracking_code = generate_tracking_code(ref_number)

        complaint = Complaint(
            reference_number=ref_number,
            title=report.title,
            description=report.description,
            **build_complaint_portal_fields(report, complaint_priority, reporter_submission, portal_tenant_id),
        )

        db.add(complaint)
        await commit_portal_record(db, "complaint")
        await db.refresh(complaint)
        triage_assigned = await complete_portal_intake_triage(
            db,
            entity=complaint,
            entity_type="complaint",
            reference_number=ref_number,
            tenant_id=portal_tenant_id,
            current_user=current_user,
        )

        return QuickReportResponse(
            success=True,
            reference_number=ref_number,
            tracking_code=tracking_code,
            message="Your complaint has been submitted successfully.",
            estimated_response="A case manager will review your complaint within 24 hours.",
            qr_code_url=f"/api/v1/portal/qr/{ref_number}",
            triage_assigned=triage_assigned,
            **staff_golden_thread_fields(current_user, entity_type="complaint", entity_id=complaint.id),
        )

    elif report.report_type.lower() == "rta":
        ref_number = generate_portal_reference("RTA")
        tracking_code = generate_tracking_code(ref_number)

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
            **build_rta_portal_fields(report, rta_severity, reporter_submission, portal_tenant_id),
        )

        db.add(rta)
        await commit_portal_record(db, "RTA")
        await db.refresh(rta)
        triage_assigned = await complete_portal_intake_triage(
            db,
            entity=rta,
            entity_type="rta",
            reference_number=ref_number,
            tenant_id=portal_tenant_id,
            current_user=current_user,
        )

        return QuickReportResponse(
            success=True,
            reference_number=ref_number,
            tracking_code=tracking_code,
            message="Your RTA report has been submitted successfully.",
            estimated_response="A fleet manager will review your report within 24 hours.",
            qr_code_url=f"/api/v1/portal/qr/{ref_number}",
            triage_assigned=triage_assigned,
            **staff_golden_thread_fields(current_user, entity_type="rta", entity_id=rta.id),
        )

    elif report.report_type.lower() == "near_miss":
        ref_number = generate_portal_reference("NM")
        tracking_code = generate_tracking_code(ref_number)

        # Map severity to priority
        priority_map = {
            "low": "LOW",
            "medium": "MEDIUM",
            "high": "HIGH",
            "critical": "CRITICAL",
        }
        priority = priority_map.get(report.severity.lower(), "MEDIUM")
        display_name = require_portal_display_name(report, reporter_submission)

        # Customer code lives on NearMiss.contract. Prefer reporter_submission.contract;
        # department is a legacy bridge from older portal clients.
        customer_code = str(reporter_submission.get("contract") or "").strip() or ((report.department or "").strip())

        # Create Near Miss record
        near_miss = NearMiss(
            reference_number=ref_number,
            reporter_name=display_name,
            reporter_email=report.reporter_email if not report.is_anonymous else None,
            contract=customer_code or "Not specified",
            location=report.location or "Not specified",
            event_date=datetime.now(timezone.utc),
            description=report.description,
            potential_severity=report.severity.lower(),
            status="REPORTED",
            priority=priority,
            source_form_id="portal_near_miss_v1",
            tenant_id=portal_tenant_id,
        )

        db.add(near_miss)
        await commit_portal_record(db, "near miss")
        await db.refresh(near_miss)
        triage_assigned = await complete_portal_intake_triage(
            db,
            entity=near_miss,
            entity_type="near_miss",
            reference_number=ref_number,
            tenant_id=portal_tenant_id,
            current_user=current_user,
        )

        return QuickReportResponse(
            success=True,
            reference_number=ref_number,
            tracking_code=tracking_code,
            message="Your near miss report has been submitted successfully.",
            estimated_response="A safety manager will review your report within 24 hours.",
            qr_code_url=f"/api/v1/portal/qr/{ref_number}",
            triage_assigned=triage_assigned,
            **staff_golden_thread_fields(current_user, entity_type="near_miss", entity_id=near_miss.id),
        )

    else:
        raise BadRequestError("Invalid report_type. Must be 'incident', 'complaint', 'rta', or 'near_miss'.")


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

    Portal tracking requires the reference-specific tracking code.
    """
    if not validate_tracking_code(reference_number, tracking_code):
        raise NotFoundError("Report not found. Please check your reference details.")

    # Determine report type from reference number prefix
    if reference_number.startswith("INC-"):
        inc_query = select(Incident).where(Incident.reference_number == reference_number)
        inc_result = await db.execute(inc_query)
        incident = inc_result.scalar_one_or_none()

        if not incident:
            raise NotFoundError("Report not found. Please check your reference number.")

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
            raise NotFoundError("Report not found. Please check your reference number.")

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
            raise NotFoundError("Report not found. Please check your reference number.")

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
            raise NotFoundError("Report not found. Please check your reference number.")

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
        raise BadRequestError("Invalid reference number format.")


@router.get(
    "/stats",
    response_model=PortalStatsResponse,
    include_in_schema=False,
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

    tracking_url = (
        f"{settings.frontend_url}/portal/track/{reference_number}"
        f"?tracking_code={generate_tracking_code(reference_number)}"
    )

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
