"""Service layer for external audit OCR/import lifecycle.

Path-to-10 S1: thin facade over OCR, analysis, and promotion collaborators.
Canonical extraction lives in ``external_audit_ocr_service``; review analysis in
``external_audit_analysis_service``; materialization/sync in
``external_audit_promotion_service``. Public method signatures are unchanged.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select, update
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.domain.exceptions import ConflictError, NotFoundError, ValidationError
from src.domain.models.audit import AuditFinding, AuditRun
from src.domain.models.document import FileType
from src.domain.models.evidence_asset import EvidenceAsset
from src.domain.models.external_audit_import import (
    ExternalAuditDraft,
    ExternalAuditDraftStatus,
    ExternalAuditImportJob,
    ExternalAuditImportStatus,
)
from src.domain.services.ai_consensus_service import AIConsensusService
from src.domain.services.external_audit_analysis_service import ExternalAuditAnalysisService
from src.domain.services.external_audit_import_ai_metadata import apply_ai_metadata_to_job
from src.domain.services.external_audit_import_failure import classify_processing_failure, is_hard_ai_failure
from src.domain.services.external_audit_ocr_service import MAX_SOURCE_FILE_BYTES, ExternalAuditOcrService
from src.domain.services.external_audit_promotion_service import ExternalAuditPromotionService, PromotionResult
from src.domain.services.external_audit_uvdb_iso_mapping_service import ExternalAuditUVDBISOMappingService
from src.domain.services.gemini_review_service import GeminiReviewService
from src.domain.services.mistral_analysis_service import MistralAnalysisService
from src.domain.services.reference_number import ReferenceNumberService
from src.domain.services.scheme_profiles import validate_against_scheme
from src.infrastructure.storage import StorageError, storage_service

logger = logging.getLogger(__name__)

PROCESSING_TTL_SECONDS = 600  # 10 minutes before a PROCESSING job is considered stale


__all__ = [
    "MAX_SOURCE_FILE_BYTES",
    "PROCESSING_TTL_SECONDS",
    "PromotionResult",
    "ExternalAuditImportService",
]


class ExternalAuditImportService:
    """Orchestrates import job creation, draft review, and promotion."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.analysis_service = ExternalAuditAnalysisService()
        self.ocr_pipeline = ExternalAuditOcrService()
        # Compatibility aliases used by create_job / older call sites
        self.ocr_service = self.ocr_pipeline.ocr_service
        self.ai_analysis_service = MistralAnalysisService()
        self.gemini_review_service = GeminiReviewService()
        self.consensus_service = AIConsensusService()
        self.promotion_service = ExternalAuditPromotionService(self)

    async def get_promotion_reconciliation(self, *, job_id: int, tenant_id: int | None) -> dict[str, object]:
        """Thin facade — canonical implementation lives on ExternalAuditPromotionService."""
        return await self.promotion_service.get_promotion_reconciliation(job_id=job_id, tenant_id=tenant_id)

    async def promote_job(self, *, job_id: int, tenant_id: int | None, user_id: int) -> ExternalAuditImportJob:
        return await self.promotion_service.promote_job(job_id=job_id, tenant_id=tenant_id, user_id=user_id)

    async def enqueue_promote(self, *, job_id: int, tenant_id: int | None, user_id: int) -> ExternalAuditImportJob:
        return await self.promotion_service.enqueue_promote(job_id=job_id, tenant_id=tenant_id, user_id=user_id)

    async def run_promote_chunks(self, *, job_id: int, tenant_id: int | None, user_id: int) -> ExternalAuditImportJob:
        return await self.promotion_service.run_promote_chunks(job_id=job_id, tenant_id=tenant_id, user_id=user_id)

    @staticmethod
    def _scheme_home(scheme: str | None) -> tuple[str, str]:
        return ExternalAuditPromotionService._scheme_home(scheme)

    async def _refresh_job_promotion_summary(self, *, job_id: int, tenant_id: int | None) -> None:
        await self.promotion_service._refresh_job_promotion_summary(job_id=job_id, tenant_id=tenant_id)

    def _build_promotion_summary(self, *, findings: list) -> dict[str, object]:
        return self.promotion_service._build_promotion_summary(findings=findings)

    async def _link_evidence_for_finding(
        self,
        *,
        finding_id: int,
        clause_ids: list[str],
        tenant_id: int | None,
        user_id: int,
        note: str | None,
        confidence: float | None,
    ) -> None:
        await self.promotion_service._link_evidence_for_finding(
            finding_id=finding_id,
            clause_ids=clause_ids,
            tenant_id=tenant_id,
            user_id=user_id,
            note=note,
            confidence=confidence,
        )

    async def _link_source_document_evidence(
        self,
        *,
        asset_id: int,
        clause_ids: list[str],
        tenant_id: int | None,
        user_id: int,
        title: str | None,
    ) -> None:
        await self.promotion_service._link_source_document_evidence(
            asset_id=asset_id,
            clause_ids=clause_ids,
            tenant_id=tenant_id,
            user_id=user_id,
            title=title,
        )

    async def _sync_scheme_records(
        self,
        *,
        job: ExternalAuditImportJob,
        run: AuditRun,
        tenant_id: int | None,
        drafts: list,
    ) -> dict[str, object]:
        return await self.promotion_service._sync_scheme_records(
            job=job,
            run=run,
            tenant_id=tenant_id,
            drafts=drafts,
        )

    async def _sync_planet_mark(
        self,
        *,
        job: ExternalAuditImportJob,
        run: AuditRun,
        tenant_id: int | None,
    ) -> dict[str, object]:
        return await self.promotion_service._sync_planet_mark(
            job=job,
            run=run,
            tenant_id=tenant_id,
        )

    @staticmethod
    def _merge_extractions(
        *,
        native_text: str,
        native_pages: list[str],
        ocr_text: str,
        ocr_pages: list[str],
        native_method: str,
    ) -> tuple[str, list[str], str]:
        return ExternalAuditOcrService._merge_extractions(
            native_text=native_text,
            native_pages=native_pages,
            ocr_text=ocr_text,
            ocr_pages=ocr_pages,
            native_method=native_method,
        )

    def _infer_file_type(self, filename: str | None, content_type: str | None) -> FileType:
        return self.ocr_pipeline._infer_file_type(filename, content_type)

    def ensure_feature_enabled(self) -> None:
        if not settings.external_audit_import_enabled:
            raise ValidationError("External audit import is disabled by configuration")

    async def create_job(
        self,
        *,
        audit_run_id: int,
        user_id: int,
        tenant_id: int | None,
        source_document_asset_id: int | None = None,
    ) -> ExternalAuditImportJob:
        self.ensure_feature_enabled()
        run = await self._get_run(audit_run_id=audit_run_id, tenant_id=tenant_id)
        parent_tenant_id = run.tenant_id
        if parent_tenant_id is None:
            raise ValidationError("Audit run must have a tenant before creating an external audit import job")
        asset_id = source_document_asset_id or run.source_document_asset_id
        if not asset_id:
            raise ValidationError("Audit run does not have a source document asset attached")
        asset = await self._get_asset(asset_id=asset_id, tenant_id=tenant_id)
        if str(asset.source_id) != str(run.id):
            raise ValidationError("Source document asset is not linked to the requested audit run")

        checksum = asset.checksum_sha256 or ""
        if not checksum:
            payload = await storage_service().download(asset.storage_key)
            checksum = hashlib.sha256(payload).hexdigest()

        idempotency_key = f"{run.id}:{asset.id}:{checksum}"
        existing = await self._get_job_by_idempotency(idempotency_key=idempotency_key, tenant_id=parent_tenant_id)
        if existing:
            return existing

        ref = await ReferenceNumberService.generate(self.db, "audit_import", ExternalAuditImportJob)
        job = ExternalAuditImportJob(
            reference_number=ref,
            audit_run_id=run.id,
            source_document_asset_id=asset.id,
            tenant_id=parent_tenant_id,
            status=ExternalAuditImportStatus.PENDING,
            provider_name="mistral" if self.ocr_service.is_configured else "native_only",
            provider_model=self.ocr_service.model if self.ocr_service.is_configured else None,
            source_filename=asset.original_filename,
            source_content_type=asset.content_type,
            source_checksum_sha256=checksum,
            idempotency_key=idempotency_key,
            provenance_json={
                "audit_run_id": run.id,
                "source_asset_id": asset.id,
                "storage_key": asset.storage_key,
                "processing_template_id": run.template_id,
                "processing_template_version": run.template_version,
                "declared_source_origin": run.source_origin,
                "declared_assurance_scheme": run.assurance_scheme,
                "declared_external_body_name": run.external_body_name,
                "declared_external_reference": run.external_reference,
            },
            created_by_id=user_id,
            updated_by_id=user_id,
        )
        self.db.add(job)
        await self.db.flush()
        await self.db.refresh(job)
        return job

    async def queue_job(
        self, *, job_id: int, tenant_id: int | None, user_id: int
    ) -> tuple[ExternalAuditImportJob, bool]:
        job = await self.get_job(job_id=job_id, tenant_id=tenant_id)
        if job.status in {
            ExternalAuditImportStatus.QUEUED,
            ExternalAuditImportStatus.PROCESSING,
            ExternalAuditImportStatus.REVIEW_REQUIRED,
            ExternalAuditImportStatus.COMPLETED,
            ExternalAuditImportStatus.PROMOTING,
        }:
            return job, False
        job.status = ExternalAuditImportStatus.QUEUED
        job.error_code = None
        job.error_detail = None
        job.updated_by_id = user_id
        await self.db.flush()
        await self.db.refresh(job)
        return job, True

    async def mark_queue_dispatch_failed(
        self,
        *,
        job_id: int,
        tenant_id: int | None,
        user_id: int,
        detail: str | None = None,
    ) -> ExternalAuditImportJob:
        """Mark a job failed when the background queue broker cannot accept work.

        Leaves the job retryable via ``queue_job`` (FAILED is outside the
        in-flight status set) with an explicit reason code for operators/UI.
        """
        job = await self.get_job(job_id=job_id, tenant_id=tenant_id)
        if job.status != ExternalAuditImportStatus.QUEUED:
            return job
        job.status = ExternalAuditImportStatus.FAILED
        job.error_code = "QUEUE_DISPATCH_FAILED"
        job.error_detail = detail or (
            "Unable to dispatch the import job to the background queue. "
            "Celery/broker is unavailable. Retry queueing or use Process."
        )
        job.updated_by_id = user_id
        await self.db.flush()
        await self.db.refresh(job)
        return job

    async def get_job(self, *, job_id: int, tenant_id: int | None) -> ExternalAuditImportJob:
        result = await self.db.execute(
            select(ExternalAuditImportJob).where(
                ExternalAuditImportJob.id == job_id,
                ExternalAuditImportJob.tenant_id == tenant_id,
            )
        )
        job = result.scalar_one_or_none()
        if job is None and tenant_id is None:
            unscoped_result = await self.db.execute(
                select(ExternalAuditImportJob).where(ExternalAuditImportJob.id == job_id)
            )
            job = unscoped_result.scalar_one_or_none()
            if job is not None:
                logger.warning(
                    "Recovered external audit import job %s without request tenant scope using persisted tenant %s",
                    job_id,
                    job.tenant_id,
                )
        if job is None and tenant_id is not None:
            legacy_result = await self.db.execute(
                select(ExternalAuditImportJob).where(
                    ExternalAuditImportJob.id == job_id,
                    ExternalAuditImportJob.tenant_id.is_(None),
                )
            )
            job = legacy_result.scalar_one_or_none()
            if job is not None:
                job.tenant_id = tenant_id
                await self.db.flush()
                logger.warning(
                    "Recovered legacy tenantless external audit import job %s into tenant %s",
                    job_id,
                    tenant_id,
                )
        if not job:
            raise NotFoundError(f"External audit import job {job_id} not found")
        await self._recover_stale_processing(job)
        return job

    async def _recover_stale_processing(self, job: ExternalAuditImportJob) -> None:
        """Auto-recover jobs stuck in QUEUED, PROCESSING, or PROMOTING beyond the TTL."""
        if job.status not in (
            ExternalAuditImportStatus.QUEUED,
            ExternalAuditImportStatus.PROCESSING,
            ExternalAuditImportStatus.PROMOTING,
        ):
            return
        if job.status == ExternalAuditImportStatus.PROMOTING and job.promote_lease_expires_at:
            expires_at = job.promote_lease_expires_at
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) >= expires_at:
                job.status = ExternalAuditImportStatus.REVIEW_REQUIRED
                job.promote_lease_expires_at = None
                job.error_code = "STALE_PROMOTION_LEASE"
                job.error_detail = "Promotion lease expired; accepted drafts remain available for a safe retry."
                await self.db.flush()
            return
        updated_at = job.updated_at if hasattr(job, "updated_at") and job.updated_at else job.created_at
        if updated_at is None:
            return
        now = datetime.now(timezone.utc)
        if updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=timezone.utc)
        elapsed = (now - updated_at).total_seconds()
        if elapsed > PROCESSING_TTL_SECONDS:
            prior_status = job.status
            logger.warning(
                "Recovering stale %s job %s (stuck for %.0fs)",
                prior_status.value if hasattr(prior_status, "value") else prior_status,
                job.id,
                elapsed,
            )
            if prior_status == ExternalAuditImportStatus.PROMOTING:
                job.status = ExternalAuditImportStatus.REVIEW_REQUIRED
                job.promote_lease_expires_at = None
                job.error_code = "STALE_PROMOTION_LEASE"
                job.error_detail = "Promotion lease expired; accepted drafts remain available for a safe retry."
                await self.db.flush()
                return
            job.status = ExternalAuditImportStatus.FAILED
            if prior_status == ExternalAuditImportStatus.QUEUED:
                job.error_code = "STALE_QUEUE_TIMEOUT"
                job.error_detail = (
                    f"Job remained queued for more than {PROCESSING_TTL_SECONDS // 60} minutes "
                    "without a worker picking it up. Retry queueing or process synchronously."
                )
            else:
                job.error_code = "PROCESSING_TIMEOUT"
                job.error_detail = (
                    f"Processing did not complete within {PROCESSING_TTL_SECONDS // 60} minutes. "
                    "The job has been automatically reset. Please retry."
                )
            await self.db.flush()

    async def get_latest_job_for_run(self, *, audit_run_id: int, tenant_id: int | None) -> ExternalAuditImportJob:
        await self._get_run(audit_run_id=audit_run_id, tenant_id=tenant_id)
        result = await self.db.execute(
            select(ExternalAuditImportJob)
            .where(
                ExternalAuditImportJob.audit_run_id == audit_run_id,
                ExternalAuditImportJob.tenant_id == tenant_id,
            )
            .order_by(ExternalAuditImportJob.id.desc())
            .limit(1)
        )
        job = result.scalar_one_or_none()
        if job is None and tenant_id is None:
            unscoped_result = await self.db.execute(
                select(ExternalAuditImportJob)
                .where(ExternalAuditImportJob.audit_run_id == audit_run_id)
                .order_by(ExternalAuditImportJob.id.desc())
                .limit(1)
            )
            job = unscoped_result.scalar_one_or_none()
            if job is not None:
                logger.warning(
                    "Recovered latest external audit import job %s for run %s without request tenant scope",
                    job.id,
                    audit_run_id,
                )
        if job is None and tenant_id is not None:
            legacy_result = await self.db.execute(
                select(ExternalAuditImportJob)
                .where(
                    ExternalAuditImportJob.audit_run_id == audit_run_id,
                    ExternalAuditImportJob.tenant_id.is_(None),
                )
                .order_by(ExternalAuditImportJob.id.desc())
                .limit(1)
            )
            job = legacy_result.scalar_one_or_none()
            if job is not None:
                job.tenant_id = tenant_id
                await self.db.flush()
                logger.warning(
                    "Recovered latest legacy tenantless external audit import job %s into tenant %s",
                    job.id,
                    tenant_id,
                )
        if not job:
            raise NotFoundError(f"External audit import job not found for audit run {audit_run_id}")
        return job

    async def list_job_drafts(self, *, job_id: int, tenant_id: int | None) -> list[ExternalAuditDraft]:
        await self.get_job(job_id=job_id, tenant_id=tenant_id)
        result = await self.db.execute(
            select(ExternalAuditDraft)
            .where(
                ExternalAuditDraft.import_job_id == job_id,
                ExternalAuditDraft.tenant_id == tenant_id,
            )
            .order_by(ExternalAuditDraft.id.asc())
        )
        drafts = list(result.scalars().all())
        if drafts:
            return drafts

        if tenant_id is None:
            unscoped_result = await self.db.execute(
                select(ExternalAuditDraft)
                .where(ExternalAuditDraft.import_job_id == job_id)
                .order_by(ExternalAuditDraft.id.asc())
            )
            drafts = list(unscoped_result.scalars().all())
            if drafts:
                logger.warning(
                    "Recovered %s external audit draft(s) for job %s without request tenant scope",
                    len(drafts),
                    job_id,
                )
            return drafts

        legacy_result = await self.db.execute(
            select(ExternalAuditDraft)
            .where(
                ExternalAuditDraft.import_job_id == job_id,
                ExternalAuditDraft.tenant_id.is_(None),
            )
            .order_by(ExternalAuditDraft.id.asc())
        )
        drafts = list(legacy_result.scalars().all())
        if drafts:
            for draft in drafts:
                draft.tenant_id = tenant_id
            await self.db.flush()
            logger.warning(
                "Recovered %s legacy tenantless external audit draft(s) for job %s into tenant %s",
                len(drafts),
                job_id,
                tenant_id,
            )
        return drafts

    async def process_job(
        self, *, job_id: int, tenant_id: int | None, user_id: int | None = None
    ) -> ExternalAuditImportJob:
        job = await self.get_job(job_id=job_id, tenant_id=tenant_id)
        effective_tenant_id = job.tenant_id
        transition_values: dict[str, object] = {"status": ExternalAuditImportStatus.PROCESSING}
        if user_id is not None:
            transition_values["updated_by_id"] = user_id

        transitioned = await self.db.execute(
            update(ExternalAuditImportJob)
            .where(
                ExternalAuditImportJob.id == job_id,
                ExternalAuditImportJob.tenant_id == effective_tenant_id,
                ExternalAuditImportJob.status.in_(
                    [
                        ExternalAuditImportStatus.QUEUED,
                        ExternalAuditImportStatus.PROCESSING,
                    ]
                ),
            )
            .values(**transition_values)
        )
        if transitioned.rowcount != 1:
            job = await self.get_job(job_id=job_id, tenant_id=effective_tenant_id)
            logger.info(
                "Skipping external audit import job %s re-entry because status is %s",
                job.id,
                job.status,
            )
            return job

        try:
            job = await self.get_job(job_id=job_id, tenant_id=effective_tenant_id)
        except Exception:
            logger.exception("Could not reload job %s after QUEUED→PROCESSING transition", job_id)
            raise

        asset = await self._get_asset(asset_id=job.source_document_asset_id, tenant_id=effective_tenant_id)
        run = await self._get_run(audit_run_id=job.audit_run_id, tenant_id=effective_tenant_id)

        job.updated_by_id = user_id or job.updated_by_id
        job.error_code = None
        job.error_detail = None
        await self.db.flush()

        try:
            raw = await storage_service().download(asset.storage_key)
        except StorageError as exc:
            job.status = ExternalAuditImportStatus.FAILED
            job.error_code = "SOURCE_DOWNLOAD_FAILED"
            job.error_detail = "Unable to download the source audit file for OCR/import processing."
            logger.warning("External audit import download failed for job %s: %s", job.id, type(exc).__name__)
            await self.db.flush()
            return job

        if len(raw) > MAX_SOURCE_FILE_BYTES:
            job.status = ExternalAuditImportStatus.FAILED
            job.error_code = "SOURCE_FILE_TOO_LARGE"
            job.error_detail = (
                f"Source file is {len(raw) // (1024 * 1024)}MB, which exceeds the "
                f"{MAX_SOURCE_FILE_BYTES // (1024 * 1024)}MB limit."
            )
            logger.warning("Source file too large for job %s: %d bytes", job.id, len(raw))
            await self.db.flush()
            return job

        try:
            extraction_result = await self.ocr_pipeline.extract(
                raw=raw,
                filename=asset.original_filename,
                content_type=asset.content_type,
            )
            if extraction_result.hard_ocr_failure:
                job.status = ExternalAuditImportStatus.FAILED
                job.error_code = "OCR_FAILED"
                job.error_detail = (
                    extraction_result.note
                    or "OCR provider failed and no native text could be extracted from the source document."
                )
                logger.warning("OCR hard-failed for job %s with no recoverable text", job.id)
                await self.db.flush()
                await self.db.refresh(job)
                return job

            text = extraction_result.text
            page_texts = extraction_result.page_texts
            extraction_method = extraction_result.extraction_method
            note = extraction_result.note
            # Compatibility names used when persisting job metadata below
            extraction = extraction_result

            import asyncio as _aio

            mistral_result, gemini_result = await _aio.gather(
                self.ai_analysis_service.analyze_text(text, assurance_scheme=run.assurance_scheme),
                self.gemini_review_service.review(
                    raw_pdf=raw,
                    text=text,
                    filename=asset.original_filename or "source.pdf",
                    content_type=asset.content_type or "application/pdf",
                    assurance_scheme=run.assurance_scheme,
                ),
            )
            ai_result = self.consensus_service.reconcile(mistral_result, gemini_result)

            if self._is_hard_ai_failure(mistral_result, gemini_result):
                job.status = ExternalAuditImportStatus.FAILED
                job.error_code = "AI_ANALYSIS_FAILED"
                warning_text = "; ".join(ai_result.warnings[:3]) if ai_result.warnings else ""
                job.error_detail = warning_text or (
                    "Configured AI analysis providers failed before review could begin. Retry the job."
                )
                logger.warning("AI analysis hard-failed for job %s", job.id)
                await self.db.flush()
                await self.db.refresh(job)
                return job

            scheme_warnings = validate_against_scheme(
                scheme=job.detected_scheme or "",
                overall_score=ai_result.overall_score,
                max_score=ai_result.max_score,
                score_percentage=ai_result.score_percentage,
                score_breakdown=ai_result.score_breakdown,
            )
            ai_result.warnings.extend(scheme_warnings)

            analysis = self.analysis_service.analyze(
                extracted_text=text,
                page_texts=page_texts or ([text] if text else []),
                assurance_scheme=run.assurance_scheme,
                ai_result=ai_result,
            )
            uvdb_iso_enrichment = await ExternalAuditUVDBISOMappingService(self.db).enrich(
                detected_scheme=analysis.detected_scheme,
                tenant_id=effective_tenant_id,
                candidate_texts=[f"{candidate.title}\n{candidate.description}" for candidate in analysis.findings],
            )
            for candidate, matrix_mappings, readiness in zip(
                analysis.findings,
                uvdb_iso_enrichment.candidate_mapped_standards,
                uvdb_iso_enrichment.candidate_readiness,
            ):
                candidate.mapped_standards = ExternalAuditUVDBISOMappingService.merge_mapped_standards(
                    candidate.mapped_standards, matrix_mappings
                )
                candidate.provenance["uvdb_iso_mapping_readiness"] = readiness
            analysis.classification_basis["uvdb_iso_mapping"] = uvdb_iso_enrichment.readiness_checklist

            preview = text[:500] if text else None
            replacement_drafts = [
                ExternalAuditDraft(
                    import_job_id=job.id,
                    audit_run_id=run.id,
                    tenant_id=effective_tenant_id,
                    status=ExternalAuditDraftStatus.DRAFT,
                    title=candidate.title,
                    description=candidate.description,
                    severity=candidate.severity,
                    finding_type=candidate.finding_type,
                    confidence_score=candidate.confidence_score,
                    competence_verdict=candidate.competence_verdict,
                    source_pages_json=candidate.source_pages,
                    evidence_snippets_json=candidate.evidence_snippets,
                    mapped_frameworks_json=candidate.mapped_frameworks,
                    mapped_standards_json=candidate.mapped_standards,
                    provenance_json=candidate.provenance,
                    suggested_action_title=candidate.suggested_action_title,
                    suggested_action_description=candidate.suggested_action_description,
                    suggested_risk_title=candidate.suggested_risk_title,
                    created_by_id=user_id or job.created_by_id,
                    updated_by_id=user_id or job.updated_by_id,
                )
                for candidate in analysis.findings
            ]
            async with self.db.begin_nested():
                await self._clear_existing_drafts(job_id=job.id, tenant_id=effective_tenant_id)
                for draft in replacement_drafts:
                    self.db.add(draft)

                job.status = ExternalAuditImportStatus.REVIEW_REQUIRED
                job.extraction_method = extraction_method
                job.extraction_text_preview = preview
                job.page_count = extraction.page_count or len(page_texts) or None
                job.source_sheet_count = extraction.sheet_count
                job.has_tabular_data = bool(extraction.has_tables)
                job.page_texts_json = page_texts or None
                provenance_update: dict = {
                    **(job.provenance_json or {}),
                    "extraction_note": note,
                    "mapped_frameworks": analysis.mapped_frameworks,
                    "mapped_standards": analysis.mapped_standards,
                    "classification_basis": analysis.classification_basis,
                    "uvdb_iso_mapping_readiness": uvdb_iso_enrichment.readiness_checklist,
                    "declared_vs_detected": {
                        "declared_source_origin": run.source_origin,
                        "declared_assurance_scheme": run.assurance_scheme,
                        "detected_scheme": analysis.detected_scheme,
                        "detected_scheme_confidence": analysis.detected_scheme_confidence,
                    },
                }
                # Store Planet Mark carbon data for downstream sync
                if analysis.planet_mark_carbon:
                    provenance_update["planet_mark_carbon"] = analysis.planet_mark_carbon
                job.provenance_json = provenance_update
                job.analysis_summary = analysis.summary
                job.detected_scheme = analysis.detected_scheme
                job.detected_scheme_confidence = analysis.detected_scheme_confidence
                job.scheme_version = analysis.scheme_version
                job.issuer_name = analysis.issuer_name
                job.report_date = analysis.report_date
                job.overall_score = analysis.overall_score
                job.max_score = analysis.max_score
                job.score_percentage = (
                    max(0.0, min(analysis.score_percentage, 100.0)) if analysis.score_percentage is not None else None
                )
                job.outcome_status = analysis.outcome_status
                self._apply_ai_metadata_to_job(job, ai_result)
                job.classification_basis_json = analysis.classification_basis
                job.score_breakdown_json = analysis.score_breakdown or None
                job.evidence_preview_json = analysis.evidence_preview or None
                job.positive_summary_json = analysis.positive_summary or None
                job.nonconformity_summary_json = analysis.nonconformity_summary or None
                job.improvement_summary_json = analysis.improvement_summary or None
                warnings = list(analysis.processing_warnings or [])
                declared = (run.assurance_scheme or "").strip().lower()
                detected = (analysis.detected_scheme or "").strip().lower()
                if declared and detected and declared != detected:
                    warnings.append(
                        f"Declared scheme '{run.assurance_scheme}' does not match "
                        f"detected scheme '{analysis.detected_scheme}'. "
                        f"Please verify the document matches the intended audit type."
                    )
                job.processing_warnings_json = warnings or None
                job.promotion_summary_json = self._build_promotion_summary(findings=analysis.findings)
                job.error_code = None
                job.error_detail = None
                job.processed_at = datetime.now(timezone.utc)
            await self.db.flush()
            await self.db.refresh(job)
            return job
        except Exception as exc:
            error_code, error_detail = self._classify_processing_failure(exc)
            job.status = ExternalAuditImportStatus.FAILED
            job.error_code = error_code
            job.error_detail = error_detail
            logger.exception("External audit import processing failed for job %s", job.id, exc_info=exc)
            await self.db.flush()
            await self.db.refresh(job)
            return job

    @staticmethod
    def _apply_ai_metadata_to_job(job: ExternalAuditImportJob, ai_result: object | None) -> None:
        """Thin facade — canonical logic lives in ``external_audit_import_ai_metadata``."""
        apply_ai_metadata_to_job(job, ai_result)

    @staticmethod
    def _is_hard_ai_failure(mistral_result: object, gemini_result: object) -> bool:
        """Thin facade — canonical logic lives in ``external_audit_import_failure``."""
        return is_hard_ai_failure(mistral_result, gemini_result)

    @staticmethod
    def _classify_processing_failure(exc: BaseException) -> tuple[str, str]:
        """Thin facade — canonical logic lives in ``external_audit_import_failure``."""
        return classify_processing_failure(exc)

    async def review_draft(
        self,
        *,
        draft_id: int,
        tenant_id: int | None,
        user_id: int,
        status_value: str,
        review_notes: str | None = None,
        title: str | None = None,
        description: str | None = None,
        severity: str | None = None,
    ) -> ExternalAuditDraft:
        draft = await self._get_draft(draft_id=draft_id, tenant_id=tenant_id)
        if draft.promoted_finding_id or draft.status == ExternalAuditDraftStatus.PROMOTED:
            raise ConflictError("Promoted drafts can no longer be modified")
        job = await self.get_job(job_id=draft.import_job_id, tenant_id=tenant_id)
        if job.status in {ExternalAuditImportStatus.PROMOTING, ExternalAuditImportStatus.COMPLETED}:
            raise ConflictError("Draft review is locked while the import job is promoting or completed")
        draft.status = ExternalAuditDraftStatus(status_value)
        if review_notes is not None:
            draft.review_notes = review_notes
        if title is not None:
            draft.title = title
        if description is not None:
            draft.description = description
        if severity is not None:
            draft.severity = severity
        draft.updated_by_id = user_id
        await self.db.flush()
        await self._refresh_job_promotion_summary(job_id=draft.import_job_id, tenant_id=tenant_id)
        await self.db.refresh(draft)
        return draft

    async def bulk_review_job_drafts(
        self,
        *,
        job_id: int,
        tenant_id: int | None,
        user_id: int,
        status_value: str,
        review_notes: str | None = None,
        current_status_filter: set[ExternalAuditDraftStatus] | None = None,
    ) -> list[ExternalAuditDraft]:
        job = await self.get_job(job_id=job_id, tenant_id=tenant_id)
        effective_tenant_id = job.tenant_id or tenant_id
        drafts = await self.list_job_drafts(job_id=job_id, tenant_id=effective_tenant_id)
        if job.status in {ExternalAuditImportStatus.PROMOTING, ExternalAuditImportStatus.COMPLETED}:
            raise ConflictError("Draft review is locked while the import job is promoting or completed")

        mutable_drafts = [
            draft
            for draft in drafts
            if not draft.promoted_finding_id and draft.status != ExternalAuditDraftStatus.PROMOTED
        ]
        if current_status_filter is not None:
            mutable_drafts = [draft for draft in mutable_drafts if draft.status in current_status_filter]

        if not mutable_drafts:
            return drafts

        next_status = ExternalAuditDraftStatus(status_value)
        for draft in mutable_drafts:
            draft.status = next_status
            if review_notes is not None:
                draft.review_notes = review_notes
            draft.updated_by_id = user_id

        await self.db.flush()
        await self._refresh_job_promotion_summary(job_id=job_id, tenant_id=effective_tenant_id)
        for draft in mutable_drafts:
            await self.db.refresh(draft)
        return drafts

    async def _get_run(self, *, audit_run_id: int, tenant_id: int | None) -> AuditRun:
        result = await self.db.execute(
            select(AuditRun).where(
                AuditRun.id == audit_run_id,
                AuditRun.tenant_id == tenant_id,
            )
        )
        run = result.scalar_one_or_none()
        if run is None and tenant_id is None:
            unscoped_result = await self.db.execute(select(AuditRun).where(AuditRun.id == audit_run_id))
            run = unscoped_result.scalar_one_or_none()
            if run is not None:
                logger.warning(
                    "Recovered audit run %s without request tenant scope using persisted tenant %s",
                    audit_run_id,
                    run.tenant_id,
                )
        if run is None and tenant_id is not None:
            legacy_result = await self.db.execute(
                select(AuditRun).where(
                    AuditRun.id == audit_run_id,
                    AuditRun.tenant_id.is_(None),
                )
            )
            run = legacy_result.scalar_one_or_none()
            if run is not None:
                run.tenant_id = tenant_id
                await self.db.flush()
                logger.warning(
                    "Recovered legacy tenantless audit run %s into tenant %s",
                    audit_run_id,
                    tenant_id,
                )
        if not run:
            raise NotFoundError(f"Audit run {audit_run_id} not found")
        return run

    async def _get_asset(self, *, asset_id: int, tenant_id: int | None) -> EvidenceAsset:
        result = await self.db.execute(
            select(EvidenceAsset).where(
                EvidenceAsset.id == asset_id,
                EvidenceAsset.tenant_id == tenant_id,
            )
        )
        asset = result.scalar_one_or_none()
        if asset is None and tenant_id is not None:
            legacy_result = await self.db.execute(
                select(EvidenceAsset).where(
                    EvidenceAsset.id == asset_id,
                    EvidenceAsset.tenant_id.is_(None),
                )
            )
            asset = legacy_result.scalar_one_or_none()
            if asset is not None:
                asset.tenant_id = tenant_id
                await self.db.flush()
                logger.warning(
                    "Recovered legacy tenantless evidence asset %s into tenant %s",
                    asset_id,
                    tenant_id,
                )
        if not asset:
            raise NotFoundError(f"Evidence asset {asset_id} not found")
        return asset

    async def _get_job_by_idempotency(
        self,
        *,
        idempotency_key: str,
        tenant_id: int | None,
    ) -> ExternalAuditImportJob | None:
        result = await self.db.execute(
            select(ExternalAuditImportJob).where(
                ExternalAuditImportJob.idempotency_key == idempotency_key,
                ExternalAuditImportJob.tenant_id == tenant_id,
            )
        )
        job = result.scalar_one_or_none()
        if job is not None or tenant_id is None:
            return job

        legacy_result = await self.db.execute(
            select(ExternalAuditImportJob).where(
                ExternalAuditImportJob.idempotency_key == idempotency_key,
                ExternalAuditImportJob.tenant_id.is_(None),
            )
        )
        job = legacy_result.scalar_one_or_none()
        if job is not None:
            job.tenant_id = tenant_id
            await self.db.flush()
            logger.warning(
                "Recovered legacy tenantless import job %s for idempotency key into tenant %s",
                job.id,
                tenant_id,
            )
        return job

    async def _get_draft(self, *, draft_id: int, tenant_id: int | None) -> ExternalAuditDraft:
        result = await self.db.execute(
            select(ExternalAuditDraft).where(
                ExternalAuditDraft.id == draft_id,
                ExternalAuditDraft.tenant_id == tenant_id,
            )
        )
        draft = result.scalar_one_or_none()
        if draft is None and tenant_id is None:
            unscoped_result = await self.db.execute(select(ExternalAuditDraft).where(ExternalAuditDraft.id == draft_id))
            draft = unscoped_result.scalar_one_or_none()
            if draft is not None:
                logger.warning(
                    "Recovered external audit draft %s without request tenant scope using persisted tenant %s",
                    draft_id,
                    draft.tenant_id,
                )
        if draft is None and tenant_id is not None:
            legacy_result = await self.db.execute(
                select(ExternalAuditDraft).where(
                    ExternalAuditDraft.id == draft_id,
                    ExternalAuditDraft.tenant_id.is_(None),
                )
            )
            draft = legacy_result.scalar_one_or_none()
            if draft is not None:
                draft.tenant_id = tenant_id
                await self.db.flush()
                logger.warning(
                    "Recovered legacy tenantless external audit draft %s into tenant %s",
                    draft_id,
                    tenant_id,
                )
        if not draft:
            raise NotFoundError(f"External audit draft {draft_id} not found")
        return draft

    async def _resolve_persisted_finding_id(self, *, finding_id: int | None, tenant_id: int | None) -> int:
        if finding_id is None:
            raise ConflictError("Promoted finding did not return a persistent identifier")

        result = await self.db.execute(
            select(AuditFinding.id).where(
                AuditFinding.id == finding_id,
                AuditFinding.tenant_id == tenant_id,
            )
        )
        persisted_id = result.scalar_one_or_none()
        if persisted_id is None:
            raise ConflictError("Promoted finding was not persisted before draft linkage")
        return persisted_id

    async def _clear_existing_drafts(self, *, job_id: int, tenant_id: int | None) -> None:
        drafts = await self.list_job_drafts(job_id=job_id, tenant_id=tenant_id)
        for draft in drafts:
            if draft.promoted_finding_id:
                raise ConflictError("Cannot reprocess an import job after findings have been promoted")
            await self.db.delete(draft)
        await self.db.flush()

    @property
    def _ACTION_FINDING_TYPES(self):
        return self.promotion_service._ACTION_FINDING_TYPES
