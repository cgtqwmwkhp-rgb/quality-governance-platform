"""Investigation Run API routes."""

import logging
import math
from datetime import datetime, timezone
from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import CurrentUser, DbSession, require_permission
from src.api.schemas.capa import CAPAResponse
from src.api.schemas.investigation import (
    CreateFromRecordRequest,
    CreateInvestigationCapaRequest,
    InvestigationClosureValidationResponse,
    InvestigationCommentResponse,
    InvestigationCommentsResponse,
    InvestigationCustomerPackResponse,
    InvestigationPackGeneratedResponse,
    InvestigationPacksResponse,
    InvestigationRunCreate,
    InvestigationRunListResponse,
    InvestigationRunResponse,
    InvestigationRunUpdate,
    InvestigationTimelineResponse,
    SourceRecordItem,
    SourceRecordsResponse,
)
from src.api.utils.tenant import apply_tenant_filter, require_tenant_id
from src.domain.exceptions import BadRequestError, ConflictError, NotFoundError, TenantAccessError, ValidationError
from src.domain.models.investigation import (
    AssignedEntityType,
    InvestigationComment,
    InvestigationCustomerPack,
    InvestigationRevisionEvent,
    InvestigationRun,
    InvestigationStatus,
    InvestigationTemplate,
)
from src.domain.models.user import User
from src.domain.services.investigation_service import InvestigationService

logger = logging.getLogger(__name__)

router = APIRouter()


class ClosureReasonCode:
    """Stable reason-code constants for closure validation contracts."""

    TEMPLATE_NOT_FOUND = "TEMPLATE_NOT_FOUND"
    MISSING_REQUIRED_FIELD = "MISSING_REQUIRED_FIELD"
    MISSING_REQUIRED_SECTION = "MISSING_REQUIRED_SECTION"
    INVALID_ARRAY_EMPTY = "INVALID_ARRAY_EMPTY"
    LEVEL_NOT_SET = "LEVEL_NOT_SET"
    STATUS_NOT_COMPLETE = "STATUS_NOT_COMPLETE"
    OPEN_ACTIONS_REMAIN = "OPEN_ACTIONS_REMAIN"
    LEAD_INVESTIGATOR_NOT_ASSIGNED = "LEAD_INVESTIGATOR_NOT_ASSIGNED"
    INVESTIGATION_NOT_STARTED = "INVESTIGATION_NOT_STARTED"
    MISSING_FINDINGS = "MISSING_FINDINGS"
    MISSING_CONCLUSION = "MISSING_CONCLUSION"


def _missing_items_to_payload(validation: Any) -> list[dict]:
    """Serialize named closure blockers, tolerating older result shapes."""
    payload: list[dict] = []
    for item in getattr(validation, "missing_items", None) or []:
        section_key = str(getattr(item, "section_key", "") or "")
        field_key = getattr(item, "field_key", None)
        payload.append(
            {
                "code": str(getattr(item, "code", "") or ""),
                "section_key": section_key,
                "section_label": str(getattr(item, "section_label", "") or section_key),
                "field_key": field_key,
                "field_label": getattr(item, "field_label", None),
                "path": f"{section_key}.{field_key}" if field_key else section_key,
            }
        )
    return payload


def _user_can_access_investigation(user: Any, investigation: InvestigationRun) -> bool:
    """Named-involvement check for investigation-scoped read endpoints.

    This answers "may this caller see this run *within their own tenant*". It is
    deliberately tenant-blind: ``_assert_investigation_tenant`` establishes the
    tenant first, so ``investigations:view_all`` here means every investigation
    in the caller's tenant, which is what its siblings in the four case
    registers mean (``rta:view_all`` and friends are only ever consulted after a
    tenant-scoped fetch, to widen a reporter-email restriction).
    """
    if getattr(user, "is_superuser", False):
        return True
    has_permission = getattr(user, "has_permission", None)
    if callable(has_permission) and has_permission("investigations:view_all"):
        return True
    user_id = getattr(user, "id", None)
    return user_id in {
        getattr(investigation, "assigned_to_user_id", None),
        getattr(investigation, "reviewer_user_id", None),
        getattr(investigation, "approved_by_id", None),
        getattr(investigation, "created_by_id", None),
    }


def _assert_investigation_tenant(investigation: InvestigationRun, current_user: Any) -> int:
    """Refuse any by-id access to a run outside the caller's tenant; return that tenant.

    Every route that reaches an ``InvestigationRun`` by id must pass through
    here, read or write. Before this existed the read path selected by bare id
    and then asked only about roles, so a holder of ``investigations:view_all``
    could read another tenant's run, and the write path checked nothing beyond
    its permission gate.

    Investigations are tenant-local, including for app superusers, so there is
    deliberately no superuser branch:

    * ``investigation_runs`` carries a FORCE RLS ``tenant_isolation`` policy
      (20260222_add_rls_policies, 20260710_force_rls) whose USING clause is
      ``tenant_id = current_setting('app.current_tenant_id')`` with no superuser
      exemption. Per ``TenantContextMiddleware``, an app superuser with a tenant
      still gets that GUC bound to *their own* tenant; cross-tenant admin is a
      BYPASSRLS database-role capability, not an application flag.
    * #1389's ``resolve_investigation_closure_scope`` already refuses a
      superuser's cross-tenant closure. A read or write that crossed where the
      close refuses would be #1382's B-2 read/write asymmetry in reverse.
    * The investigation paths that were already scoped —
      ``CAPAService.create_capa_for_investigation``,
      ``link_asset_to_investigation`` (SEC-01), ``from-record``,
      ``source-coverage`` — all scope unconditionally. Unlike the four case
      registers there is no ``skip_tenant_check`` idiom anywhere in the
      investigation services to honour.

    A run whose ``tenant_id`` is missing is refused rather than guessed at: the
    column is NOT NULL, so such a row is corrupt and no caller can be shown to
    be entitled to it.
    """
    caller_tenant_id = require_tenant_id(getattr(current_user, "tenant_id", None))
    record_tenant_id = getattr(investigation, "tenant_id", None)
    if record_tenant_id is None or int(record_tenant_id) != int(caller_tenant_id):
        logger.warning(
            "investigation_cross_tenant_access_refused",
            extra={
                "investigation_id": getattr(investigation, "id", None),
                "reference_number": getattr(investigation, "reference_number", None),
                "record_tenant_id": record_tenant_id,
                "caller_tenant_id": caller_tenant_id,
            },
        )
        raise TenantAccessError(
            "This investigation belongs to another organisation.",
            details={"investigation_id": getattr(investigation, "id", None)},
        )
    return caller_tenant_id


async def _load_investigation_or_404(investigation_id: int, db: AsyncSession) -> InvestigationRun:
    """Fetch a run by id with no authorization. Callers must gate what they get back.

    Split out only so ``add_comment`` can report a corrupt (tenant-less) run
    under its own write-specific reason before authorizing against it.
    """
    result = await db.execute(select(InvestigationRun).where(InvestigationRun.id == investigation_id))
    investigation = result.scalar_one_or_none()
    if not investigation:
        raise NotFoundError(f"Investigation with ID {investigation_id} not found")
    return investigation


async def _get_investigation_or_404(
    investigation_id: int,
    db: AsyncSession,
    current_user: Any,
) -> InvestigationRun:
    """Load a run, refusing another tenant's outright and hiding the rest as 404.

    Order matters: a cross-tenant run is refused under the shared
    ``TENANT_ACCESS_DENIED`` code #1389 introduced, *before* roles are consulted,
    so no permission can be mistaken for a licence to leave the tenant. Only
    then does a run the caller is not named on become a 404, which is the
    existing in-tenant contract these endpoints are documented and tested for.
    """
    investigation = await _load_investigation_or_404(investigation_id, db)
    _assert_investigation_tenant(investigation, current_user)
    if not _user_can_access_investigation(current_user, investigation):
        raise NotFoundError(f"Investigation with ID {investigation_id} not found")
    return investigation


