"""Compliance Schedule API routes (Wave 1 vertical slice).

Gated by ``settings.compliance_schedule_enabled`` then the kill switch
(``compliance_schedule_kill_switch``). When closed, every route returns 404.
"""

from __future__ import annotations

import math
from datetime import date, datetime, timezone
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, File, Query, UploadFile, status

from src.api.dependencies import DbSession, require_permission
from src.api.schemas.compliance_schedule import (
    CatalogueActivateRequest,
    CatalogueListResponse,
    CatalogueTemplateResponse,
    ComplianceImportCommitResponse,
    ComplianceImportValidationReportResponse,
    ComplianceScheduleStatsResponse,
    LocationCoverageGapsResponse,
    RecordCompleteRequest,
    RecordEvidenceAttachRequest,
    RecordFileRequest,
    RecordFilingResponse,
    RecordListResponse,
    RecordResponse,
    RequirementCreate,
    RequirementListResponse,
    RequirementResponse,
    RequirementUpdate,
)
from src.api.schemas.compliance_schedule_fra_ocr import (
    FraOcrAppliedSummary,
    FraOcrConfirmResponse,
    FraOcrDiscardRequest,
    FraOcrDraftConfirmRequest,
    FraOcrDraftListResponse,
    FraOcrDraftResponse,
    FraOcrFileRequest,
    FraOcrFilingResponse,
)
from src.api.utils.tenant import require_tenant_id
from src.core.config import settings
from src.domain.exceptions import BadRequestError
from src.domain.models.user import User
from src.domain.services.compliance_schedule_filing_service import (
    file_record_to_library as file_record_to_library_service,
)
from src.domain.services.compliance_schedule_fra_ocr_service import (
    ComplianceScheduleFraOcrService,
    draft_to_response_dict,
    pages_for,
)
from src.domain.services.compliance_schedule_import_service import ComplianceScheduleImportService
from src.domain.services.compliance_schedule_policy import derive_status
from src.domain.services.compliance_schedule_service import ComplianceScheduleService
from src.infrastructure.database import async_session_maker

DISABLED_DETAIL = "Compliance Schedule is not enabled in this environment."
FRA_OCR_DISABLED_DETAIL = "FRA OCR ingest is not enabled in this environment."

router = APIRouter()


async def compliance_schedule_is_open() -> bool:
    """Whether the module is available. Thin wrapper binding the app's session factory.

    Retained as a module-level name because tests and the router's dependency both
    patch it here; the decision itself belongs to the domain layer, which the Celery
    sweep also needs and which cannot import this module.
    """
    from src.domain.services.compliance_schedule_kill_switch import compliance_schedule_is_open as _domain_is_open

    return await _domain_is_open(async_session_maker)


async def require_compliance_schedule_enabled() -> None:
    from fastapi import HTTPException

    if not await compliance_schedule_is_open():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=DISABLED_DETAIL)


async def require_fra_ocr_enabled() -> None:
    from fastapi import HTTPException

    if not settings.compliance_schedule_fra_ocr_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=FRA_OCR_DISABLED_DETAIL)


_enabled_router = APIRouter(dependencies=[Depends(require_compliance_schedule_enabled)])
_fra_ocr_router = APIRouter(dependencies=[Depends(require_fra_ocr_enabled)])


def _requirement_response(row, *, now: Optional[datetime] = None) -> RequirementResponse:
    clock = now or datetime.now(timezone.utc)
    status_value = derive_status(clock, row.next_due_date)
    return RequirementResponse(
        id=row.id,
        external_id=row.external_id,
        tenant_id=row.tenant_id,
        reference_number=row.reference_number,
        template_id=row.template_id,
        location_id=row.location_id,
        title=row.title,
        taxonomy_id=row.taxonomy_id,
        description=row.description,
        regulatory_basis=row.regulatory_basis,
        frequency_months=row.frequency_months,
        frequency_days=row.frequency_days,
        anchor=row.anchor,
        statutory=row.statutory,
        next_due_date=row.next_due_date,
        last_completed_at=row.last_completed_at,
        owner_id=row.owner_id,
        is_active=row.is_active,
        status=status_value,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _pages(total: int, page_size: int) -> int:
    return max(1, int(math.ceil(total / page_size))) if total else 0


# ---------------------------------------------------------------------------
# Catalogue
# ---------------------------------------------------------------------------


@_enabled_router.get("/catalogue", response_model=CatalogueListResponse)
async def list_catalogue(
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("compliance_schedule:read"))],
    active_only: bool = Query(True),
):
    require_tenant_id(getattr(current_user, "tenant_id", None))
    service = ComplianceScheduleService(db)
    items = await service.list_catalogue(active_only=active_only)
    return CatalogueListResponse(
        items=[CatalogueTemplateResponse.model_validate(i) for i in items],
        total=len(items),
    )


