"""Unified Actions API routes for incidents, RTAs, complaints, and investigations."""

import logging
from datetime import datetime
from typing import Any, Optional, Union

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, literal, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from src.api.dependencies import CurrentUser, DbSession
from src.api.utils.entity import get_or_404
from src.domain.models.complaint import Complaint, ComplaintAction
from src.domain.models.incident import ActionStatus, Incident, IncidentAction
from src.domain.models.investigation import InvestigationAction, InvestigationActionStatus, InvestigationRun
from src.domain.models.rta import RoadTrafficCollision, RTAAction
from src.domain.models.user import User

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

    source_type: str = Field(..., description="Type of source entity: incident, rta, or complaint")
    source_id: int = Field(..., description="ID of the source entity")
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
        source_type=source_type,
        source_id=source_id,
        owner_id=action.owner_id,
        owner_email=None,
        created_at=action.created_at.isoformat() if action.created_at else "",
    )


# ============== Endpoints ==============


@router.get("/", response_model=ActionListResponse)
async def list_actions(
    db: DbSession,
    current_user: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: Optional[str] = Query(None, alias="status"),
    source_type: Optional[str] = Query(None),
    source_id: Optional[int] = Query(None),
) -> ActionListResponse:
    """List all actions across incidents, RTAs, and complaints with pagination."""
    actions_list: list[ActionResponse] = []

    # Only query if source_type not specified or matches "incident"
    if not source_type or source_type == "incident":
        incident_query = (
            select(IncidentAction)
            .join(Incident)
            .where(Incident.tenant_id == current_user.tenant_id)
            .options(selectinload(IncidentAction.incident))
        )
        if status_filter:
            incident_query = incident_query.where(IncidentAction.status == status_filter)
        if source_type == "incident" and source_id:
            incident_query = incident_query.where(IncidentAction.incident_id == source_id)

        incident_result = await db.execute(incident_query)
        for inc_action in incident_result.scalars().all():
            actions_list.append(_action_to_response(inc_action, "incident", inc_action.incident_id))

    # Only query if source_type not specified or matches "rta"
    if not source_type or source_type == "rta":
        rta_query = (
            select(RTAAction).where(RTAAction.tenant_id == current_user.tenant_id).options(selectinload(RTAAction.rta))
        )
        if status_filter:
            rta_query = rta_query.where(RTAAction.status == status_filter)
        if source_type == "rta" and source_id:
            rta_query = rta_query.where(RTAAction.rta_id == source_id)

        rta_result = await db.execute(rta_query)
        for rta_action in rta_result.scalars().all():
            actions_list.append(_action_to_response(rta_action, "rta", rta_action.rta_id))

    # Only query if source_type not specified or matches "complaint"
    if not source_type or source_type == "complaint":
        complaint_query = (
            select(ComplaintAction)
            .join(Complaint)
            .where(Complaint.tenant_id == current_user.tenant_id)
            .options(selectinload(ComplaintAction.complaint))
        )
        if status_filter:
            complaint_query = complaint_query.where(ComplaintAction.status == status_filter)
        if source_type == "complaint" and source_id:
            complaint_query = complaint_query.where(ComplaintAction.complaint_id == source_id)

        complaint_result = await db.execute(complaint_query)
        for comp_action in complaint_result.scalars().all():
            actions_list.append(_action_to_response(comp_action, "complaint", comp_action.complaint_id))

    # Only query if source_type not specified or matches "investigation"
    # This fixes the "Cannot add action" defect by including investigation actions
    if not source_type or source_type == "investigation":
        investigation_query = (
            select(InvestigationAction)
            .join(InvestigationRun)
            .where(InvestigationRun.tenant_id == current_user.tenant_id)
            .options(selectinload(InvestigationAction.investigation))
        )
        if status_filter:
            investigation_query = investigation_query.where(InvestigationAction.status == status_filter)
        if source_type == "investigation" and source_id:
            investigation_query = investigation_query.where(InvestigationAction.investigation_id == source_id)

        investigation_result = await db.execute(investigation_query)
        for inv_action in investigation_result.scalars().all():
            actions_list.append(_action_to_response(inv_action, "investigation", inv_action.investigation_id))

    # Sort by created_at descending
    actions_list.sort(key=lambda x: x.created_at, reverse=True)

    # Apply pagination
    total = len(actions_list)
    start = (page - 1) * page_size
    end = start + page_size
    paginated = actions_list[start:end]

    return ActionListResponse(
        items=paginated,
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
    """Create a new action for an incident, RTA, complaint, or investigation."""
    src_type = action_data.source_type.lower()
    src_id = action_data.source_id

    # Diagnostic logging for 500 error investigation
    logger.info(
        f"create_action called: source_type={src_type}, source_id={src_id}, "
        f"title={action_data.title[:50] if action_data.title else 'None'}, "
        f"user_id={current_user.id}"
    )

    # Validate that the source entity exists
    if src_type == "incident":
        await get_or_404(db, Incident, src_id, tenant_id=current_user.tenant_id)
    elif src_type == "rta":
        await get_or_404(db, RoadTrafficCollision, src_id, tenant_id=current_user.tenant_id)
    elif src_type == "complaint":
        await get_or_404(db, Complaint, src_id, tenant_id=current_user.tenant_id)
    elif src_type == "investigation":
        logger.info(f"Validating investigation exists: id={src_id}")
        investigation = await get_or_404(db, InvestigationRun, src_id, tenant_id=current_user.tenant_id)
        logger.info(f"Investigation found: id={investigation.id}, ref={investigation.reference_number}")
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid source_type: {src_type}. Must be 'incident', 'rta', 'complaint', or 'investigation'",
        )

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

    # Declare action variable that will hold one of the four action types
    action: Union[IncidentAction, RTAAction, ComplaintAction, InvestigationAction]

    if src_type == "incident":
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
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid source_type: {src_type}. Must be 'incident', 'rta', 'complaint', or 'investigation'",
        )

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
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Source entity {src_type} with id {src_id} not found or was deleted",
            )
        elif "unique" in error_msg.lower() or "duplicate" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An action with this reference number already exists",
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Database error while creating action: {error_msg[:200]}",
            )
    except Exception as e:
        await db.rollback()
        # Log the FULL exception with traceback for diagnosis
        logger.exception(f"Unexpected exception creating action: type={type(e).__name__}, msg={str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error creating action: {type(e).__name__}: {str(e)[:200]}",
        )

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
        source_type=src_type,
        source_id=src_id,
        owner_id=action.owner_id,
        owner_email=action_data.assigned_to_email,
        created_at=action.created_at.isoformat() if action.created_at else "",
    )


