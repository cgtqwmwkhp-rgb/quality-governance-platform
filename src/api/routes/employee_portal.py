"""Employee Self-Service Portal API routes.

Provides simplified, mobile-first endpoints for:
- Identified incident/complaint/near-miss/RTA reporting
- Report tracking by reference number
- QR code generation for quick access

Anonymous portal submissions are intentionally disabled (PX-312).
"""

import hashlib
import hmac
import logging
import re
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any, Literal, Optional

from fastapi import APIRouter, File, Form, Header, HTTPException, Query, UploadFile, status
from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator
from sqlalchemy import String, cast, func, literal, select, union_all
from sqlalchemy.exc import IntegrityError, OperationalError, ProgrammingError

from src.api.dependencies import CurrentUser, DbSession, OptionalCurrentUser
from src.api.schemas.error_codes import ErrorCode
from src.api.utils.errors import api_error
from src.core.config import settings
from src.domain.exceptions import BadRequestError, NotFoundError
from src.domain.models.complaint import Complaint, ComplaintPriority, ComplaintStatus, ComplaintType, FeedbackKind
from src.domain.models.evidence_asset import (
    EvidenceAsset,
    EvidenceAssetType,
    EvidenceRetentionPolicy,
    EvidenceSourceModule,
    EvidenceVisibility,
)
from src.domain.models.incident import Incident, IncidentSeverity, IncidentStatus, IncidentType
from src.domain.models.near_miss import NearMiss
from src.domain.models.rta import RoadTrafficCollision, RTAStatus
from src.domain.services.api_idempotency_service import begin_idempotent_create, complete_idempotent_create
from src.domain.services.audit_log_service import AuditLogService
from src.domain.services.feedback_kind_policy import (
    KIND_RECORD_TYPE,
    assert_compliment_has_subject,
    assert_kind_may_be_written,
    parse_feedback_kind,
)
from src.domain.services.portal_triage_service import assign_and_notify_portal_intake
from src.domain.services.reference_number import ReferenceNumberService
from src.domain.services.rta_severity import (
    derive_portal_rta_severity,
    interpret_rta_injury_answer,
    interpret_rta_yes_no_answer,
    read_reported_bool,
)
from src.domain.services.shared_severity import (
    map_portal_severity,
    near_miss_priority_for_severity,
    normalize_portal_severity,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Employee Portal"])

# Idempotency scopes for public portal submits (PX-001 pattern, reused from staff creates).
_PORTAL_IDEMPOTENCY_SCOPES = {
    "incident": "portal.incident.create",
    "complaint": "portal.complaint.create",
    "rta": "portal.rta.create",
    "near_miss": "portal.near_miss.create",
}

# Owner/assignee field name differs by entity (mirrors portal_triage_service.apply_portal_owner).
_PORTAL_OWNER_FIELD_BY_TYPE = {
    "incident": "owner_id",
    "complaint": "owner_id",
    "rta": "owner_id",
    "near_miss": "assigned_to_id",
}

_PORTAL_MODEL_BY_TYPE: dict[str, Any] = {
    "incident": Incident,
    "complaint": Complaint,
    "rta": RoadTrafficCollision,
    "near_miss": NearMiss,
}

_PORTAL_SUCCESS_COPY = {
    "incident": (
        "Your incident report has been submitted successfully.",
        "You will receive an update within 24-48 hours.",
    ),
    "complaint": (
        "Your complaint has been submitted successfully.",
        "A case manager will review your complaint within 24 hours.",
    ),
    "rta": (
        "Your RTA report has been submitted successfully.",
        "A fleet manager will review your report within 24 hours.",
    ),
    "near_miss": (
        "Your near miss report has been submitted successfully.",
        "A safety manager will review your report within 24 hours.",
    ),
}


# ============================================================================
# Schemas for Employee Portal
# ============================================================================

# Aligned to the narrowest DB column each field maps into (PX-281 backend half).
PORTAL_REPORTER_NAME_MAX_LENGTH = 200  # complaints.complainant_name, near_misses.reporter_name
PORTAL_REPORTER_PHONE_MAX_LENGTH = 50  # near_misses.reporter_phone
PORTAL_COMPLAINANT_PHONE_DB_LENGTH = 30  # complaints.complainant_phone
PORTAL_LOCATION_MAX_LENGTH = 500  # rtas.location
PORTAL_INCIDENT_LOCATION_DB_LENGTH = 300  # incidents.location
PORTAL_NEAR_MISS_EVENT_TIME_DB_LENGTH = 10  # near_misses.event_time
PORTAL_RTA_COLLISION_TIME_DB_LENGTH = 10  # road_traffic_collisions.collision_time

_EMAIL_LIKE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def looks_like_email(value: str) -> bool:
    """True when a free-text contact value is almost certainly an email address."""
    return bool(_EMAIL_LIKE.match(value.strip()))


def normalize_portal_contact(
    reporter_email: Optional[str],
    reporter_phone: Optional[str],
) -> tuple[Optional[str], Optional[str]]:
    """Route email-shaped ``reporter_phone`` values to ``reporter_email``.

    Non-portal callers (legacy static forms, integrations) may still map a contact
    field straight into ``reporter_phone``. Accept the payload and normalise rather
    than returning HTTP 422 for a realistic work email (PX-281).
    """
    phone = reporter_phone.strip() if isinstance(reporter_phone, str) and reporter_phone.strip() else None
    email = reporter_email
    if phone and looks_like_email(phone):
        if not email:
            email = phone
        phone = None
    return email, phone


def clip_portal_phone_for_complaint(phone: Optional[str]) -> Optional[str]:
    """Fit a normalised phone value into complaints.complainant_phone (varchar 30)."""
    if not phone:
        return None
    return phone[:PORTAL_COMPLAINANT_PHONE_DB_LENGTH]


def clip_portal_location_for_incident(location: Optional[str]) -> Optional[str]:
    """Fit a portal location into incidents.location (varchar 300)."""
    if not location:
        return None
    return location[:PORTAL_INCIDENT_LOCATION_DB_LENGTH]


def _normalized_status(value: str) -> str:
    """Field validator body: emit one status casing on every portal read (PX-316)."""
    return normalize_portal_status(value)


class QuickReportCreate(BaseModel):
    """Simplified report submission schema."""

    report_type: str = Field(..., description="Type: 'incident' or 'complaint'")
    title: str = Field(..., min_length=5, max_length=200, description="Brief title")
    description: str = Field(..., min_length=10, description="What happened?")
    location: Optional[str] = Field(None, max_length=PORTAL_LOCATION_MAX_LENGTH, description="Where did it occur?")
    severity: str = Field(default="medium", description="Severity: negligible, low, medium, high, critical")

    # Reporter info (optional for anonymous). complainant_name is accepted as an alias
    # for complaint intake clients that use the staff-schema field name.
    reporter_name: Optional[str] = Field(None, max_length=PORTAL_REPORTER_NAME_MAX_LENGTH)
    complainant_name: Optional[str] = Field(
        None,
        max_length=PORTAL_REPORTER_NAME_MAX_LENGTH,
        description="Alias for reporter_name on complaint submissions",
    )
    reporter_email: Optional[EmailStr] = None
    reporter_phone: Optional[str] = Field(None, max_length=PORTAL_REPORTER_PHONE_MAX_LENGTH)
    department: Optional[str] = Field(None, max_length=100)

    # Anonymous flag — accepted on the wire but hard-rejected in submit_quick_report (PX-312)
    is_anonymous: bool = Field(default=False, description="Must be false; anonymous portal submit is not available")

    # Optional photo/attachment reference
    attachment_ids: Optional[list[str]] = None
    reporter_submission: Optional[dict[str, Any]] = Field(
        None,
        description="Immutable snapshot of reporter-entered intake data for investigator views",
    )
    feedback_kind: Optional[str] = Field(
        None,
        description="Customer feedback kind. Omitted defaults to complaint. Non-complaint requires the kinds flag.",
    )

    # Optional client-supplied idempotency key (PX-001). Prefer the ``Idempotency-Key``
    # header; this body field is a fallback for clients that cannot set custom headers.
    idempotency_key: Optional[str] = Field(
        None,
        max_length=255,
        description="Optional idempotency key; retried submissions with the same key "
        "return the original result instead of creating a duplicate case.",
    )

    @model_validator(mode="after")
    def normalize_contact_fields(self) -> "QuickReportCreate":
        email, phone = normalize_portal_contact(self.reporter_email, self.reporter_phone)
        self.reporter_email = email
        self.reporter_phone = phone
        return self


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


class PortalAttachmentUploadResponse(BaseModel):
    """Receipt for one uploaded file, to be passed back in ``attachment_ids``."""

    attachment_id: str = Field(
        ...,
        description="Opaque handle to send in attachment_ids when submitting the report",
    )
    filename: Optional[str] = None
    content_type: str
    size_bytes: int


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

    _normalize_status = field_validator("status")(_normalized_status)


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

    _normalize_status = field_validator("status")(_normalized_status)


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


# PX-126: which register each portal prefix writes into, so the portal can draw
# from the same sequence staff intake already uses instead of its own hex space.
_PORTAL_REFERENCE_REGISTERS: dict[str, tuple[str, Any]] = {
    "INC": ("incident", Incident),
    "COMP": ("complaint", Complaint),
    "CMND": ("compliment", Complaint),
    "SUGG": ("suggestion", Complaint),
    "FDBK": ("general", Complaint),
    "RTA": ("rta", RoadTrafficCollision),
    "NM": ("near_miss", NearMiss),
}


async def mint_portal_reference(db: DbSession, prefix: str) -> str:
    """Mint a portal reference from the shared sequential register (PX-126).

    Portal intake used to mint ``COMP-2026-9F3A21C4`` while staff intake minted
    ``COMP-2026-0007`` for the same register, so a single case list showed two
    incompatible reference formats and neither operators nor complainants could
    tell which was "real".

    If the sequence cannot be read the legacy hex form is used rather than
    refusing the submission: an employee filing a near miss must never lose it to
    a reference-minting problem.
    """
    register = _PORTAL_REFERENCE_REGISTERS.get(prefix)
    if register is None:
        return generate_portal_reference(prefix)
    record_type, model_class = register
    try:
        return await ReferenceNumberService.generate(db, record_type, model_class)
    except Exception:
        logger.warning(
            "Sequential portal reference unavailable for %s; falling back to the legacy form",
            prefix,
            exc_info=True,
        )
        return generate_portal_reference(prefix)


_CUSTOMER_DISPLAY_LABELS = {
    "plantexpand_ltd": "Plantexpand Ltd",
    "plantexpand": "Plantexpand Ltd",
    "ukpn": "UK Power Networks",
    "defra": "DEFRA",
    "openreach": "Openreach",
    "thames_water": "Thames Water",
    "cadent": "Cadent",
    "network_rail": "Network Rail",
    "novuna": "Novuna",
}


def humanize_customer_code(code: Optional[str]) -> str:
    """Employee-facing customer label — never show raw lookup slugs (PX-299)."""
    if not code:
        return "Not specified"
    trimmed = str(code).strip()
    if not trimmed:
        return "Not specified"
    known = _CUSTOMER_DISPLAY_LABELS.get(trimmed.lower())
    if known:
        return known
    if "_" in trimmed or "-" in trimmed:
        return trimmed.replace("_", " ").title()
    if trimmed == trimmed.lower():
        return trimmed.upper()
    return trimmed


def format_portal_report_title(title: Optional[str]) -> str:
    """Rewrite generic type-plus-slug titles for portal track lists (PX-318)."""
    if not title:
        return ""
    text = str(title).strip()
    if " - " not in text:
        return text
    prefix, suffix = text.rsplit(" - ", 1)
    humanized = humanize_customer_code(suffix)
    if humanized == suffix:
        return text
    return f"{prefix} - {humanized}"


def hash_tracking_code(code: str) -> str:
    """Hash tracking code for storage."""
    return hashlib.sha256(code.encode()).hexdigest()


def validate_tracking_code(reference_number: str, provided_code: Optional[str]) -> bool:
    """Validate a tracking code without storing sensitive portal state."""
    if not provided_code:
        return False
    expected_code = generate_tracking_code(reference_number)
    return hmac.compare_digest(expected_code, provided_code)


_PORTAL_COMPLAINT_PREFIXES = ("COMP-", "CMND-", "SUGG-", "FDBK-")
_PORTAL_REFERENCE_PREFIXES = ("INC-", "COMP-", "CMND-", "SUGG-", "FDBK-", "RTA-", "NM-")
_PORTAL_COMPLIMENT_SUBJECT_KEYS = ("subject_name", "about_staff", "compliment_subject")
_PORTAL_FEEDBACK_SUCCESS: dict[FeedbackKind, tuple[str, str]] = {
    FeedbackKind.COMPLAINT: (
        "Your complaint has been submitted successfully.",
        "A case manager will review your complaint within 24 hours.",
    ),
    FeedbackKind.COMPLIMENT: (
        "Your compliment has been submitted successfully.",
        "Thank you — we will pass this on to the person you named.",
    ),
    FeedbackKind.SUGGESTION: (
        "Your suggestion has been submitted successfully.",
        "A case manager will review your suggestion within 24 hours.",
    ),
    FeedbackKind.GENERAL: (
        "Your feedback has been submitted successfully.",
        "A case manager will review your feedback within 24 hours.",
    ),
}

# One wording for every "no report for you here" outcome. The session path
# answers 404 rather than 403 on an ownership mismatch so that it cannot
# confirm somebody else's reference exists — which only holds if the body is
# identical to a genuinely-unknown reference as well as the status code.
# Keep this a single constant; two hand-written strings drifted apart before.
_REPORT_NOT_FOUND_MESSAGE = "Report not found. Please check your reference number."

# How the caller earned the right to read a report. ``tracking_code`` is the
# anonymous grant; ``session`` additionally requires ownership of the record.
PortalReadGrant = Literal["tracking_code", "session"]


def authorize_portal_report_read(
    reference_number: str,
    tracking_code: Optional[str],
    current_user: Optional[Any],
) -> PortalReadGrant:
    """Decide whether a caller may read a report, or raise a specific error.

    PX-315: this gate previously collapsed "you sent no credentials", "your code
    is wrong" and "no such reference" into one 404, so a client that simply
    forgot to send the tracking code looked identical to missing data. Each
    condition now has its own status code.
    """
    if validate_tracking_code(reference_number, tracking_code):
        return "tracking_code"

    if tracking_code:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=api_error(
                ErrorCode.PERMISSION_DENIED.value,
                "That tracking code does not match this reference number.",
                details={"reference_number": reference_number},
            ),
        )

    if current_user is not None:
        return "session"

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=api_error(
            ErrorCode.AUTHENTICATION_REQUIRED.value,
            "Tracking a report requires the tracking code issued when it was "
            "submitted, or a signed-in account that submitted it.",
            details={"reference_number": reference_number},
        ),
    )