@_enabled_router.post(
    "/catalogue/{template_key}/activate",
    response_model=RequirementResponse,
    status_code=status.HTTP_201_CREATED,
)
async def activate_catalogue_template(
    template_key: str,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("compliance_schedule:create"))],
    body: CatalogueActivateRequest | None = None,
):
    tenant_id = require_tenant_id(getattr(current_user, "tenant_id", None))
    payload = body or CatalogueActivateRequest()
    service = ComplianceScheduleService(db)
    row = await service.activate_catalogue_template(
        template_key,
        tenant_id=tenant_id,
        user_id=current_user.id,
        location_id=payload.location_id,
        next_due_date=payload.next_due_date,
        last_completed_at=payload.last_completed_at,
        owner_id=payload.owner_id,
    )
    return _requirement_response(row)


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------


@_enabled_router.get("/stats", response_model=ComplianceScheduleStatsResponse)
async def get_stats(
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("compliance_schedule:read"))],
):
    tenant_id = require_tenant_id(getattr(current_user, "tenant_id", None))
    service = ComplianceScheduleService(db)
    data = await service.get_stats(tenant_id=tenant_id)
    return ComplianceScheduleStatsResponse(**data)


@_enabled_router.get(
    "/coverage/location-gaps",
    response_model=LocationCoverageGapsResponse,
)
async def get_location_coverage_gaps(
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("compliance_schedule:read"))],
):
    """Active premises/offices missing an active FRA and/or fire-drill (Wave 3)."""
    tenant_id = require_tenant_id(getattr(current_user, "tenant_id", None))
    service = ComplianceScheduleService(db)
    data = await service.get_location_coverage_gaps(tenant_id=tenant_id)
    return LocationCoverageGapsResponse(**data)


async def _read_csv_upload(file: UploadFile) -> bytes:
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise BadRequestError("File must be a CSV (.csv extension)")
    content = await file.read()
    if not content:
        raise BadRequestError("CSV file is empty")
    if len(content) > 2 * 1024 * 1024:
        raise BadRequestError("CSV file exceeds 2 MiB limit")
    return content


@_enabled_router.post(
    "/import/dry-run",
    response_model=ComplianceImportValidationReportResponse,
    summary="Dry-run Compliance Schedule CSV import",
)
async def dry_run_compliance_schedule_import(
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("compliance_schedule:create"))],
    file: UploadFile = File(...),
):
    """Validate catalogue-activate CSV without writing obligations."""
    tenant_id = require_tenant_id(getattr(current_user, "tenant_id", None))
    content = await _read_csv_upload(file)
    service = ComplianceScheduleImportService(db)
    report = await service.dry_run(
        content,
        tenant_id=tenant_id,
        default_owner_id=current_user.id,
    )
    return ComplianceImportValidationReportResponse.model_validate(report.to_dict())


@_enabled_router.post(
    "/import/commit",
    response_model=ComplianceImportCommitResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Commit Compliance Schedule CSV import",
)
async def commit_compliance_schedule_import(
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("compliance_schedule:create"))],
    file: UploadFile = File(...),
):
    """Re-validate and activate catalogue obligations from CSV."""
    tenant_id = require_tenant_id(getattr(current_user, "tenant_id", None))
    content = await _read_csv_upload(file)
    service = ComplianceScheduleImportService(db)
    result = await service.commit(
        content,
        tenant_id=tenant_id,
        user_id=current_user.id,
        default_owner_id=current_user.id,
    )
    return ComplianceImportCommitResponse.model_validate(result.to_dict())


# ---------------------------------------------------------------------------
# Requirements
# ---------------------------------------------------------------------------


