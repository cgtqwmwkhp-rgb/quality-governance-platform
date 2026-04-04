"""Unified Actions API routes for incidents, RTAs, complaints, and investigations."""

import logging
from datetime import datetime, timezone
from typing import Any, Optional, Union, cast

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from src.api.dependencies import CurrentUser, DbSession
from src.api.schemas.error_codes import ErrorCode
from src.api.utils.errors import api_error
from src.domain.exceptions import BadRequestError, ConflictError, NotFoundError, ValidationError
from src.domain.models.assessment import AssessmentRun
from src.domain.models.audit import AuditFinding, AuditRun
from src.domain.models.capa import CAPAAction, CAPAPriority, CAPASource, CAPAStatus, CAPAType
from src.domain.models.complaint import Complaint, ComplaintAction
from src.domain.models.incident import ActionStatus, Incident, IncidentAction
from src.domain.models.induction import InductionRun
from src.domain.models.investigation import InvestigationAction, InvestigationActionStatus, InvestigationRun
from src.domain.models.rta import RoadTrafficCollision, RTAAction
from src.domain.models.user import User
from src.infrastructure.monitoring.azure_monitor import track_metric

logger = logging.getLogger(__name__)

router = APIRouter()


# ============== Schemas ==============


class ActionBase(BaseModel):
    """Base action schema."""

    title: str = Field(..., max_length=300)
    description: str
    action_type: str = Field(default="corrective")
    priority: str = Field(default="medium")
    due_date: Optional[str] = Field(None, description="Due date in ISO format (YYYY-MM-DD)")


class ActionCreate(ActionBase):
    """Schema for creating an action."""

    source_type: str = Field(
        ...,
        description="Type of source entity: incident, rta, complaint, investigation, assessment, or induction",
    )
    source_id: Optional[int] = Field(
        None,
        description="ID of the source entity (for incident, rta, complaint, investigation)",
    )
    source_reference: Optional[str] = Field(
        None,
        description="UUID reference for assessment_run_id or induction_run_id (for assessment, induction)",
    )
    assigned_to_email: Optional[str] = Field(None, description="Email of user to assign to")


class ActionUpdate(BaseModel):
    """Schema for updating an action. All fields are optional."""

    title: Optional[str] = Field(None, max_length=300)
    description: Optional[str] = None
    action_type: Optional[str] = None
    priority: Optional[str] = None
    status: Optional[str] = Field(
        None,
        description="One of: open, in_progress, pending_verification, completed, cancelled",
    )
    due_date: Optional[str] = Field(None, description="Due date in ISO format (YYYY-MM-DD)")
    assigned_to_email: Optional[str] = Field(None, description="Email of user to assign to")
    completion_notes: Optional[str] = Field(None, description="Notes on completion")


class ActionResponse(BaseModel):
    """Response schema for actions."""

    id: int
    reference_number: Optional[str] = None
    title: str
    description: str
    action_type: str
    priority: str
    status: str
    due_date: Optional[str] = None
    completed_at: Optional[str] = None
    completion_notes: Optional[str] = None
    source_type: str
    source_id: int
    source_reference: Optional[str] = None
    source_title: Optional[str] = None
    source_scheme: Optional[str] = None
    clause_reference: Optional[str] = None
    owner_id: Optional[int] = None
    owner_email: Optional[str] = None
    assigned_to_email: Optional[str] = None
    created_at: str

    class Config:
        from_attributes = True


class ActionListResponse(BaseModel):
    """Paginated list of actions."""

    items: list[ActionResponse]
    total: int
    page: int
    page_size: int
    pages: int


def _action_to_response(
    action: Union[IncidentAction, RTAAction, ComplaintAction, InvestigationAction],
    source_type: str,
    source_id: int,
    owner_email: Optional[str] = None,
) -> ActionResponse:
    """Convert an action model to a response."""
    return ActionResponse(
        id=action.id,
        reference_number=action.reference_number,
        title=action.title,
        description=action.description,
        action_type=action.action_type or "corrective",
        priority=action.priority or "medium",
        status=(action.status.value if hasattr(action.status, "value") else str(action.status)),
        due_date=action.due_date.isoformat() if action.due_date else None,
        completed_at=action.completed_at.isoformat() if action.completed_at else None,
        completion_notes=getattr(action, "completion_notes", None),
        source_type=source_type,
        source_id=source_id,
        source_reference=None,
        source_title=None,
        source_scheme=None,
        clause_reference=None,
        owner_id=action.owner_id,
        owner_email=owner_email,
        assigned_to_email=owner_email,
        created_at=action.created_at.isoformat() if action.created_at else "",
    )


async def _resolve_owner_email(db: Any, owner_id: Optional[int]) -> Optional[str]:
    """Resolve a user's email from their ID."""
    if not owner_id:
        return None
    try:
        result = await db.execute(select(User.email).where(User.id == owner_id))
        row = result.scalar_one_or_none()
        return row if row else None
    except Exception:
        return None


