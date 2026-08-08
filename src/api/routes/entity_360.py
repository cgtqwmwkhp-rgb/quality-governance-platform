"""Entity360 API routes (conveyor X-1).

Gated by ``settings.entity_360_enabled``. When closed, every route returns 404.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status

from src.api.dependencies import DbSession, require_permission
from src.api.schemas.entity_360 import Entity360Bundle, ImpactBundle
from src.api.utils.tenant import require_tenant_id
from src.core.config import settings
from src.domain.models.user import User
from src.domain.services.entity_360 import Entity360Service, build_impact_bundle

DISABLED_DETAIL = "Entity360 is not enabled in this environment."

router = APIRouter()


async def require_entity_360_enabled() -> None:
    from fastapi import HTTPException

    if not settings.entity_360_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=DISABLED_DETAIL)


_enabled_router = APIRouter(dependencies=[Depends(require_entity_360_enabled)])


@_enabled_router.get(
    "/documents/{document_id}/impact",
    response_model=ImpactBundle,
)
async def get_document_impact_bundle(
    document_id: int,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("document:read"))],
):
    """Server ImpactBundle for publish preview — ``can_publish`` false when degraded."""
    tenant_id = require_tenant_id(getattr(current_user, "tenant_id", None))
    bundle = await build_impact_bundle(
        db=db,
        tenant_id=tenant_id,
        document_id=document_id,
        user=current_user,
    )
    return ImpactBundle.model_validate(bundle)


@_enabled_router.get(
    "/{entity_type}/{entity_id}",
    response_model=Entity360Bundle,
)
async def get_entity_360(
    entity_type: str,
    entity_id: int,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("document:read"))],
):
    """Bidirectional Entity360 hops for any registered entity type."""
    tenant_id = require_tenant_id(getattr(current_user, "tenant_id", None))
    service = Entity360Service(db)
    bundle = await service.compose(
        tenant_id=tenant_id,
        entity_type=entity_type,
        entity_id=entity_id,
        user=current_user,
    )
    return Entity360Bundle.model_validate(bundle)


router.include_router(_enabled_router)
