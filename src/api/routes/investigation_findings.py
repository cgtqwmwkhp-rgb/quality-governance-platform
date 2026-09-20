"""Findings rows for an investigation run (INV-C7 / DEC-3).

Mounted under the same ``/investigations`` prefix as ``investigations.py`` but kept
in its own module: that file owns the run lifecycle and the timeline (INV-C9), and
findings are a child collection with their own lifecycle.

Authorisation
-------------
All five endpoints declare ``investigation:update``, and then run the same
tenant-and-involvement check every other by-id investigation endpoint runs
(``_get_investigation_or_404``: cross-tenant is refused outright, in-tenant but
not-yours is a 404).

The read is gated on the write token rather than on a new ``investigation:view``
one **because a new token is granted to nobody**. ``User.has_permission`` is exact
set membership against the tokens stored on a role, and nothing seeds roles from
``src/domain/authz/catalogue.py`` — the admin grant proposed there is a reviewable
document awaiting a human decision, not a migration. Introducing
``investigation:view`` would therefore
make the findings panel 403 for every non-superuser on the day it shipped. The
catalogue also records that no investigation read token is enforced anywhere
today (``investigation:read`` is RESERVED with exactly that reason), so inventing
one for this collection alone would be a control that is honest nowhere else.
``investigation:update`` is held by anyone who can already save the workspace,
which is who this editor is for. Leaving the read on ``CurrentUser`` alone was not
an option: ``AUTHENTICATED_ONLY_DEBT`` is at its ceiling.

The consequence, recorded rather than hidden: a caller who may read an
investigation but not update it can no longer see findings on this page. The
concatenated string is still on the run payload and in the generated pack.
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import DbSession, require_permission

# Imported, not re-implemented. These two carry the investigation tenancy contract
# (#1382/#1389): cross-tenant is refused under TENANT_ACCESS_DENIED *before* roles
# are consulted, and an in-tenant run the caller is not named on is a 404. A second
# copy of that logic in this module is a second thing to keep in step, and the
# failure mode of it drifting is a cross-tenant read.
from src.api.routes.investigations import _get_investigation_or_404
from src.api.schemas.investigation_finding import (
    InvestigationFindingCreate,
    InvestigationFindingListResponse,
    InvestigationFindingReorderRequest,
    InvestigationFindingUpdate,
)
from src.api.utils.tenant import require_tenant_id
from src.domain.exceptions import BadRequestError, NotFoundError
from src.domain.models.investigation import InvestigationRun
from src.domain.models.user import User
from src.domain.services.investigation_findings_service import InvestigationFindingsService

logger = logging.getLogger(__name__)

router = APIRouter()


async def _list_payload(
    db: AsyncSession,
    investigation: InvestigationRun,
    tenant_id: int,
) -> dict:
    """Serialise the run's findings plus the string the legacy readers will see."""
    rows, findings_text = await InvestigationFindingsService.snapshot(
        db, investigation=investigation, tenant_id=tenant_id
    )
    return {
        "items": [
            {
                "id": row.id,
                "investigation_id": row.investigation_id,
                "body": row.body,
                "sort_order": row.sort_order,
                "created_by_id": row.created_by_id,
                "created_at": row.created_at,
                "updated_at": row.updated_at,
            }
            for row in rows
        ],
        "total": len(rows),
        "investigation_id": int(investigation.id),
        "findings_text": findings_text,
    }


@router.get(
    "/{investigation_id:int}/findings",
    response_model=InvestigationFindingListResponse,
)
async def list_investigation_findings(
    investigation_id: int,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("investigation:update"))],
):
    """List one run's findings, in order.

    First call for a run with no rows converts the legacy ``data.findings`` string
    into rows and commits that conversion — a read that writes, once, deliberately.
    The alternative (returning derived rows the client must adopt on first edit)
    gives every client a second way to create findings and a second way to create
    them twice. It is idempotent: the conversion only fires at zero rows, under a
    row lock on the run, so a second reader waits and then finds the rows.

    An empty list is a successful answer, not a 404.
    """
    investigation = await _get_investigation_or_404(investigation_id, db, current_user)
    tenant_id = int(investigation.tenant_id)

    created = await InvestigationFindingsService.ensure_converted(
        db,
        investigation=investigation,
        tenant_id=tenant_id,
        actor_id=getattr(current_user, "id", None),
    )
    payload = await _list_payload(db, investigation, tenant_id)
    if created:
        await db.commit()
        logger.info(
            "investigation_findings_converted",
            extra={"investigation_id": investigation_id, "rows": len(created)},
        )
    return payload