async def _investigation_to_response(
    db: AsyncSession,
    investigation: InvestigationRun,
    *,
    tenant_id: int | None,
) -> InvestigationRunResponse:
    """Serialize investigation with hydrated source reference (PX-139)."""
    from src.domain.services.investigation_service import resolve_assigned_entity_reference

    entity_type = (
        investigation.assigned_entity_type.value
        if hasattr(investigation.assigned_entity_type, "value")
        else str(investigation.assigned_entity_type)
    )
    entity_ref: str | None = None
    entity_id = getattr(investigation, "assigned_entity_id", None)
    if entity_id is not None:
        entity_ref = await resolve_assigned_entity_reference(
            db,
            entity_type,
            int(entity_id),
            tenant_id,
        )
    payload = InvestigationRunResponse.model_validate(investigation).model_dump()
    payload["assigned_entity_reference"] = entity_ref
    return InvestigationRunResponse.model_validate(payload)


async def _collect_readiness_reasons(
    db: AsyncSession,
    *,
    investigation: InvestigationRun,
    investigation_id: int,
    current_user: Any,
    gate: str,
) -> tuple[list[str], list, list]:
    """Collect completion/closure readiness reasons (shared by GET + PATCH gates).

    ``gate`` is ``complete`` (status → completed) or ``close`` (status → closed).
    Returns ``(reasons, open_work, missing_items)``.

    The probe scope is derived from the run here, at the one point both the GET
    and the PATCH gate pass through, rather than being handed in by each caller —
    that is what stops the two from ever being given different tenants.
    """
    from src.domain.services.investigation_closure_helpers import (
        CLOSURE_REASON_OPEN_ACTIONS_REMAIN,
        collect_summary_readiness_blockers,
        fetch_open_work_for_investigation,
        resolve_investigation_closure_scope,
    )

    tenant_id = resolve_investigation_closure_scope(
        investigation,
        caller_tenant_id=getattr(current_user, "tenant_id", None),
    )

    reasons: list[str] = []
    missing_items: list = []

    if not investigation.level:
        reasons.append(ClosureReasonCode.LEVEL_NOT_SET)

    summary_reasons, summary_items = collect_summary_readiness_blockers(investigation)
    for code in summary_reasons:
        if code not in reasons:
            reasons.append(code)
    missing_items.extend(summary_items)

    if gate == "close" and investigation.status != InvestigationStatus.COMPLETED:
        reasons.append(ClosureReasonCode.STATUS_NOT_COMPLETE)

    open_work: list = []
    try:
        open_work = await fetch_open_work_for_investigation(
            db,
            investigation_id=investigation_id,
            tenant_id=tenant_id,
        )
        if open_work:
            reasons.append(CLOSURE_REASON_OPEN_ACTIONS_REMAIN)
    except Exception:  # noqa: BLE001 — never turn open-work probe into HTTP 500
        logger.exception(
            "closure_gate_open_work_failed",
            extra={"investigation_id": investigation_id, "tenant_id": tenant_id},
        )
        if CLOSURE_REASON_OPEN_ACTIONS_REMAIN not in reasons:
            reasons.append(CLOSURE_REASON_OPEN_ACTIONS_REMAIN)

    try:
        template_validation = await InvestigationService.validate_closure(
            db,
            investigation_id=investigation_id,
            tenant_id=tenant_id,
        )
        for code in getattr(template_validation, "reason_codes", None) or []:
            code_str = code.value if hasattr(code, "value") else str(code)
            if code_str not in reasons:
                reasons.append(code_str)
        missing_items.extend(getattr(template_validation, "missing_items", None) or [])
    except Exception:  # noqa: BLE001
        logger.exception(
            "closure_gate_template_failed",
            extra={"investigation_id": investigation_id, "tenant_id": tenant_id},
        )
        if ClosureReasonCode.MISSING_REQUIRED_SECTION not in reasons:
            reasons.append(ClosureReasonCode.MISSING_REQUIRED_SECTION)

    return reasons, open_work, missing_items


def _apply_open_work_override(
    reasons: list[str],
    open_work: list,
    *,
    allow_override: bool,
    override_reason: str | None,
    current_user: Any,
    investigation: InvestigationRun,
) -> tuple[list[str], list, dict | None]:
    """Strip OPEN_ACTIONS_REMAIN when a supervisor supplies an override reason."""
    from src.domain.services.investigation_closure_helpers import (
        CLOSURE_REASON_OPEN_ACTIONS_REMAIN,
        user_can_supervisor_override_closure,
    )

    if CLOSURE_REASON_OPEN_ACTIONS_REMAIN not in reasons:
        return reasons, open_work, None
    if not allow_override:
        return reasons, open_work, None

    reason_text = (override_reason or "").strip()
    if not reason_text:
        raise BadRequestError(
            "Supervisor override reason is required when open CAPA/actions remain",
            code="CLOSURE_OVERRIDE_REASON_REQUIRED",
        )
    if not user_can_supervisor_override_closure(current_user, investigation):
        raise BadRequestError(
            "Supervisor permission is required to override open CAPA/actions",
            code="CLOSURE_OVERRIDE_FORBIDDEN",
        )

    filtered = [code for code in reasons if code != CLOSURE_REASON_OPEN_ACTIONS_REMAIN]
    return filtered, [], {"closure_override": True, "closure_override_reason": reason_text}


async def _collect_closure_reasons(
    db: AsyncSession,
    *,
    investigation: InvestigationRun,
    investigation_id: int,
    current_user: Any,
) -> tuple[list[str], list]:
    """Collect closure readiness reasons (same contract as GET /closure-validation)."""
    reasons, open_work, _missing = await _collect_readiness_reasons(
        db,
        investigation=investigation,
        investigation_id=investigation_id,
        current_user=current_user,
        gate="close",
    )
    return reasons, open_work


async def _ensure_investigation_ready_for_status(
    db: AsyncSession,
    *,
    investigation: InvestigationRun,
    investigation_id: int,
    current_user: Any,
    gate: str,
    allow_open_work_override: bool = False,
    override_reason: str | None = None,
) -> dict | None:
    """Raise BadRequestError(400) when the run cannot reach completed/closed."""
    from src.domain.services.investigation_closure_helpers import open_work_to_payload

    reasons, open_work, missing_items = await _collect_readiness_reasons(
        db,
        investigation=investigation,
        investigation_id=investigation_id,
        current_user=current_user,
        gate=gate,
    )
    reasons, open_work, override_meta = _apply_open_work_override(
        reasons,
        open_work,
        allow_override=allow_open_work_override,
        override_reason=override_reason,
        current_user=current_user,
        investigation=investigation,
    )
    if not reasons:
        return override_meta
    label = "completed" if gate == "complete" else "closed"
    raise BadRequestError(
        f"Investigation cannot be marked {label} until readiness validation passes",
        code="CLOSURE_VALIDATION_FAILED",
        details={
            "can_close": False,
            "can_complete": gate == "complete" and False,
            "reasons": reasons,
            "missing_items": _missing_items_to_payload_from_list(missing_items),
            "open_work": open_work_to_payload(open_work),
            "open_work_count": len(open_work),
        },
    )


def _missing_items_to_payload_from_list(missing_items: list) -> list[dict]:
    """Serialize ClosureMissingItem rows without a full validation result wrapper."""
    payload: list[dict] = []
    for item in missing_items:
        section_key = str(getattr(item, "section_key", "") or "")
        field_key = getattr(item, "field_key", None)
        payload.append(
            {
                "code": str(getattr(item, "code", "") or ""),
                "section_key": section_key,
                "section_label": str(getattr(item, "section_label", "") or section_key),
                "field_key": field_key,
                "field_label": getattr(item, "field_label", None),
                "path": getattr(item, "path", None) or (f"{section_key}.{field_key}" if field_key else section_key),
            }
        )
    return payload


async def _ensure_investigation_ready_to_close(
    db: AsyncSession,
    *,
    investigation: InvestigationRun,
    investigation_id: int,
    current_user: Any,
    allow_open_work_override: bool = False,
    override_reason: str | None = None,
) -> dict | None:
    """Raise BadRequestError(400) with closure reasons when the run cannot close."""
    return await _ensure_investigation_ready_for_status(
        db,
        investigation=investigation,
        investigation_id=investigation_id,
        current_user=current_user,
        gate="close",
        allow_open_work_override=allow_open_work_override,
        override_reason=override_reason,
    )


