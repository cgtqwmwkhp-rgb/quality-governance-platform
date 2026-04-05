"""Service layer for external audit OCR/import lifecycle."""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TypedDict, cast

from sqlalchemy import select, update
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.domain.exceptions import ConflictError, NotFoundError, ValidationError
from src.domain.models.audit import AuditFinding, AuditRun, AuditStatus
from src.domain.models.capa import CAPAAction, CAPASource
from src.domain.models.compliance_evidence import ComplianceEvidenceLink, EvidenceLinkMethod
from src.domain.models.document import FileType
from src.domain.models.evidence_asset import EvidenceAsset
from src.domain.models.external_audit_import import (
    ExternalAuditDraft,
    ExternalAuditDraftStatus,
    ExternalAuditImportJob,
    ExternalAuditImportStatus,
)
from src.domain.models.external_audit_record import ExternalAuditRecord
from src.domain.models.risk_register import EnterpriseRisk
from src.domain.models.uvdb_achilles import UVDBAudit
from src.domain.services.ai_consensus_service import AIConsensusService
from src.domain.services.audit_service import AuditService
from src.domain.services.document_extraction_service import extract_document_content
from src.domain.services.external_audit_analysis_service import ExternalAuditAnalysisService
from src.domain.services.gemini_review_service import GeminiReviewService
from src.domain.services.mistral_analysis_service import MistralAnalysisService
from src.domain.services.mistral_ocr_service import MistralOCRService
from src.domain.services.reference_number import ReferenceNumberService
from src.domain.services.scheme_profiles import validate_against_scheme
from src.infrastructure.cache.redis_cache import invalidate_tenant_cache
from src.infrastructure.storage import StorageError, storage_service

logger = logging.getLogger(__name__)

MAX_SOURCE_FILE_BYTES = 50 * 1024 * 1024  # 50 MB hard limit
PROCESSING_TTL_SECONDS = 600  # 10 minutes before a PROCESSING job is considered stale

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


class PromotionResult(TypedDict):
    promoted_findings: list[int]
    document_clause_ids: set[str]
    failed_drafts: list[dict[str, object]]


