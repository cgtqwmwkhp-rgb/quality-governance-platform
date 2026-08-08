"""Job Lifecycle API routes (JL-1 / ADR-0022).

Gated by ``settings.job_lifecycle_enabled``. When closed, every route returns 404.
Authz: ``job:read`` for reads, ``job:author`` for axis/cell mutations.
"""

from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query, status

from src.api.dependencies import DbSession, require_permission
from src.api.schemas.job_lifecycle import (
    JobCellDocumentsPut,
    JobCellLinkCreate,
    JobCellLinkListResponse,
    JobCellLinkResponse,
    JobCellListResponse,
    JobCellResponse,
    JobDocumentFreshnessItem,
    JobDocumentFreshnessResponse,
    JobLaneCreate,
    JobLaneListResponse,
    JobLaneResponse,
    JobLaneUpdate,
    JobLinkEntityTypesResponse,
    JobStepCreate,
    JobStepListResponse,
    JobStepResponse,
    JobStepUpdate,
    JobTypeCreate,
    JobTypeListResponse,
    JobTypeResponse,
    JobTypeUpdate,
)
from src.api.utils.tenant import require_tenant_id
from src.core.config import settings
from src.domain.models.user import User
from src.domain.services.job_lifecycle_service import JobLifecycleService, list_link_entity_types

DISABLED_DETAIL = "Job Lifecycle is not enabled in this environment."
CELL_LINKS_DISABLED_DETAIL = "Job cell links are not enabled in this environment."

router = APIRouter()


async def require_job_lifecycle_enabled() -> None:
    from fastapi import HTTPException

    if not settings.job_lifecycle_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=DISABLED_DETAIL)


async def require_job_cell_links_enabled() -> None:
    from fastapi import HTTPException

    if not settings.job_cell_links_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=CELL_LINKS_DISABLED_DETAIL)


_enabled_router = APIRouter(dependencies=[Depends(require_job_lifecycle_enabled)])
_links_router = APIRouter(
    dependencies=[
        Depends(require_job_lifecycle_enabled),
        Depends(require_job_cell_links_enabled),
    ]
)


# ---------------------------------------------------------------------------
# Job types
# ---------------------------------------------------------------------------


@_enabled_router.get("/job-types", response_model=JobTypeListResponse)
async def list_job_types(
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("job:read"))],
):
    tenant_id = require_tenant_id(getattr(current_user, "tenant_id", None))
    items = await JobLifecycleService(db).list_job_types(tenant_id=tenant_id)
    return JobTypeListResponse(
        items=[JobTypeResponse.model_validate(i) for i in items],
        total=len(items),
    )


@_enabled_router.post(
    "/job-types",
    response_model=JobTypeResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_job_type(
    body: JobTypeCreate,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("job:author"))],
):
    tenant_id = require_tenant_id(getattr(current_user, "tenant_id", None))
    row = await JobLifecycleService(db).create_job_type(
        tenant_id=tenant_id,
        code=body.code,
        name=body.name,
        description=body.description,
        sort_order=body.sort_order,
        is_active=body.is_active,
    )
    return JobTypeResponse.model_validate(row)


@_enabled_router.get("/job-types/{job_type_id}", response_model=JobTypeResponse)
async def get_job_type(
    job_type_id: int,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("job:read"))],
):
    tenant_id = require_tenant_id(getattr(current_user, "tenant_id", None))
    row = await JobLifecycleService(db).get_job_type(tenant_id=tenant_id, job_type_id=job_type_id)
    return JobTypeResponse.model_validate(row)


@_enabled_router.patch("/job-types/{job_type_id}", response_model=JobTypeResponse)
async def update_job_type(
    job_type_id: int,
    body: JobTypeUpdate,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("job:author"))],
):
    tenant_id = require_tenant_id(getattr(current_user, "tenant_id", None))
    row = await JobLifecycleService(db).update_job_type(
        tenant_id=tenant_id,
        job_type_id=job_type_id,
        name=body.name,
        description=body.description,
        sort_order=body.sort_order,
        is_active=body.is_active,
    )
    return JobTypeResponse.model_validate(row)


@_enabled_router.delete("/job-types/{job_type_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_job_type(
    job_type_id: int,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("job:author"))],
):
    tenant_id = require_tenant_id(getattr(current_user, "tenant_id", None))
    await JobLifecycleService(db).soft_delete_job_type(tenant_id=tenant_id, job_type_id=job_type_id)


# ---------------------------------------------------------------------------
# Lanes
# ---------------------------------------------------------------------------