async def validate_assigned_entity(
    entity_type: str,
    entity_id: int,
    db: AsyncSession,
    request_id: str,
) -> None:
    """Validate that the assigned entity exists.

    Raises HTTPException with canonical envelope if entity doesn't exist.
    """
    # Map entity type to model
    entity_models = {
        AssignedEntityType.ROAD_TRAFFIC_COLLISION.value: "src.domain.models.rta:RoadTrafficCollision",
        AssignedEntityType.REPORTING_INCIDENT.value: "src.domain.models.incident:Incident",
        AssignedEntityType.COMPLAINT.value: "src.domain.models.complaint:Complaint",
        AssignedEntityType.NEAR_MISS.value: "src.domain.models.near_miss:NearMiss",
    }

    if entity_type not in entity_models:
        raise BadRequestError(f"Invalid entity type: {entity_type}")

    # Import the model dynamically
    model_path = entity_models[entity_type]
    module_path, class_name = model_path.split(":")
    module = __import__(module_path, fromlist=[class_name])
    model_class = getattr(module, class_name)

    # Check if entity exists
    query = select(model_class).where(model_class.id == entity_id)
    result = await db.execute(query)
    entity = result.scalar_one_or_none()

    if not entity:
        raise NotFoundError(f"{entity_type.replace('_', ' ').title()} with ID {entity_id} not found")


@router.post(
    "",
    response_model=InvestigationRunResponse,
    status_code=201,
    include_in_schema=False,
)
@router.post("/", response_model=InvestigationRunResponse, status_code=201)
async def create_investigation(
    request: Request,
    investigation_data: InvestigationRunCreate,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("investigation:create"))],
):
    """Create a new investigation run.

    Requires authentication and validates that:
    - Template exists
    - Assigned entity type is valid
    - Assigned entity exists

    Returns 400 for invalid entity type, 404 for missing template or entity.
    """
    request_id = request.headers.get("X-Request-ID", "N/A")

    # Validate template exists, create default if missing
    template_query = select(InvestigationTemplate).where(InvestigationTemplate.id == investigation_data.template_id)
    template_result = await db.execute(template_query)
    template = template_result.scalar_one_or_none()

    if not template:
        # Auto-create a default template if template_id is 1 and doesn't exist
        if investigation_data.template_id == 1:
            default_template = InvestigationTemplate(
                id=1,
                name="Default Investigation Template",
                description="Standard investigation template for incidents, RTAs, and complaints",
                version="1.0",
                is_active=True,
                structure={
                    "sections": [
                        {
                            "id": "rca",
                            "title": "Root Cause Analysis",
                            "fields": [
                                {
                                    "id": "problem_statement",
                                    "type": "text",
                                    "required": True,
                                },
                                {"id": "root_cause", "type": "text", "required": True},
                                {
                                    "id": "contributing_factors",
                                    "type": "array",
                                    "required": False,
                                },
                                {
                                    "id": "corrective_actions",
                                    "type": "array",
                                    "required": True,
                                },
                            ],
                        }
                    ]
                },
                applicable_entity_types=[
                    "road_traffic_collision",
                    "reporting_incident",
                    "complaint",
                    "near_miss",
                ],
                created_by_id=current_user.id,
                updated_by_id=current_user.id,
            )
            db.add(default_template)
            await db.commit()
            await db.refresh(default_template)
            template = default_template
        else:
            raise NotFoundError(f"Investigation template with ID {investigation_data.template_id} not found")

    # Validate assigned entity exists
    await validate_assigned_entity(
        investigation_data.assigned_entity_type,
        investigation_data.assigned_entity_id,
        db,
        request_id,
    )

    # Generate reference number
    from src.services.reference_number import ReferenceNumberService

    reference_number = await ReferenceNumberService.generate(db, "investigation", InvestigationRun)

    # Create investigation run
    investigation = InvestigationRun(
        template_id=investigation_data.template_id,
        assigned_entity_type=AssignedEntityType(investigation_data.assigned_entity_type),
        assigned_entity_id=investigation_data.assigned_entity_id,
        title=investigation_data.title,
        description=investigation_data.description,
        status=InvestigationStatus(investigation_data.status),
        data=investigation_data.data,
        reference_number=reference_number,
        tenant_id=current_user.tenant_id,
        created_by_id=current_user.id,
        updated_by_id=current_user.id,
    )

    db.add(investigation)
    await db.commit()
    await db.refresh(investigation)

    return investigation


def _revision_event_value(value: Any) -> Any:
    """Coerce an ORM attribute into a value the JSON revision-event columns accept."""
    if value is None or isinstance(value, (bool, int, float, str, list, dict)):
        return value
    if hasattr(value, "value"):
        return value.value
    return str(value)


async def _actor_names_for_events(
    db: AsyncSession,
    events: "list[InvestigationRevisionEvent]",
) -> dict[int, str]:
    """Resolve actor_id -> display name for a page of revision events."""
    actor_ids = {e.actor_id for e in events if e.actor_id is not None}
    if not actor_ids:
        return {}
    result = await db.execute(select(User).where(User.id.in_(actor_ids)))
    return {user.id: (user.full_name.strip() or user.email) for user in result.scalars().all()}


@router.get("/{investigation_id:int}/timeline", response_model=InvestigationTimelineResponse)
async def get_investigation_timeline(
    investigation_id: int,
    db: DbSession,
    current_user: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    event_type: Optional[str] = Query(None),
):
    """List revision events for an investigation (deterministic ordering)."""
    await _get_investigation_or_404(investigation_id, db, current_user)

    query = select(InvestigationRevisionEvent).where(InvestigationRevisionEvent.investigation_id == investigation_id)
    if event_type:
        query = query.where(InvestigationRevisionEvent.event_type == event_type)

    count_query = select(func.count(InvestigationRevisionEvent.id)).where(
        InvestigationRevisionEvent.investigation_id == investigation_id
    )
    if event_type:
        count_query = count_query.where(InvestigationRevisionEvent.event_type == event_type)
    total = await db.scalar(count_query) or 0
    query = query.order_by(InvestigationRevisionEvent.created_at.desc(), InvestigationRevisionEvent.id.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    events = result.scalars().all()
    actor_names = await _actor_names_for_events(db, list(events))

    return {
        "items": [
            {
                "id": e.id,
                "event_type": e.event_type,
                "field_path": e.field_path,
                "old_value": (
                    e.old_value
                    if isinstance(e.old_value, str)
                    else (str(e.old_value) if e.old_value is not None else None)
                ),
                "new_value": (
                    e.new_value
                    if isinstance(e.new_value, str)
                    else (str(e.new_value) if e.new_value is not None else None)
                ),
                "actor_id": e.actor_id,
                "actor_name": actor_names.get(e.actor_id) if e.actor_id is not None else None,
                "event_metadata": e.event_metadata,
                "version": e.version,
                "created_at": e.created_at,
            }
            for e in events
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": math.ceil(total / page_size) if total else 1,
        "investigation_id": investigation_id,
    }


class ManualTimelineEntryRequest(BaseModel):
    """Investigator-authored append-only timeline note."""

    content: str = Field(..., min_length=1, max_length=5000)


@router.post(
    "/{investigation_id:int}/timeline",
    response_model=dict,
    status_code=201,
)
async def add_manual_timeline_entry(
    investigation_id: int,
    payload: ManualTimelineEntryRequest,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("investigation:update"))],
):
    """Append a MANUAL_ENTRY revision event (system audit events remain immutable)."""
    investigation = await _get_investigation_or_404(investigation_id, db, current_user)
    event = await InvestigationService.create_revision_event(
        db=db,
        investigation=investigation,
        event_type="MANUAL_ENTRY",
        actor_id=current_user.id,
        field_path="timeline.manual",
        new_value=payload.content.strip(),
        metadata={"source": "manual_timeline"},
    )
    await db.commit()
    await db.refresh(event)
    return {
        "id": event.id,
        "event_type": event.event_type,
        "field_path": event.field_path,
        "new_value": event.new_value if isinstance(event.new_value, str) else str(event.new_value),
        "actor_id": event.actor_id,
        "created_at": event.created_at.isoformat() if event.created_at else None,
    }


class CustomerPackOmitRequest(BaseModel):
    """Request or revoke omit of a report section from customer packs."""

    section_id: str = Field(..., min_length=1, max_length=100)
    omit_requested: bool = True
    reason: Optional[str] = Field(None, max_length=2000)


class CustomerPackOmitApproveRequest(BaseModel):
    """Approve a pending customer-pack section omit (RBAC)."""

    section_id: str = Field(..., min_length=1, max_length=100)
    reason: Optional[str] = Field(None, max_length=2000)


