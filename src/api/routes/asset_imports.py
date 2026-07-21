"""Asset CSV import API routes (AM-IMPORT).

Dry-run returns a validation report without persisting.
Commit re-validates then creates assets; row errors yield HTTP 422 with the report.
"""

from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, File, Form, UploadFile, status

from src.api.dependencies import CurrentUser, DbSession, require_permission
from src.api.schemas.asset import (
    AssetImportCommitResponse,
    AssetImportValidationReportResponse,
    CesAssetImportCommitResponse,
    CesAssetImportValidationReportResponse,
)
from src.domain.exceptions import BadRequestError
from src.domain.models.user import User
from src.domain.services.asset_import_service import AssetImportService
from src.domain.services.ces_asset_import_service import CesAssetImportService, parse_confirmations

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
    if len(content) > 2 * 1024 * 1024:
        raise BadRequestError("CSV file exceeds 2 MiB limit")
    return content


async def _read_xlsx_upload(file: UploadFile) -> bytes:
    if not file.filename or not file.filename.lower().endswith(".xlsx"):
        raise BadRequestError("File must be an Excel workbook (.xlsx extension)")
    content = await file.read()
    if not content:
        raise BadRequestError("XLSX file is empty")
    if len(content) > 5 * 1024 * 1024:
        raise BadRequestError("XLSX file exceeds 5 MiB limit")
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


@router.post(
    "/ces/dry-run",
    response_model=CesAssetImportValidationReportResponse,
    summary="Dry-run CES Calibrations XLSX import",
)
async def dry_run_ces_asset_import(
    db: DbSession,
    user: CurrentUser,
    _: Annotated[User, Depends(require_permission("asset:create"))],
    file: UploadFile = File(...),
) -> CesAssetImportValidationReportResponse:
    content = await _read_xlsx_upload(file)
    report = await CesAssetImportService(db).dry_run(content, tenant_id=_tid(user))
    return CesAssetImportValidationReportResponse.model_validate(report.to_dict())


@router.post(
    "/ces/commit",
    response_model=CesAssetImportCommitResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Commit CES Calibrations XLSX import",
)
async def commit_ces_asset_import(
    db: DbSession,
    user: CurrentUser,
    _: Annotated[User, Depends(require_permission("asset:create"))],
    file: UploadFile = File(...),
    confirmations: Optional[str] = Form(default=None),
) -> CesAssetImportCommitResponse:
    content = await _read_xlsx_upload(file)
    parsed = parse_confirmations(confirmations)
    result = await CesAssetImportService(db).commit(
        content,
        user_id=user.id,
        tenant_id=_tid(user),
        confirmations=parsed,
    )
    return CesAssetImportCommitResponse.model_validate(result.to_dict())