async def _batch_resolve_owner_emails(db: Any, owner_ids: set[int]) -> dict[int, str]:
    """Batch-resolve user emails to avoid N+1 queries."""
    if not owner_ids:
        return {}
    try:
        result = await db.execute(select(User.id, User.email).where(User.id.in_(owner_ids)))
        return {row.id: row.email for row in result.all()}
    except Exception:
        return {}


def _parse_capa_priority(priority: Optional[str]) -> CAPAPriority:
    """Map a user-supplied priority string to the CAPA enum."""
    normalized = (priority or "medium").lower()
    if normalized == "critical":
        return CAPAPriority.CRITICAL
    if normalized == "high":
        return CAPAPriority.HIGH
    if normalized == "low":
        return CAPAPriority.LOW
    return CAPAPriority.MEDIUM


async def _build_capa_provenance(
    db: "DbSession",
    capa: CAPAAction,
    source_type: str,
) -> dict[str, Optional[str]]:
    source_reference = capa.source_reference
    source_title: Optional[str] = None
    source_scheme: Optional[str] = None
    clause_reference: Optional[str] = capa.clause_reference

    if source_type == "audit_finding" and capa.source_id:
        result = await db.execute(select(AuditFinding).where(AuditFinding.id == capa.source_id))
        finding = cast(Optional[AuditFinding], result.scalar_one_or_none())
        if finding is not None:
            source_reference = getattr(finding, "reference_number", None) or source_reference
            source_title = getattr(finding, "title", None)
            clause_ids = getattr(finding, "clause_ids_json_legacy", None) or []
            if clause_reference is None and clause_ids:
                clause_reference = ", ".join(str(value) for value in clause_ids[:3])
            run_id = getattr(finding, "run_id", None)
            run = None
            if run_id is not None:
                run_result = await db.execute(select(AuditRun).where(AuditRun.id == run_id))
                run = cast(Optional[AuditRun], run_result.scalar_one_or_none())
            if run is not None:
                source_scheme = getattr(run, "assurance_scheme", None)
                if clause_reference is None:
                    clause_reference = getattr(run, "external_reference", None)

    return {
        "source_reference": source_reference,
        "source_title": source_title,
        "source_scheme": source_scheme,
        "clause_reference": clause_reference,
    }


async def _capa_to_response(db: "DbSession", capa: CAPAAction, source_type: str) -> ActionResponse:
    """Convert a CAPA action to unified action response."""
    capa_status = capa.status.value if hasattr(capa.status, "value") else str(capa.status)
    provenance = await _build_capa_provenance(db, capa, source_type)
    return ActionResponse(
        id=capa.id,
        reference_number=capa.reference_number,
        title=capa.title,
        description=capa.description or "",
        action_type=(capa.capa_type.value if hasattr(capa.capa_type, "value") else "corrective"),
        priority=(capa.priority.value if hasattr(capa.priority, "value") else str(capa.priority)),
        status=capa_status,
        due_date=capa.due_date.isoformat() if capa.due_date else None,
        completed_at=capa.completed_at.isoformat() if capa.completed_at else None,
        completion_notes=capa.verification_result,
        source_type=source_type,
        source_id=capa.source_id or 0,
        source_reference=provenance["source_reference"],
        source_title=provenance["source_title"],
        source_scheme=provenance["source_scheme"],
        clause_reference=provenance["clause_reference"],
        owner_id=capa.assigned_to_id,
        owner_email=None,
        created_at=capa.created_at.isoformat() if capa.created_at else "",
    )


# ============== Endpoints ==============


def _apply_capa_status_filter(query, status_filter: str):
    """Map a unified status string to the CAPA enum and apply the filter."""
    capa_status_map = {
        "completed": CAPAStatus.CLOSED,
        "pending_verification": CAPAStatus.VERIFICATION,
    }
    capa_status = capa_status_map.get(status_filter)
    if capa_status is not None:
        return query.where(CAPAAction.status == capa_status)
    try:
        capa_status = CAPAStatus(status_filter)
        return query.where(CAPAAction.status == capa_status)
    except ValueError:
        logger.warning("Unknown status filter '%s' for CAPA, skipping", status_filter)
        return query


async def _safe_scalar(db: "DbSession", query, source_label: str) -> int:
    """Execute a count query, returning 0 and logging on failure."""
    try:
        return (await db.execute(query)).scalar() or 0
    except Exception:
        logger.warning("actions._count_for_source: %s query failed", source_label, exc_info=True)
        return 0


