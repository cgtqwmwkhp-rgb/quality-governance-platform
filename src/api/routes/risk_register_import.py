"""Enterprise Risk Register XLSX import routes (RR-W4 + Action Plan→CAPA).

Dry-run validates the Risk Register sheet and Action Plan sheet (when present).
Commit re-validates then upserts EnterpriseRisk rows by PELR* reference and
creates/updates CAPA actions from Action Plan rows.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, UploadFile, status

from src.api.dependencies import CurrentUser, DbSession, require_permission
from src.api.schemas.risk_register_import import (
    RiskRegisterImportCommitResponse,
    RiskRegisterImportValidationReportResponse,
)
from src.domain.exceptions import BadRequestError
from src.domain.models.user import User
from src.domain.services.risk_register_import_service import RiskRegisterImportService
from src.infrastructure.cache.redis_cache import invalidate_tenant_cache

router = APIRouter()


def _tenant_id(user: CurrentUser) -> int:
    tid = user.tenant_id
    assert tid is not None, "Tenant context required"
    return tid


async def _read_xlsx_upload(file: UploadFile) -> bytes:
    filename = (file.filename or "").lower()
    if not filename.endswith(".xlsx"):
        raise BadRequestError("File must be an Excel workbook (.xlsx extension)")
    content = await file.read()
    if not content:
        raise BadRequestError("XLSX file is empty")
    return content


@router.post(
    "/dry-run",
    response_model=RiskRegisterImportValidationReportResponse,
    summary="Dry-run Risk Register XLSX import (validation report only)",
)
async def dry_run_risk_register_import(
    db: DbSession,
    user: CurrentUser,
    _: Annotated[User, Depends(require_permission("risk:create"))],
    file: UploadFile = File(...),
) -> RiskRegisterImportValidationReportResponse:
    """Validate Plantexpand Risk Register workbook without writing risks."""
    content = await _read_xlsx_upload(file)
    service = RiskRegisterImportService(db)
    report = await service.dry_run(content, tenant_id=_tenant_id(user))
    return RiskRegisterImportValidationReportResponse.model_validate(report.to_dict())


@router.post(
    "/commit",
    response_model=RiskRegisterImportCommitResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Commit Risk Register XLSX import after validation",
)
async def commit_risk_register_import(
    db: DbSession,
    user: CurrentUser,
    _: Annotated[User, Depends(require_permission("risk:create"))],
    file: UploadFile = File(...),
) -> RiskRegisterImportCommitResponse:
    """Re-validate and upsert risks from the Risk Register sheet."""
    content = await _read_xlsx_upload(file)
    service = RiskRegisterImportService(db)
    result = await service.commit(content, user_id=user.id, tenant_id=_tenant_id(user))
    await invalidate_tenant_cache(_tenant_id(user), "risk_register")
    return RiskRegisterImportCommitResponse.model_validate(result.to_dict())
