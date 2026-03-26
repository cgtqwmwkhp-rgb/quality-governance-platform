"""Service layer for external audit OCR/import lifecycle."""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.domain.exceptions import ConflictError, NotFoundError, ValidationError
from src.domain.models.audit import AuditRun
from src.domain.models.document import FileType
from src.domain.models.evidence_asset import EvidenceAsset
from src.domain.models.external_audit_import import (
    ExternalAuditDraft,
    ExternalAuditDraftStatus,
    ExternalAuditImportJob,
    ExternalAuditImportStatus,
)
from src.domain.services.audit_service import AuditService
from src.domain.services.document_extraction_service import extract_document_content
from src.domain.services.external_audit_analysis_service import ExternalAuditAnalysisService
from src.domain.services.mistral_ocr_service import MistralOCRService
from src.domain.services.reference_number import ReferenceNumberService
from src.infrastructure.storage import StorageError, storage_service

logger = logging.getLogger(__name__)

_EXTENSION_TO_FILETYPE = {
    ".pdf": FileType.PDF,
    ".docx": FileType.DOCX,
    ".doc": FileType.DOC,
    ".xlsx": FileType.XLSX,
    ".xls": FileType.XLS,
    ".csv": FileType.CSV,
    ".txt": FileType.TXT,
    ".md": FileType.MD,
    ".png": FileType.PNG,
    ".jpg": FileType.JPG,
    ".jpeg": FileType.JPEG,
}