@router.get("/{action_id}", response_model=dict)
async def get_action(
    action_id: int,
    db: DbSession,
    current_user: CurrentUser,
    source_type: str = Query(..., description="Type of source: incident, rta, complaint, or investigation"),
) -> ActionResponse:
    """Get a specific action by ID."""
    src_type = source_type.lower()

    if src_type == "incident":
        action = await get_or_404(db, IncidentAction, action_id)
        await get_or_404(db, Incident, action.incident_id, tenant_id=current_user.tenant_id)
        return _action_to_response(action, "incident", action.incident_id)
    elif src_type == "rta":
        action = await get_or_404(db, RTAAction, action_id, tenant_id=current_user.tenant_id)
        return _action_to_response(action, "rta", action.rta_id)
    elif src_type == "complaint":
        action = await get_or_404(db, ComplaintAction, action_id)
        await get_or_404(db, Complaint, action.complaint_id, tenant_id=current_user.tenant_id)
        return _action_to_response(action, "complaint", action.complaint_id)
    elif src_type == "investigation":
        action = await get_or_404(db, InvestigationAction, action_id)
        await get_or_404(db, InvestigationRun, action.investigation_id, tenant_id=current_user.tenant_id)
        return _action_to_response(action, "investigation", action.investigation_id)

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Action not found",
    )


