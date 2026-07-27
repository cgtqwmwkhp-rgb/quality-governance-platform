"""Export Center API — sync CSV catalog + download (PX-160).

No async export_jobs table this wave (Lane S owns alembic). Job history and
scheduled templates remain honestly unavailable.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from src.api.dependencies import DbSession, require_permission
from src.api.schemas.exports import (
    CreateExportRequest,
    ExportCapabilities,
    ExportCatalogResponse,
    ExportModuleCatalogItem,
)
from src.api.utils.tenant import require_tenant_id
from src.domain.models.user import User
from src.domain.services.export_center_service import ExportCenterService

router = APIRouter()


def _csv_response(result) -> StreamingResponse:
    headers = {
        "Content-Disposition": f'attachment; filename="{result.filename}"',
        "X-Export-Module": result.module,
        "X-Export-Row-Count": str(result.row_count),
        "X-Export-Total-Available": str(result.total_available),
        "X-Export-Truncated": "true" if result.truncated else "false",
        "X-Export-Mode": "sync",
    }
    return StreamingResponse(
        iter([result.csv_text]),
        media_type="text/csv; charset=utf-8",
        headers=headers,
    )


@router.get("/catalog", response_model=ExportCatalogResponse)
async def get_export_catalog(
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("incident:read"))],
) -> ExportCatalogResponse:
    """List exportable modules with live tenant-scoped record counts."""
    tenant_id = require_tenant_id(getattr(current_user, "tenant_id", None))
    service = ExportCenterService(db)
    payload = await service.get_catalog(tenant_id)
    return ExportCatalogResponse(
        modules=[ExportModuleCatalogItem.model_validate(item) for item in payload["modules"]],
        capabilities=ExportCapabilities.model_validate(payload["capabilities"]),
    )


@router.post("")
@router.post("/")
async def create_sync_export(
    body: CreateExportRequest,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("incident:read"))],
) -> StreamingResponse:
    """Run a synchronous CSV export and stream the file immediately.

    Matches WORKFLOW_REGISTRY ``POST /api/v1/exports``. Does not enqueue a job.
    """
    tenant_id = require_tenant_id(getattr(current_user, "tenant_id", None))
    service = ExportCenterService(db)
    result = await service.build_sync_csv(tenant_id, body.module, body.format)
    return _csv_response(result)


@router.get("/{module}/csv")
async def download_module_csv(
    module: str,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("incident:read"))],
    export_format: str = Query("csv", alias="format"),
) -> StreamingResponse:
    """GET convenience for sync CSV download of a single module."""
    tenant_id = require_tenant_id(getattr(current_user, "tenant_id", None))
    service = ExportCenterService(db)
    result = await service.build_sync_csv(tenant_id, module, export_format)
    return _csv_response(result)
