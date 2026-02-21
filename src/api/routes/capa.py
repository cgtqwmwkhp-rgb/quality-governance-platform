"""CAPA (Corrective and Preventive Action) API routes — thin controller layer."""

from datetime import datetime, timezone
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator

from src.api.dependencies import CurrentSuperuser, CurrentUser, DbSession, require_permission
from src.api.schemas.capa import CAPAListResponse, CAPAResponse, CAPAStatsResponse
from src.api.schemas.error_codes import ErrorCode
from src.api.schemas.validators import sanitize_field
from src.domain.models.capa import CAPAPriority, CAPASource, CAPAStatus, CAPAType
from src.domain.models.user import User
from src.domain.services.capa_service import CAPAService

try:
    from opentelemetry import trace

    tracer = trace.get_tracer(__name__)
except ImportError:
    tracer = None  # type: ignore[assignment]  # TYPE-IGNORE: optional-dependency

router = APIRouter()


class CAPACreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    capa_type: CAPAType
    priority: CAPAPriority = CAPAPriority.MEDIUM
    source_type: CAPASource | None = None
    source_id: int | None = None
    root_cause: str | None = None
    proposed_action: str | None = None
    verification_method: str | None = None
    effectiveness_criteria: str | None = None
    assigned_to_id: int | None = None
    due_date: datetime | None = None
    iso_standard: str | None = None
    clause_reference: str | None = None

    @field_validator(
        "title",
        "description",
        "root_cause",
        "proposed_action",
        "verification_method",
        "effectiveness_criteria",
        "iso_standard",
        "clause_reference",
        mode="before",
    )
    @classmethod
    def _sanitize(cls, v):
        return sanitize_field(v)


class CAPAUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    priority: CAPAPriority | None = None
    root_cause: str | None = None
    proposed_action: str | None = None
    verification_method: str | None = None
    verification_result: str | None = None
    effectiveness_criteria: str | None = None
    assigned_to_id: int | None = None
    due_date: datetime | None = None

    @field_validator(
        "title",
        "description",
        "root_cause",
        "proposed_action",
        "verification_method",
        "verification_result",
        "effectiveness_criteria",
        mode="before",
    )
    @classmethod
    def _sanitize(cls, v):
        return sanitize_field(v)


class CAPAStatusTransition(BaseModel):
    status: CAPAStatus
    comment: str | None = None

    @field_validator("comment", mode="before")
    @classmethod
    def _sanitize(cls, v):
        return sanitize_field(v)


@router.get("", response_model=CAPAListResponse)
async def list_capa_actions(
    db: DbSession,
    current_user: CurrentUser,
    status_filter: Optional[CAPAStatus] = Query(None, alias="status"),
    capa_type: Optional[CAPAType] = Query(None),
    priority: Optional[CAPAPriority] = Query(None),
    source_type: Optional[CAPASource] = Query(None),
    overdue_only: bool = Query(False),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    service = CAPAService(db)
    return await service.list_capa_actions(
        tenant_id=current_user.tenant_id,
        page=page,
        page_size=page_size,
        status_filter=status_filter,
        capa_type=capa_type,
        priority=priority,
        source_type=source_type,
        overdue_only=overdue_only,
    )


@router.post("", response_model=CAPAResponse, status_code=status.HTTP_201_CREATED)
async def create_capa_action(
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("capa:create"))],
    data: CAPACreate,
):
    _span = tracer.start_span("create_capa") if tracer else None
    if _span:
        _span.set_attribute("tenant_id", str(getattr(current_user, "tenant_id", 0) or 0))

    service = CAPAService(db)
    action = await service.create_capa_action(
        data=data,
        user_id=current_user.id,
        tenant_id=getattr(current_user, "tenant_id", None),
    )

    if _span:
        _span.end()
    return action


@router.get("/stats", response_model=CAPAStatsResponse)
async def get_capa_stats(
    db: DbSession,
    current_user: CurrentUser,
):
    service = CAPAService(db)
    return await service.get_stats(current_user.tenant_id)


@router.get("/{capa_id}", response_model=CAPAResponse)
async def get_capa_action(
    capa_id: int,
    db: DbSession,
    current_user: CurrentUser,
):
    service = CAPAService(db)
    try:
        return await service.get_capa_action(capa_id, current_user.tenant_id)
    except LookupError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorCode.ENTITY_NOT_FOUND,
        )


@router.patch("/{capa_id}", response_model=CAPAResponse)
async def update_capa_action(
    capa_id: int,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("capa:update"))],
    data: CAPAUpdate,
):
    service = CAPAService(db)
    try:
        return await service.update_capa_action(capa_id, data, tenant_id=current_user.tenant_id)
    except LookupError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorCode.ENTITY_NOT_FOUND,
        )


@router.post("/{capa_id}/transition", response_model=CAPAResponse)
async def transition_capa_status(
    capa_id: int,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("capa:update"))],
    data: CAPAStatusTransition,
):
    service = CAPAService(db)
    try:
        return await service.transition_status(
            capa_id,
            data.status,
            user_id=current_user.id,
            tenant_id=current_user.tenant_id,
            comment=data.comment,
        )
    except LookupError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorCode.ENTITY_NOT_FOUND,
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorCode.INVALID_STATE_TRANSITION,
        )


@router.delete("/{capa_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_capa_action(
    capa_id: int,
    db: DbSession,
    current_user: CurrentSuperuser,
):
    service = CAPAService(db)
    try:
        await service.delete_capa_action(
            capa_id,
            user_id=current_user.id,
            tenant_id=current_user.tenant_id,
        )
    except LookupError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorCode.ENTITY_NOT_FOUND,
        )
