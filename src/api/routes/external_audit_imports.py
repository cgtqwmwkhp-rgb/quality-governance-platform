"""External audit OCR/import routes."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import update

from src.api.dependencies import CurrentUser, DbSession, require_permission
from src.domain.models.external_audit_import import ExternalAuditImportJob, ExternalAuditImportStatus
from src.domain.models.user import User
from src.domain.services.external_audit_import_service import ExternalAuditImportService
from src.infrastructure.tasks.external_audit_import_tasks import process_external_audit_import_job

router = APIRouter()
logger = logging.getLogger(__name__)


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
    source_sheet_count: Optional[int] = None
    has_tabular_data: bool = False
    analysis_summary: Optional[str] = None
    detected_scheme: Optional[str] = None
    detected_scheme_confidence: Optional[float] = None
    scheme_version: Optional[str] = None
    issuer_name: Optional[str] = None
    report_date: Optional[datetime] = None
    overall_score: Optional[float] = None
    max_score: Optional[float] = None
    score_percentage: Optional[float] = None
    outcome_status: Optional[str] = None
    provenance_json: Optional[dict] = None
    classification_basis_json: Optional[dict] = None
    score_breakdown_json: Optional[list] = None
    evidence_preview_json: Optional[list] = None
    positive_summary_json: Optional[list] = None
    nonconformity_summary_json: Optional[list] = None
    improvement_summary_json: Optional[list] = None
    promotion_summary_json: Optional[dict] = None
    processing_warnings_json: Optional[list] = None
    error_code: Optional[str] = None
    error_detail: Optional[str] = None
    specialist_home_path: Optional[str] = None
    specialist_home_label: Optional[str] = None
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


def _determine_specialist_home(job: ExternalAuditImportJobResponse) -> tuple[str, str]:
    scheme = (job.detected_scheme or "").strip().lower()
    if not scheme:
        provenance = job.provenance_json or {}
        declared_scheme = str(provenance.get("declared_assurance_scheme") or "").lower()
        declared_source = str(provenance.get("declared_source_origin") or "").lower()
        if "achilles" in declared_scheme or "uvdb" in declared_scheme:
            scheme = "achilles_uvdb"
        elif "planet mark" in declared_scheme:
            scheme = "planet_mark"
        elif declared_scheme.startswith("iso"):
            scheme = "iso"
        elif declared_source == "customer":
            scheme = "customer_other"

    if scheme == "achilles_uvdb":
        return "/uvdb", "Open Achilles / UVDB"
    if scheme == "planet_mark":
        return "/planet-mark", "Open Planet Mark"
    if scheme == "iso":
        return "/compliance", "Open ISO Compliance"
    return "/compliance", "Open Compliance Summary"


def _annotate_job_response(job: ExternalAuditImportJobResponse) -> ExternalAuditImportJobResponse:
    path, label = _determine_specialist_home(job)
    job.specialist_home_path = path
    job.specialist_home_label = label
    return job


@router.post("/jobs", response_model=ExternalAuditImportJobResponse, status_code=status.HTTP_201_CREATED)
async def create_import_job(
    payload: ExternalAuditImportJobCreate,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("audit:update"))],
) -> ExternalAuditImportJobResponse:
    """Create an idempotent external audit import job for a run/source document."""
    service = ExternalAuditImportService(db)
    job = await service.create_job(
        audit_run_id=payload.audit_run_id,
        source_document_asset_id=payload.source_document_asset_id,
        user_id=current_user.id,
        tenant_id=current_user.tenant_id,
    )
    return _annotate_job_response(ExternalAuditImportJobResponse.model_validate(job))


_processing_jobs: set[int] = set()


async def _process_import_async(job_id: int, tenant_id: int | None, user_id: int | None) -> None:
    """Fire-and-forget coroutine that processes an import job on the running event loop.

    Runs in the server's event loop via ``asyncio.create_task`` so it survives
    after the HTTP response is sent.  On failure the job is marked FAILED so
    the user sees an actionable error instead of an infinite "queued" state.
    """
    from src.infrastructure.database import async_session_maker

    try:
        async with async_session_maker() as session:
            service = ExternalAuditImportService(session)
            await service.process_job(job_id=job_id, tenant_id=tenant_id, user_id=user_id)
            await session.commit()
        logger.info("Inline import processing completed for job %s", job_id)
    except Exception:
        logger.exception("Inline import processing failed for job %s", job_id)
        try:
            async with async_session_maker() as err_session:
                await err_session.execute(
                    update(ExternalAuditImportJob)
                    .where(
                        ExternalAuditImportJob.id == job_id,
                        ExternalAuditImportJob.status.in_(
                            [
                                ExternalAuditImportStatus.QUEUED,
                                ExternalAuditImportStatus.PROCESSING,
                            ]
                        ),
                    )
                    .values(
                        status=ExternalAuditImportStatus.FAILED,
                        error_code="INLINE_PROCESSING_FAILED",
                        error_detail="Import processing failed. Check server logs and retry.",
                    )
                )
                await err_session.commit()
        except Exception:
            logger.exception("Could not mark job %s as FAILED after processing error", job_id)
    finally:
        _processing_jobs.discard(job_id)


def _schedule_inline_processing(job_id: int, tenant_id: int | None, user_id: int | None) -> None:
    """Schedule import processing on the running event loop (at most once per job)."""
    if job_id in _processing_jobs:
        return
    _processing_jobs.add(job_id)
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_process_import_async(job_id, tenant_id, user_id))
    except RuntimeError:
        _processing_jobs.discard(job_id)
        logger.warning("No running event loop for inline processing of job %s", job_id)


@router.post("/jobs/{job_id}/queue", response_model=ExternalAuditImportJobResponse)
async def queue_import_job(
    job_id: int,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("audit:update"))],
) -> ExternalAuditImportJobResponse:
    """Queue an external audit import job for asynchronous OCR/analysis."""
    service = ExternalAuditImportService(db)
    job, should_enqueue = await service.queue_job(
        job_id=job_id,
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
    )
    if should_enqueue:
        await db.commit()
        await db.refresh(job)
        try:
            process_external_audit_import_job.delay(job.id, current_user.tenant_id, current_user.id)
        except Exception:
            logger.warning("Celery dispatch unavailable for job %s", job.id)
        _schedule_inline_processing(job.id, current_user.tenant_id, current_user.id)
    elif job.status == ExternalAuditImportStatus.QUEUED:
        # Job was previously queued but never processed (e.g. no Celery worker
        # picked it up and the earlier inline attempt failed/was killed).
        # Re-trigger processing so the job doesn't stay stuck forever.
        _schedule_inline_processing(job.id, current_user.tenant_id, current_user.id)
    return _annotate_job_response(ExternalAuditImportJobResponse.model_validate(job))


@router.get("/runs/{audit_run_id}/latest-job", response_model=ExternalAuditImportJobResponse)
async def get_latest_import_job_for_run(
    audit_run_id: int,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("audit:read"))],
) -> ExternalAuditImportJobResponse:
    """Resolve the most recent import job for an audit run."""
    service = ExternalAuditImportService(db)
    job = await service.get_latest_job_for_run(audit_run_id=audit_run_id, tenant_id=current_user.tenant_id)
    return _annotate_job_response(ExternalAuditImportJobResponse.model_validate(job))


@router.get("/jobs/{job_id}", response_model=ExternalAuditImportJobResponse)
async def get_import_job(
    job_id: int,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("audit:read"))],
) -> ExternalAuditImportJobResponse:
    """Get import-job status and summary."""
    service = ExternalAuditImportService(db)
    job = await service.get_job(job_id=job_id, tenant_id=current_user.tenant_id)
    if job.status == ExternalAuditImportStatus.QUEUED:
        _schedule_inline_processing(job.id, current_user.tenant_id, current_user.id)
    return _annotate_job_response(ExternalAuditImportJobResponse.model_validate(job))


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
    return _annotate_job_response(ExternalAuditImportJobResponse.model_validate(job))
