"""Incident API routes."""

import logging
from typing import Annotated, Literal, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func as sa_func
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from src.api.dependencies import CurrentUser, DbSession, require_permission
from src.api.dependencies.request_context import get_request_id
from src.api.routes._runner_sheet import assert_can_delete_runner_sheet_entry
from src.api.schemas.error_codes import ErrorCode
from src.api.schemas.incident import IncidentCreate, IncidentListResponse, IncidentResponse, IncidentUpdate
from src.api.schemas.running_sheet import RunningSheetEntryCreate, RunningSheetEntryResponse
from src.api.utils.errors import api_error
from src.api.utils.pagination import PaginationParams
from src.api.utils.tenant import apply_tenant_filter, require_tenant_id
from src.domain.exceptions import AuthorizationError, BadRequestError, ConflictError, NotFoundError
from src.domain.models.incident import Incident, IncidentRunningSheetEntry
from src.domain.models.user import User
from src.domain.services.api_idempotency_service import (
    SCOPE_INCIDENT_CREATE,
    begin_idempotent_create,
    complete_idempotent_create,
)
from src.domain.services.audit_service import record_audit_event
from src.domain.services.case_risk_links import sync_case_risk_links_from_csv
from src.domain.services.incident_risk_links import (
    append_linked_risk_id,
    create_enterprise_risk_from_incident,
    default_impact_for_incident,
    find_existing_enterprise_risk_for_incident,
    incident_detail_href,
    resolve_enterprise_category,
    risk_register_href,
    severity_allows_raise_risk,
)
from src.domain.services.notification_service import NotificationService
from src.infrastructure.monitoring.azure_monitor import track_metric
from src.services.incident_service import IncidentService

router = APIRouter()
logger = logging.getLogger(__name__)


class IncidentResponseWithLinks(IncidentResponse):
    """Incident response including optional enterprise risk linkage."""

    linked_risk_ids: Optional[str] = None


async def _validate_case_owner(db: DbSession, owner_id: int, tenant_id: int | None) -> User:
    """Ensure owner_id refers to an active user in the tenant."""
    result = await db.execute(select(User).where(User.id == owner_id))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise BadRequestError(f"No active user found with id {owner_id}")
    if tenant_id is not None and user.tenant_id != tenant_id:
        raise BadRequestError(f"User {owner_id} is not in this tenant")
    return user


async def _notify_case_owner_assignment(
    db: DbSession,
    *,
    entity_type: str,
    entity_id: int,
    assigned_to_user_id: int,
    assigned_by_user_id: int,
    reference: str,
) -> None:
    """In-app assignment notify; never rewrite NotificationService — call site only."""
    try:
        service = NotificationService(db)
        await service.create_assignment(
            entity_type=entity_type,
            entity_id=str(entity_id),
            assigned_to_user_id=assigned_to_user_id,
            assigned_by_user_id=assigned_by_user_id,
            notes=f"You have been assigned as case owner for {reference}",
            priority="high",
        )
    except Exception:
        logger.exception(
            "Failed to notify case owner assignment for %s %s",
            entity_type,
            entity_id,
        )


async def _trigger_operational_standards_assess(
    db: DbSession,
    incident: Incident,
    current_user: User,
) -> None:
    """Fire-and-forget standards assessment; never breaks incident save."""
    tenant_id = incident.tenant_id or current_user.tenant_id
    if tenant_id is None:
        logger.warning(
            "Skipping operational standards assess for incident %s; no tenant_id",
            incident.id,
        )
        return
    try:
        from src.domain.services.governed_knowledge_service import governed_knowledge_service

        content = f"{incident.title}\n\n{incident.description}"
        # Nested savepoint: ai_decision_logs / mapping failures must not poison
        # the outer incident update transaction (staging SAMPLE rows historically
        # had null tenant_id and aborted the session → assign-owner 500).
        async with db.begin_nested():
            await governed_knowledge_service.assess_operational_entity(
                db,
                entity_type="incident",
                entity_id=str(incident.id),
                content=content,
                tenant_id=tenant_id,
                user=current_user,
            )
    except Exception:
        logger.warning(
            "Operational standards assess failed for incident %s; save continues",
            incident.id,
            exc_info=True,
        )


