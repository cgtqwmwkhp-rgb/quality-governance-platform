"""Training ticket API routes — Workforce Northern Star P0 spine.

First-class statutory / scheme tickets (CSCS, IPAF, Gas Safe, …) with
expiry + verify_state + evidence FK. Prefer this over certifications_json.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select

from src.api.dependencies import CurrentUser, DbSession, require_permission
from src.api.schemas.engineer import (
    TrainingTicketCreate,
    TrainingTicketListResponse,
    TrainingTicketResponse,
    TrainingTicketUpdate,
)
from src.api.utils.tenant import apply_tenant_filter, require_tenant_id
from src.domain.exceptions import AuthorizationError, BadRequestError, NotFoundError
from src.domain.models.engineer import Engineer, TicketVerifyState, TrainingTicket
from src.domain.models.user import User

router = APIRouter()


def _is_workforce_manager(user: CurrentUser) -> bool:
    role_names = {r.name.lower() for r in getattr(user, "roles", []) or []}
    return bool(getattr(user, "is_superuser", False) or "admin" in role_names or "supervisor" in role_names)


def _require_tenant(user: CurrentUser) -> int:
    return require_tenant_id(getattr(user, "tenant_id", None))


def _parse_verify_state(value: str) -> TicketVerifyState:
    try:
        return TicketVerifyState(value)
    except ValueError as exc:
        raise BadRequestError(f"Invalid verify_state: {value}") from exc


async def _get_engineer_or_404(db: DbSession, engineer_id: int, tenant_id: int) -> Engineer:
    query = select(Engineer).where(Engineer.id == engineer_id)
    query = apply_tenant_filter(query, Engineer, tenant_id)
    result = await db.execute(query)
    engineer = result.scalar_one_or_none()
    if engineer is None:
        raise NotFoundError("Engineer not found")
    return engineer


def _assert_ticket_access(user: CurrentUser, engineer: Engineer, *, allow_self: bool = False) -> None:
    if _is_workforce_manager(user):
        return
    if allow_self and engineer.user_id == user.id:
        return
    raise AuthorizationError("You do not have permission to access this training ticket")


@router.get("/", response_model=TrainingTicketListResponse)
async def list_training_tickets(
    db: DbSession,
    user: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=500),
    engineer_id: Optional[int] = None,
    scheme: Optional[str] = None,
    verify_state: Optional[str] = None,
):
    """List training tickets (tenant-scoped)."""
    tenant_id = _require_tenant(user)
    query = select(TrainingTicket)
    query = apply_tenant_filter(query, TrainingTicket, tenant_id)

    if not _is_workforce_manager(user):
        eng_q = select(Engineer.id).where(Engineer.user_id == user.id)
        eng_q = apply_tenant_filter(eng_q, Engineer, tenant_id)
        eng_id = (await db.execute(eng_q)).scalar_one_or_none()
        if eng_id is None:
            return TrainingTicketListResponse(items=[], total=0, page=page, page_size=page_size, pages=0)
        query = query.where(TrainingTicket.engineer_id == eng_id)
    elif engineer_id is not None:
        query = query.where(TrainingTicket.engineer_id == engineer_id)

    if scheme:
        query = query.where(TrainingTicket.scheme.ilike(scheme))
    if verify_state:
        query = query.where(TrainingTicket.verify_state == _parse_verify_state(verify_state))

    total = (await db.scalar(select(func.count()).select_from(query.subquery()))) or 0
    offset = (page - 1) * page_size
    items = (await db.execute(query.order_by(TrainingTicket.id.desc()).offset(offset).limit(page_size))).scalars().all()
    pages = (total + page_size - 1) // page_size if total > 0 else 0
    return TrainingTicketListResponse(
        items=[TrainingTicketResponse.model_validate(t) for t in items],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.post("/", response_model=TrainingTicketResponse, status_code=status.HTTP_201_CREATED)
async def create_training_ticket(
    data: TrainingTicketCreate,
    db: DbSession,
    user: Annotated[User, Depends(require_permission("engineer:update"))],
):
    """Create a training ticket for an engineer."""
    tenant_id = _require_tenant(user)
    if not _is_workforce_manager(user):
        raise AuthorizationError("You do not have permission to create training tickets")
    engineer = await _get_engineer_or_404(db, data.engineer_id, tenant_id)

    ticket = TrainingTicket(
        engineer_id=engineer.id,
        scheme=data.scheme.strip(),
        ticket_number=data.ticket_number.strip(),
        issuer=data.issuer,
        issued_at=data.issued_at,
        expires_at=data.expires_at,
        verify_state=_parse_verify_state(data.verify_state),
        evidence_id=data.evidence_id,
        notes=data.notes,
        tenant_id=tenant_id,
        created_by_id=user.id,
        updated_by_id=user.id,
    )
    if ticket.expires_at is not None and ticket.expires_at <= datetime.now(timezone.utc):
        ticket.verify_state = TicketVerifyState.EXPIRED

    db.add(ticket)
    await db.commit()
    await db.refresh(ticket)
    return TrainingTicketResponse.model_validate(ticket)


@router.get("/{ticket_id}", response_model=TrainingTicketResponse)
async def get_training_ticket(
    ticket_id: int,
    db: DbSession,
    user: CurrentUser,
):
    """Get a training ticket by id."""
    tenant_id = _require_tenant(user)
    query = select(TrainingTicket).where(TrainingTicket.id == ticket_id)
    query = apply_tenant_filter(query, TrainingTicket, tenant_id)
    ticket = (await db.execute(query)).scalar_one_or_none()
    if ticket is None:
        raise NotFoundError("Training ticket not found")
    engineer = await _get_engineer_or_404(db, ticket.engineer_id, tenant_id)
    _assert_ticket_access(user, engineer, allow_self=True)
    return TrainingTicketResponse.model_validate(ticket)


@router.patch("/{ticket_id}", response_model=TrainingTicketResponse)
async def update_training_ticket(
    ticket_id: int,
    data: TrainingTicketUpdate,
    db: DbSession,
    user: Annotated[User, Depends(require_permission("engineer:update"))],
):
    """Update a training ticket."""
    tenant_id = _require_tenant(user)
    query = select(TrainingTicket).where(TrainingTicket.id == ticket_id)
    query = apply_tenant_filter(query, TrainingTicket, tenant_id)
    ticket = (await db.execute(query)).scalar_one_or_none()
    if ticket is None:
        raise NotFoundError("Training ticket not found")
    engineer = await _get_engineer_or_404(db, ticket.engineer_id, tenant_id)
    _assert_ticket_access(user, engineer)

    updates = data.model_dump(exclude_unset=True)
    if "verify_state" in updates and updates["verify_state"] is not None:
        updates["verify_state"] = _parse_verify_state(updates["verify_state"])
    for key, value in updates.items():
        setattr(ticket, key, value)
    if ticket.expires_at is not None and ticket.expires_at <= datetime.now(timezone.utc):
        ticket.verify_state = TicketVerifyState.EXPIRED
    ticket.updated_by_id = user.id
    await db.commit()
    await db.refresh(ticket)
    return TrainingTicketResponse.model_validate(ticket)


@router.delete("/{ticket_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_training_ticket(
    ticket_id: int,
    db: DbSession,
    user: Annotated[User, Depends(require_permission("engineer:update"))],
):
    """Delete a training ticket."""
    tenant_id = _require_tenant(user)
    query = select(TrainingTicket).where(TrainingTicket.id == ticket_id)
    query = apply_tenant_filter(query, TrainingTicket, tenant_id)
    ticket = (await db.execute(query)).scalar_one_or_none()
    if ticket is None:
        raise NotFoundError("Training ticket not found")
    engineer = await _get_engineer_or_404(db, ticket.engineer_id, tenant_id)
    _assert_ticket_access(user, engineer)
    await db.delete(ticket)
    await db.commit()
    return None
