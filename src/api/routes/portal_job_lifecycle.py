"""Portal Job Lifecycle read surface (JL-UX-W5).

Field / mobile nested-cycle read. ``job:read`` only — no PATCH / POST author
routes are mounted here. Nest navigation reuses the same cycle-graph /
``job_cycle`` link SSOT as the composer; JobType is never forked.
"""

from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query, status

from src.api.dependencies import DbSession, require_permission
from src.api.routes.job_lifecycle import CELL_LINKS_DISABLED_DETAIL, DISABLED_DETAIL, require_job_lifecycle_enabled
from src.api.schemas.job_lifecycle import (
    JobCycleGraphResponse,
    JobLaneResponse,
    JobStepResponse,
    JobTypeListResponse,
    JobTypeResponse,
    PortalJobCell,
    PortalNestedCycleResponse,
)
from src.api.utils.tenant import require_tenant_id
from src.core.config import settings
from src.domain.models.user import User
from src.domain.services.job_lifecycle_service import JobLifecycleService

router = APIRouter()

_enabled_router = APIRouter(dependencies=[Depends(require_job_lifecycle_enabled)])


@_enabled_router.get("/job-types", response_model=JobTypeListResponse)
async def portal_list_job_types(
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("job:read"))],
):
    tenant_id = require_tenant_id(getattr(current_user, "tenant_id", None))
    items = await JobLifecycleService(db).list_job_types(tenant_id=tenant_id)
    return JobTypeListResponse(
        items=[JobTypeResponse.model_validate(i) for i in items],
        total=len(items),
    )


@_enabled_router.get(
    "/job-types/{job_type_id}/nested-cycle",
    response_model=PortalNestedCycleResponse,
)
async def portal_nested_cycle(
    job_type_id: int,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("job:read"))],
    depth: Annotated[Optional[int], Query(ge=1, le=5)] = None,
):
    """Read-only nest-aware cycle for field users.

    Includes lanes, steps, document refs and ``job_cycle`` nest links only.
    ``can_author`` is always false — there is no write method on this router.
    """
    tenant_id = require_tenant_id(getattr(current_user, "tenant_id", None))
    links_on = bool(settings.job_cell_links_enabled)
    payload = await JobLifecycleService(db).portal_nested_cycle(
        tenant_id=tenant_id,
        job_type_id=job_type_id,
        include_links=links_on,
        include_cycle_graph=links_on,
        depth=depth,
    )
    graph = payload.get("cycle_graph")
    return PortalNestedCycleResponse(
        job_type=JobTypeResponse.model_validate(payload["job_type"]),
        lanes=[JobLaneResponse.model_validate(i) for i in payload["lanes"]],
        steps=[JobStepResponse.model_validate(i) for i in payload["steps"]],
        cells=[PortalJobCell.model_validate(i) for i in payload["cells"]],
        cycle_graph=JobCycleGraphResponse.model_validate(graph) if graph else None,
        read_only=True,
        can_author=False,
    )


@_enabled_router.get(
    "/job-types/{job_type_id}/cycle-graph",
    response_model=JobCycleGraphResponse,
)
async def portal_cycle_graph(
    job_type_id: int,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("job:read"))],
    depth: Annotated[Optional[int], Query(ge=1, le=5)] = None,
):
    """Process interaction map for portal drill-in. Same edge model as composer."""
    from fastapi import HTTPException

    if not settings.job_cell_links_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=CELL_LINKS_DISABLED_DETAIL)

    tenant_id = require_tenant_id(getattr(current_user, "tenant_id", None))
    payload = await JobLifecycleService(db).cycle_graph(
        tenant_id=tenant_id,
        job_type_id=job_type_id,
        depth=depth,
    )
    return JobCycleGraphResponse.model_validate(payload)


router.include_router(_enabled_router)

__all__ = [
    "DISABLED_DETAIL",
    "router",
]