class ExternalAuditImportService:
    """Orchestrates import job creation, draft review, and promotion."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.analysis_service = ExternalAuditAnalysisService()
        self.ocr_service = MistralOCRService()

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
        existing = await self._get_job_by_idempotency(idempotency_key=idempotency_key, tenant_id=tenant_id)
        if existing:
            return existing

        ref = await ReferenceNumberService.generate(self.db, "audit_import", ExternalAuditImportJob)
        job = ExternalAuditImportJob(
            reference_number=ref,
            audit_run_id=run.id,
            source_document_asset_id=asset.id,
            tenant_id=tenant_id,
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
            },
            created_by_id=user_id,
            updated_by_id=user_id,
        )
        self.db.add(job)
        await self.db.flush()
        await self.db.refresh(job)
        return job

    async def queue_job(self, *, job_id: int, tenant_id: int | None, user_id: int) -> ExternalAuditImportJob:
        job = await self.get_job(job_id=job_id, tenant_id=tenant_id)
        if job.status in {
            ExternalAuditImportStatus.PROCESSING,
            ExternalAuditImportStatus.REVIEW_REQUIRED,
            ExternalAuditImportStatus.COMPLETED,
        }:
            return job
        job.status = ExternalAuditImportStatus.QUEUED
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
        if not job:
            raise NotFoundError(f"External audit import job {job_id} not found")
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
        return list(result.scalars().all())

    async def process_job(self, *, job_id: int, tenant_id: int | None, user_id: int | None = None) -> ExternalAuditImportJob:
        job = await self.get_job(job_id=job_id, tenant_id=tenant_id)
        asset = await self._get_asset(asset_id=job.source_document_asset_id, tenant_id=tenant_id)
        run = await self._get_run(audit_run_id=job.audit_run_id, tenant_id=tenant_id)

        job.status = ExternalAuditImportStatus.PROCESSING
        job.updated_by_id = user_id or job.updated_by_id
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

        file_type = self._infer_file_type(asset.original_filename, asset.content_type)
        extraction = extract_document_content(file_type, asset.original_filename or "source", raw)
        text = extraction.text.strip()
        extraction_method = extraction.extraction_method
        page_texts = extraction.page_texts or []
        note = extraction.note

        should_try_ocr = (not text) or file_type in {FileType.PNG, FileType.JPG, FileType.JPEG}
        if should_try_ocr:
            ocr_result = await self.ocr_service.ocr_bytes(
                raw,
                asset.original_filename or "source",
                asset.content_type or "application/octet-stream",
            )
            if ocr_result.text.strip():
                text = ocr_result.text.strip()
                page_texts = ocr_result.pages or [text]
                extraction_method = ocr_result.method
                note = ocr_result.note
            elif note is None:
                note = ocr_result.note

        await self._clear_existing_drafts(job_id=job.id, tenant_id=tenant_id)
        analysis = self.analysis_service.analyze(
            extracted_text=text,
            page_texts=page_texts or ([text] if text else []),
            assurance_scheme=run.assurance_scheme,
        )

        for candidate in analysis.findings:
            self.db.add(
                ExternalAuditDraft(
                    import_job_id=job.id,
                    audit_run_id=run.id,
                    tenant_id=tenant_id,
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
            )

        preview = text[:500] if text else None
        job.status = ExternalAuditImportStatus.REVIEW_REQUIRED
        job.extraction_method = extraction_method
        job.extraction_text_preview = preview
        job.page_count = extraction.page_count or len(page_texts) or None
        job.page_texts_json = page_texts or None
        job.provenance_json = {
            **(job.provenance_json or {}),
            "extraction_note": note,
            "mapped_frameworks": analysis.mapped_frameworks,
            "mapped_standards": analysis.mapped_standards,
        }
        job.analysis_summary = analysis.summary
        job.error_code = None
        job.error_detail = None
        job.processed_at = datetime.now(timezone.utc)
        await self.db.flush()
        await self.db.refresh(job)
        return job

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
        await self.db.refresh(draft)
        return draft

    async def promote_job(self, *, job_id: int, tenant_id: int | None, user_id: int) -> ExternalAuditImportJob:
        job = await self.get_job(job_id=job_id, tenant_id=tenant_id)
        if job.status == ExternalAuditImportStatus.COMPLETED:
            return job
        drafts = await self.list_job_drafts(job_id=job_id, tenant_id=tenant_id)
        accepted = [draft for draft in drafts if draft.status == ExternalAuditDraftStatus.ACCEPTED]
        if not accepted:
            raise ValidationError("At least one draft must be accepted before promotion")

        job.status = ExternalAuditImportStatus.PROMOTING
        await self.db.flush()

        audit_service = AuditService(self.db)
        for draft in accepted:
            if draft.promoted_finding_id:
                draft.status = ExternalAuditDraftStatus.PROMOTED
                continue
            finding = await audit_service.create_finding(
                draft.audit_run_id,
                {
                    "title": draft.title,
                    "description": draft.description,
                    "severity": draft.severity,
                    "finding_type": draft.finding_type,
                    "risk_ids": [],
                },
                user_id=user_id,
                tenant_id=draft.tenant_id or tenant_id or 0,
            )
            draft.promoted_finding_id = finding.id
            draft.status = ExternalAuditDraftStatus.PROMOTED
            draft.updated_by_id = user_id

        job.status = ExternalAuditImportStatus.COMPLETED
        job.promoted_at = datetime.now(timezone.utc)
        job.updated_by_id = user_id
        await self.db.flush()
        await self.db.refresh(job)
        return job

    async def _get_run(self, *, audit_run_id: int, tenant_id: int | None) -> AuditRun:
        result = await self.db.execute(
            select(AuditRun).where(
                AuditRun.id == audit_run_id,
                AuditRun.tenant_id == tenant_id,
            )
        )
        run = result.scalar_one_or_none()
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
        return result.scalar_one_or_none()

    async def _get_draft(self, *, draft_id: int, tenant_id: int | None) -> ExternalAuditDraft:
        result = await self.db.execute(
            select(ExternalAuditDraft).where(
                ExternalAuditDraft.id == draft_id,
                ExternalAuditDraft.tenant_id == tenant_id,
            )
        )
        draft = result.scalar_one_or_none()
        if not draft:
            raise NotFoundError(f"External audit draft {draft_id} not found")
        return draft

    async def _clear_existing_drafts(self, *, job_id: int, tenant_id: int | None) -> None:
        drafts = await self.list_job_drafts(job_id=job_id, tenant_id=tenant_id)
        for draft in drafts:
            if draft.promoted_finding_id:
                raise ConflictError("Cannot reprocess an import job after findings have been promoted")
            await self.db.delete(draft)
        await self.db.flush()

    def _infer_file_type(self, filename: str | None, content_type: str | None) -> FileType:
        suffix = Path(filename or "").suffix.lower()
        if suffix in _EXTENSION_TO_FILETYPE:
            return _EXTENSION_TO_FILETYPE[suffix]
        content_map = {
            "application/pdf": FileType.PDF,
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document": FileType.DOCX,
            "application/msword": FileType.DOC,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": FileType.XLSX,
            "application/vnd.ms-excel": FileType.XLS,
            "text/csv": FileType.CSV,
            "image/png": FileType.PNG,
            "image/jpeg": FileType.JPG,
        }
        inferred = content_map.get((content_type or "").lower())
        if inferred:
            return inferred
        raise ValidationError("Unsupported source document type for external audit import")