def assert_session_owns_report(
    grant: PortalReadGrant,
    current_user: Optional[Any],
    *,
    owner_email: Optional[str],
    tenant_id: Optional[int],
) -> None:
    """Reject a session-authorised read of somebody else's report.

    A valid tracking code is proof of possession and stands on its own. A
    session only unlocks the caller's own reports, and a mismatch is reported
    as "not found" so the endpoint cannot be used to probe which references
    exist. Anonymous submissions have no owner email, so they stay
    code-only — which is the point of submitting anonymously.
    """
    if grant != "session":
        return

    user_email = (getattr(current_user, "email", None) or "").strip().lower()
    record_email = (owner_email or "").strip().lower()
    user_tenant = getattr(current_user, "tenant_id", None)

    if not record_email or record_email != user_email or (tenant_id is not None and tenant_id != user_tenant):
        raise NotFoundError(_REPORT_NOT_FOUND_MESSAGE)


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


def map_severity(severity: str) -> tuple[IncidentSeverity, ComplaintPriority]:
    """Map the portal severity word onto the incident and complaint enums."""
    return map_portal_severity(severity)


_STATUS_LABELS = {
    "reported": "📋 Submitted",
    "open": "📋 Open",
    "under_investigation": "🔍 Under Investigation",
    "in_progress": "⚙️ In Progress",
    "pending_review": "👀 Pending Review",
    "resolved": "✅ Resolved",
    "closed": "🏁 Closed",
    "rejected": "❌ Rejected",
}

