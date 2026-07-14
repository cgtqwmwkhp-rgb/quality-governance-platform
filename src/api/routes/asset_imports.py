"""Asset CSV import API routes (AM-IMPORT).

Dry-run returns a validation report without persisting.
Commit re-validates then creates assets; row errors yield HTTP 422 with the report.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, UploadFile, status

from src.api.dependencies import CurrentUser, DbSession, require_permission
from src.api.schemas.asset import (
    AssetImportCommitResponse,
    AssetImportValidationReportResponse,
)
from src.domain.exceptions import BadRequestError
from src.domain.models.user import User
from src.domain.services.asset_import_service import AssetImportService

router = APIRouter()


def _tid(user: CurrentUser) -> int:
    tid = user.tenant_id
    assert tid is not None, "Tenant context required"
    return tid


async def _read_csv_upload(file: UploadFile) -> bytes:
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise BadRequestError("File must be a CSV (.csv extension)")
    content = await file.read()
    if not content:
        raise BadRequestError("CSV file is empty")
    # Soft size guard (~2 MiB) to keep dry-run responsive
    if len(content) > 2 * 1024 * 1024:
        raise BadRequestError("CSV file exceeds 2 MiB limit")
    return content


@router.post(
    "/dry-run",
    response_model=AssetImportValidationReportResponse,
    summary="Dry-run CSV asset import (validation report only)",
)
async def dry_run_asset_import(
    db: DbSession,
    user: CurrentUser,
    _: Annotated[User, Depends(require_permission("asset:create"))],
    file: UploadFile = File(...),
) -> AssetImportValidationReportResponse:
    """Validate an engineer-tools CSV without writing assets."""
    content = await _read_csv_upload(file)
    service = AssetImportService(db)
    report = await service.dry_run(content, tenant_id=_tid(user))
    return AssetImportValidationReportResponse.model_validate(report.to_dict())


@router.post(
    "/commit",
    response_model=AssetImportCommitResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Commit CSV asset import after validation",
)
async def commit_asset_import(
    db: DbSession,
    user: CurrentUser,
    _: Annotated[User, Depends(require_permission("asset:create"))],
    file: UploadFile = File(...),
) -> AssetImportCommitResponse:
    """Re-validate and create assets from CSV. Returns 422 with row errors if invalid."""
    content = await _read_csv_upload(file)
    service = AssetImportService(db)
    result = await service.commit(content, user_id=user.id, tenant_id=_tid(user))
    return AssetImportCommitResponse.model_validate(result.to_dict())
