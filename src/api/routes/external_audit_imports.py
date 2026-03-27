"""External audit OCR/import routes."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, ConfigDict, Field

from src.api.dependencies import CurrentUser, DbSession, require_permission
from src.domain.models.user import User
from src.domain.services.external_audit_import_service import ExternalAuditImportService
from src.infrastructure.tasks.external_audit_import_tasks import process_external_audit_import_job

router = APIRouter()


class ExternalAuditImportJobCreate(BaseModel):
    audit_run_id: int
    source_document_asset_id: Optional[int] = None


class ExternalAuditImportJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    reference_number: str
    audit_run_id: int
    source_document_asset_id: int
    status: str
    provider_name: Optional[str] = None
    provider_model: Optional[str] = None
    source_filename: Optional[str] = None
    extraction_method: Optional[str] = None
    extraction_text_preview: Optional[str] = None
    page_count: Optional[int] = None
    analysis_summary: Optional[str] = None
    error_code: Optional[str] = None
    error_detail: Optional[str] = None
    created_at: datetime
    processed_at: Optional[datetime] = None
    promoted_at: Optional[datetime] = None


class ExternalAuditDraftResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    import_job_id: int
    audit_run_id: int
    status: str
    title: str
    description: str
    severity: str
    finding_type: str
    confidence_score: Optional[float] = None
    competence_verdict: Optional[str] = None
    source_pages_json: Optional[list] = None
    evidence_snippets_json: Optional[list] = None
    mapped_frameworks_json: Optional[list] = None
    mapped_standards_json: Optional[list] = None
    suggested_action_title: Optional[str] = None
    suggested_action_description: Optional[str] = None
    suggested_risk_title: Optional[str] = None
    review_notes: Optional[str] = None
    promoted_finding_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime


class ExternalAuditDraftReviewRequest(BaseModel):
    status: str = Field(pattern="^(accepted|rejected|draft)$")
    review_notes: Optional[str] = None
    title: Optional[str] = Field(default=None, max_length=300)
    description: Optional[str] = None
    severity: Optional[str] = Field(default=None, max_length=50)


@router.post("/jobs", response_model=ExternalAuditImportJobResponse, status_code=status.HTTP_201_CREATED)
async def create_import_job(
    payload: ExternalAuditImportJobCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> ExternalAuditImportJobResponse:
    """Create an idempotent external audit import job for a run/source document."""
    service = ExternalAuditImportService(db)
    job = await service.create_job(
        audit_run_id=payload.audit_run_id,
        source_document_asset_id=payload.source_document_asset_id,
        user_id=current_user.id,
        tenant_id=current_user.tenant_id,
    )
    return ExternalAuditImportJobResponse.model_validate(job)


@router.post("/jobs/{job_id}/queue", response_model=ExternalAuditImportJobResponse)
async def queue_import_job(
    job_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> ExternalAuditImportJobResponse:
    """Queue an external audit import job for asynchronous OCR/analysis."""
    service = ExternalAuditImportService(db)
    job = await service.queue_job(job_id=job_id, tenant_id=current_user.tenant_id, user_id=current_user.id)
    process_external_audit_import_job.delay(job.id, current_user.tenant_id, current_user.id)
    return ExternalAuditImportJobResponse.model_validate(job)


@router.get("/jobs/{job_id}", response_model=ExternalAuditImportJobResponse)
async def get_import_job(
    job_id: int,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("audit:read"))],
) -> ExternalAuditImportJobResponse:
    """Get import-job status and summary."""
    service = ExternalAuditImportService(db)
    job = await service.get_job(job_id=job_id, tenant_id=current_user.tenant_id)
    return ExternalAuditImportJobResponse.model_validate(job)


@router.get("/jobs/{job_id}/drafts", response_model=list[ExternalAuditDraftResponse])
async def list_import_job_drafts(
    job_id: int,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("audit:read"))],
) -> list[ExternalAuditDraftResponse]:
    """List reviewable drafts generated for an import job."""
    service = ExternalAuditImportService(db)
    drafts = await service.list_job_drafts(job_id=job_id, tenant_id=current_user.tenant_id)
    return [ExternalAuditDraftResponse.model_validate(draft) for draft in drafts]


@router.patch("/drafts/{draft_id}", response_model=ExternalAuditDraftResponse)
async def review_import_draft(
    draft_id: int,
    payload: ExternalAuditDraftReviewRequest,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("audit:update"))],
) -> ExternalAuditDraftResponse:
    """Accept, reject, or edit a draft before live promotion."""
    service = ExternalAuditImportService(db)
    draft = await service.review_draft(
        draft_id=draft_id,
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        status_value=payload.status,
        review_notes=payload.review_notes,
        title=payload.title,
        description=payload.description,
        severity=payload.severity,
    )
    return ExternalAuditDraftResponse.model_validate(draft)


@router.post("/jobs/{job_id}/promote", response_model=ExternalAuditImportJobResponse)
async def promote_import_job(
    job_id: int,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("audit:update"))],
) -> ExternalAuditImportJobResponse:
    """Promote approved drafts into live audit findings and downstream remediation."""
    service = ExternalAuditImportService(db)
    job = await service.promote_job(job_id=job_id, tenant_id=current_user.tenant_id, user_id=current_user.id)
    return ExternalAuditImportJobResponse.model_validate(job)
