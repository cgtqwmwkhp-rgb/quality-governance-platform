"""Tenant-scoped matter legal-hold register API.

This route records hold instructions only.  It does not claim that every
retention worker or asset purge path already consumes those instructions.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from src.api.dependencies import DbSession, require_permission
from src.api.utils.tenant import require_tenant_id
from src.domain.models.legal_hold import LegalHoldStatus, MatterLegalHold
from src.domain.models.user import User

router = APIRouter()


class MatterLegalHoldCreate(BaseModel):
    matter_reference: str = Field(..., min_length=1, max_length=128)


class MatterLegalHoldResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    matter_reference: str
    status: LegalHoldStatus
    issued_at: datetime
    released_at: datetime | None
    created_at: datetime
    updated_at: datetime


class MatterLegalHoldListResponse(BaseModel):
    items: list[MatterLegalHoldResponse]
    total: int


def _tenant_id_for(user: User) -> int:
    return require_tenant_id(getattr(user, "tenant_id", None))


@router.post("", response_model=MatterLegalHoldResponse, status_code=status.HTTP_201_CREATED)
async def create_matter_legal_hold(
    data: MatterLegalHoldCreate,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("admin:manage"))],
) -> MatterLegalHold:
    """Record an active legal hold for a tenant matter reference."""
    hold = MatterLegalHold(
        tenant_id=_tenant_id_for(current_user),
        matter_reference=data.matter_reference.strip(),
        issued_at=datetime.now(timezone.utc),
        created_by_id=current_user.id,
    )
    db.add(hold)
    await db.flush()
    return hold


@router.get("", response_model=MatterLegalHoldListResponse)
async def list_matter_legal_holds(
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("admin:manage"))],
    matter_reference: str | None = Query(None, min_length=1, max_length=128),
    active_only: bool = True,
) -> MatterLegalHoldListResponse:
    """List this tenant's hold instructions, optionally restricted to active holds."""
    statement = select(MatterLegalHold).where(MatterLegalHold.tenant_id == _tenant_id_for(current_user))
    if matter_reference is not None:
        statement = statement.where(MatterLegalHold.matter_reference == matter_reference.strip())
    if active_only:
        statement = statement.where(MatterLegalHold.status == LegalHoldStatus.ACTIVE)
    result = await db.execute(statement.order_by(MatterLegalHold.id.desc()))
    holds = list(result.scalars().all())
    return MatterLegalHoldListResponse(
        items=[MatterLegalHoldResponse.model_validate(hold) for hold in holds],
        total=len(holds),
    )


@router.post("/{hold_id}/release", response_model=MatterLegalHoldResponse)
async def release_matter_legal_hold(
    hold_id: int,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("admin:manage"))],
) -> MatterLegalHold:
    """Release an active hold; repeat releases are rejected."""
    result = await db.execute(
        select(MatterLegalHold).where(
            MatterLegalHold.id == hold_id,
            MatterLegalHold.tenant_id == _tenant_id_for(current_user),
        )
    )
    hold = result.scalar_one_or_none()
    if hold is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Legal hold not found")
    if hold.status != LegalHoldStatus.ACTIVE:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Legal hold is already released")
    hold.status = LegalHoldStatus.RELEASED
    hold.released_at = datetime.now(timezone.utc)
    hold.released_by_id = current_user.id
    await db.flush()
    return hold