async def _count_for_source(
    db: "DbSession",
    source_type: Optional[str],
    status_filter: Optional[str],
    source_id: Optional[int],
    source_reference: Optional[str],
    tenant_id: Optional[int] = None,
) -> int:
    """Compute total count across all applicable source tables using SQL COUNT."""
    total = 0
    if not source_type or source_type == "incident":
        q = select(func.count()).select_from(IncidentAction)
        if status_filter:
            q = q.where(IncidentAction.status == status_filter)
        if source_type == "incident" and source_id:
            q = q.where(IncidentAction.incident_id == source_id)
        total += await _safe_scalar(db, q, "incident")

    if not source_type or source_type == "rta":
        q = select(func.count()).select_from(RTAAction)
        if status_filter:
            q = q.where(RTAAction.status == status_filter)
        if source_type == "rta" and source_id:
            q = q.where(RTAAction.rta_id == source_id)
        total += await _safe_scalar(db, q, "rta")

    if not source_type or source_type == "complaint":
        q = select(func.count()).select_from(ComplaintAction)
        if status_filter:
            q = q.where(ComplaintAction.status == status_filter)
        if source_type == "complaint" and source_id:
            q = q.where(ComplaintAction.complaint_id == source_id)
        total += await _safe_scalar(db, q, "complaint")

    if not source_type or source_type == "investigation":
        q = select(func.count()).select_from(InvestigationAction)
        if status_filter:
            q = q.where(InvestigationAction.status == status_filter)
        if source_type == "investigation" and source_id:
            q = q.where(InvestigationAction.investigation_id == source_id)
        total += await _safe_scalar(db, q, "investigation")

    if not source_type or source_type == "assessment":
        q = (
            select(func.count())
            .select_from(CAPAAction)
            .where(
                CAPAAction.source_type == CAPASource.JOB_ASSESSMENT,
                CAPAAction.tenant_id == tenant_id,
            )
        )
        if status_filter:
            q = _apply_capa_status_filter(q, status_filter)
        if source_type == "assessment" and source_reference:
            q = q.where(CAPAAction.source_reference == source_reference)
        total += await _safe_scalar(db, q, "assessment")

    if not source_type or source_type == "induction":
        q = (
            select(func.count())
            .select_from(CAPAAction)
            .where(
                CAPAAction.source_type == CAPASource.INDUCTION,
                CAPAAction.tenant_id == tenant_id,
            )
        )
        if status_filter:
            q = _apply_capa_status_filter(q, status_filter)
        if source_type == "induction" and source_reference:
            q = q.where(CAPAAction.source_reference == source_reference)
        total += await _safe_scalar(db, q, "induction")

    if not source_type or source_type == "audit_finding":
        q = (
            select(func.count())
            .select_from(CAPAAction)
            .where(
                CAPAAction.source_type == CAPASource.AUDIT_FINDING,
                CAPAAction.tenant_id == tenant_id,
            )
        )
        if status_filter:
            q = _apply_capa_status_filter(q, status_filter)
        if source_type == "audit_finding" and source_id:
            q = q.where(CAPAAction.source_id == source_id)
        total += await _safe_scalar(db, q, "audit_finding")

    return total