@router.post("/{investigation_id:int}/customer-pack-omit")
async def request_customer_pack_omit(
    investigation_id: int,
    payload: CustomerPackOmitRequest,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("investigation:update"))],
):
    """Request (or revoke) omit of a section from customer packs. Approval required to hide."""
    investigation = await _get_investigation_or_404(investigation_id, db, current_user)
    if payload.omit_requested and not (payload.reason or "").strip():
        raise BadRequestError("Reason is required when requesting customer-pack omit")
    meta = await InvestigationService.set_customer_pack_omit(
        db,
        investigation=investigation,
        section_id=payload.section_id.strip(),
        omit_requested=payload.omit_requested,
        reason=(payload.reason or "").strip() or None,
        actor_id=current_user.id,
        approve=False,
    )
    return {
        "investigation_id": investigation_id,
        "section_id": payload.section_id.strip(),
        "visibility": meta,
        "customer_pack_visibility": InvestigationService.get_customer_pack_visibility(investigation),
    }


@router.post("/{investigation_id:int}/customer-pack-omit/approve")
async def approve_customer_pack_omit(
    investigation_id: int,
    payload: CustomerPackOmitApproveRequest,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("investigation:approve_customer_omit"))],
):
    """Approve a pending section omit (H&S Advisor / Admin)."""
    investigation = await _get_investigation_or_404(investigation_id, db, current_user)
    meta = await InvestigationService.set_customer_pack_omit(
        db,
        investigation=investigation,
        section_id=payload.section_id.strip(),
        omit_requested=True,
        reason=(payload.reason or "").strip() or None,
        actor_id=current_user.id,
        approve=True,
        approver_id=current_user.id,
    )
    return {
        "investigation_id": investigation_id,
        "section_id": payload.section_id.strip(),
        "visibility": meta,
        "customer_pack_visibility": InvestigationService.get_customer_pack_visibility(investigation),
    }