_PRIORITY_LABELS = {
    "negligible": "⚪ Negligible",
    "low": "🟢 Low",
    "medium": "🟡 Medium",
    "high": "🟠 High",
    "critical": "🔴 Critical",
}


def normalize_portal_status(value: Any) -> str:
    """Canonical wire form for portal status/priority values (PX-316).

    Portal reads span four models with three different storage conventions:
    ``Incident``/``Complaint``/``RoadTrafficCollision`` persist lowercase enum
    values, while ``NearMiss`` persists an uppercase plain string. Callers get
    one casing regardless of which table the reference resolves to.
    """
    raw = getattr(value, "value", value)
    return str(raw or "").strip().lower()


def get_status_label(status: Any) -> str:
    """Get human-readable status label from any supported status casing."""
    key = normalize_portal_status(status)
    return _STATUS_LABELS.get(key, key)


def get_priority_label(priority: Any) -> str:
    """Get priority with visual indicator from any supported casing."""
    key = normalize_portal_status(priority)
    return _PRIORITY_LABELS.get(key, key)


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
        "location": clip_portal_location_for_incident(report.location),
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


# The published complaint template asks the reporter for ``complaint_date``, and
# ``received_date`` is the column every complaint time limit is measured from.
# The builder never read either name, so the reporter's stated date was replaced
# by the instant they pressed submit. Both spellings are accepted because
# template field names live in admin-editable ``form_fields`` rows and the portal
# deploys independently of this API, so neither shape can be assumed.
_COMPLAINT_RECEIVED_DATE_KEYS: tuple[str, ...] = ("complaint_date", "received_date")


def resolve_complaint_received_date(
    reporter_submission: dict[str, Any],
    *,
    reference_number: Optional[str] = None,
) -> datetime:
    """Resolve the reporter's stated complaint date from any accepted key.

    Falls back to the submission instant when no accepted key carries a
    parseable date, because losing the complaint is worse than an imprecise
    clock — but that substitution is logged rather than made silently, since
    ``received_date`` is what statutory response deadlines are counted from.
    """
    resolved: list[tuple[str, datetime]] = []
    for key in _COMPLAINT_RECEIVED_DATE_KEYS:
        parsed = parse_portal_datetime(reporter_submission.get(key))
        if parsed is not None:
            resolved.append((key, parsed))

    if not resolved:
        logger.warning(
            "Complaint %s carried no usable complaint date; recording the submission instant instead. "
            "Accepted date keys: %s. Keys present in reporter_submission: %s.",
            reference_number or "<reference not yet minted>",
            list(_COMPLAINT_RECEIVED_DATE_KEYS),
            sorted(reporter_submission),
        )
        return datetime.now(timezone.utc)

    chosen_key, chosen_datetime = resolved[0]
    conflicts = [(key, dt.isoformat()) for key, dt in resolved[1:] if dt != chosen_datetime]
    if conflicts:
        logger.warning(
            "Complaint %s carried conflicting complaint dates across accepted keys; using %s=%s and ignoring %s.",
            reference_number or "<reference not yet minted>",
            chosen_key,
            chosen_datetime.isoformat(),
            conflicts,
        )
    return chosen_datetime


def portal_compliment_subject(reporter_submission: dict[str, Any]) -> str | None:
    """Named staff member from the portal snapshot. Compliment write requires one."""
    for key in _PORTAL_COMPLIMENT_SUBJECT_KEYS:
        value = reporter_submission.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def resolve_portal_feedback_kind(
    report: QuickReportCreate,
    reporter_submission: dict[str, Any],
) -> FeedbackKind:
    """Parse kind from the body or snapshot, then apply the same write gate as staff create."""
    raw = report.feedback_kind
    if raw is None:
        raw = reporter_submission.get("feedback_kind")
    kind = parse_feedback_kind(raw)
    assert_kind_may_be_written(kind)
    if kind is FeedbackKind.COMPLIMENT:
        assert_compliment_has_subject(
            subject_user_id=None,
            subject_name=portal_compliment_subject(reporter_submission),
        )
    return kind


def portal_kind_prefix(kind: FeedbackKind) -> str:
    return ReferenceNumberService.PREFIXES[KIND_RECORD_TYPE[kind]]


def portal_feedback_success_copy(kind: FeedbackKind) -> tuple[str, str]:
    return _PORTAL_FEEDBACK_SUCCESS.get(kind, _PORTAL_FEEDBACK_SUCCESS[FeedbackKind.COMPLAINT])


def build_complaint_portal_fields(
    report: QuickReportCreate,
    complaint_priority: ComplaintPriority,
    reporter_submission: dict[str, Any],
    tenant_id: Optional[int] = None,
    *,
    reference_number: Optional[str] = None,
    feedback_kind: FeedbackKind | None = None,
    subject_name: str | None = None,
) -> dict[str, Any]:
    resolved_tenant_id = tenant_id if tenant_id is not None else get_default_portal_tenant_id()
    display_name = require_portal_display_name(report, reporter_submission)
    kind = feedback_kind if feedback_kind is not None else parse_feedback_kind(reporter_submission.get("feedback_kind"))
    named_subject = subject_name if subject_name is not None else portal_compliment_subject(reporter_submission)
    fields: dict[str, Any] = {
        "complaint_type": ComplaintType.OTHER,
        "priority": complaint_priority,
        "status": ComplaintStatus.RECEIVED,
        "received_date": resolve_complaint_received_date(
            reporter_submission,
            reference_number=reference_number,
        ),
        "complainant_name": display_name,
        "complainant_email": (report.reporter_email if not report.is_anonymous else None),
        "complainant_phone": (
            clip_portal_phone_for_complaint(report.reporter_phone) if not report.is_anonymous else None
        ),
        "department": report.department,
        "source_form_id": "portal_complaint_v1",
        "source_type": "portal",
        "reporter_submission": reporter_submission or None,
        "tenant_id": resolved_tenant_id,
        "feedback_kind": kind,
    }
    if named_subject:
        fields["subject_name"] = named_subject
    return fields


# ``/report/rta`` renders the hardcoded PortalRTAForm, which posts
# ``accident_date`` / ``accident_time`` / ``pe_vehicle`` / ``third_parties``. The
# published 'rta' template — currently unreachable, because App.tsx routes
# report/rta to that hardcoded form rather than to PortalDynamicForm — names the
# same facts ``incident_date`` / ``incident_time`` / ``vehicle_reg`` /
# ``third_party_involved``. Both shapes are accepted, live keys first, for the
# same reason the near-miss path accepts both: 'incident-legacy' and
# 'near-miss-static' exist because those routes were already converted from
# hardcoded to template-driven, RTA is the last one left, and template field
# names are admin-editable at runtime with no gate in front of them.
#
# Date and time are resolved as a *pair* so a value from one client shape can
# never be spliced onto a value from another.
_RTA_COLLISION_DATETIME_KEYS: tuple[tuple[str, str], ...] = (
    ("accident_date", "accident_time"),
    ("incident_date", "incident_time"),
)

_RTA_VEHICLE_REGISTRATION_KEYS: tuple[str, ...] = ("pe_vehicle", "vehicle_reg")