@_enabled_router.get("/requirements", response_model=RequirementListResponse)
async def list_requirements(
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("compliance_schedule:read"))],
    is_active: Optional[bool] = Query(True),
    location_id: Optional[int] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
):
    tenant_id = require_tenant_id(getattr(current_user, "tenant_id", None))
    service = ComplianceScheduleService(db)
    rows, total = await service.list_requirements(
        tenant_id=tenant_id,
        is_active=is_active,
        location_id=location_id,
        status=status_filter,
        page=page,
        page_size=page_size,
    )
    return RequirementListResponse(
        items=[_requirement_response(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
        pages=_pages(total, page_size),
    )


@_enabled_router.post(
    "/requirements",
    response_model=RequirementResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_requirement(
    data: RequirementCreate,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("compliance_schedule:create"))],
):
    tenant_id = require_tenant_id(getattr(current_user, "tenant_id", None))
    service = ComplianceScheduleService(db)
    row = await service.create_requirement(
        tenant_id=tenant_id,
        user_id=current_user.id,
        title=data.title,
        taxonomy_id=data.taxonomy_id,
        next_due_date=data.next_due_date,
        frequency_months=data.frequency_months,
        frequency_days=data.frequency_days,
        anchor=data.anchor.value if hasattr(data.anchor, "value") else str(data.anchor),
        description=data.description,
        regulatory_basis=data.regulatory_basis,
        statutory=data.statutory,
        location_id=data.location_id,
        owner_id=data.owner_id,
        template_id=data.template_id,
        last_completed_at=data.last_completed_at,
        is_active=data.is_active,
    )
    return _requirement_response(row)


@_enabled_router.get("/requirements/{requirement_id}", response_model=RequirementResponse)
async def get_requirement(
    requirement_id: int,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("compliance_schedule:read"))],
):
    tenant_id = require_tenant_id(getattr(current_user, "tenant_id", None))
    service = ComplianceScheduleService(db)
    row = await service.get_requirement(requirement_id, tenant_id=tenant_id)
    return _requirement_response(row)


@_enabled_router.patch("/requirements/{requirement_id}", response_model=RequirementResponse)
async def update_requirement(
    requirement_id: int,
    data: RequirementUpdate,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("compliance_schedule:update"))],
):
    tenant_id = require_tenant_id(getattr(current_user, "tenant_id", None))
    service = ComplianceScheduleService(db)
    updates = data.model_dump(exclude_unset=True)
    if "anchor" in updates and updates["anchor"] is not None:
        anchor = updates["anchor"]
        updates["anchor"] = anchor.value if hasattr(anchor, "value") else str(anchor)
    row = await service.update_requirement(
        requirement_id,
        tenant_id=tenant_id,
        user_id=current_user.id,
        updates=updates,
    )
    return _requirement_response(row)


@_enabled_router.post(
    "/requirements/{requirement_id}/deactivate",
    response_model=RequirementResponse,
)
async def deactivate_requirement(
    requirement_id: int,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("compliance_schedule:update"))],
):
    tenant_id = require_tenant_id(getattr(current_user, "tenant_id", None))
    service = ComplianceScheduleService(db)
    row = await service.deactivate_requirement(
        requirement_id,
        tenant_id=tenant_id,
        user_id=current_user.id,
    )
    return _requirement_response(row)


@_enabled_router.get(
    "/requirements/{requirement_id}/records",
    response_model=RecordListResponse,
)
async def list_requirement_records(
    requirement_id: int,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("compliance_schedule:read"))],
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
):
    tenant_id = require_tenant_id(getattr(current_user, "tenant_id", None))
    service = ComplianceScheduleService(db)
    rows, total = await service.list_records(
        requirement_id,
        tenant_id=tenant_id,
        page=page,
        page_size=page_size,
    )
    return RecordListResponse(
        items=[RecordResponse.model_validate(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
        pages=_pages(total, page_size),
    )


@_enabled_router.post(
    "/requirements/{requirement_id}/records",
    response_model=RecordResponse,
    status_code=status.HTTP_201_CREATED,
)
async def complete_requirement(
    requirement_id: int,
    data: RecordCompleteRequest,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("compliance_schedule:update"))],
):
    tenant_id = require_tenant_id(getattr(current_user, "tenant_id", None))
    service = ComplianceScheduleService(db)
    record = await service.complete_requirement(
        requirement_id,
        tenant_id=tenant_id,
        user_id=current_user.id,
        completed_at=data.completed_at,
        check_passed=data.check_passed,
        notes=data.notes,
        evidence_asset_ids=data.evidence_asset_ids,
        due_date_override=data.due_date,
    )
    return RecordResponse.model_validate(record)