@router.patch("/{action_id}", response_model=ActionResponse)
async def update_action(  # noqa: C901 - complexity justified by unified action types
    action_id: int,
    action_data: ActionUpdate,
    db: DbSession,
    current_user: CurrentUser,
    source_type: str = Query(..., description="Type of source: incident, rta, complaint, or investigation"),
) -> ActionResponse:
    """Update an existing action by ID.

    Supports partial updates - only provided fields will be updated.
    Returns 404 if action not found, 400 for validation errors.
    """
    src_type = source_type.lower()

    # Bounded error class: validate source_type
    if src_type not in ("incident", "rta", "complaint", "investigation"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid source_type: {src_type}. Must be 'incident', 'rta', 'complaint', or 'investigation'",
        )

    # Bounded error class: validate status if provided
    incident_statuses = {s.value for s in ActionStatus}
    investigation_statuses = {s.value for s in InvestigationActionStatus}
    valid_statuses = incident_statuses | investigation_statuses
    if action_data.status and action_data.status.lower() not in valid_statuses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status: {action_data.status}. Must be one of: {', '.join(sorted(valid_statuses))}",
        )

    # Bounded error class: validate priority if provided
    valid_priorities = {"low", "medium", "high", "critical"}
    if action_data.priority and action_data.priority.lower() not in valid_priorities:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid priority: {action_data.priority}. Must be one of: {', '.join(sorted(valid_priorities))}",
        )

    # Find the action by type
    action: Union[IncidentAction, RTAAction, ComplaintAction, InvestigationAction]
    source_id: int

    if src_type == "incident":
        action = await get_or_404(db, IncidentAction, action_id)
        await get_or_404(db, Incident, action.incident_id, tenant_id=current_user.tenant_id)
        source_id = action.incident_id
    elif src_type == "rta":
        action = await get_or_404(db, RTAAction, action_id, tenant_id=current_user.tenant_id)
        source_id = action.rta_id
    elif src_type == "complaint":
        action = await get_or_404(db, ComplaintAction, action_id)
        await get_or_404(db, Complaint, action.complaint_id, tenant_id=current_user.tenant_id)
        source_id = action.complaint_id
    elif src_type == "investigation":
        action = await get_or_404(db, InvestigationAction, action_id)
        await get_or_404(db, InvestigationRun, action.investigation_id, tenant_id=current_user.tenant_id)
        source_id = action.investigation_id
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Action not found",
        )

    # Apply updates - only update fields that were provided
    if action_data.title is not None:
        action.title = action_data.title
    if action_data.description is not None:
        action.description = action_data.description
    if action_data.action_type is not None:
        action.action_type = action_data.action_type
    if action_data.priority is not None:
        action.priority = action_data.priority.lower()
    if action_data.status is not None:
        # Convert string to appropriate status enum based on source type
        status_value = action_data.status.lower()
        if src_type == "investigation":
            action.status = InvestigationActionStatus(status_value)
        else:
            action.status = ActionStatus(status_value)
        # Set completed_at if status changed to completed
        if status_value == "completed" and not action.completed_at:
            action.completed_at = datetime.utcnow()
        # Clear completed_at if status changed away from completed
        elif status_value != "completed":
            action.completed_at = None

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

    if action_data.assigned_to_email is not None:
        result = await db.execute(select(User).where(User.email == action_data.assigned_to_email))
        user = result.scalar_one_or_none()
        if user:
            action.owner_id = user.id

    if action_data.completion_notes is not None:
        action.completion_notes = action_data.completion_notes

    await db.commit()
    await db.refresh(action)

    return _action_to_response(action, src_type, source_id)