def resolve_rta_collision_datetime(
    reporter_submission: dict[str, Any],
    *,
    reference_number: Optional[str] = None,
) -> tuple[datetime, Optional[str]]:
    """Resolve the reporter-submitted collision date/time from any accepted key pair.

    Returns ``(collision_datetime, raw_time_string)``. The submission instant is
    used when no accepted key carries a parseable date — losing a collision
    report is worse than an imprecise timestamp — but that is logged, and no time
    is invented to go with it.
    """
    resolved: list[tuple[str, datetime, Any]] = []
    for date_key, time_key in _RTA_COLLISION_DATETIME_KEYS:
        parsed = parse_portal_datetime(reporter_submission.get(date_key), reporter_submission.get(time_key))
        if parsed is not None:
            resolved.append((date_key, parsed, reporter_submission.get(time_key)))

    if not resolved:
        logger.warning(
            "RTA %s carried no usable collision date; recording the submission instant instead. "
            "Accepted date keys: %s. Keys present in reporter_submission: %s.",
            reference_number or "<reference not yet minted>",
            [date_key for date_key, _ in _RTA_COLLISION_DATETIME_KEYS],
            sorted(reporter_submission),
        )
        return datetime.now(timezone.utc), None

    chosen_key, chosen_datetime, chosen_time = resolved[0]
    conflicts = [(key, dt.isoformat()) for key, dt, _ in resolved[1:] if dt != chosen_datetime]
    if conflicts:
        logger.warning(
            "RTA %s carried conflicting collision dates across accepted keys; using %s=%s and ignoring %s.",
            reference_number or "<reference not yet minted>",
            chosen_key,
            chosen_datetime.isoformat(),
            conflicts,
        )

    raw_time = str(chosen_time).strip() if chosen_time is not None else ""
    if len(raw_time) > PORTAL_RTA_COLLISION_TIME_DB_LENGTH:
        # road_traffic_collisions.collision_time is varchar(10). An over-long value
        # raises StringDataRightTruncation, which aborts the INSERT and loses the
        # entire collision report rather than just the time. The template declares
        # this field as 'time' today, but field_type is a database row an
        # administrator can retype to text, and the endpoint accepts JSON from any
        # caller. Full precision is already on collision_date and in the reporter
        # snapshot, so clip and say so — the same trade the near-miss path makes.
        logger.warning(
            "RTA %s submitted a %d-character time under %s; clipping to fit collision_time(varchar %d). "
            "Full precision is retained on collision_date.",
            reference_number or "<reference not yet minted>",
            len(raw_time),
            chosen_key,
            PORTAL_RTA_COLLISION_TIME_DB_LENGTH,
        )
        raw_time = raw_time[:PORTAL_RTA_COLLISION_TIME_DB_LENGTH]
    return chosen_datetime, raw_time or None


def resolve_rta_vehicle_registration(reporter_submission: dict[str, Any]) -> Any:
    """Resolve the company vehicle registration from any accepted key.

    The registration is what ties a collision to a vehicle, a driver and an
    insurer, so a name mismatch here loses the identity of the vehicle involved.
    """
    for key in _RTA_VEHICLE_REGISTRATION_KEYS:
        value = reporter_submission.get(key)
        if value == "other":
            # The live form's vehicle picker offers an "other" escape hatch.
            value = reporter_submission.get("pe_vehicle_other")
        if value:
            return value
    return None