# ---------------------------------------------------------------------------
# Records
# ---------------------------------------------------------------------------


@_enabled_router.get("/records/{record_id}", response_model=RecordResponse)
async def get_record(
    record_id: int,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("compliance_schedule:read"))],
):
    tenant_id = require_tenant_id(getattr(current_user, "tenant_id", None))
    service = ComplianceScheduleService(db)
    record = await service.get_record(record_id, tenant_id=tenant_id)
    return RecordResponse.model_validate(record)


@_enabled_router.post("/records/{record_id}/evidence", response_model=RecordResponse)
async def attach_record_evidence(
    record_id: int,
    data: RecordEvidenceAttachRequest,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("compliance_schedule:update"))],
):
    """Attach existing evidence assets to a compliance record."""
    tenant_id = require_tenant_id(getattr(current_user, "tenant_id", None))
    service = ComplianceScheduleService(db)
    record = await service.attach_evidence_to_record(
        record_id,
        tenant_id=tenant_id,
        evidence_asset_ids=data.evidence_asset_ids,
    )
    return RecordResponse.model_validate(record)


@_enabled_router.post(
    "/records/{record_id}/file",
    response_model=RecordFilingResponse,
    dependencies=[Depends(require_permission("document:create"))],
)
async def file_record_to_library(
    record_id: int,
    data: RecordFileRequest,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("compliance_schedule:update"))],
):
    """File this occurrence's evidence into the Governance Library.

    ADR-0020: filing is its own step. Recording a completion files nothing, and
    this is the only route that sets ``library_document_id`` — a record can be
    complete and unfiled indefinitely, which is a state the register is meant to
    be able to show.

    ``document:create`` is required for both modes, including the link mode that
    creates no document. Linking publishes a Library document's id onto the
    occurrence, and the narrower alternative — branching the permission on which
    mode the body selected — makes what a caller may do depend on what they
    asked for, which is the harder thing to reason about when it is wrong.
    """
    tenant_id = require_tenant_id(getattr(current_user, "tenant_id", None))
    result = await file_record_to_library_service(
        db,
        record_id=record_id,
        tenant_id=tenant_id,
        user=current_user,
        evidence_asset_id=data.evidence_asset_id,
        category_id=data.category_id,
        library_document_id=data.library_document_id,
        title=data.title,
    )
    return RecordFilingResponse(
        record=RecordResponse.model_validate(result.record),
        library_document_id=result.document.id,
        pel_doc_ref=getattr(result.document, "pel_doc_ref", None),
        linked_existing=result.linked_existing,
        duplicate_warning=result.duplicate_warning,
        duplicate_warning_detail=result.duplicate_warning_detail,
    )


# ---------------------------------------------------------------------------
# FRA / PAS 79 OCR (Wave 3) — nested under the module enabled router
# ---------------------------------------------------------------------------


async def _read_fra_pdf_upload(file: UploadFile) -> bytes:
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise BadRequestError("File must be a PDF (.pdf extension)")
    content = await file.read()
    if not content:
        raise BadRequestError("PDF file is empty")
    if len(content) > 25 * 1024 * 1024:
        raise BadRequestError("PDF file exceeds 25 MiB limit")
    if not content.startswith(b"%PDF-"):
        raise BadRequestError("File does not look like a PDF")
    return content


def _fra_draft_response(draft) -> FraOcrDraftResponse:
    return FraOcrDraftResponse.model_validate(draft_to_response_dict(draft))


@_fra_ocr_router.post(
    "/requirements/{requirement_id}/fra-ocr/drafts",
    response_model=FraOcrDraftResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_fra_ocr_draft(
    requirement_id: int,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("compliance_schedule:update"))],
    file: UploadFile = File(...),
):
    """Upload a PAS 79-style FRA PDF and create a pending OCR draft."""
    tenant_id = require_tenant_id(getattr(current_user, "tenant_id", None))
    content = await _read_fra_pdf_upload(file)
    service = ComplianceScheduleFraOcrService(db)
    draft = await service.create_draft_from_upload(
        requirement_id=requirement_id,
        tenant_id=tenant_id,
        user_id=current_user.id,
        content=content,
        filename=file.filename or "fra.pdf",
        content_type=file.content_type or "application/pdf",
    )
    return _fra_draft_response(draft)