@router.get("/", response_model=ActionListResponse)
async def list_actions(
    db: DbSession,
    current_user: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    status_filter: Optional[str] = Query(None, alias="status"),
    source_type: Optional[str] = Query(None),
    source_id: Optional[int] = Query(None),
    source_reference: Optional[str] = Query(None, description="UUID ref for assessment_run_id or induction_run_id"),
) -> ActionListResponse:
    """List actions across all source types with SQL-level pagination.

    When *source_type* is specified, LIMIT/OFFSET is pushed to the database.
    When listing across all source types, individual queries are capped and
    merged client-side to honour the requested page window.
    """
    total = await _count_for_source(
        db, source_type, status_filter, source_id, source_reference, tenant_id=current_user.tenant_id
    )

    if total == 0:
        return ActionListResponse(items=[], total=0, page=page, page_size=page_size, pages=0)

    offset = (page - 1) * page_size
    actions_list: list[ActionResponse] = []
    # When listing across all sources, cap each sub-query to avoid full table scans
    _cross_source_cap = offset + page_size

    _pending_incident: list = []
    if not source_type or source_type == "incident":
        try:
            q = (
                select(IncidentAction)
                .options(selectinload(IncidentAction.incident))
                .order_by(IncidentAction.created_at.desc())
            )
            if status_filter:
                q = q.where(IncidentAction.status == status_filter)
            if source_type == "incident" and source_id:
                q = q.where(IncidentAction.incident_id == source_id)
            if source_type:
                q = q.offset(offset).limit(page_size)
            else:
                q = q.limit(_cross_source_cap)
            result = await db.execute(q)
            _pending_incident = result.scalars().all()
        except Exception:
            _pending_incident = []
            logger.warning("list_actions: incident query failed", exc_info=True)

    _pending_rta: list = []
    if not source_type or source_type == "rta":
        try:
            q = select(RTAAction).options(selectinload(RTAAction.rta)).order_by(RTAAction.created_at.desc())
            if status_filter:
                q = q.where(RTAAction.status == status_filter)
            if source_type == "rta" and source_id:
                q = q.where(RTAAction.rta_id == source_id)
            if source_type:
                q = q.offset(offset).limit(page_size)
            else:
                q = q.limit(_cross_source_cap)
            result = await db.execute(q)
            _pending_rta = result.scalars().all()
        except Exception:
            logger.warning("list_actions: rta query failed", exc_info=True)

    _pending_complaint: list = []
    if not source_type or source_type == "complaint":
        try:
            q = (
                select(ComplaintAction)
                .options(selectinload(ComplaintAction.complaint))
                .order_by(ComplaintAction.created_at.desc())
            )
            if status_filter:
                q = q.where(ComplaintAction.status == status_filter)
            if source_type == "complaint" and source_id:
                q = q.where(ComplaintAction.complaint_id == source_id)
            if source_type:
                q = q.offset(offset).limit(page_size)
            else:
                q = q.limit(_cross_source_cap)
            result = await db.execute(q)
            _pending_complaint = result.scalars().all()
        except Exception:
            logger.warning("list_actions: complaint query failed", exc_info=True)

    _pending_investigation: list = []
    if not source_type or source_type == "investigation":
        try:
            q = (
                select(InvestigationAction)
                .options(selectinload(InvestigationAction.investigation))
                .order_by(InvestigationAction.created_at.desc())
            )
            if status_filter:
                q = q.where(InvestigationAction.status == status_filter)
            if source_type == "investigation" and source_id:
                q = q.where(InvestigationAction.investigation_id == source_id)
            if source_type:
                q = q.offset(offset).limit(page_size)
            else:
                q = q.limit(_cross_source_cap)
            result = await db.execute(q)
            _pending_investigation = result.scalars().all()
        except Exception:
            logger.warning("list_actions: investigation query failed", exc_info=True)

    _all_owner_ids: set[int] = set()
    for _batch in (_pending_incident, _pending_rta, _pending_complaint, _pending_investigation):
        for a in _batch:
            if a.owner_id:
                _all_owner_ids.add(a.owner_id)
    _email_map = await _batch_resolve_owner_emails(db, _all_owner_ids)

    for a in _pending_incident:
        actions_list.append(_action_to_response(a, "incident", a.incident_id, owner_email=_email_map.get(a.owner_id)))
    for a in _pending_rta:
        actions_list.append(_action_to_response(a, "rta", a.rta_id, owner_email=_email_map.get(a.owner_id)))
    for a in _pending_complaint:
        actions_list.append(_action_to_response(a, "complaint", a.complaint_id, owner_email=_email_map.get(a.owner_id)))
    for a in _pending_investigation:
        actions_list.append(
            _action_to_response(a, "investigation", a.investigation_id, owner_email=_email_map.get(a.owner_id))
        )

    if not source_type or source_type == "assessment":
        try:
            q = (
                select(CAPAAction)
                .where(
                    CAPAAction.source_type == CAPASource.JOB_ASSESSMENT,
                    CAPAAction.tenant_id == current_user.tenant_id,
                )
                .order_by(CAPAAction.created_at.desc())
            )
            if status_filter:
                q = _apply_capa_status_filter(q, status_filter)
            if source_type == "assessment" and source_reference:
                q = q.where(CAPAAction.source_reference == source_reference)
            if source_type:
                q = q.offset(offset).limit(page_size)
            else:
                q = q.limit(_cross_source_cap)
            result = await db.execute(q)
            for a in result.scalars().all():
                actions_list.append(await _capa_to_response(db, a, "assessment"))
        except Exception:
            logger.warning("list_actions: assessment query failed", exc_info=True)

    if not source_type or source_type == "induction":
        try:
            q = (
                select(CAPAAction)
                .where(
                    CAPAAction.source_type == CAPASource.INDUCTION,
                    CAPAAction.tenant_id == current_user.tenant_id,
                )
                .order_by(CAPAAction.created_at.desc())
            )
            if status_filter:
                q = _apply_capa_status_filter(q, status_filter)
            if source_type == "induction" and source_reference:
                q = q.where(CAPAAction.source_reference == source_reference)
            if source_type:
                q = q.offset(offset).limit(page_size)
            else:
                q = q.limit(_cross_source_cap)
            result = await db.execute(q)
            for a in result.scalars().all():
                actions_list.append(await _capa_to_response(db, a, "induction"))
        except Exception:
            logger.warning("list_actions: induction query failed", exc_info=True)

    if not source_type or source_type == "audit_finding":
        try:
            q = (
                select(CAPAAction)
                .where(
                    CAPAAction.source_type == CAPASource.AUDIT_FINDING,
                    CAPAAction.tenant_id == current_user.tenant_id,
                )
                .order_by(CAPAAction.created_at.desc())
            )
            if status_filter:
                q = _apply_capa_status_filter(q, status_filter)
            if source_type == "audit_finding" and source_id:
                q = q.where(CAPAAction.source_id == source_id)
            if source_type:
                q = q.offset(offset).limit(page_size)
            else:
                q = q.limit(_cross_source_cap)
            result = await db.execute(q)
            for a in result.scalars().all():
                actions_list.append(await _capa_to_response(db, a, "audit_finding"))
        except Exception:
            logger.warning("list_actions: audit_finding query failed", exc_info=True)

    # When listing across ALL source types, merge-sort and slice in Python
    # (cross-table UNION ALL with heterogeneous schemas is impractical here).
    if not source_type:
        actions_list.sort(key=lambda x: x.created_at, reverse=True)
        actions_list = actions_list[offset : offset + page_size]

    return ActionListResponse(
        items=actions_list,
        total=total,
        page=page,
        page_size=page_size,
        pages=(total + page_size - 1) // page_size if total > 0 else 0,
    )


