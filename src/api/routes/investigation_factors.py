"""ICAM contributing factors for an investigation run (INV-C12 / DEC-1).

Mounted under the same ``/investigations`` prefix as ``investigations.py`` but
kept in its own module, the way INV-C7 findings and INV-C10 RCA are: that file
owns the run lifecycle and the timeline, and contributing factors are a child
collection with their own lifecycle. Every path here carries the literal
``/factors`` segment, so nothing in the run router can shadow it and it can
shadow nothing there.

Authorisation matches INV-C7 and INV-C10: every endpoint declares
``investigation:update``, then runs ``_get_investigation_or_404`` (cross-tenant
is ``TENANT_ACCESS_DENIED`` before roles are consulted; in-tenant but not-yours
is a 404). The read is gated on the write token because a new
``investigation:view`` token is granted to nobody — see
``investigation_findings.py`` for the full reasoning — and
``AUTHENTICATED_ONLY_DEBT`` is at its ceiling, so ``CurrentUser`` alone is not
an option.

Every mutation answers with the whole ordered list, as findings do: category
order is the server's, so a client that only received the new row would have to
guess where it landed.
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, status

from src.api.dependencies import DbSession, require_permission
from src.api.routes.investigations import _get_investigation_or_404
from src.api.schemas.investigation_factor import (
    InvestigationFactorCreate,
    InvestigationFactorListResponse,
    InvestigationFactorUpdate,
)
from src.domain.exceptions import AuthorizationError, NotFoundError
from src.domain.models.investigation import InvestigationRun
from src.domain.models.user import User
from src.domain.services.investigation_factors_service import InvestigationFactorsService

logger = logging.getLogger(__name__)

router = APIRouter()


def _tenant_id_or_none(investigation) -> int | None:
    raw = getattr(investigation, "tenant_id", None)
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


async def _list_payload(db, investigation: InvestigationRun, tenant_id: int) -> dict:
    """Serialise the run's factors plus the text the legacy readers will see."""
    snapshot = await InvestigationFactorsService.snapshot(db, investigation=investigation, tenant_id=tenant_id)
    return {
        "items": [factor.as_payload() for factor in snapshot.factors],
        "total": len(snapshot.factors),
        "investigation_id": int(investigation.id),
        "diagram_id": snapshot.diagram_id,
        "contributing_factors_text": snapshot.text,
        "unmapped_categories": snapshot.unmapped_categories,
        "unreadable_total": snapshot.unreadable_total,
    }


@router.get(
    "/{investigation_id:int}/factors",
    response_model=InvestigationFactorListResponse,
)
async def list_investigation_factors(
    investigation_id: int,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("investigation:update"))],
):
    """List one run's ICAM contributing factors, in category order.

    Reads only. Unlike findings and RCA there is no legacy string to convert
    here: the leftover ``contributing_factors`` paragraph is one box of prose,
    and splitting it into categorised factors would mean this endpoint deciding
    which ICAM category somebody else's sentence belongs to. It stays where it
    is and is overwritten from the factors once there are any.

    An empty list is a successful answer, not a 404, and a run whose tenant is
    missing reads as empty rather than 500.
    """
    investigation = await _get_investigation_or_404(investigation_id, db, current_user)
    tenant_id = _tenant_id_or_none(investigation)
    if tenant_id is None:
        return {
            "items": [],
            "total": 0,
            "investigation_id": investigation_id,
            "diagram_id": None,
            "contributing_factors_text": "",
            "unmapped_categories": [],
            "unreadable_total": 0,
        }
    return await _list_payload(db, investigation, tenant_id)


@router.post(
    "/{investigation_id:int}/factors",
    response_model=InvestigationFactorListResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_investigation_factor(
    investigation_id: int,
    payload: InvestigationFactorCreate,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("investigation:update"))],
):
    """Add one factor under one ICAM category.

    Empty factor text is a 422 from the schema — no factor is created with
    words the server chose. A missing tenant is a refused write, not a 500 and
    not a factor filed nowhere.
    """
    investigation = await _get_investigation_or_404(investigation_id, db, current_user)
    tenant_id = _tenant_id_or_none(investigation)
    if tenant_id is None:
        raise AuthorizationError("Investigation is missing a tenant and cannot store contributing factors")

    created = await InvestigationFactorsService.create_factor(
        db,
        investigation=investigation,
        tenant_id=tenant_id,
        category=payload.category,
        cause=payload.cause,
        sub_causes=payload.sub_causes,
        depth=payload.depth,
        actor_id=getattr(current_user, "id", None),
    )
    if created is None:
        raise AuthorizationError("Contributing factors cannot be stored for this tenant")
    result = await _list_payload(db, investigation, tenant_id)
    await db.commit()
    logger.info(
        "investigation_factor_created",
        extra={"investigation_id": investigation_id, "factor_id": created.id},
    )
    return result


@router.patch(
    "/{investigation_id:int}/factors/{factor_id:int}",
    response_model=InvestigationFactorListResponse,
)
async def update_investigation_factor(
    investigation_id: int,
    factor_id: int,
    payload: InvestigationFactorUpdate,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("investigation:update"))],
):
    """Change one factor's category, text, sub-causes or depth."""
    investigation = await _get_investigation_or_404(investigation_id, db, current_user)
    tenant_id = _tenant_id_or_none(investigation)
    if tenant_id is None:
        raise AuthorizationError("Investigation is missing a tenant and cannot store contributing factors")

    updated = await InvestigationFactorsService.update_factor(
        db,
        investigation=investigation,
        tenant_id=tenant_id,
        factor_id=factor_id,
        category=payload.category,
        cause=payload.cause,
        sub_causes=payload.sub_causes,
        depth=payload.depth,
        clear_depth=payload.clears_depth,
        actor_id=getattr(current_user, "id", None),
    )
    if updated is None:
        raise NotFoundError(f"Contributing factor with ID {factor_id} not found on investigation {investigation_id}")
    result = await _list_payload(db, investigation, tenant_id)
    await db.commit()
    return result


@router.delete(
    "/{investigation_id:int}/factors/{factor_id:int}",
    response_model=InvestigationFactorListResponse,
)
async def delete_investigation_factor(
    investigation_id: int,
    factor_id: int,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("investigation:update"))],
):
    """Remove one factor. Deleting the last one leaves a valid empty list."""
    investigation = await _get_investigation_or_404(investigation_id, db, current_user)
    tenant_id = _tenant_id_or_none(investigation)
    if tenant_id is None:
        raise AuthorizationError("Investigation is missing a tenant and cannot store contributing factors")

    removed = await InvestigationFactorsService.delete_factor(
        db,
        investigation=investigation,
        tenant_id=tenant_id,
        factor_id=factor_id,
        actor_id=getattr(current_user, "id", None),
    )
    if not removed:
        raise NotFoundError(f"Contributing factor with ID {factor_id} not found on investigation {investigation_id}")
    result = await _list_payload(db, investigation, tenant_id)
    await db.commit()
    return result
