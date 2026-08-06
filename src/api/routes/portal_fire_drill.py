"""Portal fire-drill capture routes (Wave 3).

Gated by the Compliance Schedule opener + kill switch (same composition as
staff CS routes). When closed, every route returns 404.
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, status

from src.api.dependencies import CurrentUser, DbSession
from src.api.schemas.portal_fire_drill import (
    PortalFireDrillCompleteRequest,
    PortalFireDrillCompleteResponse,
    PortalFireDrillListResponse,
)
from src.api.utils.tenant import require_tenant_id
from src.domain.services.portal_fire_drill_service import PortalFireDrillService
from src.infrastructure.database import async_session_maker

logger = logging.getLogger(__name__)

DISABLED_DETAIL = "Compliance Schedule is not enabled in this environment."

router = APIRouter()


async def compliance_schedule_is_open() -> bool:
    """Whether the module is available. Thin wrapper binding the app's session factory.

    Retained as a module-level name so tests can patch it the same way as the
    staff compliance_schedule router.
    """
    from src.domain.services.compliance_schedule_kill_switch import compliance_schedule_is_open as _domain_is_open

    return await _domain_is_open(async_session_maker)


async def require_compliance_schedule_enabled() -> None:
    from fastapi import HTTPException

    if not await compliance_schedule_is_open():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=DISABLED_DETAIL)


_enabled_router = APIRouter(dependencies=[Depends(require_compliance_schedule_enabled)])


def _tenant(user: CurrentUser) -> int:
    return require_tenant_id(getattr(user, "tenant_id", None))


@_enabled_router.get("/fire-drills", response_model=PortalFireDrillListResponse)
async def list_fire_drills(db: DbSession, user: CurrentUser) -> PortalFireDrillListResponse:
    """Active fire-drill obligations owned by the caller."""
    tenant_id = _tenant(user)
    payload = await PortalFireDrillService(db).list_my_fire_drills(
        user_id=user.id,
        tenant_id=tenant_id,
    )
    logger.info(
        "portal_fire_drills_list user_id=%s total=%s",
        user.id,
        payload.get("total"),
    )
    return PortalFireDrillListResponse.model_validate(payload)


@_enabled_router.post(
    "/fire-drills/{requirement_id}/complete",
    response_model=PortalFireDrillCompleteResponse,
    status_code=status.HTTP_201_CREATED,
)
async def complete_fire_drill(
    requirement_id: int,
    data: PortalFireDrillCompleteRequest,
    db: DbSession,
    user: CurrentUser,
) -> PortalFireDrillCompleteResponse:
    """Complete an owned fire-drill occurrence (notes + check_passed for v1)."""
    tenant_id = _tenant(user)
    record = await PortalFireDrillService(db).complete_my_fire_drill(
        requirement_id,
        user_id=user.id,
        tenant_id=tenant_id,
        notes=data.notes,
        check_passed=data.check_passed,
        evidence_asset_ids=data.evidence_asset_ids,
        completed_at=data.completed_at,
        due_date_override=data.due_date,
    )
    return PortalFireDrillCompleteResponse.model_validate(record)


router.include_router(_enabled_router)