@router.get("/{investigation_id:int}/comments", response_model=InvestigationCommentsResponse)
async def get_investigation_comments(
    investigation_id: int,
    db: DbSession,
    current_user: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    include_deleted: bool = Query(False),
):
    """List investigation comments with optional deleted visibility."""
    tenant_id = require_tenant_id(getattr(current_user, "tenant_id", None))
    await _get_investigation_or_404(investigation_id, db, current_user)

    if include_deleted:
        has_permission = getattr(current_user, "has_permission", None)
        can_read_deleted = callable(has_permission) and has_permission("investigations:comments:read_deleted")
        if not getattr(current_user, "is_superuser", False) and not can_read_deleted:
            raise NotFoundError(f"Investigation with ID {investigation_id} not found")

    query = select(
        InvestigationComment.id,
        InvestigationComment.investigation_id,
        InvestigationComment.content,
        InvestigationComment.author_id,
        InvestigationComment.created_at,
        InvestigationComment.deleted_at,
        InvestigationComment.section_id,
        InvestigationComment.field_id,
        InvestigationComment.parent_comment_id,
    ).where(InvestigationComment.investigation_id == investigation_id)
    query = query.where(InvestigationComment.tenant_id == tenant_id)
    if not include_deleted:
        query = query.where(InvestigationComment.deleted_at.is_(None))

    count_query = select(func.count(InvestigationComment.id)).where(
        InvestigationComment.investigation_id == investigation_id,
        InvestigationComment.tenant_id == tenant_id,
    )
    if not include_deleted:
        count_query = count_query.where(InvestigationComment.deleted_at.is_(None))
    total = await db.scalar(count_query) or 0
    query = query.order_by(InvestigationComment.created_at.desc(), InvestigationComment.id.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    comments = result.mappings().all()

    return {
        "items": [
            {
                "id": c["id"],
                "investigation_id": c["investigation_id"],
                "content": c["content"],
                "author_id": c["author_id"],
                "created_at": c["created_at"],
                "section_id": c["section_id"],
                "field_id": c["field_id"],
                "parent_comment_id": c["parent_comment_id"],
                "deleted_at": c["deleted_at"],
            }
            for c in comments
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": math.ceil(total / page_size) if total else 1,
        "investigation_id": investigation_id,
    }


@router.get("/{investigation_id:int}/packs", response_model=InvestigationPacksResponse)
async def get_investigation_packs(
    investigation_id: int,
    db: DbSession,
    current_user: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """List customer pack metadata without exposing full content payloads."""
    await _get_investigation_or_404(investigation_id, db, current_user)

    query = select(InvestigationCustomerPack).where(InvestigationCustomerPack.investigation_id == investigation_id)
    count_query = select(func.count(InvestigationCustomerPack.id)).where(
        InvestigationCustomerPack.investigation_id == investigation_id
    )
    total = await db.scalar(count_query) or 0
    query = query.order_by(InvestigationCustomerPack.created_at.desc(), InvestigationCustomerPack.id.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    packs = result.scalars().all()

    return {
        "items": [
            {
                "id": p.id,
                "investigation_id": p.investigation_id,
                "pack_uuid": p.pack_uuid,
                "audience": p.audience.value if hasattr(p.audience, "value") else str(p.audience),
                "generated_at": p.created_at,
                "checksum_sha256": p.checksum_sha256,
            }
            for p in packs
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": math.ceil(total / page_size) if total else 1,
        "investigation_id": investigation_id,
    }


@router.get(
    "/{investigation_id:int}/packs/{pack_id:int}/pdf",
    response_class=Response,
    responses={200: {"content": {"application/pdf": {}}, "description": "Branded customer pack PDF"}},
)
async def download_customer_pack_pdf(
    investigation_id: int,
    pack_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> Response:
    """Render a previously generated customer pack as a branded PDF (PX-143).

    Renders the stored, already-redacted pack payload — this endpoint never
    re-reads the investigation, so it cannot leak content the pack omitted.
    """
    from src.domain.models.tenant import Tenant
    from src.domain.services.investigation_pack_pdf import InvestigationPackPdfService

    investigation = await _get_investigation_or_404(investigation_id, db, current_user)

    result = await db.execute(
        select(InvestigationCustomerPack).where(
            InvestigationCustomerPack.id == pack_id,
            InvestigationCustomerPack.investigation_id == investigation_id,
        )
    )
    pack = result.scalar_one_or_none()
    if pack is None:
        raise NotFoundError(f"Customer pack {pack_id} not found for investigation {investigation_id}")

    organisation_name: Optional[str] = None
    primary_color: Optional[str] = None
    if investigation.tenant_id is not None:
        tenant = await db.scalar(select(Tenant).where(Tenant.id == investigation.tenant_id))
        if tenant is not None:
            organisation_name = tenant.name
            primary_color = tenant.primary_color

    payload = {
        "pack_uuid": pack.pack_uuid,
        "audience": pack.audience.value if hasattr(pack.audience, "value") else str(pack.audience),
        "investigation_reference": investigation.reference_number,
        "investigation_title": investigation.title,
        "generated_at": pack.created_at.isoformat() if pack.created_at else None,
        "checksum_sha256": pack.checksum_sha256,
        "content": pack.content,
        "redaction_log": pack.redaction_log,
        "included_assets": pack.included_assets,
    }

    service = InvestigationPackPdfService()
    try:
        pdf_bytes = service.build_pdf_bytes(
            payload,
            organisation_name=organisation_name,
            primary_color=primary_color,
        )
    except RuntimeError as exc:
        # Fail loudly rather than handing back an empty or half-rendered file.
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    filename = service.pdf_filename(investigation.reference_number, pack.pack_uuid)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get(
    "/{investigation_id:int}/closure-validation",
    response_model=InvestigationClosureValidationResponse,
)
async def get_closure_validation(
    investigation_id: int,
    db: DbSession,
    current_user: CurrentUser,
):
    """Return closure-validation state for a given investigation."""
    from src.domain.services.investigation_closure_helpers import open_work_to_payload

    investigation = await _get_investigation_or_404(investigation_id, db, current_user)

    close_reasons, open_work, missing_items = await _collect_readiness_reasons(
        db,
        investigation=investigation,
        investigation_id=investigation_id,
        current_user=current_user,
        gate="close",
    )
    complete_reasons, _complete_open_work, complete_missing = await _collect_readiness_reasons(
        db,
        investigation=investigation,
        investigation_id=investigation_id,
        current_user=current_user,
        gate="complete",
    )

    # Merge missing_items from both probes (dedupe by path).
    merged_missing: list = []
    seen_paths: set[str] = set()
    for item in [*missing_items, *complete_missing]:
        path = getattr(item, "path", None) or ""
        if path in seen_paths:
            continue
        seen_paths.add(path)
        merged_missing.append(item)

    return {
        "can_close": len(close_reasons) == 0,
        "can_complete": len(complete_reasons) == 0,
        "reasons": close_reasons,
        "completion_reasons": complete_reasons,
        "open_work": open_work_to_payload(open_work),
        "open_work_count": len(open_work),
        "missing_items": _missing_items_to_payload_from_list(merged_missing),
    }


@router.get("", response_model=InvestigationRunListResponse, include_in_schema=False)
@router.get("/", response_model=InvestigationRunListResponse)
async def list_investigations(
    request: Request,
    db: DbSession,
    current_user: CurrentUser,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(10, ge=1, le=100, description="Items per page"),
    entity_type: Optional[str] = Query(None, description="Filter by entity type"),
    entity_id: Optional[int] = Query(None, description="Filter by entity ID"),
    status: Optional[str] = Query(None, description="Filter by status"),
    q: Optional[str] = Query(
        None,
        description="Smart search across reference/title/description, comments, actions/CAPA, people",
    ),
):
    """List investigation runs with pagination.

    Returns investigations in deterministic order (created_at DESC, id ASC).
    Can filter by entity_type, entity_id, status, and optional smart-search `q`.
    """
    request_id = request.headers.get("X-Request-ID", "N/A")

    # Build query, scoped to the caller's tenant. Fail-closed and unconditional:
    # the register is tenant-local (see _assert_investigation_tenant), and a
    # caller with no tenant must match nothing rather than everything.
    tenant_id = require_tenant_id(getattr(current_user, "tenant_id", None))
    query = apply_tenant_filter(select(InvestigationRun), InvestigationRun, tenant_id)

    # Apply filters
    if entity_type is not None:
        try:
            entity_type_enum = AssignedEntityType(entity_type)
            query = query.where(InvestigationRun.assigned_entity_type == entity_type_enum)
        except ValueError:
            raise BadRequestError(f"Invalid entity type: {entity_type}")

    if entity_id is not None:
        query = query.where(InvestigationRun.assigned_entity_id == entity_id)

    if status is not None:
        try:
            status_enum = InvestigationStatus(status)
            query = query.where(InvestigationRun.status == status_enum)
        except ValueError:
            raise BadRequestError(f"Invalid status: {status}")

    if q and q.strip():
        query = InvestigationService.apply_smart_search_filter(query, q.strip())

    # Deterministic ordering: created_at DESC, id ASC
    query = query.order_by(InvestigationRun.created_at.desc(), InvestigationRun.id.asc())

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total = await db.scalar(count_query)

    # Apply pagination
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)

    # Execute query
    result = await db.execute(query)
    investigations = result.scalars().all()

    total_pages = math.ceil(total / page_size) if total and total > 0 else 1

    return InvestigationRunListResponse(
        items=[InvestigationRunResponse.model_validate(inv) for inv in investigations],
        total=total or 0,
        page=page,
        page_size=page_size,
        pages=total_pages,
    )


@router.get("/{investigation_id:int}", response_model=InvestigationRunResponse)
async def get_investigation(
    request: Request,
    investigation_id: int,
    db: DbSession,
    current_user: CurrentUser,
):
    """Get a specific investigation run by ID."""
    request_id = request.headers.get("X-Request-ID", "N/A")

    investigation = await _load_investigation_or_404(investigation_id, db)
    tenant_id = _assert_investigation_tenant(investigation, current_user)
    return await _investigation_to_response(db, investigation, tenant_id=tenant_id)


@router.post("/{investigation_id:int}/capa", response_model=CAPAResponse, status_code=201)
async def create_capa_for_investigation(
    investigation_id: int,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("investigation:update"))],
    body: CreateInvestigationCapaRequest | None = None,
):
    """Create a CAPA action linked to an investigation (idempotent if already linked)."""
    from src.domain.services.capa_service import CAPAService

    tenant_id = require_tenant_id(getattr(current_user, "tenant_id", None))
    payload = body if body is not None else CreateInvestigationCapaRequest.model_validate({})
    svc = CAPAService(db)
    try:
        capa = await svc.create_capa_for_investigation(
            investigation_id,
            user_id=current_user.id,
            tenant_id=tenant_id,
            title=payload.title,
            description=payload.description,
            assignee_id=payload.assignee_id,
            assignee_email=payload.assignee_email,
            assignee_name=payload.assignee_name,
            due_date=payload.due_date,
            priority=payload.priority,
        )
    except LookupError as exc:
        raise NotFoundError(str(exc)) from exc
    except ValueError as exc:
        raise BadRequestError(str(exc)) from exc
    return CAPAResponse.model_validate(capa)


@router.patch("/{investigation_id:int}", response_model=InvestigationRunResponse)
async def update_investigation(  # noqa: C901 - completion/close gates + revision events
    request: Request,
    investigation_id: int,
    investigation_data: InvestigationRunUpdate,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("investigation:update"))],
):
    """Update an investigation run.

    Only provided fields will be updated (partial update).
    Can update RCA section fields via the data field.
    """
    request_id = request.headers.get("X-Request-ID", "N/A")

    # Get existing investigation. The tenant gate runs before anything is read
    # off the record or written to it, so a refused edit leaves it untouched.
    investigation = await _load_investigation_or_404(investigation_id, db)
    _assert_investigation_tenant(investigation, current_user)

    update_data = investigation_data.model_dump(exclude_unset=True)
    override_meta: dict | None = None
    new_status = update_data.get("status")
    if new_status in {"completed", "closed"}:
        gate = "complete" if new_status == "completed" else "close"
        override_meta = await _ensure_investigation_ready_for_status(
            db,
            investigation=investigation,
            investigation_id=investigation_id,
            current_user=current_user,
            gate=gate,
            allow_open_work_override=bool(update_data.get("closure_override")),
            override_reason=update_data.get("closure_override_reason"),
        )

    previous_values = {field: getattr(investigation, field, None) for field in update_data}

    # Update fields (closure override fields are gate-only, not persisted on the run).
    for field, value in update_data.items():
        if field in {"closure_override", "closure_override_reason"}:
            continue
        if field == "status" and value is not None:
            setattr(investigation, field, InvestigationStatus(value))
        elif field == "level" and value is not None:
            from src.domain.models.investigation import InvestigationLevel

            try:
                setattr(investigation, field, InvestigationLevel(str(value).lower()))
            except ValueError as exc:
                raise BadRequestError(f"Invalid investigation level: {value}") from exc
        else:
            setattr(investigation, field, value)

    investigation.updated_by_id = current_user.id

    # Update status timestamps (naive UTC — completed_at/closed_at columns are TIMESTAMP WITHOUT TIME ZONE)
    if investigation_data.status:
        active_statuses = {"in_progress", "under_review", "completed", "closed"}
        if investigation_data.status in active_statuses and not investigation.started_at:
            setattr(investigation, "started_at", datetime.utcnow())
        if investigation_data.status == "completed" and not investigation.completed_at:
            setattr(investigation, "completed_at", datetime.utcnow())
        elif investigation_data.status == "closed" and not investigation.closed_at:
            setattr(investigation, "closed_at", datetime.utcnow())
        elif investigation_data.status != "closed" and investigation.closed_at:
            # Reopening: the closure stamp must not outlive the closed status,
            # or a reopened run still reads as closed to every report.
            setattr(investigation, "closed_at", None)

    # Promote lessons narrative onto the linked case when present and case field empty.
    raw_data = update_data.get("data") if "data" in update_data else investigation.data
    lessons_payload = raw_data if isinstance(raw_data, dict) else None
    if lessons_payload is not None or update_data.get("status") == "closed":
        from src.domain.services.lessons_learnt_promote import extract_lessons_text, promote_lessons_to_case

        if lessons_payload is None and isinstance(investigation.data, dict):
            lessons_payload = investigation.data
        lessons_text = extract_lessons_text(lessons_payload)
        if lessons_text and investigation.assigned_entity_type is not None:
            entity_type = (
                investigation.assigned_entity_type.value
                if hasattr(investigation.assigned_entity_type, "value")
                else str(investigation.assigned_entity_type)
            )
            await promote_lessons_to_case(
                db,
                entity_type=entity_type,
                entity_id=investigation.assigned_entity_id,
                lessons_text=lessons_text,
                overwrite=False,
            )

    for field, previous in previous_values.items():
        if field in {"closure_override", "closure_override_reason"}:
            continue
        before = _revision_event_value(previous)
        after = _revision_event_value(getattr(investigation, field, None))
        if before == after:
            continue
        # JSON blobs (notably `data`) are recorded by field_path only: the full
        # before/after would be stringified into the timeline body by GET /timeline.
        structured = isinstance(before, (list, dict)) or isinstance(after, (list, dict))
        event_metadata: dict = {"request_id": request_id, "source": "investigation_patch"}
        if field == "status" and override_meta:
            event_metadata.update(override_meta)
        await InvestigationService.create_revision_event(
            db=db,
            investigation=investigation,
            event_type="STATUS_CHANGED" if field == "status" else "DATA_UPDATED",
            actor_id=current_user.id,
            field_path=field,
            old_value=None if structured else before,
            new_value=None if structured else after,
            metadata=event_metadata,
        )

    if override_meta and "status" not in update_data:
        await InvestigationService.create_revision_event(
            db=db,
            investigation=investigation,
            event_type="CLOSURE_OVERRIDE",
            actor_id=current_user.id,
            field_path="closure",
            old_value=None,
            new_value=override_meta.get("closure_override_reason"),
            metadata={"request_id": request_id, "source": "investigation_patch", **override_meta},
        )

    await db.commit()
    await db.refresh(investigation)

    tenant_id = require_tenant_id(getattr(current_user, "tenant_id", None))
    return await _investigation_to_response(db, investigation, tenant_id=tenant_id)


# === Stage 2 Endpoints ===


@router.post("/from-record", response_model=InvestigationRunResponse, status_code=201)
async def create_investigation_from_record(
    request: Request,
    request_body: CreateFromRecordRequest,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("investigation:create"))],
):
    """Create an investigation from a source record (Near Miss, Complaint, RTA).

    Request Body (JSON):
    - source_type: near_miss, road_traffic_collision, complaint, reporting_incident
    - source_id: ID of the source record
    - title: Investigation title
    - template_id: Optional template ID (default: 1)

    Performs deterministic prefill using Mapping Contract v1:
    - Creates immutable source snapshot
    - Maps fields with explicit reason codes
    - Links existing evidence assets
    - Determines investigation level from source severity

    Returns:
    - 201: Created investigation with prefilled data
    - 400: VALIDATION_ERROR - Invalid request body
    - 404: SOURCE_NOT_FOUND - Source record doesn't exist
    - 409: INV_ALREADY_EXISTS - Investigation already exists for this source

    Error Response Format:
    {
        "error_code": "ERROR_CODE",
        "message": "Human-readable message",
        "details": {...},
        "request_id": "..."
    }
    """
    from src.domain.services.investigation_service import InvestigationService
    from src.services.reference_number import ReferenceNumberService

    request_id = request.headers.get("X-Request-ID", "N/A")

    # Extract values from request body
    source_type = request_body.source_type
    source_id = request_body.source_id
    title = request_body.title
    template_id = request_body.template_id

    # Parse source type enum
    source_type_enum = AssignedEntityType(source_type)

    tenant_id = require_tenant_id(getattr(current_user, "tenant_id", None))

    # === DUPLICATE CHECK: Return 409 if investigation already exists ===
    # Tenant-scoped: another tenant's investigation must never block this one.
    existing_query = (
        select(InvestigationRun)
        .where(
            InvestigationRun.assigned_entity_type == source_type_enum,
            InvestigationRun.assigned_entity_id == source_id,
            InvestigationRun.tenant_id == tenant_id,
        )
        .order_by(InvestigationRun.id.asc())
    )
    existing_result = await db.execute(existing_query)
    existing_investigation = existing_result.scalars().first()

    if existing_investigation:
        raise ConflictError(
            f"An investigation already exists for this {source_type.replace('_', ' ')}",
            code="INV_ALREADY_EXISTS",
            details={
                "existing_investigation_id": int(existing_investigation.id),
                "existing_reference_number": existing_investigation.reference_number,
                "source_type": source_type,
                "source_id": source_id,
            },
        )

    # Get source record (tenant-scoped — never investigate another tenant's record)
    record, error = await InvestigationService.get_source_record(db, source_type_enum, source_id, tenant_id=tenant_id)
    if error:
        raise NotFoundError(error)

    # Create source snapshot (immutable)
    source_snapshot = InvestigationService.create_source_snapshot(record, source_type_enum)

    # Map source to investigation data
    data, mapping_log, level = InvestigationService.map_source_to_investigation(record, source_type_enum)

    # Validate template exists or create default
    template_query = select(InvestigationTemplate).where(InvestigationTemplate.id == template_id)
    template_result = await db.execute(template_query)
    template = template_result.scalar_one_or_none()

    if not template and template_id == 1:
        # Auto-create default template
        template = InvestigationTemplate(
            id=1,
            name="Investigation Report Template v2.1",
            description="Standard investigation template based on Plantexpand Template v2.0",
            version="2.1",
            is_active=True,
            structure={"sections": []},
            applicable_entity_types=[e.value for e in AssignedEntityType],
            created_by_id=current_user.id,
            updated_by_id=current_user.id,
        )
        db.add(template)
        await db.commit()
        await db.refresh(template)

    if not template:
        raise NotFoundError(f"Template {template_id} not found")

    # Generate reference number
    reference_number = await ReferenceNumberService.generate(db, "investigation", InvestigationRun)

    # Create investigation
    from src.domain.models.investigation import InvestigationLevel as InvLevel

    investigation = InvestigationRun(
        template_id=template.id,
        assigned_entity_type=source_type_enum,
        assigned_entity_id=source_id,
        title=title,
        status=InvestigationStatus.DRAFT,
        level=level,
        data=data,
        source_schema_version="1.0",
        source_snapshot=source_snapshot,
        mapping_log=mapping_log,
        version=1,
        reference_number=reference_number,
        tenant_id=tenant_id,
        created_by_id=current_user.id,
        updated_by_id=current_user.id,
    )

    db.add(investigation)
    await db.commit()
    await db.refresh(investigation)

    # Create revision event
    await InvestigationService.create_revision_event(
        db=db,
        investigation=investigation,
        event_type="CREATED",
        actor_id=current_user.id,
        metadata={
            "source_type": source_type,
            "source_id": source_id,
            "mapping_log_count": len(mapping_log),
        },
    )

    # Link source evidence assets to investigation
    evidence_assets = await InvestigationService.get_source_evidence_assets(db, source_type_enum, source_id)
    for asset in evidence_assets:
        asset.linked_investigation_id = investigation.id

    await db.commit()
    await db.refresh(investigation)

    return investigation