@_enabled_router.get("/job-types/{job_type_id}/lanes", response_model=JobLaneListResponse)
async def list_lanes(
    job_type_id: int,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("job:read"))],
):
    tenant_id = require_tenant_id(getattr(current_user, "tenant_id", None))
    items = await JobLifecycleService(db).list_lanes(tenant_id=tenant_id, job_type_id=job_type_id)
    return JobLaneListResponse(
        items=[JobLaneResponse.model_validate(i) for i in items],
        total=len(items),
    )


@_enabled_router.post(
    "/job-types/{job_type_id}/lanes",
    response_model=JobLaneResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_lane(
    job_type_id: int,
    body: JobLaneCreate,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("job:author"))],
):
    tenant_id = require_tenant_id(getattr(current_user, "tenant_id", None))
    row = await JobLifecycleService(db).create_lane(
        tenant_id=tenant_id,
        job_type_id=job_type_id,
        code=body.code,
        name=body.name,
        description=body.description,
        sort_order=body.sort_order,
        is_active=body.is_active,
    )
    return JobLaneResponse.model_validate(row)


@_enabled_router.patch("/lanes/{lane_id}", response_model=JobLaneResponse)
async def update_lane(
    lane_id: int,
    body: JobLaneUpdate,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("job:author"))],
):
    tenant_id = require_tenant_id(getattr(current_user, "tenant_id", None))
    row = await JobLifecycleService(db).update_lane(
        tenant_id=tenant_id,
        lane_id=lane_id,
        name=body.name,
        description=body.description,
        sort_order=body.sort_order,
        is_active=body.is_active,
    )
    return JobLaneResponse.model_validate(row)


@_enabled_router.delete("/lanes/{lane_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_lane(
    lane_id: int,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("job:author"))],
):
    tenant_id = require_tenant_id(getattr(current_user, "tenant_id", None))
    await JobLifecycleService(db).soft_delete_lane(tenant_id=tenant_id, lane_id=lane_id)


# ---------------------------------------------------------------------------
# Steps
# ---------------------------------------------------------------------------


@_enabled_router.get("/job-types/{job_type_id}/steps", response_model=JobStepListResponse)
async def list_steps(
    job_type_id: int,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("job:read"))],
):
    tenant_id = require_tenant_id(getattr(current_user, "tenant_id", None))
    items = await JobLifecycleService(db).list_steps(tenant_id=tenant_id, job_type_id=job_type_id)
    return JobStepListResponse(
        items=[JobStepResponse.model_validate(i) for i in items],
        total=len(items),
    )


@_enabled_router.post(
    "/job-types/{job_type_id}/steps",
    response_model=JobStepResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_step(
    job_type_id: int,
    body: JobStepCreate,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("job:author"))],
):
    tenant_id = require_tenant_id(getattr(current_user, "tenant_id", None))
    row = await JobLifecycleService(db).create_step(
        tenant_id=tenant_id,
        job_type_id=job_type_id,
        code=body.code,
        name=body.name,
        description=body.description,
        sort_order=body.sort_order,
        is_active=body.is_active,
        pdca_phase=body.pdca_phase,
    )
    return JobStepResponse.model_validate(row)


@_enabled_router.patch("/steps/{step_id}", response_model=JobStepResponse)
async def update_step(
    step_id: int,
    body: JobStepUpdate,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("job:author"))],
):
    tenant_id = require_tenant_id(getattr(current_user, "tenant_id", None))
    row = await JobLifecycleService(db).update_step(
        tenant_id=tenant_id,
        step_id=step_id,
        name=body.name,
        description=body.description,
        sort_order=body.sort_order,
        is_active=body.is_active,
        pdca_phase=body.pdca_phase,
        pdca_phase_set="pdca_phase" in body.model_fields_set,
    )
    return JobStepResponse.model_validate(row)


@_enabled_router.delete("/steps/{step_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_step(
    step_id: int,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("job:author"))],
):
    tenant_id = require_tenant_id(getattr(current_user, "tenant_id", None))
    await JobLifecycleService(db).soft_delete_step(tenant_id=tenant_id, step_id=step_id)


# ---------------------------------------------------------------------------
# Cells
# ---------------------------------------------------------------------------


@_enabled_router.get("/job-types/{job_type_id}/cells", response_model=JobCellListResponse)
async def list_cells(
    job_type_id: int,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("job:read"))],
):
    tenant_id = require_tenant_id(getattr(current_user, "tenant_id", None))
    items = await JobLifecycleService(db).list_cells(
        tenant_id=tenant_id,
        job_type_id=job_type_id,
        include_links=bool(settings.job_cell_links_enabled),
    )
    return JobCellListResponse(
        items=[JobCellResponse.model_validate(i) for i in items],
        total=len(items),
    )