@router.post(
    "",
    response_model=IncidentResponse,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False,
)
@router.post(
    "/",
    response_model=IncidentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_incident(
    incident_data: IncidentCreate,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("incident:create"))],
    request_id: str = Depends(get_request_id),
    idempotency_key: Annotated[Optional[str], Header(alias="Idempotency-Key")] = None,
) -> Incident:
    """
    Report a new incident.

    Requires authentication. Delegates to IncidentService for audit trail,
    cache invalidation, and telemetry.

    Optional ``Idempotency-Key`` header (PX-001): retries return the same record.
    """
    svc = IncidentService(db)
    try:
        claim = await begin_idempotent_create(
            db,
            tenant_id=current_user.tenant_id,
            scope=SCOPE_INCIDENT_CREATE,
            idempotency_key=idempotency_key,
            payload=incident_data,
        )
        if claim is not None and claim.is_replay and claim.entity_id is not None:
            return await svc.get_incident(
                claim.entity_id,
                current_user.tenant_id,
                skip_tenant_check=current_user.is_superuser,
            )

        has_set_ref = current_user.has_permission("incident:set_reference_number")
        incident = await svc.create_incident(
            incident_data=incident_data,
            user_id=current_user.id,
            tenant_id=current_user.tenant_id,
            has_set_ref_permission=has_set_ref,
            request_id=request_id,
        )
        await complete_idempotent_create(
            db,
            record_id=claim.record_id if claim else None,
            entity_type="incident",
            entity_id=incident.id,
        )
        track_metric("incidents.created")
        await _trigger_operational_standards_assess(db, incident, current_user)
        return incident
    except PermissionError as e:
        raise AuthorizationError(str(e))
    except ValueError as e:
        raise ConflictError(str(e))
    except LookupError as e:
        raise NotFoundError(str(e))