class ExternalAuditImportService:
    """Orchestrates import job creation, draft review, and promotion."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.analysis_service = ExternalAuditAnalysisService()
        self.ocr_service = MistralOCRService()
        self.ai_analysis_service = MistralAnalysisService()
        self.gemini_review_service = GeminiReviewService()
        self.consensus_service = AIConsensusService()

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
        if normalized == "iso" or normalized.startswith("iso_") or normalized.startswith("iso-"):
            return "/compliance", "ISO Compliance"
        if normalized in ("customer_other", "other"):
            return "/customer-audits", "Customer Audits"
        return "/customer-audits", "Customer Audits"

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
        """Auto-recover jobs stuck in PROCESSING or PROMOTING beyond the TTL."""
        if job.status not in (ExternalAuditImportStatus.PROCESSING, ExternalAuditImportStatus.PROMOTING):
            return
        updated_at = job.updated_at if hasattr(job, "updated_at") and job.updated_at else job.created_at
        if updated_at is None:
            return
        now = datetime.now(timezone.utc)
        if updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=timezone.utc)
        elapsed = (now - updated_at).total_seconds()
        if elapsed > PROCESSING_TTL_SECONDS:
            logger.warning(
                "Recovering stale PROCESSING job %s (stuck for %.0fs)",
                job.id,
                elapsed,
            )
            job.status = ExternalAuditImportStatus.FAILED
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

    async def get_promotion_reconciliation(self, *, job_id: int, tenant_id: int | None) -> dict[str, object]:
        job = await self.get_job(job_id=job_id, tenant_id=tenant_id)
        effective_tenant_id = job.tenant_id or tenant_id
        run = await self._get_run(audit_run_id=job.audit_run_id, tenant_id=effective_tenant_id)
        drafts = await self.list_job_drafts(job_id=job_id, tenant_id=effective_tenant_id)
        stored_summary = job.promotion_summary_json or {}
        return await self._build_promotion_reconciliation(
            job=job,
            run=run,
            drafts=drafts,
            tenant_id=effective_tenant_id,
            failed_drafts=cast(list[dict[str, object]], stored_summary.get("failed_drafts") or []),
            scheme_alignment=stored_summary.get("scheme_alignment") if isinstance(stored_summary, dict) else None,
        )

    async def _load_capa_actions_for_finding(self, *, finding_id: int, tenant_id: int | None) -> list[CAPAAction]:
        try:
            result = await self.db.execute(
                select(CAPAAction).where(
                    CAPAAction.tenant_id == tenant_id,
                    CAPAAction.source_type == CAPASource.AUDIT_FINDING,
                    CAPAAction.source_id == finding_id,
                )
            )
            return list(result.scalars().all())
        except (OperationalError, ProgrammingError):
            logger.debug("CAPA table is unavailable while building reconciliation")
            return []

    async def _load_risks_for_finding(self, *, finding: AuditFinding, tenant_id: int | None) -> list[EnterpriseRisk]:
        risk_ids = [int(risk_id) for risk_id in (finding.risk_ids_json or []) if str(risk_id).isdigit()]
        if not risk_ids:
            return []
        try:
            result = await self.db.execute(
                select(EnterpriseRisk).where(
                    EnterpriseRisk.tenant_id == tenant_id,
                    EnterpriseRisk.id.in_(risk_ids),
                )
            )
            return list(result.scalars().all())
        except (OperationalError, ProgrammingError):
            logger.debug("Risk register table is unavailable while building reconciliation")
            return []

    def _build_promotion_proof_matrix(
        self,
        *,
        job: ExternalAuditImportJob,
        run: AuditRun,
        drafts: list[ExternalAuditDraft],
        actions_total: int,
        risks_total: int,
        uvdb_audit_id: int | None,
        external_audit_record_id: int | None,
        failed_drafts: list[dict[str, object]],
    ) -> list[dict[str, object]]:
        promoted_total = sum(1 for draft in drafts if draft.promoted_finding_id)
        accepted_total = sum(
            1
            for draft in drafts
            if draft.status in {ExternalAuditDraftStatus.ACCEPTED, ExternalAuditDraftStatus.PROMOTED}
        )
        return [
            {
                "step": "upload",
                "status": "ok" if job.source_document_asset_id else "missing",
                "detail": job.source_filename or "Source document attached",
            },
            {
                "step": "analysis",
                "status": "ok" if job.processed_at else "pending",
                "detail": job.reference_number,
            },
            {
                "step": "review",
                "status": "ok" if accepted_total else "pending",
                "detail": f"{accepted_total} draft(s) approved for promotion",
            },
            {
                "step": "promotion",
                "status": "partial" if failed_drafts else ("ok" if promoted_total else "blocked"),
                "detail": f"{promoted_total} finding(s) materialized for {run.reference_number}",
            },
            {
                "step": "capa_actions",
                "status": "ok" if actions_total else "none",
                "detail": f"{actions_total} CAPA action(s)",
            },
            {
                "step": "enterprise_risks",
                "status": "ok" if risks_total else "none",
                "detail": f"{risks_total} enterprise risk(s)",
            },
            {
                "step": "uvdb_sync",
                "status": "ok" if uvdb_audit_id else ("n/a" if not self._is_uvdb_scheme(job, run) else "missing"),
                "detail": f"UVDB audit id {uvdb_audit_id}" if uvdb_audit_id else "No UVDB sync required or visible",
            },
            {
                "step": "registry",
                "status": "ok" if external_audit_record_id else "missing",
                "detail": (
                    f"External audit record id {external_audit_record_id}"
                    if external_audit_record_id
                    else "No unified registry row found"
                ),
            },
        ]

    async def _build_promotion_reconciliation(
        self,
        *,
        job: ExternalAuditImportJob,
        run: AuditRun,
        drafts: list[ExternalAuditDraft],
        tenant_id: int | None,
        failed_drafts: list[dict[str, object]],
        scheme_alignment: object | None,
    ) -> dict[str, object]:
        home_route, home_label = self._scheme_home(job.detected_scheme)
        promoted_drafts = [draft for draft in drafts if draft.promoted_finding_id]
        accepted_pending = [
            draft
            for draft in drafts
            if draft.status == ExternalAuditDraftStatus.ACCEPTED and not draft.promoted_finding_id
        ]

        registry_record = None
        try:
            record_result = await self.db.execute(
                select(ExternalAuditRecord).where(
                    ExternalAuditRecord.tenant_id == tenant_id,
                    ExternalAuditRecord.import_job_id == job.id,
                )
            )
            registry_record = record_result.scalar_one_or_none()
        except (OperationalError, ProgrammingError):
            logger.debug("External audit registry table is unavailable while building reconciliation")

        uvdb_audit = None
        if self._is_uvdb_scheme(job, run):
            try:
                uvdb_result = await self.db.execute(
                    select(UVDBAudit).where(
                        UVDBAudit.tenant_id == tenant_id,
                        UVDBAudit.audit_reference == run.reference_number,
                    )
                )
                uvdb_audit = uvdb_result.scalar_one_or_none()
            except (OperationalError, ProgrammingError):
                logger.debug("UVDB table is unavailable while building reconciliation")

        draft_results: list[dict[str, object]] = []
        capa_total = 0
        risk_total = 0
        for draft in promoted_drafts:
            finding_result = await self.db.execute(
                select(AuditFinding).where(
                    AuditFinding.id == draft.promoted_finding_id,
                    AuditFinding.tenant_id == tenant_id,
                )
            )
            finding = finding_result.scalar_one_or_none()
            if finding is None:
                continue
            capa_actions = await self._load_capa_actions_for_finding(finding_id=finding.id, tenant_id=tenant_id)
            risks = await self._load_risks_for_finding(finding=finding, tenant_id=tenant_id)
            capa_total += len(capa_actions)
            risk_total += len(risks)
            draft_results.append(
                {
                    "draft_id": draft.id,
                    "draft_title": draft.title,
                    "draft_status": draft.status.value if hasattr(draft.status, "value") else str(draft.status),
                    "finding_type": draft.finding_type,
                    "severity": draft.severity,
                    "finding_id": finding.id,
                    "finding_reference": finding.reference_number,
                    "capa_actions": [
                        {"id": action.id, "reference_number": action.reference_number, "title": action.title}
                        for action in capa_actions
                    ],
                    "enterprise_risks": [
                        {"id": risk.id, "reference": risk.reference, "title": risk.title} for risk in risks
                    ],
                    "view_links": {
                        "actions": f"/actions?sourceType=audit_finding&sourceId={finding.id}",
                        "risk_register": f"/risk-register?auditOnly=1&auditRef={run.reference_number}",
                        "uvdb": f"/uvdb?auditRef={run.reference_number}",
                    },
                }
            )

        return {
            "job_id": job.id,
            "audit_run_id": run.id,
            "audit_reference": run.reference_number,
            "job_status": job.status.value if hasattr(job.status, "value") else str(job.status),
            "canonical_read_model": "specialist_sync_verification",
            "specialist_home": {"path": home_route, "label": home_label},
            "scheme_alignment": scheme_alignment,
            "accepted_total": sum(
                1
                for draft in drafts
                if draft.status in {ExternalAuditDraftStatus.ACCEPTED, ExternalAuditDraftStatus.PROMOTED}
            ),
            "promoted_total": len(draft_results),
            "accepted_pending_total": len(accepted_pending),
            "failed_total": len(failed_drafts),
            "failed_drafts": failed_drafts,
            "materialized": {
                "audit_findings": len(draft_results),
                "capa_actions": capa_total,
                "enterprise_risks": risk_total,
                "uvdb_audit_id": uvdb_audit.id if uvdb_audit else None,
                "external_audit_record_id": registry_record.id if registry_record else None,
            },
            "proof_matrix": self._build_promotion_proof_matrix(
                job=job,
                run=run,
                drafts=drafts,
                actions_total=capa_total,
                risks_total=risk_total,
                uvdb_audit_id=uvdb_audit.id if uvdb_audit else None,
                external_audit_record_id=registry_record.id if registry_record else None,
                failed_drafts=failed_drafts,
            ),
            "draft_results": draft_results,
            "view_links": {
                "actions": "/actions?sourceType=audit_finding",
                "risk_register": f"/risk-register?auditOnly=1&auditRef={run.reference_number}",
                "uvdb": f"/uvdb?auditRef={run.reference_number}",
                "specialist_home": f"{home_route}?auditRef={run.reference_number}",
            },
        }

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
            file_type = self._infer_file_type(asset.original_filename, asset.content_type)
            extraction = extract_document_content(file_type, asset.original_filename or "source", raw)
            native_text = extraction.text.strip()
            extraction_method = extraction.extraction_method
            page_texts = extraction.page_texts or []
            note = extraction.note

            ocr_text = ""
            ocr_pages: list[str] = []
            if self.ocr_service.is_configured:
                ocr_result = await self.ocr_service.ocr_bytes(
                    raw,
                    asset.original_filename or "source",
                    asset.content_type or "application/octet-stream",
                )
                ocr_text = ocr_result.text.strip()
                ocr_pages = ocr_result.pages or []
                if ocr_result.note and note is None:
                    note = ocr_result.note

            text, page_texts, extraction_method = self._merge_extractions(
                native_text=native_text,
                native_pages=page_texts,
                ocr_text=ocr_text,
                ocr_pages=ocr_pages,
                native_method=extraction_method,
            )

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
                job.score_percentage = (
                    max(0.0, min(analysis.score_percentage, 100.0)) if analysis.score_percentage is not None else None
                )
                job.outcome_status = analysis.outcome_status
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

    async def promote_job(self, *, job_id: int, tenant_id: int | None, user_id: int) -> ExternalAuditImportJob:
        job = await self.get_job(job_id=job_id, tenant_id=tenant_id)
        effective_tenant_id = job.tenant_id
        transitioned = await self.db.execute(
            update(ExternalAuditImportJob)
            .where(
                ExternalAuditImportJob.id == job_id,
                ExternalAuditImportJob.tenant_id == effective_tenant_id,
                ExternalAuditImportJob.status == ExternalAuditImportStatus.REVIEW_REQUIRED,
            )
            .values(
                status=ExternalAuditImportStatus.PROMOTING,
                updated_by_id=user_id,
            )
        )
        if transitioned.rowcount != 1:
            job = await self.get_job(job_id=job_id, tenant_id=effective_tenant_id)
            if job.status == ExternalAuditImportStatus.COMPLETED:
                return job
            if job.status == ExternalAuditImportStatus.PROMOTING:
                raise ConflictError("Import job promotion is already in progress")
            raise ValidationError("Import job must be in review_required state before promotion")

        job = await self.get_job(job_id=job_id, tenant_id=effective_tenant_id)
        drafts = await self.list_job_drafts(job_id=job_id, tenant_id=effective_tenant_id)
        accepted = [draft for draft in drafts if draft.status == ExternalAuditDraftStatus.ACCEPTED]
        if not accepted:
            job.status = ExternalAuditImportStatus.REVIEW_REQUIRED
            job.updated_by_id = user_id
            await self.db.flush()
            raise ValidationError("At least one draft must be accepted before promotion")

        run = await self._get_run(audit_run_id=job.audit_run_id, tenant_id=effective_tenant_id)
        resolved_tenant_id = run.tenant_id or job.tenant_id or tenant_id
        if resolved_tenant_id is None:
            raise ValidationError("Cannot promote external audit findings without a tenant context")

        await self._backfill_tenant_ids(
            resolved_tenant_id=resolved_tenant_id,
            run=run,
            job=job,
            drafts=drafts,
        )

        try:
            promotion_result: PromotionResult = await self._promote_accepted_drafts(
                accepted=accepted,
                user_id=user_id,
                resolved_tenant_id=resolved_tenant_id,
            )
            promoted_findings = promotion_result["promoted_findings"]
            document_clause_ids = promotion_result["document_clause_ids"]
            failed_drafts = promotion_result["failed_drafts"]
            reconciled_drafts = [draft for draft in drafts if draft.promoted_finding_id]

            if document_clause_ids:
                try:
                    await self._link_source_document_evidence(
                        asset_id=job.source_document_asset_id,
                        clause_ids=sorted(document_clause_ids),
                        tenant_id=resolved_tenant_id,
                        user_id=user_id,
                        title=job.source_filename,
                    )
                except Exception as link_exc:
                    logger.warning("Source document evidence linking failed (non-fatal): %s", link_exc)

            scheme_alignment: dict[str, object] | None = None
            try:
                scheme_alignment = await self._sync_scheme_records(
                    job=job,
                    run=run,
                    tenant_id=resolved_tenant_id,
                    drafts=reconciled_drafts,
                )
            except Exception as sync_exc:
                logger.warning("Scheme record sync failed (non-fatal): %s", sync_exc)
                scheme_alignment = {"status": "sync_failed", "error": str(sync_exc)[:200]}

            reconciliation: dict[str, object] = {}
            try:
                reconciliation = await self._build_promotion_reconciliation(
                    job=job,
                    run=run,
                    drafts=drafts,
                    tenant_id=resolved_tenant_id,
                    failed_drafts=failed_drafts,
                    scheme_alignment=scheme_alignment,
                )
            except Exception as recon_exc:
                logger.warning("Promotion reconciliation build failed (non-fatal): %s", recon_exc)
                reconciliation = {"status": "reconciliation_failed", "error": str(recon_exc)[:200]}
            if failed_drafts:
                job.status = ExternalAuditImportStatus.REVIEW_REQUIRED
                existing_warnings = list(job.processing_warnings_json or [])
                existing_warnings.append(
                    f"Promotion partially completed: {len(failed_drafts)} accepted draft(s) still need attention."
                )
                job.processing_warnings_json = existing_warnings
            else:
                self._apply_run_completion(run, job)
                job.status = ExternalAuditImportStatus.COMPLETED
                job.promoted_at = datetime.now(timezone.utc)
            job.updated_by_id = user_id
            job.promotion_summary_json = {
                **(job.promotion_summary_json or {}),
                "materialization_contract_version": 1,
                "canonical_read_model": "specialist_sync_verification",
                "promoted_findings": promoted_findings,
                "evidence_link_candidates": len(document_clause_ids),
                "failed_drafts": failed_drafts,
                "scheme_alignment": scheme_alignment,
                "reconciliation": reconciliation,
            }
            await self.db.flush()
            await self.db.refresh(job)
        except Exception as exc:
            logger.error("Promotion failed for job %s: %s", job_id, exc, exc_info=True)
            try:
                await self.db.rollback()
                job_reload = await self.db.execute(
                    select(ExternalAuditImportJob).where(ExternalAuditImportJob.id == job_id)
                )
                job = job_reload.scalar_one_or_none() or job
                job.status = ExternalAuditImportStatus.REVIEW_REQUIRED
                job.updated_by_id = user_id
                existing_warnings = list(job.processing_warnings_json or [])
                existing_warnings.append(f"Promotion failed: {str(exc)[:300]}")
                job.processing_warnings_json = existing_warnings
                await self.db.flush()
                await self.db.commit()
            except Exception as cleanup_exc:
                logger.warning("Could not persist promotion error for job %s: %s", job_id, cleanup_exc)
            raise

        try:
            await invalidate_tenant_cache(resolved_tenant_id, "audits")
            await invalidate_tenant_cache(resolved_tenant_id, "capa")
            await invalidate_tenant_cache(resolved_tenant_id, "risk-register")
            await invalidate_tenant_cache(resolved_tenant_id, "risks")
            await invalidate_tenant_cache(resolved_tenant_id, "governance")
            await invalidate_tenant_cache(resolved_tenant_id, "uvdb")
        except Exception:
            logger.debug("Cache invalidation after promotion skipped (not available)")

        return job

    async def _backfill_tenant_ids(
        self,
        *,
        resolved_tenant_id: int,
        run: AuditRun,
        job: ExternalAuditImportJob,
        drafts: list[ExternalAuditDraft],
    ) -> None:
        """Patch NULL tenant_id on entities created before tenant auto-assign was deployed."""
        touched = False
        if run.tenant_id is None:
            run.tenant_id = resolved_tenant_id
            touched = True
        if job.tenant_id is None:
            job.tenant_id = resolved_tenant_id
            touched = True
        for draft in drafts:
            if draft.tenant_id is None:
                draft.tenant_id = resolved_tenant_id
                touched = True
        if touched:
            await self.db.flush()
            logger.info(
                "Backfilled tenant_id=%s on run %s / job %s / %d drafts",
                resolved_tenant_id,
                run.id,
                job.id,
                len(drafts),
            )

    async def _promote_accepted_drafts(
        self,
        *,
        accepted: list[ExternalAuditDraft],
        user_id: int,
        resolved_tenant_id: int,
    ) -> PromotionResult:
        """Promote each accepted draft into a live finding with per-draft savepoints."""
        audit_service = AuditService(self.db)
        promoted_findings: list[int] = []
        document_clause_ids: set[str] = set()
        default_due_date = datetime.now(timezone.utc) + timedelta(days=30)
        failed_drafts: list[dict[str, object]] = []

        for draft in accepted:
            if draft.promoted_finding_id:
                draft.status = ExternalAuditDraftStatus.PROMOTED
                continue
            try:
                async with self.db.begin_nested():
                    clause_ids = self._extract_clause_ids(draft)
                    _POSITIVE_ONLY_TYPES = {"positive_practice", "strength", "commendation"}
                    requires_action = draft.finding_type not in _POSITIVE_ONLY_TYPES
                    finding_data: dict = {
                        "title": draft.title,
                        "description": draft.description,
                        "severity": draft.severity,
                        "finding_type": draft.finding_type,
                        "clause_ids": clause_ids,
                        "risk_ids": [],
                        "corrective_action_required": requires_action,
                    }
                    if requires_action:
                        finding_data["corrective_action_due_date"] = default_due_date
                    if draft.suggested_action_title:
                        finding_data["_suggested_action_title"] = draft.suggested_action_title
                    if draft.suggested_action_description:
                        finding_data["_suggested_action_description"] = draft.suggested_action_description
                    if draft.suggested_risk_title:
                        finding_data["_suggested_risk_title"] = draft.suggested_risk_title
                    finding_data["_external_import_risk_triage_pending"] = True

                    draft_tid = draft.tenant_id if draft.tenant_id is not None else resolved_tenant_id
                    finding = await audit_service.create_finding(
                        draft.audit_run_id, finding_data, user_id=user_id, tenant_id=draft_tid
                    )
                    finding_id = await self._resolve_persisted_finding_id(
                        finding_id=getattr(finding, "id", None), tenant_id=draft_tid
                    )
                    await self._link_evidence_for_finding(
                        finding_id=finding_id,
                        clause_ids=clause_ids,
                        tenant_id=draft_tid,
                        user_id=user_id,
                        note=draft.description,
                        confidence=draft.confidence_score,
                    )
                    draft.promoted_finding_id = finding_id
                    draft.status = ExternalAuditDraftStatus.PROMOTED
                    draft.updated_by_id = user_id
                    promoted_findings.append(finding_id)
                    document_clause_ids.update(clause_ids)
            except Exception as exc:
                logger.error("Failed to promote draft %s: %s", draft.id, exc, exc_info=True)
                draft.status = ExternalAuditDraftStatus.DRAFT
                draft.review_notes = f"Promotion failed: {str(exc)[:200]}"
                failed_drafts.append(
                    {
                        "draft_id": draft.id,
                        "title": draft.title,
                        "finding_type": draft.finding_type,
                        "severity": draft.severity,
                        "error": str(exc)[:300],
                    }
                )

        if failed_drafts and not promoted_findings:
            raise RuntimeError(
                f"All {len(failed_drafts)} drafts failed to promote. First error: {failed_drafts[0]['error']}"
            )
        if failed_drafts:
            logger.warning(
                "Partial promotion: %d succeeded, %d failed",
                len(promoted_findings),
                len(failed_drafts),
            )

        return {
            "promoted_findings": promoted_findings,
            "document_clause_ids": document_clause_ids,
            "failed_drafts": failed_drafts,
        }

    @staticmethod
    def _apply_run_completion(run: AuditRun, job: ExternalAuditImportJob) -> None:
        """Update the audit run with final scores and status."""
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

    @staticmethod
    def _merge_extractions(
        *,
        native_text: str,
        native_pages: list[str],
        ocr_text: str,
        ocr_pages: list[str],
        native_method: str,
    ) -> tuple[str, list[str], str]:
        """Pick the richer extraction source, preferring OCR when it yields more content."""
        if not ocr_text:
            return native_text, native_pages, native_method
        if not native_text:
            return ocr_text, ocr_pages, "mistral_ocr"

        native_words = len(native_text.split())
        ocr_words = len(ocr_text.split())

        if ocr_words >= native_words * 1.15:
            logger.info(
                "OCR text chosen over native (%d vs %d words)",
                ocr_words,
                native_words,
            )
            return ocr_text, ocr_pages, "mistral_ocr"

        if native_words >= ocr_words * 1.15:
            return native_text, native_pages, native_method

        return ocr_text, ocr_pages, "mistral_ocr_preferred"

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

    _ACTION_FINDING_TYPES = {
        "nonconformity",
        "major_nonconformity",
        "minor_nonconformity",
        "competence_gap",
        "finding",
        "flagged_item",
        "question_answered_no",
    }

    def _build_promotion_summary(self, *, findings: list) -> dict[str, object]:
        action_candidates = sum(
            1 for finding in findings if getattr(finding, "finding_type", "") in self._ACTION_FINDING_TYPES
        )
        risk_candidates = sum(
            1
            for finding in findings
            if getattr(finding, "finding_type", "") in self._ACTION_FINDING_TYPES
            and getattr(finding, "severity", "") in {"medium", "high", "critical"}
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
                1 for finding in findings if getattr(finding, "finding_type", "") in self._ACTION_FINDING_TYPES
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

    def _count_findings(self, drafts: list[ExternalAuditDraft]) -> tuple[int, int, int, int]:
        nc_types = self._ACTION_FINDING_TYPES
        findings_count = sum(1 for d in drafts if d.finding_type in nc_types)
        major = sum(1 for d in drafts if d.finding_type in nc_types and d.severity in {"high", "critical"})
        minor = sum(1 for d in drafts if d.finding_type in nc_types and d.severity == "medium")
        obs = sum(1 for d in drafts if d.finding_type == "observation")
        return findings_count, major, minor, obs

    async def _sync_scheme_records(
        self,
        *,
        job: ExternalAuditImportJob,
        run: AuditRun,
        tenant_id: int | None,
        drafts: list[ExternalAuditDraft],
    ) -> dict[str, object]:
        home_route, home_label = self._scheme_home(job.detected_scheme)
        findings_count, major, minor, obs = self._count_findings(drafts)

        existing_record = await self.db.execute(
            select(ExternalAuditRecord).where(
                ExternalAuditRecord.import_job_id == job.id,
            )
        )
        existing = existing_record.scalar_one_or_none()
        if existing is not None:
            logger.info("ExternalAuditRecord for job %s already exists — skipping duplicate insert", job.id)
            uvdb_audit_id = None
            if self._is_uvdb_scheme(job, run):
                uvdb_result = await self.db.execute(
                    select(UVDBAudit).where(
                        UVDBAudit.tenant_id == tenant_id,
                        UVDBAudit.audit_reference == run.reference_number,
                    )
                )
                uvdb_row = uvdb_result.scalar_one_or_none()
                uvdb_audit_id = uvdb_row.id if uvdb_row else None
            return {
                "status": "already_synced",
                "scheme": job.detected_scheme,
                "external_audit_record_id": existing.id,
                "uvdb_audit_id": uvdb_audit_id,
                "home_route": home_route,
                "home_label": home_label,
            }

        record = ExternalAuditRecord(
            tenant_id=tenant_id,
            scheme=job.detected_scheme or "unknown",
            scheme_version=job.scheme_version,
            scheme_label=run.assurance_scheme or home_label,
            audit_run_id=job.audit_run_id,
            import_job_id=job.id,
            issuer_name=job.issuer_name,
            company_name=run.title or run.location,
            report_date=(
                job.report_date.replace(tzinfo=None) if job.report_date and job.report_date.tzinfo else job.report_date
            ),
            overall_score=job.overall_score,
            max_score=job.max_score,
            score_percentage=job.score_percentage,
            section_scores=job.score_breakdown_json,
            outcome_status=job.outcome_status,
            findings_count=findings_count,
            major_findings=major,
            minor_findings=minor,
            observations=obs,
            analysis_summary=job.analysis_summary,
            status="completed",
        )
        self.db.add(record)
        await self.db.flush()

        uvdb_audit_id = None
        if self._is_uvdb_scheme(job, run):
            uvdb_audit_id = await self._sync_uvdb_audit(
                job=job,
                run=run,
                tenant_id=tenant_id,
                findings_count=findings_count,
                major=major,
                minor=minor,
                obs=obs,
            )

        return {
            "status": "synced",
            "scheme": job.detected_scheme,
            "external_audit_record_id": record.id,
            "uvdb_audit_id": uvdb_audit_id,
            "home_route": home_route,
            "home_label": home_label,
        }

    @staticmethod
    def _is_uvdb_scheme(job: ExternalAuditImportJob, run: AuditRun) -> bool:
        """Determine if this import should sync to the UVDB audits table.

        Checks detected_scheme first, then falls back to the declared
        assurance_scheme on the audit run and provenance metadata.
        """
        _UVDB_KEYWORDS = {"achilles", "uvdb", "b2", "verify"}

        detected = (job.detected_scheme or "").strip().lower()
        if detected == "achilles_uvdb":
            return True
        if any(kw in detected for kw in _UVDB_KEYWORDS):
            return True

        declared = (getattr(run, "assurance_scheme", None) or "").strip().lower()
        if any(kw in declared for kw in _UVDB_KEYWORDS):
            return True

        provenance = job.provenance_json or {}
        declared_info = provenance.get("declared_vs_detected", {})
        if isinstance(declared_info, dict):
            declared_src = str(declared_info.get("declared_assurance_scheme", "")).lower()
            if any(kw in declared_src for kw in _UVDB_KEYWORDS):
                return True

        source_fn = (job.source_filename or "").lower()
        if any(kw in source_fn for kw in {"b2", "uvdb", "achilles", "verify"}):
            return True

        return False

    async def _sync_uvdb_audit(
        self,
        *,
        job: ExternalAuditImportJob,
        run: AuditRun,
        tenant_id: int | None,
        findings_count: int,
        major: int,
        minor: int,
        obs: int,
    ) -> int | None:
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
        uvdb_audit.findings_count = findings_count
        uvdb_audit.major_findings = major
        uvdb_audit.minor_findings = minor
        uvdb_audit.observations = obs
        uvdb_audit.audit_notes = job.analysis_summary
        await self.db.flush()
        return uvdb_audit.id