@router.post("/", response_model=ActionResponse, status_code=status.HTTP_201_CREATED)
async def create_action(  # noqa: C901 - complexity justified by multi-entity support
    action_data: ActionCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> ActionResponse:
    """Create a new action for an incident, RTA, complaint, investigation, assessment, induction, or audit finding."""
    src_type = action_data.source_type.lower()

    # Assessment and induction use source_reference (UUID); others use source_id.
    if src_type in ("assessment", "induction"):
        src_id = 0
        source_ref = action_data.source_reference
        if not source_ref:
            raise ValidationError("source_reference is required for this source type")
    else:
        src_id = action_data.source_id or 0
        source_ref = None
        if src_id == 0:
            raise ValidationError("source_id is required for this source type")

    # Diagnostic logging for 500 error investigation
    logger.info(
        f"create_action called: source_type={src_type}, source_id={src_id}, "
        f"source_reference={source_ref}, title={action_data.title[:50] if action_data.title else 'None'}, "
        f"user_id={current_user.id}"
    )

    # Validate that the source entity exists
    if src_type == "assessment":
        result = await db.execute(select(AssessmentRun).where(AssessmentRun.id == source_ref))
        if not result.scalar_one_or_none():
            raise NotFoundError("Assessment run not found")
    elif src_type == "induction":
        result = await db.execute(select(InductionRun).where(InductionRun.id == source_ref))
        if not result.scalar_one_or_none():
            raise NotFoundError("Induction run not found")
    elif src_type == "incident":
        result = await db.execute(select(Incident).where(Incident.id == src_id))
        if not result.scalar_one_or_none():
            raise NotFoundError("Incident not found")
    elif src_type == "rta":
        result = await db.execute(select(RoadTrafficCollision).where(RoadTrafficCollision.id == src_id))
        if not result.scalar_one_or_none():
            raise NotFoundError("RTA not found")
    elif src_type == "complaint":
        result = await db.execute(select(Complaint).where(Complaint.id == src_id))
        if not result.scalar_one_or_none():
            raise NotFoundError("Complaint not found")
    elif src_type == "investigation":
        logger.info(f"Validating investigation exists: id={src_id}")
        result = await db.execute(select(InvestigationRun).where(InvestigationRun.id == src_id))
        investigation = result.scalar_one_or_none()
        if not investigation:
            logger.warning(f"Investigation not found: id={src_id}")
            raise NotFoundError("Investigation not found")
        logger.info(f"Investigation found: id={investigation.id}, ref={investigation.reference_number}")
    elif src_type == "audit_finding":
        result = await db.execute(select(AuditFinding).where(AuditFinding.id == src_id))
        if not result.scalar_one_or_none():
            raise NotFoundError("Audit finding not found")
    else:
        raise BadRequestError("Invalid source_type")

    # Find owner by email if provided
    owner_id: Optional[int] = None
    if action_data.assigned_to_email:
        result = await db.execute(select(User).where(User.email == action_data.assigned_to_email))
        user = result.scalar_one_or_none()
        if user:
            owner_id = user.id

    # Generate reference number based on source type
    year = datetime.now().year
    if src_type == "incident":
        count_result = await db.execute(select(func.count()).select_from(IncidentAction))
        count = count_result.scalar() or 0
        ref_number = f"INA-{year}-{count + 1:04d}"
    elif src_type == "rta":
        count_result = await db.execute(select(func.count()).select_from(RTAAction))
        count = count_result.scalar() or 0
        ref_number = f"RTAACT-{year}-{count + 1:04d}"
    elif src_type == "complaint":
        count_result = await db.execute(select(func.count()).select_from(ComplaintAction))
        count = count_result.scalar() or 0
        ref_number = f"CMA-{year}-{count + 1:04d}"
    elif src_type == "investigation":
        count_result = await db.execute(select(func.count()).select_from(InvestigationAction))
        count = count_result.scalar() or 0
        ref_number = f"INVACT-{year}-{count + 1:04d}"
    elif src_type in ("assessment", "induction", "audit_finding"):
        from src.domain.services.reference_number import ReferenceNumberService

        ref_number = await ReferenceNumberService.generate(db, "capa", CAPAAction)
    else:
        ref_number = f"ACT-{year}-0001"

    # Parse due_date string to datetime if provided
    parsed_due_date: Optional[datetime] = None
    if action_data.due_date:
        try:
            # Try ISO format first (YYYY-MM-DD)
            parsed_due_date = datetime.fromisoformat(action_data.due_date.replace("Z", "+00:00"))
        except ValueError:
            # Try other common formats
            for fmt in ["%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"]:
                try:
                    parsed_due_date = datetime.strptime(action_data.due_date, fmt)
                    break
                except ValueError:
                    continue

    # Declare action variable
    action: Union[IncidentAction, RTAAction, ComplaintAction, InvestigationAction, CAPAAction]

    if src_type == "assessment":
        action = CAPAAction(
            reference_number=ref_number,
            title=action_data.title,
            description=action_data.description,
            capa_type=CAPAType.CORRECTIVE,
            status=CAPAStatus.OPEN,
            source_type=CAPASource.JOB_ASSESSMENT,
            source_id=None,
            source_reference=source_ref,
            priority=(
                CAPAPriority.MEDIUM
                if action_data.priority == "medium"
                else (
                    CAPAPriority.HIGH
                    if action_data.priority == "high"
                    else (CAPAPriority.CRITICAL if action_data.priority == "critical" else CAPAPriority.LOW)
                )
            ),
            assigned_to_id=owner_id,
            created_by_id=current_user.id,
            due_date=parsed_due_date,
        )
    elif src_type == "induction":
        action = CAPAAction(
            reference_number=ref_number,
            title=action_data.title,
            description=action_data.description,
            capa_type=CAPAType.CORRECTIVE,
            status=CAPAStatus.OPEN,
            source_type=CAPASource.INDUCTION,
            source_id=None,
            source_reference=source_ref,
            priority=_parse_capa_priority(action_data.priority),
            assigned_to_id=owner_id,
            created_by_id=current_user.id,
            due_date=parsed_due_date,
        )
    elif src_type == "audit_finding":
        action = CAPAAction(
            reference_number=ref_number,
            title=action_data.title,
            description=action_data.description,
            capa_type=CAPAType.CORRECTIVE,
            status=CAPAStatus.OPEN,
            source_type=CAPASource.AUDIT_FINDING,
            source_id=src_id,
            source_reference=None,
            priority=_parse_capa_priority(action_data.priority),
            assigned_to_id=owner_id,
            created_by_id=current_user.id,
            due_date=parsed_due_date,
        )
    elif src_type == "incident":
        action = IncidentAction(
            incident_id=src_id,
            title=action_data.title,
            description=action_data.description,
            action_type=action_data.action_type,
            priority=action_data.priority,
            due_date=parsed_due_date,
            owner_id=owner_id,
            status=ActionStatus.OPEN,
            reference_number=ref_number,
        )
    elif src_type == "rta":
        action = RTAAction(
            rta_id=src_id,
            title=action_data.title,
            description=action_data.description,
            action_type=action_data.action_type,
            priority=action_data.priority,
            due_date=parsed_due_date,
            owner_id=owner_id,
            status=ActionStatus.OPEN,
            reference_number=ref_number,
        )
    elif src_type == "complaint":
        action = ComplaintAction(
            complaint_id=src_id,
            title=action_data.title,
            description=action_data.description,
            action_type=action_data.action_type,
            priority=action_data.priority,
            due_date=parsed_due_date,
            owner_id=owner_id,
            status=ActionStatus.OPEN,
            reference_number=ref_number,
        )
    elif src_type == "investigation":
        # This branch fixes the "Cannot add action" defect
        action = InvestigationAction(
            investigation_id=src_id,
            title=action_data.title,
            description=action_data.description,
            action_type=action_data.action_type,
            priority=action_data.priority,
            due_date=parsed_due_date,
            owner_id=owner_id,
            status=InvestigationActionStatus.OPEN,
            reference_number=ref_number,
        )
    else:
        raise BadRequestError("Invalid source_type")

    try:
        logger.info(f"Adding action to session: ref_number={ref_number}, status={action.status}")
        db.add(action)
        logger.info("Committing action to database...")
        await db.commit()
        logger.info("Action committed successfully, refreshing...")
        await db.refresh(action)
        logger.info(f"Action created successfully: id={action.id}, ref={action.reference_number}")
    except IntegrityError as e:
        await db.rollback()
        error_msg = str(e.orig) if hasattr(e, "orig") else str(e)
        logger.error(f"IntegrityError creating action: {error_msg}")
        if "foreign key" in error_msg.lower() or "violates foreign key constraint" in error_msg.lower():
            raise NotFoundError("Source entity not found or was deleted")
        elif "unique" in error_msg.lower() or "duplicate" in error_msg.lower():
            raise ConflictError("An action with this reference number already exists")
        else:
            logger.error("Database error creating action: %s", error_msg[:500])
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=api_error(ErrorCode.DATABASE_ERROR, "Database error while creating action"),
            )
    except Exception as e:
        await db.rollback()
        logger.exception("Unexpected exception creating action: type=%s", type(e).__name__)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=api_error(ErrorCode.INTERNAL_ERROR, "An unexpected error occurred while creating the action"),
        )

    track_metric("actions.created")

    if isinstance(action, CAPAAction):
        return await _capa_to_response(db, action, src_type)

    resolved_email = action_data.assigned_to_email or await _resolve_owner_email(db, action.owner_id)
    return ActionResponse(
        id=action.id,
        reference_number=action.reference_number,
        title=action.title,
        description=action.description,
        action_type=action.action_type or "corrective",
        priority=action.priority or "medium",
        status=(action.status.value if hasattr(action.status, "value") else str(action.status)),
        due_date=action.due_date.isoformat() if action.due_date else None,
        completed_at=action.completed_at.isoformat() if action.completed_at else None,
        completion_notes=getattr(action, "completion_notes", None),
        source_type=src_type,
        source_id=src_id,
        source_reference=None,
        source_title=None,
        source_scheme=None,
        clause_reference=None,
        owner_id=action.owner_id,
        owner_email=resolved_email,
        assigned_to_email=resolved_email,
        created_at=action.created_at.isoformat() if action.created_at else "",
    )