def build_rta_portal_fields(
    report: QuickReportCreate,
    reporter_submission: dict[str, Any],
    tenant_id: Optional[int] = None,
    *,
    reference_number: Optional[str] = None,
) -> dict[str, Any]:
    """Map a portal RTA submission onto RoadTrafficCollision columns.

    Severity is derived here rather than passed in, so there is exactly one place
    that decides an injury outcome. ``report.severity`` is the portal's generic
    triage word and is deliberately not consulted: see
    :mod:`src.domain.services.rta_severity`.
    """
    resolved_tenant_id = tenant_id if tenant_id is not None else get_default_portal_tenant_id()
    collision_occurred_at, collision_time_value = resolve_rta_collision_datetime(
        reporter_submission,
        reference_number=reference_number,
    )
    vehicle_registration = resolve_rta_vehicle_registration(reporter_submission)
    witness_details = reporter_submission.get("witness_details")
    third_party_entries = reporter_submission.get("third_parties")
    from src.domain.services.rta_injury_fields import derive_third_party_injured

    third_parties_payload = (
        {"parties": third_party_entries} if isinstance(third_party_entries, list) and third_party_entries else None
    )
    explicit_tp_injured = reporter_submission.get("third_party_injured")
    if explicit_tp_injured is None and reporter_submission.get("injured") is not None:
        # Legacy portal key used by some RTA clients
        explicit_tp_injured = reporter_submission.get("injured")
    third_party_injured = derive_third_party_injured(
        third_parties_payload,
        explicit=interpret_rta_injury_answer(explicit_tp_injured),
    )
    # The published template asks "Third Party Involved?" as a yes/no toggle and
    # never asks how many, so the only typed column it can reach is the vehicle
    # count. A detailed party record still requires the ``third_parties`` array.
    reported_third_party_involved = interpret_rta_yes_no_answer(reporter_submission.get("third_party_involved"))
    # None = the form never asked, which is not the same as "nobody was hurt".
    driver_injured = interpret_rta_injury_answer(reporter_submission.get("driver_injured"))
    # reporter_submission is arbitrary client JSON; only a string belongs in a Text column.
    raw_injury_details = reporter_submission.get("driver_injury_details")
    driver_injury_details = raw_injury_details.strip() or None if isinstance(raw_injury_details, str) else None
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
        "severity": derive_portal_rta_severity(
            driver_injured=driver_injured,
            third_party_injured=third_party_injured,
        ),
        "status": RTAStatus.REPORTED,
        "location": report.location or "Not specified",
        "collision_date": collision_occurred_at,
        "collision_time": collision_time_value,
        "reported_date": datetime.now(timezone.utc),
        "weather_conditions": reporter_submission.get("weather"),
        "road_conditions": reporter_submission.get("road_condition"),
        "company_vehicle_registration": vehicle_registration,
        "company_vehicle_damage": reporter_submission.get("damage_description"),
        "reporter_name": display_name,
        "reporter_email": report.reporter_email if not report.is_anonymous else None,
        "driver_name": display_name,
        "driver_email": report.reporter_email if not report.is_anonymous else None,
        "driver_injured": driver_injured is True,
        "driver_injury_details": driver_injury_details,
        "third_party_injured": third_party_injured,
        # Drivability is the operational urgency signal the triage word used to carry.
        "vehicle_drivable": read_reported_bool(reporter_submission.get("is_drivable")),
        "third_parties": third_parties_payload,
        "vehicles_involved_count": max(
            2 if reported_third_party_involved else 1,
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


# The portal's dynamic form renderer builds one generic field set for every
# report type, so a Near Miss arrives carrying the incident-shaped keys the
# published template defines (``incident_date``/``incident_time``/
# ``preventive_action``) rather than the NearMiss domain names. Both shapes are
# accepted: template field names live in admin-editable ``form_fields`` rows and
# the portal deploys independently of this API, so the backend cannot assume
# either shape is the one that will arrive.
#
# Date and time are resolved as a *pair* so a value from one client shape can
# never be spliced onto a value from another.
_NEAR_MISS_EVENT_DATETIME_KEYS: tuple[tuple[str, str], ...] = (
    ("event_date", "event_time"),
    ("incident_date", "incident_time"),
)

_NEAR_MISS_PREVENTIVE_ACTION_KEYS: tuple[str, ...] = (
    "preventive_action_suggested",
    "preventive_action",
)


def resolve_near_miss_event_datetime(
    reporter_submission: dict[str, Any],
    *,
    reference_number: Optional[str] = None,
) -> tuple[datetime, Optional[str]]:
    """Resolve the reporter-submitted event date/time from any accepted key pair.

    Returns ``(event_datetime, raw_time_string)``. When no accepted key carries a
    parseable date the submission instant is used, because losing a safety report
    is worse than an imprecise timestamp — but that substitution is logged rather
    than made silently, and no time is invented to go with it.
    """
    resolved: list[tuple[str, datetime, Any]] = []
    for date_key, time_key in _NEAR_MISS_EVENT_DATETIME_KEYS:
        parsed = parse_portal_datetime(reporter_submission.get(date_key), reporter_submission.get(time_key))
        if parsed is not None:
            resolved.append((date_key, parsed, reporter_submission.get(time_key)))

    if not resolved:
        logger.warning(
            "Near miss %s carried no usable event date; recording the submission instant instead. "
            "Accepted date keys: %s. Keys present in reporter_submission: %s.",
            reference_number or "<reference not yet minted>",
            [date_key for date_key, _ in _NEAR_MISS_EVENT_DATETIME_KEYS],
            sorted(reporter_submission),
        )
        return datetime.now(timezone.utc), None

    chosen_key, chosen_datetime, chosen_time = resolved[0]
    conflicts = [(key, dt.isoformat()) for key, dt, _ in resolved[1:] if dt != chosen_datetime]
    if conflicts:
        logger.warning(
            "Near miss %s carried conflicting event dates across accepted keys; using %s=%s and ignoring %s.",
            reference_number or "<reference not yet minted>",
            chosen_key,
            chosen_datetime.isoformat(),
            conflicts,
        )

    raw_time = str(chosen_time).strip() if chosen_time is not None else ""
    if len(raw_time) > PORTAL_NEAR_MISS_EVENT_TIME_DB_LENGTH:
        # near_misses.event_time is varchar(10); an over-long value would abort the
        # whole insert and lose the safety report. The full-precision instant is
        # already on event_date and in the reporter snapshot, so clip and say so.
        logger.warning(
            "Near miss %s submitted a %d-character time under %s; clipping to fit event_time(varchar %d). "
            "Full precision is retained on event_date.",
            reference_number or "<reference not yet minted>",
            len(raw_time),
            chosen_key,
            PORTAL_NEAR_MISS_EVENT_TIME_DB_LENGTH,
        )
        raw_time = raw_time[:PORTAL_NEAR_MISS_EVENT_TIME_DB_LENGTH]
    return chosen_datetime, raw_time or None


def resolve_near_miss_preventive_action(
    reporter_submission: dict[str, Any],
    *,
    reference_number: Optional[str] = None,
) -> Optional[Any]:
    """Resolve the reporter's suggested preventive action from any accepted key."""
    present = [
        (key, reporter_submission.get(key))
        for key in _NEAR_MISS_PREVENTIVE_ACTION_KEYS
        if str(reporter_submission.get(key) or "").strip()
    ]
    if not present:
        return None

    chosen_key, chosen_value = present[0]
    ignored = [key for key, _ in present[1:]]
    if ignored:
        logger.warning(
            "Near miss %s carried a suggested preventive action under multiple accepted keys; "
            "using %s and ignoring %s.",
            reference_number or "<reference not yet minted>",
            chosen_key,
            ignored,
        )
    return chosen_value


def build_near_miss_portal_fields(
    report: QuickReportCreate,
    priority: str,
    reporter_submission: dict[str, Any],
    tenant_id: Optional[int] = None,
    *,
    reference_number: Optional[str] = None,
) -> dict[str, Any]:
    """Map portal Near Miss submission onto every NearMiss column it already has.

    NearMiss has no ``reporter_submission`` JSON column (unlike Incident/Complaint/
    RTA), so the raw snapshot is persisted separately via
    :func:`persist_near_miss_reporter_snapshot`; this function's job is to promote
    every field the reporter actually submitted onto the typed columns so staff
    views never need the raw JSON to see what was reported.
    """
    resolved_tenant_id = tenant_id if tenant_id is not None else get_default_portal_tenant_id()
    display_name = require_portal_display_name(report, reporter_submission)

    # Customer code lives on NearMiss.contract. Prefer reporter_submission.contract;
    # department is a legacy bridge from older portal clients.
    customer_code = str(reporter_submission.get("contract") or "").strip() or ((report.department or "").strip())

    is_hipo = bool(
        reporter_submission.get("is_hipo")
        if reporter_submission.get("is_hipo") is not None
        else reporter_submission.get("hipo")
    )

    # CRITICAL: use the reporter-submitted event date/time — never silently overwrite
    # with server utcnow when the client provided one (data integrity requirement).
    event_occurred_at, event_time_value = resolve_near_miss_event_datetime(
        reporter_submission,
        reference_number=reference_number,
    )

    witnesses_present_raw = reporter_submission.get("witnesses_present")
    witnesses_present = bool(witnesses_present_raw) if witnesses_present_raw is not None else False
    witness_names = reporter_submission.get("witness_names")

    was_involved_raw = reporter_submission.get("was_involved")
    was_involved = bool(was_involved_raw) if was_involved_raw is not None else True

    return {
        "reporter_name": display_name,
        "reporter_email": report.reporter_email if not report.is_anonymous else None,
        "reporter_phone": report.reporter_phone if not report.is_anonymous else None,
        "reporter_role": reporter_submission.get("reporter_role"),
        "was_involved": was_involved,
        "contract": customer_code or "Not specified",
        "contract_other": reporter_submission.get("contract_other"),
        "location": report.location or "Not specified",
        "location_coordinates": reporter_submission.get("location_coordinates"),
        "event_date": event_occurred_at,
        "event_time": event_time_value,
        "potential_consequences": reporter_submission.get("potential_consequences"),
        "preventive_action_suggested": resolve_near_miss_preventive_action(
            reporter_submission,
            reference_number=reference_number,
        ),
        "persons_involved": reporter_submission.get("persons_involved"),
        "witnesses_present": witnesses_present,
        "witness_names": witness_names if witnesses_present and isinstance(witness_names, str) else None,
        "asset_number": reporter_submission.get("asset_number"),
        "asset_type": reporter_submission.get("asset_type"),
        "risk_category": reporter_submission.get("risk_category"),
        "potential_severity": normalize_portal_severity(report.severity),
        "is_hipo": is_hipo,
        "status": "reported",
        "priority": priority,
        "source_form_id": "portal_near_miss_v1",
        "tenant_id": resolved_tenant_id,
    }


# ============================================================================
# Attachment fidelity — portal evidence upload, then linking onto portal cases
# ============================================================================

_PORTAL_EVIDENCE_SOURCE_MODULE = {
    "incident": EvidenceSourceModule.INCIDENT,
    "complaint": EvidenceSourceModule.COMPLAINT,
    "rta": EvidenceSourceModule.ROAD_TRAFFIC_COLLISION,
    "near_miss": EvidenceSourceModule.NEAR_MISS,
}

# An asset that has been uploaded but not yet claimed by a case parks on this
# sentinel source_id. No authenticated upload path can produce it
# (``_normalize_evidence_upload_source`` rejects source_id < 1 and writes the
# action_key otherwise), so it unambiguously means "pending portal upload".
PORTAL_PENDING_SOURCE_ID = "0"

# Mirrors MAX_UPLOAD_BYTES in
# frontend/src/components/DynamicForm/DynamicFormRenderer.tsx. Deliberately
# below the 50MB staff ceiling in evidence_assets.py: this endpoint is public.
PORTAL_MAX_UPLOAD_BYTES = 10 * 1024 * 1024

_PORTAL_UPLOAD_CHUNK_BYTES = 64 * 1024

# Narrower than evidence_assets.ALLOWED_CONTENT_TYPES: no video or audio, so an
# anonymous caller cannot park large media in blob storage. Matches the `accept`
# list the portal upload control offers.
PORTAL_ALLOWED_CONTENT_TYPES: dict[str, EvidenceAssetType] = {
    "image/jpeg": EvidenceAssetType.PHOTO,
    "image/png": EvidenceAssetType.PHOTO,
    "image/gif": EvidenceAssetType.PHOTO,
    "image/webp": EvidenceAssetType.PHOTO,
    "image/heic": EvidenceAssetType.PHOTO,
    "image/heif": EvidenceAssetType.PHOTO,
    "application/pdf": EvidenceAssetType.PDF,
    "application/msword": EvidenceAssetType.DOCUMENT,
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": EvidenceAssetType.DOCUMENT,
    "application/vnd.ms-excel": EvidenceAssetType.DOCUMENT,
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": EvidenceAssetType.DOCUMENT,
    "text/csv": EvidenceAssetType.DOCUMENT,
    "text/plain": EvidenceAssetType.DOCUMENT,
}

# An abandoned form must not strand evidence in storage forever. Pending uploads
# carry a short temporary retention; claiming one promotes it to standard.
PORTAL_PENDING_RETENTION_DAYS = 7

_PORTAL_UPLOAD_TOKEN_KEY = "portal_upload_token"


def _parse_portal_attachment_handle(raw: str) -> tuple[Optional[int], Optional[str]]:
    """Split an ``<id>`` or ``<id>.<token>`` handle into its parts.

    Returns ``(None, ...)`` when the id part is not an integer, so the caller
    can report it as malformed rather than guessing.
    """
    id_part, _, token_part = raw.partition(".")
    try:
        asset_id = int(id_part)
    except (TypeError, ValueError):
        return None, None
    return asset_id, token_part or None


def _portal_upload_token_matches(asset: EvidenceAsset, token: Optional[str]) -> bool:
    """Check the one-shot token issued when a pending upload was created.

    Asset ids are sequential, so without this a caller could claim a stranger's
    in-flight upload simply by guessing the number. Assets seeded without a
    token (staff tooling, fixtures) keep the older plain-id contract.
    """
    metadata = asset.metadata_json if isinstance(asset.metadata_json, dict) else {}
    expected = metadata.get(_PORTAL_UPLOAD_TOKEN_KEY)
    if not expected:
        return True
    return bool(token) and hmac.compare_digest(str(expected), str(token))


async def resolve_portal_attachment_assets(
    db: DbSession,
    *,
    tenant_id: int,
    attachment_ids: Optional[list[str]],
) -> list[EvidenceAsset]:
    """Resolve and validate pending portal uploads for linking to a new case.

    Fails closed (422) when any handle is malformed, unknown, soft-deleted,
    already attached to a case, owned by another tenant, or carries a token that
    does not match. Evidence must never cross a tenant boundary, must never be
    lifted off an existing case, and an unusable handle must never be silently
    dropped — that is the failure mode this whole path exists to prevent.
    """
    if not attachment_ids:
        return []

    seen: set[str] = set()
    requested: list[tuple[str, int, Optional[str]]] = []
    malformed: list[str] = []
    for raw_id in attachment_ids:
        raw = str(raw_id).strip()
        if not raw or raw in seen:
            continue
        seen.add(raw)
        asset_id, token = _parse_portal_attachment_handle(raw)
        if asset_id is None:
            malformed.append(raw)
            continue
        requested.append((raw, asset_id, token))

    if malformed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=api_error(
                ErrorCode.VALIDATION_ERROR,
                "attachment_ids must be evidence asset handles returned by the portal upload endpoint.",
                details={"invalid_ids": malformed},
            ),
        )

    if not requested:
        return []

    result = await db.execute(select(EvidenceAsset).where(EvidenceAsset.id.in_([a for _, a, _ in requested])))
    found = {asset.id: asset for asset in result.scalars().all()}

    invalid_ids: list[str] = []
    resolved: list[EvidenceAsset] = []
    for raw, asset_id, token in requested:
        asset = found.get(asset_id)
        if asset is None or asset.tenant_id != tenant_id or asset.deleted_at is not None:
            invalid_ids.append(raw)
            continue
        # Only an unclaimed upload may be linked. Without this a public caller
        # could re-point evidence off a live investigation onto its own report.
        if str(asset.source_id) != PORTAL_PENDING_SOURCE_ID:
            invalid_ids.append(raw)
            continue
        if not _portal_upload_token_matches(asset, token):
            invalid_ids.append(raw)
            continue
        resolved.append(asset)

    if invalid_ids:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=api_error(
                ErrorCode.VALIDATION_ERROR,
                "One or more attachment_ids could not be linked: not found, expired, already "
                "attached to another record, or belong to a different tenant.",
                details={"invalid_ids": invalid_ids},
            ),
        )

    return resolved