@router.post(
    "/{investigation_id:int}/findings",
    response_model=InvestigationFindingListResponse,
    status_code=201,
)
async def create_investigation_finding(
    investigation_id: int,
    payload: InvestigationFindingCreate,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("investigation:update"))],
):
    """Append a finding.

    Returns the whole ordered list, as every mutation here does: ``sort_order`` is
    assigned by the server, so a client that only received the new row would have
    to guess where it landed.
    """
    investigation = await _get_investigation_or_404(investigation_id, db, current_user)
    tenant_id = int(investigation.tenant_id)

    await InvestigationFindingsService.create_finding(
        db,
        investigation=investigation,
        tenant_id=tenant_id,
        body=payload.body,
        actor_id=getattr(current_user, "id", None),
    )
    result = await _list_payload(db, investigation, tenant_id)
    await db.commit()
    return result


@router.patch(
    "/{investigation_id:int}/findings/{finding_id:int}",
    response_model=InvestigationFindingListResponse,
)
async def update_investigation_finding(
    investigation_id: int,
    finding_id: int,
    payload: InvestigationFindingUpdate,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("investigation:update"))],
):
    """Rewrite one finding's text."""
    investigation = await _get_investigation_or_404(investigation_id, db, current_user)
    tenant_id = int(investigation.tenant_id)

    row = await InvestigationFindingsService.update_finding(
        db,
        investigation=investigation,
        tenant_id=tenant_id,
        finding_id=finding_id,
        body=payload.body,
        actor_id=getattr(current_user, "id", None),
    )
    if row is None:
        raise NotFoundError(f"Finding with ID {finding_id} not found on investigation {investigation_id}")
    result = await _list_payload(db, investigation, tenant_id)
    await db.commit()
    return result


@router.delete(
    "/{investigation_id:int}/findings/{finding_id:int}",
    response_model=InvestigationFindingListResponse,
)
async def delete_investigation_finding(
    investigation_id: int,
    finding_id: int,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("investigation:update"))],
):
    """Remove one finding. Deleting the last one leaves a valid empty list."""
    investigation = await _get_investigation_or_404(investigation_id, db, current_user)
    tenant_id = int(investigation.tenant_id)

    removed = await InvestigationFindingsService.delete_finding(
        db,
        investigation=investigation,
        tenant_id=tenant_id,
        finding_id=finding_id,
    )
    if not removed:
        raise NotFoundError(f"Finding with ID {finding_id} not found on investigation {investigation_id}")
    result = await _list_payload(db, investigation, tenant_id)
    await db.commit()
    return result


@router.post(
    "/{investigation_id:int}/findings/reorder",
    response_model=InvestigationFindingListResponse,
)
async def reorder_investigation_findings(
    investigation_id: int,
    payload: InvestigationFindingReorderRequest,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("investigation:update"))],
):
    """Apply a new order to the run's findings.

    ``finding_ids`` must name exactly this run's findings, each once. A list that
    does not is refused with 400 rather than partially applied, because the
    plausible cause is a stale editor and applying it would silently move or lose
    a finding another tab added.
    """
    investigation = await _get_investigation_or_404(investigation_id, db, current_user)
    tenant_id = int(investigation.tenant_id)

    reordered = await InvestigationFindingsService.reorder_findings(
        db,
        investigation=investigation,
        tenant_id=tenant_id,
        finding_ids=payload.finding_ids,
    )
    if reordered is None:
        raise BadRequestError(
            "finding_ids must list exactly this investigation's findings, each once",
            code="INVESTIGATION_FINDINGS_REORDER_MISMATCH",
            details={"investigation_id": investigation_id},
        )
    result = await _list_payload(db, investigation, tenant_id)
    await db.commit()
    return result