@_enabled_router.put(
    "/job-types/{job_type_id}/cells/{lane_id}/{step_id}/documents",
    response_model=JobCellResponse,
)
async def put_cell_documents(
    job_type_id: int,
    lane_id: int,
    step_id: int,
    body: JobCellDocumentsPut,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("job:author"))],
):
    tenant_id = require_tenant_id(getattr(current_user, "tenant_id", None))
    payload = await JobLifecycleService(db).set_cell_documents(
        tenant_id=tenant_id,
        job_type_id=job_type_id,
        lane_id=lane_id,
        step_id=step_id,
        library_document_ids=body.library_document_ids,
        include_links=bool(settings.job_cell_links_enabled),
    )
    return JobCellResponse.model_validate(payload)


# ---------------------------------------------------------------------------
# Document freshness (JL-UX-W3)
# ---------------------------------------------------------------------------


@_enabled_router.get("/document-freshness", response_model=JobDocumentFreshnessResponse)
async def list_document_freshness(
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("job:read"))],
    library_document_ids: Annotated[Optional[list[int]], Query()] = None,
):
    """Library / Document Control status for the documents the composer can see.

    A read, so it is a GET: the composer asks for the loaded library page plus
    the ids already attached to cells. Nothing here writes, and the freshness
    lives entirely in the document tables — the job lifecycle never caches it.
    """
    tenant_id = require_tenant_id(getattr(current_user, "tenant_id", None))
    items = await JobLifecycleService(db).document_freshness(
        tenant_id=tenant_id,
        library_document_ids=library_document_ids or [],
    )
    return JobDocumentFreshnessResponse(
        items=[JobDocumentFreshnessItem.model_validate(i) for i in items],
        total=len(items),
    )


# ---------------------------------------------------------------------------
# Cell links (JL-3) — gated by job_lifecycle + job_cell_links
# ---------------------------------------------------------------------------


@_links_router.get(
    "/job-types/{job_type_id}/cells/{lane_id}/{step_id}/links",
    response_model=JobCellLinkListResponse,
)
async def list_cell_links(
    job_type_id: int,
    lane_id: int,
    step_id: int,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("job:read"))],
):
    tenant_id = require_tenant_id(getattr(current_user, "tenant_id", None))
    items = await JobLifecycleService(db).list_cell_links(
        tenant_id=tenant_id,
        job_type_id=job_type_id,
        lane_id=lane_id,
        step_id=step_id,
    )
    return JobCellLinkListResponse(
        items=[JobCellLinkResponse.model_validate(i) for i in items],
        total=len(items),
    )


@_links_router.post(
    "/job-types/{job_type_id}/cells/{lane_id}/{step_id}/links",
    response_model=JobCellLinkResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_cell_link(
    job_type_id: int,
    lane_id: int,
    step_id: int,
    body: JobCellLinkCreate,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("job:author"))],
):
    tenant_id = require_tenant_id(getattr(current_user, "tenant_id", None))
    payload = await JobLifecycleService(db).create_cell_link(
        tenant_id=tenant_id,
        job_type_id=job_type_id,
        lane_id=lane_id,
        step_id=step_id,
        kind=body.kind,
        label=body.label,
        entity_type=body.entity_type,
        entity_id=body.entity_id,
        external_url=body.external_url,
        audit_run_id=body.audit_run_id,
        audit_finding_id=body.audit_finding_id,
        target_job_type_id=body.target_job_type_id,
        sort_order=body.sort_order,
    )
    return JobCellLinkResponse.model_validate(payload)


@_links_router.get("/link-entity-types", response_model=JobLinkEntityTypesResponse)
async def list_link_entity_types_route(
    current_user: Annotated[User, Depends(require_permission("job:read"))],
):
    """App-link entity types the composer may offer, sourced from href_registry."""
    _ = current_user
    items = list_link_entity_types()
    return JobLinkEntityTypesResponse(items=items, total=len(items))


@_links_router.delete("/links/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_cell_link(
    link_id: int,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("job:author"))],
):
    tenant_id = require_tenant_id(getattr(current_user, "tenant_id", None))
    await JobLifecycleService(db).delete_cell_link(tenant_id=tenant_id, link_id=link_id)


router.include_router(_enabled_router)
router.include_router(_links_router)

__all__ = [
    "CELL_LINKS_DISABLED_DETAIL",
    "DISABLED_DETAIL",
    "require_job_cell_links_enabled",
    "require_job_lifecycle_enabled",
    "router",
]