def apply_portal_attachment_links(
    assets: list[EvidenceAsset],
    *,
    source_module: EvidenceSourceModule,
    source_id: int,
) -> None:
    """Attach resolved uploads to the newly created portal case.

    Promotes the asset out of the pending-upload retention window and burns the
    one-shot token, so the same handle cannot be replayed onto a second case.
    """
    for asset in assets:
        asset.source_module = source_module
        asset.source_id = str(source_id)
        if asset.retention_policy == EvidenceRetentionPolicy.TEMPORARY:
            asset.retention_policy = EvidenceRetentionPolicy.STANDARD
            asset.retention_expires_at = None
        metadata = dict(asset.metadata_json) if isinstance(asset.metadata_json, dict) else {}
        if metadata.pop(_PORTAL_UPLOAD_TOKEN_KEY, None) is not None:
            asset.metadata_json = metadata


async def persist_near_miss_reporter_snapshot(
    db: DbSession,
    *,
    tenant_id: int,
    near_miss: NearMiss,
    reporter_submission: dict[str, Any],
) -> None:
    """Immutable audit-log snapshot of raw reporter intake for Near Miss.

    NearMiss has no ``reporter_submission`` column (unlike Incident/Complaint/RTA),
    so the raw submission is preserved in the tamper-evident audit log instead,
    tied to the case via entity_type/entity_id, so no reporter-entered data is
    ever silently dropped. Best-effort: audit infra issues must never block a
    public portal submission that has already promoted every typed field.
    """
    if not reporter_submission:
        return
    try:
        await AuditLogService(db).log(
            tenant_id=tenant_id,
            entity_type="near_miss",
            entity_id=str(near_miss.id),
            action="portal_submit",
            new_values=reporter_submission,
            entity_name=near_miss.reference_number,
            action_category="data",
            is_sensitive=True,
            commit=False,
        )
    except Exception:
        logger.warning(
            "Failed to persist near miss reporter_submission snapshot for %s",
            near_miss.reference_number,
            exc_info=True,
        )


async def commit_portal_record(db: DbSession, record_label: str, *, flush_only: bool = False) -> None:
    """Persist a portal record with an explicit configuration failure on schema drift.

    ``flush_only=True`` assigns the record's primary key within the open
    transaction (e.g. so dependent attachment links / audit entries can
    reference it) without committing yet; the same error handling applies to
    both the flush and the final commit.
    """
    from sqlalchemy.exc import IntegrityError

    try:
        if flush_only:
            await db.flush()
        else:
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


def _portal_owner_id(entity: Any, entity_type: str) -> Optional[int]:
    """Read the owner/assignee id, whatever the column is named for this entity type."""
    field_name = _PORTAL_OWNER_FIELD_BY_TYPE.get(entity_type, "owner_id")
    return getattr(entity, field_name, None)