@router.get("/{action_id}")
async def get_action(
    action_id: int,
    db: DbSession,
    current_user: CurrentUser,
    source_type: str = Query(
        ...,
        description="Type of source: incident, rta, complaint, investigation, assessment, induction, or audit_finding",
    ),
) -> ActionResponse:
    """Get a specific action by ID."""
    src_type = source_type.lower()

    if src_type == "assessment":
        result = await db.execute(
            select(CAPAAction).where(
                CAPAAction.id == action_id,
                CAPAAction.source_type == CAPASource.JOB_ASSESSMENT,
                CAPAAction.tenant_id == current_user.tenant_id,
            )
        )
        capa_action = cast(Optional[CAPAAction], result.scalar_one_or_none())
        if capa_action:
            return await _capa_to_response(db, capa_action, "assessment")
    elif src_type == "induction":
        result = await db.execute(
            select(CAPAAction).where(
                CAPAAction.id == action_id,
                CAPAAction.source_type == CAPASource.INDUCTION,
                CAPAAction.tenant_id == current_user.tenant_id,
            )
        )
        capa_action = cast(Optional[CAPAAction], result.scalar_one_or_none())
        if capa_action:
            return await _capa_to_response(db, capa_action, "induction")
    elif src_type == "audit_finding":
        result = await db.execute(
            select(CAPAAction).where(
                CAPAAction.id == action_id,
                CAPAAction.source_type == CAPASource.AUDIT_FINDING,
                CAPAAction.tenant_id == current_user.tenant_id,
            )
        )
        capa_action = cast(Optional[CAPAAction], result.scalar_one_or_none())
        if capa_action:
            return await _capa_to_response(db, capa_action, "audit_finding")
    elif src_type == "incident":
        result = await db.execute(select(IncidentAction).where(IncidentAction.id == action_id))
        incident_action = cast(Optional[IncidentAction], result.scalar_one_or_none())
        if incident_action:
            email = await _resolve_owner_email(db, incident_action.owner_id)
            return _action_to_response(incident_action, "incident", incident_action.incident_id, owner_email=email)
    elif src_type == "rta":
        result = await db.execute(select(RTAAction).where(RTAAction.id == action_id))
        rta_action = cast(Optional[RTAAction], result.scalar_one_or_none())
        if rta_action:
            email = await _resolve_owner_email(db, rta_action.owner_id)
            return _action_to_response(rta_action, "rta", rta_action.rta_id, owner_email=email)
    elif src_type == "complaint":
        result = await db.execute(select(ComplaintAction).where(ComplaintAction.id == action_id))
        complaint_action = cast(Optional[ComplaintAction], result.scalar_one_or_none())
        if complaint_action:
            email = await _resolve_owner_email(db, complaint_action.owner_id)
            return _action_to_response(complaint_action, "complaint", complaint_action.complaint_id, owner_email=email)
    elif src_type == "investigation":
        result = await db.execute(select(InvestigationAction).where(InvestigationAction.id == action_id))
        investigation_action = cast(Optional[InvestigationAction], result.scalar_one_or_none())
        if investigation_action:
            email = await _resolve_owner_email(db, investigation_action.owner_id)
            return _action_to_response(
                investigation_action,
                "investigation",
                investigation_action.investigation_id,
                owner_email=email,
            )

    raise NotFoundError("Action not found")