@router.get("/{incident_id}", response_model=IncidentResponseWithLinks)
async def get_incident(
    incident_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> Incident:
    """
    Get an incident by ID.

    Requires authentication.
    """
    svc = IncidentService(db)
    try:
        return await svc.get_incident(
            incident_id,
            current_user.tenant_id,
            skip_tenant_check=current_user.is_superuser,
        )
    except LookupError:
        raise NotFoundError(f"Incident {incident_id} not found")


class RaiseRiskFromIncidentRequest(BaseModel):
    """Optional overrides when raising an enterprise risk from an incident."""

    title: Optional[str] = Field(None, min_length=1, max_length=300)
    description: Optional[str] = Field(None, min_length=1)
    likelihood: int = Field(4, ge=1, le=5)
    impact: int = Field(3, ge=1, le=5)
    category: Literal[
        "strategic",
        "operational",
        "financial",
        "compliance",
        "reputational",
        "safety",
        "environmental",
        "information_security",
    ] = "safety"
    treatment_strategy: Literal[
        "accept",
        "mitigate",
        "transfer",
        "avoid",
        "exploit",
        "treat",
        "tolerate",
        "terminate",
    ] = "mitigate"


class RaisedEnterpriseRiskSummary(BaseModel):
    """Slim risk payload for FE toast/navigation (enterprise register)."""

    id: int
    reference_number: str
    title: str
    risk_source: Optional[str] = None


class RaiseRiskFromIncidentResponse(BaseModel):
    risk: RaisedEnterpriseRiskSummary
    incident_id: int
    linked_risk_ids: str
    incident_href: str
    risk_register_href: str


@router.post(
    "/{incident_id}/raise-risk",
    response_model=RaiseRiskFromIncidentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def raise_risk_from_incident(
    incident_id: int,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("risk:create"))],
    request_id: str = Depends(get_request_id),
    body: Optional[RaiseRiskFromIncidentRequest] = None,
):
    """Create an Enterprise Risk Register entry linked to this incident."""
    if body is None:
        body = RaiseRiskFromIncidentRequest.model_validate({})

    svc = IncidentService(db)
    try:
        incident = await svc.get_incident(
            incident_id,
            current_user.tenant_id,
            skip_tenant_check=current_user.is_superuser,
        )
    except LookupError:
        raise NotFoundError(f"Incident {incident_id} not found")

    if not severity_allows_raise_risk(incident.severity):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=api_error(
                ErrorCode.VALIDATION_ERROR,
                "Only high or critical severity incidents can raise an enterprise risk.",
            ),
        )

    tenant_id = incident.tenant_id or current_user.tenant_id
    if tenant_id is None:
        raise BadRequestError("Incident has no tenant; cannot raise an enterprise risk.")

    existing = await find_existing_enterprise_risk_for_incident(db, incident=incident)
    if existing is not None:
        incident.linked_risk_ids = append_linked_risk_id(incident.linked_risk_ids, existing.id)
        await sync_case_risk_links_from_csv(
            db,
            tenant_id=tenant_id,
            case_type="incident",
            case_id=incident.id,
            linked_risk_ids_raw=incident.linked_risk_ids,
        )
        await db.commit()
        return RaiseRiskFromIncidentResponse(
            risk=RaisedEnterpriseRiskSummary(
                id=existing.id,
                reference_number=existing.reference,
                title=existing.title,
                risk_source=existing.context,
            ),
            incident_id=incident.id,
            linked_risk_ids=incident.linked_risk_ids or str(existing.id),
            incident_href=incident_detail_href(incident.id),
            risk_register_href=risk_register_href(existing.id, incident_ref=incident.reference_number),
        )

    impact = default_impact_for_incident(incident, body.impact)
    category = resolve_enterprise_category(body.category, incident)
    title = body.title or f"Risk from incident {incident.reference_number}"
    description = body.description or (
        f"Raised from incident {incident.reference_number}.\n\n"
        f"{incident.title}\n\n{incident.description}"
        + (f"\n\nRoot cause: {incident.root_cause}" if incident.root_cause else "")
    )

    try:
        risk = await create_enterprise_risk_from_incident(
            db,
            incident=incident,
            actor_user_id=current_user.id,
            title=title,
            description=description,
            likelihood=body.likelihood,
            impact=impact,
            category=category,
            treatment_strategy=body.treatment_strategy,
            tenant_id=tenant_id,
        )
        incident.linked_risk_ids = append_linked_risk_id(incident.linked_risk_ids, risk.id)
        await sync_case_risk_links_from_csv(
            db,
            tenant_id=tenant_id,
            case_type="incident",
            case_id=incident.id,
            linked_risk_ids_raw=incident.linked_risk_ids,
        )

        await record_audit_event(
            db=db,
            event_type="incident.risk_raised",
            entity_type="incident",
            entity_id=str(incident.id),
            action="create",
            description=f"Risk {risk.reference} raised from incident {incident.reference_number}",
            payload={"risk_id": risk.id, "risk_reference": risk.reference},
            user_id=current_user.id,
            request_id=request_id,
            tenant_id=tenant_id,
        )

        await db.commit()
        await db.refresh(risk)
    except IntegrityError as exc:
        await db.rollback()
        logger.exception("raise-risk IntegrityError for incident_id=%s", incident_id)
        # Concurrent double-submit may have created the row — return it when present.
        try:
            incident = await svc.get_incident(
                incident_id,
                current_user.tenant_id,
                skip_tenant_check=current_user.is_superuser,
            )
            recovered = await find_existing_enterprise_risk_for_incident(db, incident=incident)
        except Exception:
            recovered = None
        if recovered is not None:
            incident.linked_risk_ids = append_linked_risk_id(incident.linked_risk_ids, recovered.id)
            await db.commit()
            return RaiseRiskFromIncidentResponse(
                risk=RaisedEnterpriseRiskSummary(
                    id=recovered.id,
                    reference_number=recovered.reference,
                    title=recovered.title,
                    risk_source=recovered.context,
                ),
                incident_id=incident.id,
                linked_risk_ids=incident.linked_risk_ids or str(recovered.id),
                incident_href=incident_detail_href(incident.id),
                risk_register_href=risk_register_href(recovered.id, incident_ref=incident.reference_number),
            )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=api_error(
                ErrorCode.DATABASE_ERROR,
                "Could not raise risk due to a data conflict. Refresh and try again, "
                "or open any already-linked risk from this incident.",
            ),
        ) from exc
    except BadRequestError:
        await db.rollback()
        raise
    except Exception as exc:
        await db.rollback()
        logger.exception("raise-risk failed for incident_id=%s", incident_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=api_error(ErrorCode.INTERNAL_ERROR, "Could not raise risk from incident."),
        ) from exc

    return RaiseRiskFromIncidentResponse(
        risk=RaisedEnterpriseRiskSummary(
            id=risk.id,
            reference_number=risk.reference,
            title=risk.title,
            risk_source=risk.context,
        ),
        incident_id=incident.id,
        linked_risk_ids=incident.linked_risk_ids or str(risk.id),
        incident_href=incident_detail_href(incident.id),
        risk_register_href=risk_register_href(risk.id, incident_ref=incident.reference_number),
    )