async def build_portal_idempotency_replay_response(
    db: DbSession,
    *,
    entity_type: str,
    entity_id: int,
    tenant_id: int,
    current_user: Optional[Any],
) -> QuickReportResponse:
    """Rebuild the original 201 response body for an Idempotency-Key replay."""
    model = _PORTAL_MODEL_BY_TYPE[entity_type]
    result = await db.execute(select(model).where(model.id == entity_id, model.tenant_id == tenant_id))
    entity = result.scalar_one_or_none()
    if entity is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=api_error(
                ErrorCode.VALIDATION_ERROR,
                "Idempotency-Key was already used but the original record could not be found.",
            ),
        )
    message, estimated_response = _PORTAL_SUCCESS_COPY[entity_type]
    ref_number = entity.reference_number
    return QuickReportResponse(
        success=True,
        reference_number=ref_number,
        tracking_code=generate_tracking_code(ref_number),
        message=message,
        estimated_response=estimated_response,
        qr_code_url=f"/api/v1/portal/qr/{ref_number}",
        triage_assigned=_portal_owner_id(entity, entity_type) is not None,
        **staff_golden_thread_fields(current_user, entity_type=entity_type, entity_id=entity.id),
    )


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


async def _read_upload_within_limit(file: UploadFile, max_bytes: int) -> bytes:
    """Read an upload, aborting as soon as it exceeds ``max_bytes``.

    Chunked rather than a single ``await file.read()``: this endpoint is public,
    so an oversized body must not be buffered in full before being rejected.
    """
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(_PORTAL_UPLOAD_CHUNK_BYTES)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=api_error(
                    ErrorCode.VALIDATION_ERROR,
                    f"File is larger than the {max_bytes // (1024 * 1024)}MB limit for portal uploads.",
                    details={"max_size_bytes": max_bytes},
                ),
            )
        chunks.append(chunk)
    return b"".join(chunks)


@router.post(
    "/reports/attachments",
    response_model=PortalAttachmentUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload evidence for a portal report",
    description="Upload one photo or document before submitting a portal report. Can be anonymous.",
)
async def upload_portal_attachment(
    db: DbSession,
    file: UploadFile = File(..., description="Photo or document to attach to the report"),
    report_type: str = Form(..., description="Type: incident, complaint, rta or near_miss"),
    current_user: OptionalCurrentUser = None,
):
    """Upload one evidence file ahead of submitting a portal report.

    Public, like the submit endpoint itself, and rate limited by path prefix in
    ``rate_limiter.ENDPOINT_LIMITS``. The returned ``attachment_id`` must be
    passed back in ``attachment_ids`` on submit; until it is claimed the asset is
    parked as a pending upload on a short retention, so an abandoned form cannot
    strand evidence in storage indefinitely.

    Fails loudly on every rejection path. A caller that gets an error here has
    not had its file stored, and must not be told the evidence was accepted.
    """
    from src.infrastructure.storage import StorageDependencyError, StorageError, storage_service

    tenant_id = get_default_portal_tenant_id()

    normalized_type = (report_type or "").strip().lower()
    if normalized_type not in _PORTAL_EVIDENCE_SOURCE_MODULE:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=api_error(
                ErrorCode.VALIDATION_ERROR,
                "report_type must be one of: incident, complaint, rta, near_miss.",
                details={"report_type": report_type},
            ),
        )
    source_module = _PORTAL_EVIDENCE_SOURCE_MODULE[normalized_type]

    # Strip any ``; charset=`` parameter before matching the allowlist.
    content_type = (file.content_type or "").split(";")[0].strip().lower()
    asset_type = PORTAL_ALLOWED_CONTENT_TYPES.get(content_type)
    if asset_type is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=api_error(
                ErrorCode.VALIDATION_ERROR,
                f"Files of type '{content_type or 'unknown'}' cannot be attached to a portal report.",
                details={"allowed_types": sorted(PORTAL_ALLOWED_CONTENT_TYPES)},
            ),
        )

    content = await _read_upload_within_limit(file, PORTAL_MAX_UPLOAD_BYTES)
    if not content:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=api_error(ErrorCode.VALIDATION_ERROR, "The selected file is empty."),
        )

    safe_filename = (file.filename or "attachment").replace("/", "_").replace("\\", "_")[:255]
    storage_key = f"evidence/portal-pending/{normalized_type}/{uuid.uuid4().hex}_{safe_filename}"
    checksum = hashlib.sha256(content).hexdigest()

    try:
        await storage_service().upload(
            storage_key=storage_key,
            content=content,
            content_type=content_type,
            metadata={"portal_pending": "true", "checksum_sha256": checksum},
        )
    except StorageDependencyError:
        logger.exception("Portal attachment upload blocked by storage dependency failure")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=api_error(
                ErrorCode.CONFIGURATION_ERROR,
                "Attachment upload is temporarily unavailable. Please try again shortly.",
            ),
        )
    except StorageError:
        logger.exception("Portal attachment upload failed")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=api_error(
                ErrorCode.CONFIGURATION_ERROR,
                "Attachment upload failed. Please try again, or submit without attachments.",
            ),
        )

    token = secrets.token_urlsafe(24)
    asset = EvidenceAsset(
        tenant_id=tenant_id,
        storage_key=storage_key,
        original_filename=safe_filename,
        content_type=content_type,
        file_size_bytes=len(content),
        checksum_sha256=checksum,
        asset_type=asset_type,
        source_module=source_module,
        source_id=PORTAL_PENDING_SOURCE_ID,
        # Un-triaged content from an anonymous reporter must never default into
        # a customer pack; staff can widen visibility after review.
        visibility=EvidenceVisibility.INTERNAL_ONLY,
        retention_policy=EvidenceRetentionPolicy.TEMPORARY,
        retention_expires_at=datetime.now(timezone.utc) + timedelta(days=PORTAL_PENDING_RETENTION_DAYS),
        metadata_json={_PORTAL_UPLOAD_TOKEN_KEY: token, "portal_pending": True},
        created_by_id=getattr(current_user, "id", None),
    )
    db.add(asset)
    try:
        await db.commit()
        await db.refresh(asset)
    except (IntegrityError, ProgrammingError, OperationalError) as exc:
        await db.rollback()
        # The blob is already written but will never be referenced. Drop it
        # rather than leaving an orphan a public caller can accumulate at will.
        try:
            await storage_service().delete(storage_key)
        except StorageError:
            logger.warning("Could not remove orphaned portal upload %s", storage_key, exc_info=True)
        logger.exception("Portal attachment record could not be persisted")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=api_error(
                ErrorCode.CONFIGURATION_ERROR,
                "Attachment upload could not be recorded. Please try again, or submit without attachments.",
            ),
        ) from exc

    return PortalAttachmentUploadResponse(
        attachment_id=f"{asset.id}.{token}",
        filename=asset.original_filename,
        content_type=asset.content_type,
        size_bytes=len(content),
    )


