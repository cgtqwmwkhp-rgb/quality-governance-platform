"""CAPA (Corrective and Preventive Action) API routes."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import CurrentUser, DbSession
from src.domain.models.capa import CAPAAction, CAPAPriority, CAPASource, CAPAStatus, CAPAType
from src.domain.services.reference_number import ReferenceNumberService

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


class CAPAStatusTransition(BaseModel):
    status: CAPAStatus
    comment: str | None = None


@router.get("")
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
    query = select(CAPAAction)

    if status_filter:
        query = query.where(CAPAAction.status == status_filter)
    if capa_type:
        query = query.where(CAPAAction.capa_type == capa_type)
    if priority:
        query = query.where(CAPAAction.priority == priority)
    if source_type:
        query = query.where(CAPAAction.source_type == source_type)
    if overdue_only:
        query = query.where(
            CAPAAction.due_date < datetime.utcnow(),
            CAPAAction.status.notin_([CAPAStatus.CLOSED]),
        )

    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar_one()

    offset = (page - 1) * page_size
    query = query.order_by(CAPAAction.created_at.desc()).offset(offset).limit(page_size)
    result = await db.execute(query)
    items = result.scalars().all()

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": (total + page_size - 1) // page_size if total > 0 else 0,
    }


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_capa_action(
    db: DbSession,
    current_user: CurrentUser,
    data: CAPACreate,
):
    ref = await ReferenceNumberService.generate(db, "capa", CAPAAction)
    action = CAPAAction(
        reference_number=ref,
        created_by_id=current_user.id,
        tenant_id=getattr(current_user, "tenant_id", None),
        **data.model_dump(),
    )
    db.add(action)
    await db.commit()
    await db.refresh(action)
    return action


@router.get("/stats")
async def get_capa_stats(
    db: DbSession,
    current_user: CurrentUser,
):
    total = await db.execute(select(func.count(CAPAAction.id)))
    open_count = await db.execute(select(func.count(CAPAAction.id)).where(CAPAAction.status == CAPAStatus.OPEN))
    in_progress = await db.execute(select(func.count(CAPAAction.id)).where(CAPAAction.status == CAPAStatus.IN_PROGRESS))
    overdue = await db.execute(
        select(func.count(CAPAAction.id)).where(
            CAPAAction.due_date < datetime.utcnow(),
            CAPAAction.status.notin_([CAPAStatus.CLOSED]),
        )
    )
    return {
        "total": total.scalar_one(),
        "open": open_count.scalar_one(),
        "in_progress": in_progress.scalar_one(),
        "overdue": overdue.scalar_one(),
    }


@router.get("/{capa_id}")
async def get_capa_action(
    capa_id: int,
    db: DbSession,
    current_user: CurrentUser,
):
    result = await db.execute(select(CAPAAction).where(CAPAAction.id == capa_id))
    action = result.scalar_one_or_none()
    if not action:
        raise HTTPException(status_code=404, detail="CAPA action not found")
    return action


@router.patch("/{capa_id}")
async def update_capa_action(
    capa_id: int,
    db: DbSession,
    current_user: CurrentUser,
    data: CAPAUpdate,
):
    result = await db.execute(select(CAPAAction).where(CAPAAction.id == capa_id))
    action = result.scalar_one_or_none()
    if not action:
        raise HTTPException(status_code=404, detail="CAPA action not found")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(action, key, value)
    action.updated_at = datetime.utcnow()

    await db.commit()
    await db.refresh(action)
    return action


@router.post("/{capa_id}/transition")
async def transition_capa_status(
    capa_id: int,
    db: DbSession,
    current_user: CurrentUser,
    data: CAPAStatusTransition,
):
    result = await db.execute(select(CAPAAction).where(CAPAAction.id == capa_id))
    action = result.scalar_one_or_none()
    if not action:
        raise HTTPException(status_code=404, detail="CAPA action not found")

    valid_transitions = {
        CAPAStatus.OPEN: [CAPAStatus.IN_PROGRESS],
        CAPAStatus.IN_PROGRESS: [CAPAStatus.VERIFICATION, CAPAStatus.OPEN],
        CAPAStatus.VERIFICATION: [CAPAStatus.CLOSED, CAPAStatus.IN_PROGRESS],
        CAPAStatus.OVERDUE: [CAPAStatus.IN_PROGRESS, CAPAStatus.CLOSED],
    }

    current = action.status
    if data.status not in valid_transitions.get(current, []):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot transition from {current} to {data.status}",
        )

    action.status = data.status
    if data.status == CAPAStatus.VERIFICATION:
        action.completed_at = datetime.utcnow()
    elif data.status == CAPAStatus.CLOSED:
        action.verified_at = datetime.utcnow()
        action.verified_by_id = current_user.id

    await db.commit()
    await db.refresh(action)
    return action


@router.delete("/{capa_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_capa_action(
    capa_id: int,
    db: DbSession,
    current_user: CurrentUser,
):
    result = await db.execute(select(CAPAAction).where(CAPAAction.id == capa_id))
    action = result.scalar_one_or_none()
    if not action:
        raise HTTPException(status_code=404, detail="CAPA action not found")
    await db.delete(action)
    await db.commit()
