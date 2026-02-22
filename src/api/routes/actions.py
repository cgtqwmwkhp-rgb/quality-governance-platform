"""Unified Actions API routes — thin controller layer."""

import logging
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.domain.exceptions import ConflictError, NotFoundError, ValidationError
from pydantic import BaseModel, Field, field_validator

from src.api.dependencies import CurrentUser, DbSession, require_permission
from src.api.schemas.error_codes import ErrorCode
from src.api.schemas.validators import sanitize_field
from src.domain.models.user import User
from src.domain.services.action_service import ActionService

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

    @field_validator("title", "description", "action_type", "priority", mode="before")
    @classmethod
    def _sanitize(cls, v):
        return sanitize_field(v)


class ActionCreate(ActionBase):
    """Schema for creating an action."""

    source_type: str = Field(..., description="Type of source entity: incident, rta, or complaint")
    source_id: int = Field(..., description="ID of the source entity")
    assigned_to_email: Optional[str] = Field(None, description="Email of user to assign to")

    @field_validator("source_type", "assigned_to_email", mode="before")
    @classmethod
    def _sanitize_create(cls, v):
        return sanitize_field(v)


class ActionUpdate(BaseModel):
    """Schema for updating an action. All fields are optional."""

    title: Optional[str] = Field(None, max_length=300)
    description: Optional[str] = None
    action_type: Optional[str] = None
    priority: Optional[str] = None
    status: Optional[str] = Field(
        None, description="One of: open, in_progress, pending_verification, completed, cancelled"
    )
    due_date: Optional[str] = Field(None, description="Due date in ISO format (YYYY-MM-DD)")
    assigned_to_email: Optional[str] = Field(None, description="Email of user to assign to")
    completion_notes: Optional[str] = Field(None, description="Notes on completion")

    @field_validator(
        "title",
        "description",
        "action_type",
        "priority",
        "status",
        "assigned_to_email",
        "completion_notes",
        mode="before",
    )
    @classmethod
    def _sanitize(cls, v):
        return sanitize_field(v)


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
    service = ActionService(db)
    result = await service.list_actions(
        tenant_id=current_user.tenant_id,
        page=page,
        page_size=page_size,
        status_filter=status_filter,
        source_type=source_type,
        source_id=source_id,
    )
    return ActionListResponse(
        items=[ActionResponse(**item) for item in result["items"]],
        total=result["total"],
        page=result["page"],
        page_size=result["page_size"],
        pages=result["pages"],
    )


@router.post("/", response_model=ActionResponse, status_code=status.HTTP_201_CREATED)
async def create_action(
    action_data: ActionCreate,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("action:create"))],
) -> ActionResponse:
    """Create a new action for an incident, RTA, complaint, or investigation."""
    service = ActionService(db)
    try:
        result = await service.create_action(
            source_type=action_data.source_type,
            source_id=action_data.source_id,
            title=action_data.title,
            description=action_data.description,
            action_type=action_data.action_type,
            priority=action_data.priority,
            due_date_str=action_data.due_date,
            assigned_to_email=action_data.assigned_to_email,
            user_id=current_user.id,
            tenant_id=current_user.tenant_id,
        )
    except ValueError as e:
        msg = str(e)
        if "Duplicate" in msg:
            raise ConflictError(ErrorCode.DUPLICATE_ENTITY)
        raise ValidationError(ErrorCode.VALIDATION_ERROR)
    except LookupError:
        raise NotFoundError(ErrorCode.ENTITY_NOT_FOUND)
    except Exception:
        logger.exception("Unexpected error creating action")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ErrorCode.INTERNAL_ERROR,
        )
    return ActionResponse(**result)


@router.get("/{action_id}", response_model=ActionResponse)
async def get_action(
    action_id: int,
    db: DbSession,
    current_user: CurrentUser,
    source_type: str = Query(..., description="Type of source: incident, rta, complaint, or investigation"),
) -> ActionResponse:
    """Get a specific action by ID."""
    service = ActionService(db)
    try:
        result = await service.get_action(action_id, source_type, current_user.tenant_id)
    except (LookupError, ValueError):
        raise NotFoundError(ErrorCode.ENTITY_NOT_FOUND)
    return ActionResponse(**result)


@router.patch("/{action_id}", response_model=ActionResponse)
async def update_action(
    action_id: int,
    action_data: ActionUpdate,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("action:update"))],
    source_type: str = Query(..., description="Type of source: incident, rta, complaint, or investigation"),
) -> ActionResponse:
    """Update an existing action by ID."""
    service = ActionService(db)
    try:
        result = await service.update_action(
            action_id,
            source_type,
            tenant_id=current_user.tenant_id,
            title=action_data.title,
            description=action_data.description,
            action_type=action_data.action_type,
            priority=action_data.priority,
            status_value=action_data.status,
            due_date_str=action_data.due_date,
            assigned_to_email=action_data.assigned_to_email,
            completion_notes=action_data.completion_notes,
        )
    except ValueError:
        raise ValidationError(ErrorCode.VALIDATION_ERROR)
    except LookupError:
        raise NotFoundError(ErrorCode.ENTITY_NOT_FOUND)
    return ActionResponse(**result)