# Source registers that can be turned into an investigation. Keyed by AssignedEntityType value.
_SOURCE_RECORD_MODELS: dict[str, str] = {
    AssignedEntityType.ROAD_TRAFFIC_COLLISION.value: "src.domain.models.rta:RoadTrafficCollision",
    AssignedEntityType.REPORTING_INCIDENT.value: "src.domain.models.incident:Incident",
    AssignedEntityType.COMPLAINT.value: "src.domain.models.complaint:Complaint",
    AssignedEntityType.NEAR_MISS.value: "src.domain.models.near_miss:NearMiss",
}


def _resolve_source_record_model(source_type: str) -> Optional[Any]:
    """Import the ORM model backing a source register, or None when unsupported."""
    model_path = _SOURCE_RECORD_MODELS.get(source_type)
    if not model_path:
        return None
    module_path, class_name = model_path.split(":")
    module = __import__(module_path, fromlist=[class_name])
    return getattr(module, class_name)


class SourceCoverageItem(BaseModel):
    """Investigation coverage for a single source register."""

    source_type: str
    total: int
    investigated: int
    not_investigated: int


class SourceCoverageResponse(BaseModel):
    """How much of each source register actually has an investigation attached."""

    items: list[SourceCoverageItem]
    total: int
    investigated: int
    not_investigated: int


