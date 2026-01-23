"""Unified Actions API routes for incidents, RTAs, and complaints."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select, union_all
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
    due_date: Optional[datetime] = None


class ActionCreate(ActionBase):
    """Schema for creating an action."""

    source_type: str = Field(..., description="Type of source entity: incident, rta, or complaint")
    source_id: int = Field(..., description="ID of the source entity")
    assigned_to_email: Optional[str] = Field(None, description="Email of user to assign to")


class ActionResponse(BaseModel):
    """Response schema for actions."""

    id: int
    reference_number: Optional[str] = None
    title: str
    description: str
    action_type: str
    priority: str
    status: str
    due_date: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    source_type: str
    source_id: int
    owner_id: Optional[int] = None
    owner_email: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ActionListResponse(BaseModel):
    """Paginated list of actions."""

    items: list[ActionResponse]
    total: int
    page: int
    size: int
    pages: int


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
    actions = []

    # Query incident actions
    incident_query = select(IncidentAction).options(selectinload(IncidentAction.incident))
    if status_filter:
        incident_query = incident_query.where(IncidentAction.status == status_filter)
    if source_type == "incident" and source_id:
        incident_query = incident_query.where(IncidentAction.incident_id == source_id)
    elif source_type and source_type != "incident":
        incident_query = incident_query.where(False)  # No results for wrong type

    result = await db.execute(incident_query)
    for action in result.scalars().all():
        actions.append(
            {
                "id": action.id,
                "reference_number": action.reference_number,
                "title": action.title,
                "description": action.description,
                "action_type": action.action_type or "corrective",
                "priority": action.priority or "medium",
                "status": action.status.value if hasattr(action.status, "value") else str(action.status),
                "due_date": action.due_date,
                "completed_at": action.completed_at,
                "source_type": "incident",
                "source_id": action.incident_id,
                "owner_id": action.owner_id,
                "owner_email": None,
                "created_at": action.created_at,
            }
        )

    # Query RTA actions
    rta_query = select(RTAAction).options(selectinload(RTAAction.rta))
    if status_filter:
        rta_query = rta_query.where(RTAAction.status == status_filter)
    if source_type == "rta" and source_id:
        rta_query = rta_query.where(RTAAction.rta_id == source_id)
    elif source_type and source_type != "rta":
        rta_query = rta_query.where(False)

    result = await db.execute(rta_query)
    for action in result.scalars().all():
        actions.append(
            {
                "id": action.id,
                "reference_number": action.reference_number,
                "title": action.title,
                "description": action.description,
                "action_type": action.action_type or "corrective",
                "priority": action.priority or "medium",
                "status": action.status.value if hasattr(action.status, "value") else str(action.status),
                "due_date": action.due_date,
                "completed_at": action.completed_at,
                "source_type": "rta",
                "source_id": action.rta_id,
                "owner_id": action.owner_id,
                "owner_email": None,
                "created_at": action.created_at,
            }
        )

    # Query Complaint actions
    complaint_query = select(ComplaintAction).options(selectinload(ComplaintAction.complaint))
    if status_filter:
        complaint_query = complaint_query.where(ComplaintAction.status == status_filter)
    if source_type == "complaint" and source_id:
        complaint_query = complaint_query.where(ComplaintAction.complaint_id == source_id)
    elif source_type and source_type != "complaint":
        complaint_query = complaint_query.where(False)

    result = await db.execute(complaint_query)
    for action in result.scalars().all():
        actions.append(
            {
                "id": action.id,
                "reference_number": action.reference_number,
                "title": action.title,
                "description": action.description,
                "action_type": action.action_type or "corrective",
                "priority": action.priority or "medium",
                "status": action.status.value if hasattr(action.status, "value") else str(action.status),
                "due_date": action.due_date,
                "completed_at": action.completed_at,
                "source_type": "complaint",
                "source_id": action.complaint_id,
                "owner_id": action.owner_id,
                "owner_email": None,
                "created_at": action.created_at,
            }
        )

    # Sort by created_at descending
    actions.sort(key=lambda x: x["created_at"], reverse=True)

    # Apply pagination
    total = len(actions)
    start = (page - 1) * size
    end = start + size
    paginated = actions[start:end]

    return ActionListResponse(
        items=[ActionResponse(**a) for a in paginated],
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
    owner_id = None
    if action_data.assigned_to_email:
        result = await db.execute(select(User).where(User.email == action_data.assigned_to_email))
        user = result.scalar_one_or_none()
        if user:
            owner_id = user.id

    source_type = action_data.source_type.lower()
    source_id = action_data.source_id

    if source_type == "incident":
        action = IncidentAction(
            incident_id=source_id,
            title=action_data.title,
            description=action_data.description,
            action_type=action_data.action_type,
            priority=action_data.priority,
            due_date=action_data.due_date,
            owner_id=owner_id,
            status=ActionStatus.OPEN,
            created_by_id=current_user.id,
        )
    elif source_type == "rta":
        action = RTAAction(
            rta_id=source_id,
            title=action_data.title,
            description=action_data.description,
            action_type=action_data.action_type,
            priority=action_data.priority,
            due_date=action_data.due_date,
            owner_id=owner_id,
            status=ActionStatus.OPEN,
            created_by_id=current_user.id,
        )
    elif source_type == "complaint":
        action = ComplaintAction(
            complaint_id=source_id,
            title=action_data.title,
            description=action_data.description,
            action_type=action_data.action_type,
            priority=action_data.priority,
            due_date=action_data.due_date,
            owner_id=owner_id,
            status=ActionStatus.OPEN,
            created_by_id=current_user.id,
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid source_type: {source_type}. Must be 'incident', 'rta', or 'complaint'",
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
        due_date=action.due_date,
        completed_at=action.completed_at,
        source_type=source_type,
        source_id=source_id,
        owner_id=action.owner_id,
        owner_email=action_data.assigned_to_email,
        created_at=action.created_at,
    )


@router.get("/{action_id}")
async def get_action(
    action_id: int,
    db: DbSession,
    current_user: CurrentUser,
    source_type: str = Query(..., description="Type of source: incident, rta, or complaint"),
) -> ActionResponse:
    """Get a specific action by ID."""
    source_type = source_type.lower()

    if source_type == "incident":
        result = await db.execute(select(IncidentAction).where(IncidentAction.id == action_id))
        action = result.scalar_one_or_none()
        if action:
            return ActionResponse(
                id=action.id,
                reference_number=action.reference_number,
                title=action.title,
                description=action.description,
                action_type=action.action_type or "corrective",
                priority=action.priority or "medium",
                status=action.status.value if hasattr(action.status, "value") else str(action.status),
                due_date=action.due_date,
                completed_at=action.completed_at,
                source_type="incident",
                source_id=action.incident_id,
                owner_id=action.owner_id,
                owner_email=None,
                created_at=action.created_at,
            )
    elif source_type == "rta":
        result = await db.execute(select(RTAAction).where(RTAAction.id == action_id))
        action = result.scalar_one_or_none()
        if action:
            return ActionResponse(
                id=action.id,
                reference_number=action.reference_number,
                title=action.title,
                description=action.description,
                action_type=action.action_type or "corrective",
                priority=action.priority or "medium",
                status=action.status.value if hasattr(action.status, "value") else str(action.status),
                due_date=action.due_date,
                completed_at=action.completed_at,
                source_type="rta",
                source_id=action.rta_id,
                owner_id=action.owner_id,
                owner_email=None,
                created_at=action.created_at,
            )
    elif source_type == "complaint":
        result = await db.execute(select(ComplaintAction).where(ComplaintAction.id == action_id))
        action = result.scalar_one_or_none()
        if action:
            return ActionResponse(
                id=action.id,
                reference_number=action.reference_number,
                title=action.title,
                description=action.description,
                action_type=action.action_type or "corrective",
                priority=action.priority or "medium",
                status=action.status.value if hasattr(action.status, "value") else str(action.status),
                due_date=action.due_date,
                completed_at=action.completed_at,
                source_type="complaint",
                source_id=action.complaint_id,
                owner_id=action.owner_id,
                owner_email=None,
                created_at=action.created_at,
            )

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Action not found",
    )
