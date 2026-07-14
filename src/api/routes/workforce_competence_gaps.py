"""Workforce competence-gap closed-loop API.

Routes under /api/v1/workforce/competence-gaps/*
"""

from __future__ import annotations

import logging
from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from src.api.dependencies import CurrentUser, DbSession, require_permission
from src.api.utils.tenant import require_tenant_id
from src.domain.models.user import User
from src.domain.services.competence_gap_service import competence_gap_service

router = APIRouter()
logger = logging.getLogger(__name__)


class FromSignalRequest(BaseModel):
    source_type: str = Field(..., description="assessor_case | external_audit_finding | compliance_evidence_link")
    source_id: int
    signal_type: Optional[str] = Field(None, description="competence_gap | nonconformity (required when not inferred)")
    rationale: Optional[str] = None
    confidence: Optional[float] = None


class LinkRequest(BaseModel):
    engineer_id: int
    requirement_id: Optional[int] = None
    ticket_scheme: Optional[str] = None


class CreateCapaRequest(BaseModel):
    owner_id: Optional[int] = None
    owner_email: Optional[str] = None
    due_date: Optional[str] = None
    priority: Optional[str] = None


class ResolveRequest(BaseModel):
    notes: Optional[str] = None
    dismiss: bool = False
    close_capa: bool = True


def _tenant_id_for(user: User) -> int:
    return require_tenant_id(getattr(user, "tenant_id", None))


def _http_from_exc(exc: Exception) -> HTTPException:
    if isinstance(exc, LookupError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, ValueError):
        return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    logger.exception("Unexpected competence gap error")
    return HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal error")


@router.post("/from-signal", status_code=status.HTTP_201_CREATED)
async def create_from_signal(
    body: FromSignalRequest,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("audit:create"))],
) -> dict[str, Any]:
    """Create competence_gap_actions from Assessor / evidence signal (idempotent)."""
    tenant_id = _tenant_id_for(current_user)
    try:
        gap = await competence_gap_service.from_signal(
            db,
            tenant_id=tenant_id,
            created_by_id=current_user.id,
            source_type=body.source_type,
            source_id=body.source_id,
            signal_type=body.signal_type,
            rationale=body.rationale,
            confidence=body.confidence,
        )
    except (LookupError, ValueError) as exc:
        raise _http_from_exc(exc) from exc
    return competence_gap_service.serialize(gap)


@router.get("")
async def list_competence_gaps(
    db: DbSession,
    current_user: CurrentUser,
    status_filter: Optional[str] = Query(None, alias="status"),
) -> list[dict[str, Any]]:
    """HSEQ inbox of competence gap actions."""
    tenant_id = _tenant_id_for(current_user)
    gaps = await competence_gap_service.list_gaps(db, tenant_id=tenant_id, status=status_filter)
    return [competence_gap_service.serialize(g) for g in gaps]


@router.get("/{gap_id}")
async def get_competence_gap(
    gap_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> dict[str, Any]:
    tenant_id = _tenant_id_for(current_user)
    try:
        gap = await competence_gap_service.get_gap(db, gap_id=gap_id, tenant_id=tenant_id)
    except LookupError as exc:
        raise _http_from_exc(exc) from exc
    return competence_gap_service.serialize(gap)


@router.post("/{gap_id}/link")
async def link_competence_gap(
    gap_id: int,
    body: LinkRequest,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("audit:create"))],
) -> dict[str, Any]:
    tenant_id = _tenant_id_for(current_user)
    try:
        gap = await competence_gap_service.get_gap(db, gap_id=gap_id, tenant_id=tenant_id)
        gap = await competence_gap_service.link_engineer(
            db,
            gap=gap,
            tenant_id=tenant_id,
            actor_id=current_user.id,
            engineer_id=body.engineer_id,
            requirement_id=body.requirement_id,
            ticket_scheme=body.ticket_scheme,
        )
    except (LookupError, ValueError) as exc:
        raise _http_from_exc(exc) from exc
    return competence_gap_service.serialize(gap)


@router.post("/{gap_id}/create-capa")
async def create_capa_for_gap(
    gap_id: int,
    body: CreateCapaRequest,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("audit:create"))],
) -> dict[str, Any]:
    tenant_id = _tenant_id_for(current_user)
    try:
        gap = await competence_gap_service.get_gap(db, gap_id=gap_id, tenant_id=tenant_id)
        capa = await competence_gap_service.create_capa(
            db,
            gap=gap,
            tenant_id=tenant_id,
            created_by_id=current_user.id,
            owner_id=body.owner_id,
            owner_email=body.owner_email,
            due_date=body.due_date,
            priority=body.priority,
        )
        gap = await competence_gap_service.get_gap(db, gap_id=gap_id, tenant_id=tenant_id)
    except (LookupError, ValueError) as exc:
        raise _http_from_exc(exc) from exc
    return {
        "gap": competence_gap_service.serialize(gap),
        "action": competence_gap_service.serialize_capa(capa),
    }


@router.post("/{gap_id}/resolve")
async def resolve_competence_gap(
    gap_id: int,
    body: ResolveRequest,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("audit:create"))],
) -> dict[str, Any]:
    tenant_id = _tenant_id_for(current_user)
    try:
        gap = await competence_gap_service.get_gap(db, gap_id=gap_id, tenant_id=tenant_id)
        gap = await competence_gap_service.resolve(
            db,
            gap=gap,
            tenant_id=tenant_id,
            resolved_by_id=current_user.id,
            notes=body.notes,
            dismiss=body.dismiss,
            close_capa=body.close_capa,
        )
    except (LookupError, ValueError) as exc:
        raise _http_from_exc(exc) from exc
    return competence_gap_service.serialize(gap)


@router.get("/{gap_id}/golden-thread")
async def get_golden_thread(
    gap_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> dict[str, Any]:
    """Ordered auditor pack for a competence gap."""
    tenant_id = _tenant_id_for(current_user)
    try:
        gap = await competence_gap_service.get_gap(db, gap_id=gap_id, tenant_id=tenant_id)
        return await competence_gap_service.golden_thread(db, gap=gap, tenant_id=tenant_id)
    except LookupError as exc:
        raise _http_from_exc(exc) from exc