@router.get("/source-coverage", response_model=SourceCoverageResponse)
async def get_source_coverage(
    db: DbSession,
    current_user: CurrentUser,
) -> SourceCoverageResponse:
    """Count source records with and without an investigation, per register.

    Exists so the Investigations list can state plainly how many real incidents
    (and other source records) have no investigation, instead of letting a short
    list of test investigations imply the register is covered.
    """
    tenant_id = require_tenant_id(getattr(current_user, "tenant_id", None))

    items: list[SourceCoverageItem] = []
    for source_type in _SOURCE_RECORD_MODELS:
        model_class = _resolve_source_record_model(source_type)
        if model_class is None:
            continue
        entity_type = AssignedEntityType(source_type)

        total = (
            await db.scalar(select(func.count()).select_from(model_class).where(model_class.tenant_id == tenant_id))
        ) or 0

        investigated_ids = select(InvestigationRun.assigned_entity_id).where(
            InvestigationRun.assigned_entity_type == entity_type,
            InvestigationRun.tenant_id == tenant_id,
            InvestigationRun.assigned_entity_id.isnot(None),
        )
        investigated = (
            await db.scalar(
                select(func.count())
                .select_from(model_class)
                .where(
                    model_class.tenant_id == tenant_id,
                    model_class.id.in_(investigated_ids),
                )
            )
        ) or 0

        items.append(
            SourceCoverageItem(
                source_type=source_type,
                total=int(total),
                investigated=int(investigated),
                not_investigated=max(int(total) - int(investigated), 0),
            )
        )

    return SourceCoverageResponse(
        items=items,
        total=sum(i.total for i in items),
        investigated=sum(i.investigated for i in items),
        not_investigated=sum(i.not_investigated for i in items),
    )


@router.get("/source-records", response_model=SourceRecordsResponse)
async def list_source_records(
    db: DbSession,
    current_user: CurrentUser,
    source_type: str = Query(
        ...,
        description="Source type (near_miss, road_traffic_collision, complaint, reporting_incident)",
    ),
    q: Optional[str] = Query(None, description="Search query (searches title, reference)"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Page size"),
):
    """List source records available for investigation creation.

    Returns records of the specified type with investigation status.
    Records that already have an investigation are marked with investigation_id.

    Query Parameters:
    - source_type: Required. One of: near_miss, road_traffic_collision, complaint, reporting_incident
    - q: Optional search query
    - page: Page number (default: 1)
    - page_size: Page size (default: 20, max: 100)

    Response includes:
    - source_id: Record ID
    - display_label: Human-readable label for dropdown
    - reference_number: Record reference
    - status: Current status
    - created_at: Creation date
    - investigation_id: If already investigated, the investigation ID (null otherwise)
    - investigation_reference: If investigated, the investigation reference
    """
    request_id = "N/A"

    # Validate source type
    try:
        source_type_enum = AssignedEntityType(source_type)
    except ValueError:
        raise BadRequestError(f"Invalid source type: {source_type}")

    model_class = _resolve_source_record_model(source_type)
    if model_class is None:
        raise BadRequestError(f"Source type {source_type} is not supported")

    tenant_id = require_tenant_id(getattr(current_user, "tenant_id", None))

    # Build base query for source records (tenant-scoped)
    base_query = select(model_class).where(model_class.tenant_id == tenant_id)

    # Apply search filter if provided
    if q:
        search_term = f"%{q}%"
        # Try to apply search on common fields
        search_conditions = []
        if hasattr(model_class, "title"):
            search_conditions.append(model_class.title.ilike(search_term))
        if hasattr(model_class, "reference_number"):
            search_conditions.append(model_class.reference_number.ilike(search_term))
        if hasattr(model_class, "description"):
            search_conditions.append(model_class.description.ilike(search_term))
        if search_conditions:
            from sqlalchemy import or_

            base_query = base_query.where(or_(*search_conditions))

    # Count total records
    count_query = select(func.count()).select_from(base_query.subquery())
    total = await db.scalar(count_query) or 0

    # Apply deterministic ordering and pagination
    base_query = base_query.order_by(model_class.created_at.desc(), model_class.id.asc())
    offset = (page - 1) * page_size
    base_query = base_query.offset(offset).limit(page_size)

    # Execute query
    result = await db.execute(base_query)
    records = list(result.scalars().all())

    # Get existing investigations for these source records
    source_ids = [r.id for r in records]
    inv_query = select(InvestigationRun).where(
        InvestigationRun.assigned_entity_type == source_type_enum,
        InvestigationRun.assigned_entity_id.in_(source_ids),
        InvestigationRun.tenant_id == tenant_id,
    )
    inv_result = await db.execute(inv_query)
    existing_investigations = {inv.assigned_entity_id: inv for inv in inv_result.scalars().all()}

    # Build response items
    items = []
    for record in records:
        # Get reference number
        ref_num = getattr(record, "reference_number", f"REF-{record.id}")

        # Get status (safe enum value)
        status = getattr(record, "status", "unknown")
        if hasattr(status, "value"):
            status = status.value

        # Format created_at as date only (no PII)
        created_date = record.created_at.strftime("%Y-%m-%d") if record.created_at else "Unknown"

        # === SAFE DISPLAY LABEL (NO PII) ===
        # Format: "{reference_number} — {status} — {date}"
        # This avoids exposing free-text fields that may contain PII
        display_label = f"{ref_num} — {status.upper()} — {created_date}"

        # Check if already investigated
        existing_inv = existing_investigations.get(record.id)

        items.append(
            SourceRecordItem(
                source_id=record.id,
                display_label=display_label,
                reference_number=ref_num,
                status=status,
                created_at=record.created_at,
                investigation_id=int(existing_inv.id) if existing_inv else None,
                investigation_reference=(str(existing_inv.reference_number) if existing_inv else None),
            )
        )

    total_pages = math.ceil(total / page_size) if total > 0 else 1

    return SourceRecordsResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=total_pages,
        source_type=source_type,
    )


@router.patch("/{investigation_id:int}/autosave", response_model=InvestigationRunResponse)
async def autosave_investigation(
    investigation_id: int,
    data: dict,
    version: int,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("investigation:update"))],
):
    """Autosave investigation data with optimistic locking.

    Uses version field to prevent concurrent edit conflicts.
    Returns 409 Conflict if version mismatch.
    """
    from src.domain.services.investigation_service import InvestigationService

    request_id = "N/A"

    # Get investigation with version check
    investigation = await _load_investigation_or_404(investigation_id, db)
    _assert_investigation_tenant(investigation, current_user)

    # Optimistic locking: check version
    if investigation.version != version:
        raise ConflictError("Investigation was modified by another user")

    # Store old data for revision event
    old_data = investigation.data

    # Update data and increment version
    investigation.data = data  # type: ignore[assignment]  # TYPE-IGNORE: SQLALCHEMY-1
    investigation.version += 1  # type: ignore[assignment]  # TYPE-IGNORE: SQLALCHEMY-1
    investigation.updated_by_id = current_user.id

    # Create revision event
    await InvestigationService.create_revision_event(
        db=db,
        investigation=investigation,
        event_type="DATA_UPDATED",
        actor_id=current_user.id,
        old_value=old_data,
        new_value=data,
    )

    await db.commit()
    await db.refresh(investigation)

    return investigation


class AddCommentRequest(BaseModel):
    """Request body for adding a comment to an investigation."""

    content: str = Field(..., min_length=1, max_length=10000)
    body: Optional[str] = Field(None, exclude=True)
    section_id: Optional[str] = None
    field_id: Optional[str] = None
    parent_comment_id: Optional[int] = None

    @model_validator(mode="before")
    @classmethod
    def accept_body_as_content(cls, data: Any) -> Any:
        """Accept 'body' as an alias for 'content' for backward compatibility."""
        if isinstance(data, dict) and "body" in data and "content" not in data:
            data["content"] = data.pop("body")
        return data


