"""Unified Actions API routes for incidents, RTAs, and complaints."""

from datetime import datetime
from typing import Any, Optional, Union

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import literal, select
from sqlalchemy.orm import selectinload

from src.api.dependencies import CurrentUser, DbSession
from src.domain.models.complaint import ComplaintAction
from src.domain.models.incident import ActionStatus, IncidentAction
from src.domain.models.rta import RTAAction
from src.domain.models.user import User

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
        ..., description="Type of source entity: incident, rta, or complaint"
    )
    source_id: int = Field(..., description="ID of the source entity")
    assigned_to_email: Optional[str] = Field(
        None, description="Email of user to assign to"
    )


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
    source_type: str
    source_id: int
    owner_id: Optional[int] = None
    owner_email: Optional[str] = None
    created_at: str

    class Config:
        from_attributes = True


class ActionListResponse(BaseModel):
    """Paginated list of actions."""

    items: list[ActionResponse]
    total: int
    page: int
    size: int
    pages: int


def _action_to_response(
    action: Union[IncidentAction, RTAAction, ComplaintAction],
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
        status=action.status.value if hasattr(action.status, "value") else str(action.status),
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
    size: int = Query(20, ge=1, le=100),
    status_filter: Optional[str] = Query(None, alias="status"),
    source_type: Optional[str] = Query(None),
    source_id: Optional[int] = Query(None),
) -> ActionListResponse:
    """List all actions across incidents, RTAs, and complaints with pagination."""
    actions_list: list[ActionResponse] = []

    # Only query if source_type not specified or matches "incident"
    if not source_type or source_type == "incident":
        incident_query = select(IncidentAction).options(
            selectinload(IncidentAction.incident)
        )
        if status_filter:
            incident_query = incident_query.where(
                IncidentAction.status == status_filter
            )
        if source_type == "incident" and source_id:
            incident_query = incident_query.where(
                IncidentAction.incident_id == source_id
            )

        incident_result = await db.execute(incident_query)
        for inc_action in incident_result.scalars().all():
            actions_list.append(
                _action_to_response(inc_action, "incident", inc_action.incident_id)
            )

    # Only query if source_type not specified or matches "rta"
    if not source_type or source_type == "rta":
        rta_query = select(RTAAction).options(selectinload(RTAAction.rta))
        if status_filter:
            rta_query = rta_query.where(RTAAction.status == status_filter)
        if source_type == "rta" and source_id:
            rta_query = rta_query.where(RTAAction.rta_id == source_id)

        rta_result = await db.execute(rta_query)
        for rta_action in rta_result.scalars().all():
            actions_list.append(
                _action_to_response(rta_action, "rta", rta_action.rta_id)
            )

    # Only query if source_type not specified or matches "complaint"
    if not source_type or source_type == "complaint":
        complaint_query = select(ComplaintAction).options(
            selectinload(ComplaintAction.complaint)
        )
        if status_filter:
            complaint_query = complaint_query.where(
                ComplaintAction.status == status_filter
            )
        if source_type == "complaint" and source_id:
            complaint_query = complaint_query.where(
                ComplaintAction.complaint_id == source_id
            )

        complaint_result = await db.execute(complaint_query)
        for comp_action in complaint_result.scalars().all():
            actions_list.append(
                _action_to_response(comp_action, "complaint", comp_action.complaint_id)
            )

    # Sort by created_at descending
    actions_list.sort(key=lambda x: x.created_at, reverse=True)

    # Apply pagination
    total = len(actions_list)
    start = (page - 1) * size
    end = start + size
    paginated = actions_list[start:end]

    return ActionListResponse(
        items=paginated,
        total=total,
        page=page,
        size=size,
        pages=(total + size - 1) // size if total > 0 else 0,
    )


@router.post("/", response_model=ActionResponse, status_code=status.HTTP_201_CREATED)
async def create_action(
    action_data: ActionCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> ActionResponse:
    """Create a new action for an incident, RTA, or complaint."""
    # Find owner by email if provided
    owner_id: Optional[int] = None
    if action_data.assigned_to_email:
        result = await db.execute(
            select(User).where(User.email == action_data.assigned_to_email)
        )
        user = result.scalar_one_or_none()
        if user:
            owner_id = user.id

    src_type = action_data.source_type.lower()
    src_id = action_data.source_id

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

    # Using type: ignore for Union type - we use src_id directly for source_id
    action: Union[IncidentAction, RTAAction, ComplaintAction]  # type: ignore[assignment]

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
            created_by_id=current_user.id,
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
            created_by_id=current_user.id,
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
            created_by_id=current_user.id,
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid source_type: {src_type}. Must be 'incident', 'rta', or 'complaint'",
        )

    db.add(action)
    await db.commit()
    await db.refresh(action)

    return ActionResponse(
        id=action.id,
        reference_number=action.reference_number,
        title=action.title,
        description=action.description,
        action_type=action.action_type or "corrective",
        priority=action.priority or "medium",
        status=action.status.value if hasattr(action.status, "value") else str(action.status),
        due_date=action.due_date.isoformat() if action.due_date else None,
        completed_at=action.completed_at.isoformat() if action.completed_at else None,
        source_type=src_type,
        source_id=src_id,
        owner_id=action.owner_id,
        owner_email=action_data.assigned_to_email,
        created_at=action.created_at.isoformat() if action.created_at else "",
    )


@router.get("/{action_id}")
async def get_action(
    action_id: int,
    db: DbSession,
    current_user: CurrentUser,
    source_type: str = Query(
        ..., description="Type of source: incident, rta, or complaint"
    ),
) -> ActionResponse:
    """Get a specific action by ID."""
    src_type = source_type.lower()

    if src_type == "incident":
        result = await db.execute(
            select(IncidentAction).where(IncidentAction.id == action_id)
        )
        incident_action = result.scalar_one_or_none()
        if incident_action:
            return _action_to_response(
                incident_action, "incident", incident_action.incident_id
            )
    elif src_type == "rta":
        result = await db.execute(
            select(RTAAction).where(RTAAction.id == action_id)
        )
        rta_action = result.scalar_one_or_none()
        if rta_action:
            return _action_to_response(rta_action, "rta", rta_action.rta_id)
    elif src_type == "complaint":
        result = await db.execute(
            select(ComplaintAction).where(ComplaintAction.id == action_id)
        )
        complaint_action = result.scalar_one_or_none()
        if complaint_action:
            return _action_to_response(
                complaint_action, "complaint", complaint_action.complaint_id
            )

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Action not found",
    )
