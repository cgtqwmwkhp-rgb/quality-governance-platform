"""H&S Excel workbook import routes (dry-run / commit)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, UploadFile

from src.api.dependencies import CurrentUser, DbSession, require_permission
from src.domain.exceptions import BadRequestError
from src.domain.models.user import User
from src.domain.services.hs_excel_import_service import HsExcelImportService

router = APIRouter()


async def _read_xlsx(file: UploadFile) -> bytes:
    if not file.filename or not file.filename.lower().endswith(".xlsx"):
        raise BadRequestError("File must be an Excel workbook (.xlsx)")
    content = await file.read()
    if not content:
        raise BadRequestError("Workbook is empty")
    if len(content) > 8 * 1024 * 1024:
        raise BadRequestError("Workbook exceeds 8 MiB limit")
    return content


@router.post("/excel/dry-run")
async def dry_run_hs_excel_import(
    db: DbSession,
    current_user: CurrentUser,
    _: Annotated[User, Depends(require_permission("incident:create"))],
    file: UploadFile = File(...),
):
    content = await _read_xlsx(file)
    assert current_user.tenant_id is not None
    return await HsExcelImportService(db).dry_run(content, tenant_id=current_user.tenant_id)


@router.post("/excel/commit")
async def commit_hs_excel_import(
    db: DbSession,
    current_user: CurrentUser,
    _: Annotated[User, Depends(require_permission("incident:create"))],
    file: UploadFile = File(...),
):
    content = await _read_xlsx(file)
    assert current_user.tenant_id is not None
    return await HsExcelImportService(db).commit(content, tenant_id=current_user.tenant_id, user_id=current_user.id)