@router.get("", response_model=IncidentListResponse, include_in_schema=False)
@router.get("/", response_model=IncidentListResponse)
async def list_incidents(
    db: DbSession,
    current_user: CurrentUser,
    request_id: str = Depends(get_request_id),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    reporter_email: Optional[str] = Query(None, description="Filter by reporter email"),
    owner: Optional[str] = Query(
        None,
        description="Filter by case owner: 'unassigned' for intakes with no owner_id",
    ),
    asset_id: Optional[int] = Query(None, description="Filter by linked Asset registry id"),
) -> IncidentListResponse:
    """
    List all incidents with deterministic ordering.

    Incidents are ordered by reported_date DESC, id ASC.
    Requires authentication. Users can only filter by their own email
    unless they have admin permissions.
    """
    if owner is not None and owner != "unassigned":
        raise BadRequestError("Invalid owner filter. Supported value: unassigned")

    svc = IncidentService(db)

    if reporter_email:
        user_email = getattr(current_user, "email", None)
        has_view_all = (
            current_user.has_permission("incident:view_all") if hasattr(current_user, "has_permission") else False
        )
        is_superuser = getattr(current_user, "is_superuser", False)

        if not await svc.check_reporter_email_access(reporter_email, user_email, has_view_all, is_superuser):
            raise AuthorizationError("You can only view your own incidents")

        await record_audit_event(
            db=db,
            event_type="incident.list_filtered",
            entity_type="incident",
            entity_id="*",
            action="list",
            description="Incident list accessed with email filter",
            payload={
                "filter_type": "reporter_email",
                "is_own_email": user_email and reporter_email.lower() == user_email.lower(),
                "has_view_all_permission": has_view_all,
                "is_superuser": is_superuser,
            },
            user_id=current_user.id,
            request_id=request_id,
        )

    try:
        result = await svc.list_incidents(
            tenant_id=current_user.tenant_id,
            params=PaginationParams(page=page, page_size=page_size),
            reporter_email=reporter_email,
            owner=owner,
            asset_id=asset_id,
            skip_tenant_check=current_user.is_superuser,
        )
        items: list[IncidentResponse] = []
        skipped = 0
        for row in result.items:
            try:
                items.append(IncidentResponse.model_validate(row))
            except Exception as validate_err:
                skipped += 1
                logger.error(
                    "Skipping unserializable incident id=%s during list: %s",
                    getattr(row, "id", None),
                    validate_err,
                    exc_info=True,
                )
        if skipped:
            logger.warning(
                "Incident list skipped %s unserializable row(s); returning %s of %s",
                skipped,
                len(items),
                result.total,
            )
        return IncidentListResponse(
            items=items,
            total=result.total,
            page=result.page,
            page_size=result.page_size,
            pages=result.pages,
        )
    except Exception as e:
        error_str = str(e).lower()
        logger.error("Error listing incidents: %s", e, exc_info=True)

        column_errors = [
            "reporter_email",
            "column",
            "does not exist",
            "unknown column",
            "no such column",
            "undefined column",
            "relation",
            "programmingerror",
        ]

        if any(err in error_str for err in column_errors):
            logger.warning("Database column missing - migration may be pending")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=api_error(
                    ErrorCode.DATABASE_ERROR,
                    "Database migration pending. Please wait for migrations to complete.",
                ),
            )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=api_error(
                ErrorCode.INTERNAL_ERROR,
                "Unable to list incidents at this time.",
            ),
        )


