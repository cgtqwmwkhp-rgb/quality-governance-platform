"""Investigation-scoped 5-Whys on ``five_whys_analyses`` (INV-C10).

Mounted under the same ``/investigations`` prefix as ``investigations.py`` but
kept in its own module: that file owns the run lifecycle and the timeline
(INV-C9), and RCA is a child document with its own lifecycle.

Authorisation matches INV-C7 findings: both endpoints declare
``investigation:update``, then run ``_get_investigation_or_404`` (cross-tenant
is ``TENANT_ACCESS_DENIED`` before roles; in-tenant but not-yours is a 404).
The read is gated on the write token because a new ``investigation:view``
token is granted to nobody — see ``investigation_findings.py``.
``AUTHENTICATED_ONLY_DEBT`` is at its ceiling, so ``CurrentUser`` alone is not
an option.

DEC-2 (CAPA per Why) is INV-C11 and is not folded in here.
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends

from src.api.dependencies import DbSession, require_permission
from src.api.routes.investigations import _get_investigation_or_404
from src.api.schemas.investigation_rca import InvestigationRcaResponse, InvestigationRcaUpsert
from src.domain.exceptions import AuthorizationError
from src.domain.models.user import User
from src.domain.services.investigation_rca_service import InvestigationRcaService

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


@router.get(
    "/{investigation_id:int}/rca",
    response_model=InvestigationRcaResponse,
)
async def get_investigation_rca(
    investigation_id: int,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("investigation:update"))],
):
    """Return this run's workspace 5-Whys analysis.

    First call for a run with no tenant-scoped analysis converts leftover
    ``why_1``..``why_5`` strings into ``five_whys_analyses`` and commits that
    conversion — a read that writes, once, deliberately. Empty Whys are a
    successful payload with blank answers, not a 404 and not a 500.
    """
    investigation = await _get_investigation_or_404(investigation_id, db, current_user)
    tenant_id = _tenant_id_or_none(investigation)
    if tenant_id is None:
        return InvestigationRcaService.serialise(investigation, None)

    written = await InvestigationRcaService.ensure_converted(
        db,
        investigation=investigation,
        tenant_id=tenant_id,
        actor_id=getattr(current_user, "id", None),
    )
    payload = await InvestigationRcaService.get_workspace(
        db,
        investigation=investigation,
        tenant_id=tenant_id,
        actor_id=getattr(current_user, "id", None),
    )
    if written is not None:
        await db.commit()
        logger.info(
            "investigation_rca_converted",
            extra={"investigation_id": investigation_id, "analysis_id": payload.get("id")},
        )
    return payload


@router.put(
    "/{investigation_id:int}/rca",
    response_model=InvestigationRcaResponse,
)
async def put_investigation_rca(
    investigation_id: int,
    payload: InvestigationRcaUpsert,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("investigation:update"))],
):
    """Replace this run's workspace 5-Whys analysis and dual-write the legacy strings."""
    investigation = await _get_investigation_or_404(investigation_id, db, current_user)
    tenant_id = _tenant_id_or_none(investigation)
    if tenant_id is None:
        raise AuthorizationError("Investigation is missing a tenant and cannot store RCA")

    result = await InvestigationRcaService.upsert_workspace(
        db,
        investigation=investigation,
        tenant_id=tenant_id,
        problem_statement=payload.problem_statement,
        whys=[item.model_dump() for item in payload.whys],
        root_cause=payload.root_cause,
        contributing_factors=payload.contributing_factors,
        actor_id=getattr(current_user, "id", None),
    )
    if result is None:
        raise AuthorizationError("RCA cannot be stored for this tenant")
    await db.commit()
    return result
