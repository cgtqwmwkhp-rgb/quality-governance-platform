"""Service layer for external audit OCR/import lifecycle."""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.domain.exceptions import ConflictError, NotFoundError, ValidationError
from src.domain.models.audit import AuditFinding, AuditRun, AuditStatus
from src.domain.models.compliance_evidence import ComplianceEvidenceLink, EvidenceLinkMethod
from src.domain.models.document import FileType
from src.domain.models.evidence_asset import EvidenceAsset
from src.domain.models.external_audit_import import (
    ExternalAuditDraft,
    ExternalAuditDraftStatus,
    ExternalAuditImportJob,
    ExternalAuditImportStatus,
)
from src.domain.models.uvdb_achilles import UVDBAudit
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

    @staticmethod
    def _scheme_home(scheme: str | None) -> tuple[str, str]:
        normalized = (scheme or "").strip().lower()
        if normalized == "achilles_uvdb":
            return "/uvdb", "Achilles / UVDB"
        if normalized == "planet_mark":
            return "/planet-mark", "Planet Mark"
        if normalized == "iso":
            return "/compliance", "ISO Compliance"
        return "/compliance", "Compliance Summary"

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
        job.updated_by_id = user_id
        await self.db.flush()
        await self.db.refresh(job)
        return job, True

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

    async def process_job(
        self, *, job_id: int, tenant_id: int | None, user_id: int | None = None
    ) -> ExternalAuditImportJob:
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

        try:
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

            analysis = self.analysis_service.analyze(
                extracted_text=text,
                page_texts=page_texts or ([text] if text else []),
                assurance_scheme=run.assurance_scheme,
            )

            preview = text[:500] if text else None
            replacement_drafts = [
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
                for candidate in analysis.findings
            ]
            async with self.db.begin_nested():
                await self._clear_existing_drafts(job_id=job.id, tenant_id=tenant_id)
                for draft in replacement_drafts:
                    self.db.add(draft)

                job.status = ExternalAuditImportStatus.REVIEW_REQUIRED
                job.extraction_method = extraction_method
                job.extraction_text_preview = preview
                job.page_count = extraction.page_count or len(page_texts) or None
                job.source_sheet_count = extraction.sheet_count
                job.has_tabular_data = bool(extraction.has_tables)
                job.page_texts_json = page_texts or None
                job.provenance_json = {
                    **(job.provenance_json or {}),
                    "extraction_note": note,
                    "mapped_frameworks": analysis.mapped_frameworks,
                    "mapped_standards": analysis.mapped_standards,
                    "classification_basis": analysis.classification_basis,
                    "declared_vs_detected": {
                        "declared_source_origin": run.source_origin,
                        "declared_assurance_scheme": run.assurance_scheme,
                        "detected_scheme": analysis.detected_scheme,
                        "detected_scheme_confidence": analysis.detected_scheme_confidence,
                    },
                }
                job.analysis_summary = analysis.summary
                job.detected_scheme = analysis.detected_scheme
                job.detected_scheme_confidence = analysis.detected_scheme_confidence
                job.scheme_version = analysis.scheme_version
                job.issuer_name = analysis.issuer_name
                job.report_date = analysis.report_date
                job.overall_score = analysis.overall_score
                job.max_score = analysis.max_score
                job.score_percentage = analysis.score_percentage
                job.outcome_status = analysis.outcome_status
                job.classification_basis_json = analysis.classification_basis
                job.score_breakdown_json = analysis.score_breakdown or None
                job.evidence_preview_json = analysis.evidence_preview or None
                job.positive_summary_json = analysis.positive_summary or None
                job.nonconformity_summary_json = analysis.nonconformity_summary or None
                job.improvement_summary_json = analysis.improvement_summary or None
                job.processing_warnings_json = analysis.processing_warnings or None
                job.promotion_summary_json = self._build_promotion_summary(findings=analysis.findings)
                job.error_code = None
                job.error_detail = None
                job.processed_at = datetime.now(timezone.utc)
            await self.db.flush()
            await self.db.refresh(job)
            return job
        except Exception as exc:
            job.status = ExternalAuditImportStatus.FAILED
            job.error_code = "IMPORT_PROCESSING_FAILED"
            job.error_detail = "Import analysis failed before review could begin. Review logs and retry the job."
            logger.exception("External audit import processing failed for job %s", job.id, exc_info=exc)
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

    async def promote_job(self, *, job_id: int, tenant_id: int | None, user_id: int) -> ExternalAuditImportJob:
        transitioned = await self.db.execute(
            update(ExternalAuditImportJob)
            .where(
                ExternalAuditImportJob.id == job_id,
                ExternalAuditImportJob.tenant_id == tenant_id,
                ExternalAuditImportJob.status == ExternalAuditImportStatus.REVIEW_REQUIRED,
            )
            .values(
                status=ExternalAuditImportStatus.PROMOTING,
                updated_by_id=user_id,
            )
        )
        if transitioned.rowcount != 1:
            job = await self.get_job(job_id=job_id, tenant_id=tenant_id)
            if job.status == ExternalAuditImportStatus.COMPLETED:
                return job
            if job.status == ExternalAuditImportStatus.PROMOTING:
                raise ConflictError("Import job promotion is already in progress")
            raise ValidationError("Import job must be in review_required state before promotion")

        job = await self.get_job(job_id=job_id, tenant_id=tenant_id)
        drafts = await self.list_job_drafts(job_id=job_id, tenant_id=tenant_id)
        accepted = [draft for draft in drafts if draft.status == ExternalAuditDraftStatus.ACCEPTED]
        if not accepted:
            job.status = ExternalAuditImportStatus.REVIEW_REQUIRED
            job.updated_by_id = user_id
            await self.db.flush()
            raise ValidationError("At least one draft must be accepted before promotion")

        audit_service = AuditService(self.db)
        run = await self._get_run(audit_run_id=job.audit_run_id, tenant_id=tenant_id)
        resolved_tenant_id = run.tenant_id if run.tenant_id is not None else tenant_id
        if resolved_tenant_id is None:
            raise ValidationError("Cannot promote external audit findings without a tenant context")
        promoted_findings: list[int] = []
        document_clause_ids: set[str] = set()
        for draft in accepted:
            if draft.promoted_finding_id:
                draft.status = ExternalAuditDraftStatus.PROMOTED
                continue
            clause_ids = self._extract_clause_ids(draft)
            finding = await audit_service.create_finding(
                draft.audit_run_id,
                {
                    "title": draft.title,
                    "description": draft.description,
                    "severity": draft.severity,
                    "finding_type": draft.finding_type,
                    "clause_ids": clause_ids,
                    "risk_ids": [],
                    "corrective_action_required": draft.finding_type in {"nonconformity", "competence_gap", "finding"},
                },
                user_id=user_id,
                tenant_id=draft.tenant_id if draft.tenant_id is not None else resolved_tenant_id,
            )
            finding_id = await self._resolve_persisted_finding_id(
                finding_id=getattr(finding, "id", None),
                tenant_id=draft.tenant_id if draft.tenant_id is not None else resolved_tenant_id,
            )
            await self._link_evidence_for_finding(
                finding_id=finding_id,
                clause_ids=clause_ids,
                tenant_id=draft.tenant_id if draft.tenant_id is not None else resolved_tenant_id,
                user_id=user_id,
                note=draft.description,
                confidence=draft.confidence_score,
            )
            draft.promoted_finding_id = finding_id
            draft.status = ExternalAuditDraftStatus.PROMOTED
            draft.updated_by_id = user_id
            promoted_findings.append(finding_id)
            document_clause_ids.update(clause_ids)

        if document_clause_ids:
            await self._link_source_document_evidence(
                asset_id=job.source_document_asset_id,
                clause_ids=sorted(document_clause_ids),
                tenant_id=resolved_tenant_id,
                user_id=user_id,
                title=job.source_filename,
            )

        completion_timestamp = job.report_date or datetime.now(timezone.utc)
        if run.started_at is None:
            run.started_at = completion_timestamp
        run.status = AuditStatus.COMPLETED
        run.completed_at = completion_timestamp
        if job.overall_score is not None:
            run.score = job.overall_score
        if job.max_score is not None:
            run.max_score = job.max_score
        if job.score_percentage is not None:
            run.score_percentage = job.score_percentage
        normalized_outcome = (job.outcome_status or "").strip().lower()
        if normalized_outcome in {"pass", "passed", "compliant"}:
            run.passed = True
        elif normalized_outcome in {"fail", "failed", "non_compliant", "non-compliant"}:
            run.passed = False
        else:
            run.passed = None

        scheme_alignment = await self._sync_scheme_records(
            job=job,
            run=run,
            tenant_id=resolved_tenant_id,
            drafts=accepted,
        )
        job.status = ExternalAuditImportStatus.COMPLETED
        job.promoted_at = datetime.now(timezone.utc)
        job.updated_by_id = user_id
        job.promotion_summary_json = {
            **(job.promotion_summary_json or {}),
            "promoted_findings": promoted_findings,
            "evidence_link_candidates": len(document_clause_ids),
            "scheme_alignment": scheme_alignment,
        }
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

    def _build_promotion_summary(self, *, findings: list) -> dict[str, object]:
        action_candidates = sum(
            1
            for finding in findings
            if getattr(finding, "finding_type", "") in {"nonconformity", "competence_gap", "finding"}
        )
        risk_candidates = sum(
            1
            for finding in findings
            if getattr(finding, "finding_type", "") in {"nonconformity", "competence_gap", "finding"}
            and getattr(finding, "severity", "") in {"high", "critical"}
        )
        evidence_link_candidates = len(
            {
                str(mapping.get("clause_id"))
                for finding in findings
                for mapping in (
                    (getattr(finding, "mapped_standards", None) or getattr(finding, "mapped_standards_json", []) or [])
                )
                if mapping.get("clause_id")
            }
        )
        return {
            "total_candidates": len(findings),
            "action_candidates": action_candidates,
            "risk_candidates": risk_candidates,
            "evidence_link_candidates": evidence_link_candidates,
            "positive_findings": sum(
                1 for finding in findings if getattr(finding, "finding_type", "") == "positive_practice"
            ),
            "improvement_findings": sum(
                1
                for finding in findings
                if getattr(finding, "finding_type", "") in {"opportunity_for_improvement", "observation"}
            ),
            "nonconformities": sum(
                1
                for finding in findings
                if getattr(finding, "finding_type", "") in {"nonconformity", "competence_gap", "finding"}
            ),
        }

    async def _refresh_job_promotion_summary(self, *, job_id: int, tenant_id: int | None) -> None:
        job = await self.get_job(job_id=job_id, tenant_id=tenant_id)
        drafts = await self.list_job_drafts(job_id=job_id, tenant_id=tenant_id)
        summary = self._build_promotion_summary(findings=drafts)
        summary["accepted_candidates"] = sum(
            1
            for draft in drafts
            if draft.status in {ExternalAuditDraftStatus.ACCEPTED, ExternalAuditDraftStatus.PROMOTED}
        )
        summary["rejected_candidates"] = sum(1 for draft in drafts if draft.status == ExternalAuditDraftStatus.REJECTED)
        job.promotion_summary_json = summary
        await self.db.flush()

    def _extract_clause_ids(self, draft: ExternalAuditDraft) -> list[str]:
        clause_ids: list[str] = []
        for mapping in draft.mapped_standards_json or []:
            clause_id = mapping.get("clause_id") if isinstance(mapping, dict) else None
            if clause_id:
                clause_ids.append(str(clause_id))
        return sorted(set(clause_ids))

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
        for clause_id in clause_ids:
            existing = await self.db.execute(
                select(ComplianceEvidenceLink).where(
                    ComplianceEvidenceLink.tenant_id == tenant_id,
                    ComplianceEvidenceLink.entity_type == "audit_finding",
                    ComplianceEvidenceLink.entity_id == str(finding_id),
                    ComplianceEvidenceLink.clause_id == clause_id,
                )
            )
            link = existing.scalar_one_or_none()
            if link is None:
                link = ComplianceEvidenceLink(
                    tenant_id=tenant_id,
                    entity_type="audit_finding",
                    entity_id=str(finding_id),
                    clause_id=clause_id,
                    created_by_id=user_id,
                )
                self.db.add(link)
            else:
                link.deleted_at = None
            link.linked_by = EvidenceLinkMethod.AUTO
            link.confidence = confidence
            link.title = f"Imported audit evidence for finding {finding_id}"
            link.notes = note
        await self.db.flush()

    async def _link_source_document_evidence(
        self,
        *,
        asset_id: int,
        clause_ids: list[str],
        tenant_id: int | None,
        user_id: int,
        title: str | None,
    ) -> None:
        for clause_id in clause_ids:
            existing = await self.db.execute(
                select(ComplianceEvidenceLink).where(
                    ComplianceEvidenceLink.tenant_id == tenant_id,
                    ComplianceEvidenceLink.entity_type == "document",
                    ComplianceEvidenceLink.entity_id == str(asset_id),
                    ComplianceEvidenceLink.clause_id == clause_id,
                )
            )
            link = existing.scalar_one_or_none()
            if link is None:
                link = ComplianceEvidenceLink(
                    tenant_id=tenant_id,
                    entity_type="document",
                    entity_id=str(asset_id),
                    clause_id=clause_id,
                    created_by_id=user_id,
                )
                self.db.add(link)
            else:
                link.deleted_at = None
            link.linked_by = EvidenceLinkMethod.AUTO
            link.title = title or f"Imported audit source document {asset_id}"
        await self.db.flush()

    async def _sync_scheme_records(
        self,
        *,
        job: ExternalAuditImportJob,
        run: AuditRun,
        tenant_id: int | None,
        drafts: list[ExternalAuditDraft],
    ) -> dict[str, object]:
        home_route, home_label = self._scheme_home(job.detected_scheme)
        if job.detected_scheme != "achilles_uvdb":
            return {
                "status": "completed_outcome_routed",
                "scheme": job.detected_scheme,
                "home_route": home_route,
                "home_label": home_label,
                "reason": "This imported external audit is routed into the relevant completed compliance area without executable audit-run semantics.",
            }

        result = await self.db.execute(
            select(UVDBAudit).where(
                UVDBAudit.tenant_id == tenant_id,
                UVDBAudit.audit_reference == run.reference_number,
            )
        )
        uvdb_audit = result.scalar_one_or_none()
        if uvdb_audit is None:
            uvdb_audit = UVDBAudit(
                tenant_id=tenant_id,
                audit_reference=run.reference_number,
                company_name=run.title or run.location or "Imported UVDB Audit",
                company_id=run.external_reference,
                audit_type=(job.scheme_version or "B2").split(",")[0][:50],
            )
            self.db.add(uvdb_audit)

        uvdb_audit.audit_date = job.report_date.replace(tzinfo=None) if job.report_date else None
        uvdb_audit.auditor_organization = run.external_body_name
        uvdb_audit.lead_auditor = run.external_auditor_name
        uvdb_audit.total_score = job.overall_score
        uvdb_audit.max_possible_score = job.max_score
        uvdb_audit.percentage_score = job.score_percentage
        uvdb_audit.section_scores = {"sections": job.score_breakdown_json or []}
        uvdb_audit.status = "completed"
        uvdb_audit.findings_count = sum(
            1 for draft in drafts if draft.finding_type in {"nonconformity", "competence_gap", "finding"}
        )
        uvdb_audit.major_findings = sum(
            1
            for draft in drafts
            if draft.finding_type in {"nonconformity", "competence_gap", "finding"}
            and draft.severity in {"high", "critical"}
        )
        uvdb_audit.minor_findings = sum(
            1
            for draft in drafts
            if draft.finding_type in {"nonconformity", "competence_gap", "finding"} and draft.severity == "medium"
        )
        uvdb_audit.observations = sum(1 for draft in drafts if draft.finding_type == "observation")
        uvdb_audit.audit_notes = job.analysis_summary
        await self.db.flush()
        return {
            "status": "synced",
            "scheme": "achilles_uvdb",
            "uvdb_audit_id": uvdb_audit.id,
            "home_route": home_route,
            "home_label": home_label,
        }