@router.get("/{incident_id}/investigations", response_model=dict)
async def list_incident_investigations(
    incident_id: int,
    db: DbSession,
    current_user: CurrentUser,
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(25, ge=1, le=100, description="Items per page (1-100)"),
):
    """
    List investigations for a specific incident (paginated).

    Requires authentication.
    Returns investigations assigned to this incident with pagination.
    Deterministic ordering: created_at DESC, id ASC.
    """
    from math import ceil

    from src.api.schemas.investigation import InvestigationRunResponse
    from src.domain.models.investigation import AssignedEntityType, InvestigationRun

    svc = IncidentService(db)
    try:
        await svc.get_incident(
            incident_id,
            current_user.tenant_id,
            skip_tenant_check=current_user.is_superuser,
        )
    except LookupError:
        raise NotFoundError(f"Incident {incident_id} not found")

    count_query = (
        select(sa_func.count())
        .select_from(InvestigationRun)
        .where(
            InvestigationRun.assigned_entity_type == AssignedEntityType.REPORTING_INCIDENT,
            InvestigationRun.assigned_entity_id == incident_id,
            InvestigationRun.tenant_id == current_user.tenant_id,
        )
    )
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Calculate total pages
    total_pages = ceil(total / page_size) if total > 0 else 1

    # Get paginated results
    query = (
        select(InvestigationRun)
        .where(
            InvestigationRun.assigned_entity_type == AssignedEntityType.REPORTING_INCIDENT,
            InvestigationRun.assigned_entity_id == incident_id,
            InvestigationRun.tenant_id == current_user.tenant_id,
        )
        .order_by(InvestigationRun.created_at.desc(), InvestigationRun.id.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(query)
    investigations = result.scalars().all()

    return {
        "items": [InvestigationRunResponse.model_validate(inv) for inv in investigations],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": total_pages,
    }


@router.get("/{incident_id}/running-sheet", response_model=list[RunningSheetEntryResponse])
async def list_incident_running_sheet_entries(
    incident_id: int,
    db: DbSession,
    current_user: CurrentUser,
):
    """List incident runner-sheet entries, newest first."""
    svc = IncidentService(db)
    try:
        incident = await svc.get_incident(
            incident_id,
            current_user.tenant_id,
            skip_tenant_check=current_user.is_superuser,
        )
    except LookupError:
        raise NotFoundError(f"Incident {incident_id} not found")

    query = select(IncidentRunningSheetEntry).where(IncidentRunningSheetEntry.incident_id == incident_id)
    if getattr(current_user, "is_superuser", False):
        if incident.tenant_id is not None:
            query = apply_tenant_filter(query, IncidentRunningSheetEntry, incident.tenant_id)
    else:
        tenant_id = require_tenant_id(getattr(current_user, "tenant_id", None))
        query = apply_tenant_filter(query, IncidentRunningSheetEntry, tenant_id)

    result = await db.execute(
        query.order_by(IncidentRunningSheetEntry.created_at.desc(), IncidentRunningSheetEntry.id.asc())
    )
    return result.scalars().all()


@router.post(
    "/{incident_id}/running-sheet",
    response_model=RunningSheetEntryResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_incident_running_sheet_entry(
    incident_id: int,
    payload: RunningSheetEntryCreate,
    db: DbSession,
    current_user: CurrentUser,
    request_id: str = Depends(get_request_id),
):
    """Add a timestamped entry to the incident runner sheet."""
    svc = IncidentService(db)
    try:
        incident = await svc.get_incident(
            incident_id,
            current_user.tenant_id,
            skip_tenant_check=current_user.is_superuser,
        )
    except LookupError:
        raise NotFoundError(f"Incident {incident_id} not found")

    entry = IncidentRunningSheetEntry(
        tenant_id=incident.tenant_id,
        incident_id=incident.id,
        content=payload.content,
        entry_type=payload.entry_type.value,
        author_id=current_user.id,
        author_email=current_user.email,
    )
    db.add(entry)
    await db.flush()

    await record_audit_event(
        db=db,
        event_type="incident.runner_sheet_entry.created",
        entity_type="incident",
        entity_id=str(incident.id),
        action="create",
        description=f"Runner-sheet entry added to incident {incident.reference_number}",
        payload={"entry_id": entry.id, "entry_type": entry.entry_type},
        user_id=current_user.id,
        request_id=request_id,
    )

    await db.commit()
    await db.refresh(entry)
    return entry


@router.delete("/{incident_id}/running-sheet/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_incident_running_sheet_entry(
    incident_id: int,
    entry_id: int,
    db: DbSession,
    current_user: CurrentUser,
    request_id: str = Depends(get_request_id),
) -> None:
    """Delete an incident runner-sheet entry."""
    svc = IncidentService(db)
    try:
        incident = await svc.get_incident(
            incident_id,
            current_user.tenant_id,
            skip_tenant_check=current_user.is_superuser,
        )
    except LookupError:
        raise NotFoundError(f"Incident {incident_id} not found")

    result = await db.execute(
        select(IncidentRunningSheetEntry).where(
            IncidentRunningSheetEntry.id == entry_id,
            IncidentRunningSheetEntry.incident_id == incident_id,
            IncidentRunningSheetEntry.tenant_id == incident.tenant_id,
        )
    )
    entry = result.scalar_one_or_none()
    if entry is None:
        raise NotFoundError("Runner-sheet entry not found")

    assert_can_delete_runner_sheet_entry(current_user, entry.author_id, "incident")

    await record_audit_event(
        db=db,
        event_type="incident.runner_sheet_entry.deleted",
        entity_type="incident",
        entity_id=str(incident.id),
        action="delete",
        description=f"Runner-sheet entry deleted from incident {incident.reference_number}",
        payload={"entry_id": entry.id, "entry_type": entry.entry_type},
        user_id=current_user.id,
        request_id=request_id,
    )

    await db.delete(entry)
    await db.commit()


@router.patch("/{incident_id}", response_model=IncidentResponse)
async def update_incident(
    incident_id: int,
    incident_data: IncidentUpdate,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("incident:update"))],
    request_id: str = Depends(get_request_id),
) -> Incident:
    """
    Partially update an incident.

    Requires authentication. StateTransitionError is caught by the
    global domain error handler and returned as a structured JSON response.
    """
    updates = incident_data.model_dump(exclude_unset=True)
    if "owner_id" in updates and updates["owner_id"] is not None:
        await _validate_case_owner(db, updates["owner_id"], current_user.tenant_id)

    svc = IncidentService(db)
    try:
        existing = await svc.get_incident(
            incident_id,
            current_user.tenant_id,
            skip_tenant_check=current_user.is_superuser,
        )
        previous_owner_id = existing.owner_id

        incident = await svc.update_incident(
            incident_id,
            incident_data,
            user_id=current_user.id,
            tenant_id=current_user.tenant_id,
            request_id=request_id,
            skip_tenant_check=current_user.is_superuser,
        )
        await _trigger_operational_standards_assess(db, incident, current_user)

        if "owner_id" in updates and updates["owner_id"] is not None and updates["owner_id"] != previous_owner_id:
            await _notify_case_owner_assignment(
                db,
                entity_type="incident",
                entity_id=incident.id,
                assigned_to_user_id=updates["owner_id"],
                assigned_by_user_id=current_user.id,
                reference=incident.reference_number,
            )
            # NotificationService.create_assignment may commit or abort; re-load safely
            try:
                await db.refresh(incident)
            except Exception:
                logger.warning(
                    "Refresh after owner assign failed for incident %s; re-fetching",
                    incident_id,
                    exc_info=True,
                )
                incident = await svc.get_incident(
                    incident_id,
                    current_user.tenant_id,
                    skip_tenant_check=current_user.is_superuser,
                )
        return incident
    except LookupError:
        raise NotFoundError(f"Incident {incident_id} not found")


@router.delete("/{incident_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_incident(
    incident_id: int,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("incident:delete"))],
    request_id: str = Depends(get_request_id),
) -> None:
    """
    Delete an incident.

    Requires authentication.
    """
    svc = IncidentService(db)
    try:
        await svc.delete_incident(
            incident_id,
            user_id=current_user.id,
            tenant_id=current_user.tenant_id,
            request_id=request_id,
            skip_tenant_check=current_user.is_superuser,
        )
    except LookupError:
        raise NotFoundError(f"Incident {incident_id} not found")
