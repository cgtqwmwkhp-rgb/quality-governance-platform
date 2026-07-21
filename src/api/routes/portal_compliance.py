"""Person-scoped tool + van compliance for the employee portal."""

from __future__ import annotations

import logging

from fastapi import APIRouter

from src.api.dependencies import CurrentUser, DbSession
from src.api.schemas.portal_compliance import (
    PortalDriverMeResponse,
    PortalMyComplianceResponse,
    PortalMyToolsResponse,
    PortalMyVanResponse,
)
from src.api.utils.tenant import require_tenant_id
from src.domain.services.portal_compliance_service import PortalComplianceService

logger = logging.getLogger(__name__)

router = APIRouter()


def _tenant(user: CurrentUser) -> int:
    return require_tenant_id(getattr(user, "tenant_id", None))


@router.get("/my-compliance", response_model=PortalMyComplianceResponse)
async def my_compliance(db: DbSession, user: CurrentUser) -> PortalMyComplianceResponse:
    """Landing one-shot: clear-to-work state + tool/van badges (self only)."""
    tenant_id = _tenant(user)
    payload = await PortalComplianceService(db).my_compliance(user_id=user.id, tenant_id=tenant_id)
    logger.info(
        "portal_my_compliance user_id=%s clear_state=%s tool_badge=%s van_badge=%s",
        user.id,
        payload.get("clear_state"),
        payload.get("tool_badge"),
        payload.get("van_badge"),
    )
    return PortalMyComplianceResponse.model_validate(payload)


@router.get("/my-tools", response_model=PortalMyToolsResponse)
async def my_tools(db: DbSession, user: CurrentUser) -> PortalMyToolsResponse:
    """Tools assigned to me union kit on my van (deduped)."""
    tenant_id = _tenant(user)
    payload = await PortalComplianceService(db).my_tools(user_id=user.id, tenant_id=tenant_id)
    return PortalMyToolsResponse.model_validate(payload)


@router.get("/my-van", response_model=PortalMyVanResponse)
async def my_van(db: DbSession, user: CurrentUser) -> PortalMyVanResponse:
    """My van checks + open defects for the resolved vehicle only."""
    tenant_id = _tenant(user)
    payload = await PortalComplianceService(db).my_van_status(user_id=user.id, tenant_id=tenant_id)
    return PortalMyVanResponse.model_validate(payload)


@router.get("/drivers/me", response_model=PortalDriverMeResponse)
async def drivers_me(db: DbSession, user: CurrentUser) -> PortalDriverMeResponse:
    """Resolve my driver profile + van assignment (honest empty_reason)."""
    tenant_id = _tenant(user)
    payload = await PortalComplianceService(db).my_driver(user_id=user.id, tenant_id=tenant_id)
    return PortalDriverMeResponse.model_validate(payload)