@router.patch("/{action_id}", response_model=ActionResponse)
async def update_action(  # noqa: C901 - complexity justified by unified action types
    action_id: int,
    action_data: ActionUpdate,
    db: DbSession,
    current_user: CurrentUser,
    source_type: str = Query(
        ...,
        description="Type of source: incident, rta, complaint, investigation, assessment, induction, or audit_finding",
    ),
) -> ActionResponse:
    """Update an existing action by ID.

    Supports partial updates - only provided fields will be updated.
    Returns 404 if action not found, 400 for validation errors.
    """
    src_type = source_type.lower()

    # Bounded error class: validate source_type
    if src_type not in (
        "incident",
        "rta",
        "complaint",
        "investigation",
        "assessment",
        "induction",
        "audit_finding",
    ):
        raise BadRequestError("Invalid source_type")

    # Bounded error class: validate status if provided
    valid_statuses = {
        "open",
        "in_progress",
        "pending_verification",
        "completed",
        "cancelled",
        "verification",
        "closed",
        "overdue",  # CAPA statuses
    }
    if action_data.status and action_data.status.lower() not in valid_statuses:
        raise BadRequestError("Invalid status value")

    # Bounded error class: validate priority if provided
    valid_priorities = {"low", "medium", "high", "critical"}
    if action_data.priority and action_data.priority.lower() not in valid_priorities:
        raise BadRequestError("Invalid priority value")

    # Find the action by type
    action: Optional[Union[IncidentAction, RTAAction, ComplaintAction, InvestigationAction, CAPAAction]] = None
    source_id: int = 0

    if src_type == "assessment":
        result = await db.execute(
            select(CAPAAction).where(
                CAPAAction.id == action_id,
                CAPAAction.source_type == CAPASource.JOB_ASSESSMENT,
                CAPAAction.tenant_id == current_user.tenant_id,
            )
        )
        action = cast(Optional[CAPAAction], result.scalar_one_or_none())
        if action:
            source_id = action.source_id or 0
    elif src_type == "induction":
        result = await db.execute(
            select(CAPAAction).where(
                CAPAAction.id == action_id,
                CAPAAction.source_type == CAPASource.INDUCTION,
                CAPAAction.tenant_id == current_user.tenant_id,
            )
        )
        action = cast(Optional[CAPAAction], result.scalar_one_or_none())
        if action:
            source_id = action.source_id or 0
    elif src_type == "audit_finding":
        result = await db.execute(
            select(CAPAAction).where(
                CAPAAction.id == action_id,
                CAPAAction.source_type == CAPASource.AUDIT_FINDING,
                CAPAAction.tenant_id == current_user.tenant_id,
            )
        )
        action = cast(Optional[CAPAAction], result.scalar_one_or_none())
        if action:
            source_id = action.source_id or 0
    elif src_type == "incident":
        result = await db.execute(select(IncidentAction).where(IncidentAction.id == action_id))
        action = cast(Optional[IncidentAction], result.scalar_one_or_none())
        if action:
            source_id = action.incident_id
    elif src_type == "rta":
        result = await db.execute(select(RTAAction).where(RTAAction.id == action_id))
        action = cast(Optional[RTAAction], result.scalar_one_or_none())
        if action:
            source_id = action.rta_id
    elif src_type == "complaint":
        result = await db.execute(select(ComplaintAction).where(ComplaintAction.id == action_id))
        action = cast(Optional[ComplaintAction], result.scalar_one_or_none())
        if action:
            source_id = action.complaint_id
    elif src_type == "investigation":
        result = await db.execute(select(InvestigationAction).where(InvestigationAction.id == action_id))
        action = cast(Optional[InvestigationAction], result.scalar_one_or_none())
        if action:
            source_id = action.investigation_id

    if not action:
        raise NotFoundError("Action not found")

    # Apply updates - only update fields that were provided
    if action_data.title is not None:
        action.title = action_data.title
    if action_data.description is not None:
        action.description = action_data.description

    if isinstance(action, CAPAAction):
        if action_data.action_type is not None:
            action.capa_type = CAPAType(action_data.action_type)
        if action_data.priority is not None:
            action.priority = CAPAPriority(action_data.priority.lower())
        if action_data.status is not None:
            status_value = action_data.status.lower()
            status_map = {
                "completed": CAPAStatus.CLOSED,
                "closed": CAPAStatus.CLOSED,
                "pending_verification": CAPAStatus.VERIFICATION,
                "verification": CAPAStatus.VERIFICATION,
            }
            capa_status = status_map.get(status_value)
            if capa_status is None:
                try:
                    capa_status = CAPAStatus(status_value)
                except ValueError:
                    pass
            if capa_status is not None:
                action.status = capa_status
                if status_value == "completed" and not action.completed_at:
                    action.completed_at = datetime.now(timezone.utc)
                elif status_value != "completed":
                    action.completed_at = None
        if action_data.assigned_to_email is not None:
            result = await db.execute(select(User).where(User.email == action_data.assigned_to_email))
            user = result.scalar_one_or_none()
            if user:
                action.assigned_to_id = user.id
        if action_data.completion_notes is not None:
            action.verification_result = action_data.completion_notes
    else:
        if action_data.action_type is not None:
            action.action_type = action_data.action_type
        if action_data.priority is not None:
            action.priority = action_data.priority.lower()
        if action_data.status is not None:
            status_value = action_data.status.lower()
            if src_type == "investigation":
                try:
                    action.status = InvestigationActionStatus(status_value)
                except ValueError:
                    raise BadRequestError(f"Invalid status '{status_value}' for investigation action")
            else:
                try:
                    action.status = ActionStatus(status_value)
                except ValueError:
                    raise BadRequestError(f"Invalid status '{status_value}' for {src_type} action")
            if status_value == "completed" and not action.completed_at:
                action.completed_at = datetime.now(timezone.utc)
            elif status_value != "completed":
                action.completed_at = None
        if action_data.assigned_to_email is not None:
            result = await db.execute(select(User).where(User.email == action_data.assigned_to_email))
            user = result.scalar_one_or_none()
            if user:
                action.owner_id = user.id
        if action_data.completion_notes is not None:
            action.completion_notes = action_data.completion_notes

    if action_data.due_date is not None:
        try:
            action.due_date = datetime.fromisoformat(action_data.due_date.replace("Z", "+00:00"))
        except ValueError:
            for fmt in ["%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"]:
                try:
                    action.due_date = datetime.strptime(action_data.due_date, fmt)
                    break
                except ValueError:
                    continue

    await db.commit()
    await db.refresh(action)

    if isinstance(action, CAPAAction):
        return await _capa_to_response(db, action, src_type)
    owner_id = getattr(action, "owner_id", None) or getattr(action, "assigned_to_id", None)
    email = await _resolve_owner_email(db, owner_id)
    return _action_to_response(action, src_type, source_id, owner_email=email)