@router.post(
    "/{investigation_id:int}/comments",
    response_model=InvestigationCommentResponse,
    status_code=201,
)
async def add_comment(
    investigation_id: int,
    payload: AddCommentRequest,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("investigation:update"))],
):
    """Add an internal comment to an investigation.

    Comments are INTERNAL ONLY - never included in customer packs.
    Can be attached to specific sections/fields and support threading.
    """
    from src.domain.models.investigation import InvestigationComment
    from src.domain.services.investigation_service import InvestigationService

    request_id = "N/A"

    # Validate investigation exists within the caller's tenant scope. A caller
    # with no tenant learns nothing about the record, so that is refused before
    # it is even loaded. The record integrity check then keeps its own
    # write-specific reason — this route has to copy the run's tenant onto a new
    # row, so a run without one is a bad record rather than a bad caller — and
    # cross-tenant refuses under the shared code, where it used to answer 404.
    require_tenant_id(getattr(current_user, "tenant_id", None))
    investigation = await _load_investigation_or_404(investigation_id, db)
    if investigation.tenant_id is None:
        raise ValidationError(
            "tenant_id is required to create an investigation comment",
            details={"investigation_id": investigation.id},
        )
    _assert_investigation_tenant(investigation, current_user)
    if not _user_can_access_investigation(current_user, investigation):
        raise NotFoundError(f"Investigation with ID {investigation_id} not found")

    # Validate parent comment if provided
    if payload.parent_comment_id:
        parent_query = select(InvestigationComment).where(
            InvestigationComment.id == payload.parent_comment_id,
            InvestigationComment.investigation_id == investigation_id,
            InvestigationComment.deleted_at.is_(None),
        )
        parent_result = await db.execute(parent_query)
        parent_comment = parent_result.scalar_one_or_none()
        if not parent_comment:
            raise NotFoundError(f"Parent comment {payload.parent_comment_id} not found")

    # tenant_id is NOT NULL — inherit from parent investigation (never invent a default).
    if investigation.tenant_id is None:
        raise BadRequestError("Investigation is missing tenant_id; cannot create comment")

    comment = InvestigationComment(
        tenant_id=investigation.tenant_id,
        investigation_id=investigation_id,
        content=payload.content,
        section_id=payload.section_id,
        field_id=payload.field_id,
        parent_comment_id=payload.parent_comment_id,
        author_id=current_user.id,
    )

    db.add(comment)

    # Create revision event
    await InvestigationService.create_revision_event(
        db=db,
        investigation=investigation,
        event_type="COMMENT_ADDED",
        actor_id=current_user.id,
        metadata={
            "section_id": payload.section_id,
            "field_id": payload.field_id,
            "is_reply": payload.parent_comment_id is not None,
        },
    )

    await db.commit()
    await db.refresh(comment)

    return {
        "id": comment.id,
        "investigation_id": comment.investigation_id,
        "content": comment.content,
        "section_id": comment.section_id,
        "field_id": comment.field_id,
        "parent_comment_id": comment.parent_comment_id,
        "author_id": comment.author_id,
        "created_at": comment.created_at.isoformat() if comment.created_at else None,
    }


@router.post("/{investigation_id:int}/approve", response_model=InvestigationRunResponse)
async def approve_investigation(
    investigation_id: int,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("investigation:update"))],
    approved: bool = True,
    rejection_reason: Optional[str] = None,
):
    """Approve or reject an investigation.

    Moves investigation to COMPLETED (approved) or back to IN_PROGRESS (rejected).
    """
    from src.domain.services.investigation_service import InvestigationService

    request_id = "N/A"

    # Get investigation
    investigation = await _load_investigation_or_404(investigation_id, db)
    _assert_investigation_tenant(investigation, current_user)

    # Check status allows approval
    if investigation.status not in (
        InvestigationStatus.UNDER_REVIEW,
        InvestigationStatus.IN_PROGRESS,
    ):
        raise BadRequestError(f"Cannot approve investigation in status {investigation.status.value}")

    old_status = investigation.status

    if approved:
        investigation.status = InvestigationStatus.COMPLETED  # type: ignore[assignment]  # TYPE-IGNORE: SQLALCHEMY-1
        investigation.approved_at = datetime.now(timezone.utc)  # type: ignore[assignment]  # TYPE-IGNORE: SQLALCHEMY-1
        investigation.approved_by_id = current_user.id  # type: ignore[assignment]  # TYPE-IGNORE: SQLALCHEMY-1
        # completed_at is TIMESTAMP WITHOUT TIME ZONE — aware datetimes 500 via asyncpg
        investigation.completed_at = datetime.utcnow()  # type: ignore[assignment]  # TYPE-IGNORE: SQLALCHEMY-1
        investigation.rejection_reason = None  # type: ignore[assignment]  # TYPE-IGNORE: SQLALCHEMY-1
        event_type = "APPROVED"
    else:
        if not rejection_reason:
            raise BadRequestError("Rejection reason is required")
        investigation.status = InvestigationStatus.IN_PROGRESS
        investigation.rejection_reason = rejection_reason
        event_type = "REJECTED"

    investigation.updated_by_id = current_user.id
    investigation.version = (investigation.version or 0) + 1

    old_status_value = old_status.value if hasattr(old_status, "value") else str(old_status)
    new_status_value = (
        investigation.status.value if hasattr(investigation.status, "value") else str(investigation.status)
    )

    # Create revision event
    await InvestigationService.create_revision_event(
        db=db,
        investigation=investigation,
        event_type=event_type,
        actor_id=current_user.id,
        old_value={"status": old_status_value},
        new_value={"status": new_status_value},
        metadata={"rejection_reason": rejection_reason} if not approved else None,
    )

    await db.commit()
    await db.refresh(investigation)

    return investigation


@router.post(
    "/{investigation_id:int}/customer-pack",
    response_model=InvestigationPackGeneratedResponse,
)
async def generate_customer_pack(
    investigation_id: int,
    audience: str,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("investigation:update"))],
):
    """Generate a customer pack with audience-specific redaction.

    Audience options:
    - internal_customer: identities retained, internal comments excluded
    - external_customer: identities redacted, only external-allowed evidence

    Returns the generated pack with redaction log.
    """
    from src.domain.models.investigation import CustomerPackAudience
    from src.domain.services.investigation_service import InvestigationService

    request_id = "N/A"

    # Validate audience
    try:
        audience_enum = CustomerPackAudience(audience)
    except ValueError:
        raise BadRequestError(f"Invalid audience: {audience}")

    # Get investigation. A pack is the exportable copy of the record, so this is
    # a read of it and is gated exactly as the detail read is.
    investigation = await _load_investigation_or_404(investigation_id, db)
    _assert_investigation_tenant(investigation, current_user)

    pending = InvestigationService.pending_customer_omits(investigation)
    if pending:
        raise BadRequestError(
            "Customer pack cannot be generated while section omits are pending approval: " + ", ".join(pending)
        )

    # Get linked evidence assets
    from src.domain.models.evidence_asset import EvidenceAsset

    assets_query = select(EvidenceAsset).where(
        EvidenceAsset.linked_investigation_id == investigation_id,
        EvidenceAsset.deleted_at.is_(None),
    )
    assets_result = await db.execute(assets_query)
    evidence_assets = list(assets_result.scalars().all())

    # Generate pack with redaction
    content, redaction_log, included_assets = InvestigationService.generate_customer_pack(
        investigation=investigation,
        audience=audience_enum,
        evidence_assets=evidence_assets,
        generated_by_id=current_user.id,
        generated_by_role=getattr(current_user, "role", None),
    )

    # Create pack entity
    pack = InvestigationService.create_customer_pack_entity(
        investigation=investigation,
        audience=audience_enum,
        content=content,
        redaction_log=redaction_log,
        included_assets=included_assets,
        generated_by_id=current_user.id,
    )

    db.add(pack)

    # Create revision event
    await InvestigationService.create_revision_event(
        db=db,
        investigation=investigation,
        event_type="PACK_GENERATED",
        actor_id=current_user.id,
        metadata={
            "pack_uuid": pack.pack_uuid,
            "audience": audience,
            "redaction_count": len(redaction_log),
            "assets_included": sum(1 for a in included_assets if a["included"]),
            "assets_excluded": sum(1 for a in included_assets if not a["included"]),
        },
    )

    await db.commit()
    await db.refresh(pack)

    return {
        "pack_id": pack.id,
        "pack_uuid": pack.pack_uuid,
        "audience": pack.audience.value,
        "investigation_id": investigation_id,
        "investigation_reference": investigation.reference_number,
        "generated_at": pack.created_at.isoformat() if pack.created_at else None,
        "content": pack.content,
        "redaction_log": pack.redaction_log,
        "included_assets": pack.included_assets,
        "checksum_sha256": pack.checksum_sha256,
    }