@router.post(
    "/reports/",
    response_model=QuickReportResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a Quick Report",
    description="Submit an identified incident, complaint, near-miss, or RTA report.",
)
async def submit_quick_report(
    report: QuickReportCreate,
    db: DbSession,
    current_user: OptionalCurrentUser = None,
    idempotency_key_header: Annotated[Optional[str], Header(alias="Idempotency-Key")] = None,
):
    """
    Submit a quick report (incident or complaint).

    This endpoint is public and doesn't require authentication.
    Anonymous submissions are not available (PX-312) and are rejected with 422
    before any persistence. Authenticated staff receive a golden-thread
    staff_href when role allows.

    Optional ``Idempotency-Key`` header (or ``idempotency_key`` body field, for
    clients that cannot set custom headers): retries with the same key return
    the original 201 response instead of creating a duplicate case (PX-001).
    """
    # PX-312: anonymous portal reporting stays off — refuse before any DB write.
    if report.is_anonymous:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=api_error(
                ErrorCode.VALIDATION_ERROR,
                "Anonymous portal submissions are not available",
                details={"fields": ["is_anonymous"]},
            ),
        )

    incident_severity, complaint_priority = map_severity(report.severity)
    reporter_submission = report.reporter_submission or {}
    portal_tenant_id = get_default_portal_tenant_id()
    report_type = report.report_type.lower()
    effective_idempotency_key = (idempotency_key_header or report.idempotency_key or "").strip() or None

    idem_scope = _PORTAL_IDEMPOTENCY_SCOPES.get(report_type)
    idem_claim = None
    if idem_scope is not None:
        idem_claim = await begin_idempotent_create(
            db,
            tenant_id=portal_tenant_id,
            scope=idem_scope,
            idempotency_key=effective_idempotency_key,
            payload=report,
        )
        if idem_claim is not None and idem_claim.is_replay and idem_claim.entity_id is not None:
            return await build_portal_idempotency_replay_response(
                db,
                entity_type=report_type,
                entity_id=idem_claim.entity_id,
                tenant_id=portal_tenant_id,
                current_user=current_user,
            )

    attachment_assets = await resolve_portal_attachment_assets(
        db, tenant_id=portal_tenant_id, attachment_ids=report.attachment_ids
    )

    if report_type == "incident":
        ref_number = await mint_portal_reference(db, "INC")
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
        await commit_portal_record(db, "incident", flush_only=True)
        apply_portal_attachment_links(
            attachment_assets, source_module=_PORTAL_EVIDENCE_SOURCE_MODULE["incident"], source_id=incident.id
        )
        await complete_idempotent_create(
            db,
            record_id=idem_claim.record_id if idem_claim else None,
            entity_type="incident",
            entity_id=incident.id,
        )
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

    elif report_type == "complaint":
        kind = resolve_portal_feedback_kind(report, reporter_submission)
        named_subject = portal_compliment_subject(reporter_submission)
        ref_number = await mint_portal_reference(db, portal_kind_prefix(kind))
        tracking_code = generate_tracking_code(ref_number)
        success_message, estimated_response = portal_feedback_success_copy(kind)

        complaint = Complaint(
            reference_number=ref_number,
            title=report.title,
            description=report.description,
            **build_complaint_portal_fields(
                report,
                complaint_priority,
                reporter_submission,
                portal_tenant_id,
                reference_number=ref_number,
                feedback_kind=kind,
                subject_name=named_subject,
            ),
        )

        db.add(complaint)
        await commit_portal_record(db, "complaint", flush_only=True)
        apply_portal_attachment_links(
            attachment_assets, source_module=_PORTAL_EVIDENCE_SOURCE_MODULE["complaint"], source_id=complaint.id
        )
        await complete_idempotent_create(
            db,
            record_id=idem_claim.record_id if idem_claim else None,
            entity_type="complaint",
            entity_id=complaint.id,
        )
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
            message=success_message,
            estimated_response=estimated_response,
            qr_code_url=f"/api/v1/portal/qr/{ref_number}",
            triage_assigned=triage_assigned,
            **staff_golden_thread_fields(current_user, entity_type="complaint", entity_id=complaint.id),
        )

    elif report_type == "rta":
        ref_number = await mint_portal_reference(db, "RTA")
        tracking_code = generate_tracking_code(ref_number)

        rta = RoadTrafficCollision(
            reference_number=ref_number,
            title=report.title,
            description=report.description,
            **build_rta_portal_fields(
                report,
                reporter_submission,
                portal_tenant_id,
                reference_number=ref_number,
            ),
        )

        db.add(rta)
        await commit_portal_record(db, "RTA", flush_only=True)
        apply_portal_attachment_links(
            attachment_assets, source_module=_PORTAL_EVIDENCE_SOURCE_MODULE["rta"], source_id=rta.id
        )
        await complete_idempotent_create(
            db,
            record_id=idem_claim.record_id if idem_claim else None,
            entity_type="rta",
            entity_id=rta.id,
        )
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

    elif report_type == "near_miss":
        ref_number = await mint_portal_reference(db, "NM")
        tracking_code = generate_tracking_code(ref_number)

        priority = near_miss_priority_for_severity(report.severity)

        near_miss = NearMiss(
            reference_number=ref_number,
            description=report.description,
            **build_near_miss_portal_fields(
                report,
                priority,
                reporter_submission,
                portal_tenant_id,
                reference_number=ref_number,
            ),
        )

        db.add(near_miss)
        await commit_portal_record(db, "near miss", flush_only=True)
        apply_portal_attachment_links(
            attachment_assets, source_module=_PORTAL_EVIDENCE_SOURCE_MODULE["near_miss"], source_id=near_miss.id
        )
        await persist_near_miss_reporter_snapshot(
            db,
            tenant_id=portal_tenant_id,
            near_miss=near_miss,
            reporter_submission=reporter_submission,
        )
        await complete_idempotent_create(
            db,
            record_id=idem_claim.record_id if idem_claim else None,
            entity_type="near_miss",
            entity_id=near_miss.id,
        )
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
    current_user: OptionalCurrentUser = None,
    tracking_code: Optional[str] = Query(
        None,
        description="Tracking code issued at submission. Required unless the caller "
        "is signed in as the account that submitted the report.",
    ),
):
    """
    Track a report's status by reference number.

    Readable with either the reference-specific tracking code (anonymous
    submitters) or a session belonging to the submitter.
    """
    if not reference_number.startswith(_PORTAL_REFERENCE_PREFIXES):
        raise BadRequestError("Invalid reference number format.")

    grant = authorize_portal_report_read(reference_number, tracking_code, current_user)

    # Determine report type from reference number prefix
    if reference_number.startswith("INC-"):
        inc_query = select(Incident).where(Incident.reference_number == reference_number)
        inc_result = await db.execute(inc_query)
        incident = inc_result.scalar_one_or_none()

        if not incident:
            raise NotFoundError(_REPORT_NOT_FOUND_MESSAGE)

        assert_session_owns_report(
            grant,
            current_user,
            owner_email=incident.reporter_email,
            tenant_id=incident.tenant_id,
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

    elif reference_number.startswith(_PORTAL_COMPLAINT_PREFIXES):
        comp_query = select(Complaint).where(Complaint.reference_number == reference_number)
        comp_result = await db.execute(comp_query)
        complaint = comp_result.scalar_one_or_none()

        if not complaint:
            raise NotFoundError(_REPORT_NOT_FOUND_MESSAGE)

        assert_session_owns_report(
            grant,
            current_user,
            owner_email=complaint.complainant_email,
            tenant_id=complaint.tenant_id,
        )

        report_type_label = {
            "compliment": "Compliment",
            "suggestion": "Suggestion",
            "general": "Feedback",
        }.get(
            getattr(complaint.feedback_kind, "value", complaint.feedback_kind) or "complaint",
            "Complaint",
        )

        timeline = [
            {
                "date": complaint.created_at.isoformat(),
                "event": f"{report_type_label} Submitted",
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
            report_type=report_type_label,
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
            raise NotFoundError(_REPORT_NOT_FOUND_MESSAGE)

        assert_session_owns_report(
            grant,
            current_user,
            owner_email=rta.reporter_email,
            tenant_id=rta.tenant_id,
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
            priority=get_priority_label(rta.severity),
            timeline=timeline,
            next_steps="A fleet manager will review your report.",
        )

    elif reference_number.startswith("NM-"):
        nm_query = select(NearMiss).where(NearMiss.reference_number == reference_number)
        nm_result = await db.execute(nm_query)
        near_miss = nm_result.scalar_one_or_none()

        if not near_miss:
            raise NotFoundError(_REPORT_NOT_FOUND_MESSAGE)

        assert_session_owns_report(
            grant,
            current_user,
            owner_email=near_miss.reporter_email,
            tenant_id=near_miss.tenant_id,
        )

        timeline = [
            {
                "date": near_miss.created_at.isoformat(),
                "event": "Near Miss Reported",
                "icon": "⚠️",
            },
        ]

        if normalize_portal_status(near_miss.status) != "reported":
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
            title=format_portal_report_title(f"Near Miss - {near_miss.contract}"),
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
        .where(Complaint.feedback_kind == "complaint")
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
        .where(Complaint.feedback_kind == "complaint")
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
                "id": "negligible",
                "label": "Negligible",
                "description": "No harm or loss, recorded for the trend",
                "color": "#94a3b8",
            },
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
            title=format_portal_report_title(row.title),
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