@_fra_ocr_router.get(
    "/requirements/{requirement_id}/fra-ocr/drafts",
    response_model=FraOcrDraftListResponse,
)
async def list_fra_ocr_drafts(
    requirement_id: int,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("compliance_schedule:read"))],
    status_filter: Optional[str] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    tenant_id = require_tenant_id(getattr(current_user, "tenant_id", None))
    service = ComplianceScheduleFraOcrService(db)
    items, total = await service.list_drafts(
        requirement_id=requirement_id,
        tenant_id=tenant_id,
        status=status_filter,
        page=page,
        page_size=page_size,
    )
    return FraOcrDraftListResponse(
        items=[_fra_draft_response(d) for d in items],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages_for(total, page_size),
    )


@_fra_ocr_router.get("/fra-ocr/drafts/{draft_id}", response_model=FraOcrDraftResponse)
async def get_fra_ocr_draft(
    draft_id: int,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("compliance_schedule:read"))],
):
    tenant_id = require_tenant_id(getattr(current_user, "tenant_id", None))
    service = ComplianceScheduleFraOcrService(db)
    draft = await service.get_draft(draft_id=draft_id, tenant_id=tenant_id)
    return _fra_draft_response(draft)


@_fra_ocr_router.post("/fra-ocr/drafts/{draft_id}/confirm", response_model=FraOcrConfirmResponse)
async def confirm_fra_ocr_draft(
    draft_id: int,
    data: FraOcrDraftConfirmRequest,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("compliance_schedule:update"))],
):
    """Human gate: write ``next_due_date`` and record confirmed actions on the draft."""
    tenant_id = require_tenant_id(getattr(current_user, "tenant_id", None))
    service = ComplianceScheduleFraOcrService(db)
    draft, requirement, applied = await service.apply_confirmed_plan(
        draft_id=draft_id,
        tenant_id=tenant_id,
        user_id=current_user.id,
        next_due_date=data.next_due_date,
        actions=[a.model_dump(mode="json") for a in data.actions],
        note=data.note,
        acknowledged_warnings=data.acknowledged_warnings,
    )
    applied_summary = dict(applied)
    for key in ("next_due_date_before", "next_due_date_after"):
        value = applied_summary.get(key)
        if isinstance(value, str):
            applied_summary[key] = date.fromisoformat(value)
    return FraOcrConfirmResponse(
        draft=_fra_draft_response(draft),
        requirement=_requirement_response(requirement),
        applied=FraOcrAppliedSummary.model_validate(applied_summary),
    )


@_fra_ocr_router.post(
    "/fra-ocr/drafts/{draft_id}/file",
    response_model=FraOcrFilingResponse,
    dependencies=[Depends(require_permission("document:create"))],
)
async def file_fra_ocr_draft(
    draft_id: int,
    data: FraOcrFileRequest,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("compliance_schedule:update"))],
):
    """File a confirmed FRA OCR source PDF into the Governance Library (taxonomy 03.01)."""
    tenant_id = require_tenant_id(getattr(current_user, "tenant_id", None))
    service = ComplianceScheduleFraOcrService(db)
    result = await service.file_draft_to_library(
        draft_id=draft_id,
        tenant_id=tenant_id,
        user=current_user,
        category_id=data.category_id,
        title=data.title,
    )
    return FraOcrFilingResponse(
        draft=_fra_draft_response(result.draft),
        library_document_id=result.document.id,
        pel_doc_ref=getattr(result.document, "pel_doc_ref", None),
        duplicate_warning=result.duplicate_warning,
        duplicate_warning_detail=result.duplicate_warning_detail,
    )


@_fra_ocr_router.post("/fra-ocr/drafts/{draft_id}/discard", response_model=FraOcrDraftResponse)
async def discard_fra_ocr_draft(
    draft_id: int,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("compliance_schedule:update"))],
    body: FraOcrDiscardRequest | None = None,
):
    tenant_id = require_tenant_id(getattr(current_user, "tenant_id", None))
    payload = body or FraOcrDiscardRequest()
    service = ComplianceScheduleFraOcrService(db)
    draft = await service.discard_draft(
        draft_id=draft_id,
        tenant_id=tenant_id,
        user_id=current_user.id,
        reason=payload.reason,
    )
    return _fra_draft_response(draft)


_enabled_router.include_router(_fra_ocr_router)
router.include_router(_enabled_router)
