"""Tenant-scoped matter legal-hold register API.

This route records hold instructions and the Register documents each matter
covers.  Since WC-1 the document lifecycle enforces them: revise, submit,
approve, reject, publish, obsolete and disposal all refuse while a matter is
held (``src/domain/services/legal_hold_enforcement.py``).  It still does not
claim that every retention worker or asset purge path consumes them — that
boundary remains as the privacy API discloses it.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from src.api.dependencies import DbSession, require_permission
from src.api.utils.tenant import require_tenant_id
from src.domain.exceptions import NotFoundError
from src.domain.models.document import Document
from src.domain.models.legal_hold import LegalHoldStatus, MatterLegalHold
from src.domain.models.user import User
from src.domain.services.audit_service import record_audit_event
from src.domain.services.legal_hold_enforcement import active_hold_for_document

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


class DocumentHoldScopeRequest(BaseModel):
    """Which matter a Register document is filed under.

    ``extra="forbid"`` so a misspelled field cannot leave a document outside every
    hold while the call reports 200 (B-10).
    """

    model_config = ConfigDict(extra="forbid")

    matter_reference: str | None = Field(default=None, max_length=128)


class DocumentHoldScopeResponse(BaseModel):
    document_id: int
    matter_reference: str | None
    legal_hold_active: bool
    legal_hold_id: int | None


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


@router.put("/documents/{document_id}", response_model=DocumentHoldScopeResponse)
async def set_document_hold_scope(
    document_id: int,
    data: DocumentHoldScopeRequest,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("admin:manage"))],
) -> DocumentHoldScopeResponse:
    """File a Register document under a legal matter, or clear it.

    Guarded by ``admin:manage`` rather than ``document:update`` on purpose: the
    matter a record is filed under decides whether the record can be changed at
    all, so it must not be writable by the same permission the write it blocks
    uses. It is also why this lives on the hold register rather than on the
    document PATCH — that writer is refused outright while a hold is active, and
    a field that can release its own brake is not a control.

    Clearing (``matter_reference: null``) is allowed while a hold is active: a
    document can be genuinely out of scope of a matter, and the alternative is
    that a mis-filing can never be corrected. Because that is the one call that
    can take a record out from under a hold, both directions are written to the
    audit trail with the before and after matter — otherwise the only trace of
    who unfroze a record would be its absence.
    """
    tenant_id = _tenant_id_for(current_user)
    document = await db.scalar(select(Document).where(Document.id == document_id, Document.tenant_id == tenant_id))
    if document is None:
        raise NotFoundError(
            f"Register document {document_id} was not found in this tenant.",
            details={"document_id": document_id},
        )

    raw = data.matter_reference
    trimmed = raw.strip() if isinstance(raw, str) else None
    previous = document.legal_matter_reference
    document.legal_matter_reference = trimmed or None
    await db.flush()

    await record_audit_event(
        db=db,
        event_type="document.legal_hold_scope_changed",
        entity_type="document",
        entity_id=str(document.id),
        entity_name=document.title,
        action="update",
        description=(
            f"Filed document under legal matter '{document.legal_matter_reference}'"
            if document.legal_matter_reference
            else "Removed document from legal matter scope"
        ),
        payload={
            "actor_id": current_user.id,
            "document_id": document.id,
            "previous_matter_reference": previous,
            "matter_reference": document.legal_matter_reference,
        },
        changed_fields=["legal_matter_reference"],
        user_id=current_user.id,
        tenant_id=tenant_id,
    )

    hold = await active_hold_for_document(db, document)
    return DocumentHoldScopeResponse(
        document_id=document.id,
        matter_reference=document.legal_matter_reference,
        legal_hold_active=hold is not None,
        legal_hold_id=hold.id if hold is not None else None,
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
