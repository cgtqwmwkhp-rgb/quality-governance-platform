"""Compliance Schedule FRA / PAS 79 OCR draft lifecycle (propose → confirm → file).

Confirm writes ``ComplianceRequirement.next_due_date`` after a human gate.
Checked priority actions are recorded on the draft; CAPAs are created only when
``COMPLIANCE_SCHEDULE_FRA_OCR_ACTIONS_ENABLED`` is on. An optional risk proposal
with operator-entered likelihood/impact creates one Enterprise Risk only when
``COMPLIANCE_SCHEDULE_FRA_OCR_RISK_ENABLED`` is on — never from OCR scores alone.
Library filing is a separate step after confirm (ADR-0020 permission reasoning).
"""

from __future__ import annotations

import hashlib
import logging
import math
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import false, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.config import settings
from src.domain.exceptions import ConflictError, ExternalServiceError, NotFoundError, ValidationError
from src.domain.models.compliance_schedule import (
    ComplianceOcrDraftStatus,
    ComplianceOcrFilingStatus,
    ComplianceRecord,
    ComplianceRequirement,
    ComplianceScheduleOcrDraft,
)
from src.domain.models.document import Document, FileType, IndexJob
from src.domain.models.enums import DocumentStatus, DocumentType
from src.domain.models.risk_register import EnterpriseRisk
from src.domain.models.user import User
from src.domain.services.audit_service import record_audit_event
from src.domain.services.capa_auto_service import CAPAAutoService
from src.domain.services.compliance_schedule_filing_service import FILING_ERROR_MAX_CHARS, _load_bound_evidence_asset
from src.domain.services.compliance_schedule_service import ComplianceScheduleService
from src.domain.services.document_category_service import allocate_pel_doc_ref
from src.domain.services.document_library_filing_service import (
    filing_defaults_for_category,
    find_duplicate_approved_candidates,
    load_filing_category,
)
from src.domain.services.document_version_service import document_version_service
from src.domain.services.fra_pas79_ocr_service import FRA_OCR_PURPOSE, FRA_TAXONOMY_ID, FraPas79OcrService
from src.domain.services.index_job_service import maybe_create_filing_index_job
from src.domain.services.reference_number import ReferenceNumberService
from src.domain.services.risk_service import RiskService
from src.infrastructure.storage import StorageError, storage_service

logger = logging.getLogger(__name__)

_DUE_DATE_FLOOR = date(2000, 1, 1)
FRA_OCR_MAX_PDF_BYTES = 25 * 1024 * 1024
FRA_OCR_PDF_MAGIC = b"%PDF-"


@dataclass(frozen=True)
class FraOcrFilingOutcome:
    draft: ComplianceScheduleOcrDraft
    document: Document
    duplicate_warning: bool
    duplicate_warning_detail: Optional[list[dict]]
    index_job: Optional[IndexJob] = None


def _safe_storage_filename(filename: Optional[str]) -> str:
    return (filename or "unnamed").replace("/", "_").replace("\\", "_")


def _utc_now(now: datetime | None = None) -> datetime:
    if now is not None:
        return now if now.tzinfo else now.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc)


def _split_proposed(proposed_json: dict | None) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    raw = dict(proposed_json or {})
    actions = raw.pop("actions", []) or []
    if not isinstance(actions, list):
        actions = []
    return raw, actions


class ComplianceScheduleFraOcrService:
    """Draft CRUD + confirm + discard + file for FRA OCR ingest."""

    def __init__(
        self,
        db: AsyncSession,
        *,
        ocr_service: FraPas79OcrService | None = None,
    ) -> None:
        self.db = db
        self._ocr = ocr_service or FraPas79OcrService()

    async def create_draft_from_upload(
        self,
        *,
        requirement_id: int,
        tenant_id: int,
        user_id: int,
        content: bytes,
        filename: str,
        content_type: str,
    ) -> ComplianceScheduleOcrDraft:
        requirement = await self._load_fra_requirement(
            requirement_id=requirement_id,
            tenant_id=tenant_id,
            for_update=False,
        )
        checksum = hashlib.sha256(content).hexdigest()
        safe_name = _safe_storage_filename(filename)
        storage_key = f"compliance-schedule/fra-ocr/{tenant_id}/{uuid.uuid4()}/{safe_name}"

        try:
            await storage_service().upload(
                storage_key=storage_key,
                content=content,
                content_type=content_type or "application/pdf",
                metadata={
                    "tenant_id": str(tenant_id),
                    "requirement_id": str(requirement.id),
                    "uploaded_by": str(user_id),
                    "file_name": safe_name,
                    "purpose": FRA_OCR_PURPOSE,
                },
            )
        except StorageError as exc:
            logger.warning(
                "fra_ocr upload storage failed tenant_id=%s requirement_id=%s filename=%s err=%s",
                tenant_id,
                requirement_id,
                safe_name,
                type(exc).__name__,
            )
            raise ExternalServiceError(
                "Could not store the FRA PDF; try again shortly.",
                code="EXTERNAL_SERVICE_ERROR",
            ) from exc

        extraction = await self._ocr.extract(
            content=content,
            filename=filename,
            content_type=content_type or "application/pdf",
        )
        proposed = extraction.to_proposed_json()
        draft = ComplianceScheduleOcrDraft(
            tenant_id=tenant_id,
            requirement_id=requirement.id,
            purpose=FRA_OCR_PURPOSE,
            status=ComplianceOcrDraftStatus.PENDING,
            source_filename=filename,
            source_content_type=content_type or "application/pdf",
            source_size_bytes=len(content),
            source_checksum_sha256=checksum,
            source_storage_key=storage_key,
            extraction_method=extraction.extraction_method,
            ocr_provider_status=extraction.ocr_provider_status,
            page_count=extraction.page_count,
            proposed_json=proposed,
            warnings_json=list(extraction.warnings),
            filing_status=ComplianceOcrFilingStatus.NOT_FILED,
            created_by_id=user_id,
            updated_by_id=user_id,
        )
        self.db.add(draft)
        try:
            await self.db.commit()
        except IntegrityError as exc:
            await self.db.rollback()
            # Best-effort cleanup of the orphan blob from this attempt.
            try:
                await storage_service().delete(storage_key)
            except Exception:  # noqa: BLE001
                logger.warning(
                    "fra_ocr orphan blob cleanup failed tenant_id=%s requirement_id=%s",
                    tenant_id,
                    requirement_id,
                )
            raise ConflictError(
                "A pending FRA OCR draft already exists for this PDF on this obligation.",
                code="DUPLICATE_ENTITY",
            ) from exc

        await self.db.refresh(draft)
        logger.info(
            "fra_ocr draft created draft_id=%s requirement_id=%s tenant_id=%s "
            "method=%s provider_status=%s action_count=%s warning_count=%s",
            draft.id,
            requirement_id,
            tenant_id,
            draft.extraction_method,
            draft.ocr_provider_status,
            len(proposed.get("actions") or []),
            len(draft.warnings_json or []),
        )
        return draft

    async def create_draft_from_evidence_asset(
        self,
        *,
        record_id: int,
        evidence_asset_id: int,
        tenant_id: int,
        user_id: int,
    ) -> ComplianceScheduleOcrDraft:
        """Create a pending FRA OCR draft from an occurrence evidence PDF blob.

        Reuses the EvidenceAsset storage key (no second upload). Sets
        ``evidence_asset_id`` so discard / IntegrityError cleanup never deletes
        the shared evidence blob.
        """
        record = await self._load_record(record_id=record_id, tenant_id=tenant_id)
        asset = await _load_bound_evidence_asset(
            self.db,
            evidence_asset_id=evidence_asset_id,
            record=record,
            tenant_id=tenant_id,
        )
        requirement = await self._load_fra_requirement(
            requirement_id=record.requirement_id,
            tenant_id=tenant_id,
            for_update=False,
        )

        if not asset.storage_key:
            raise ValidationError(
                "Evidence asset has no storage key to OCR",
                code="VALIDATION_ERROR",
                details={"evidence_asset_id": evidence_asset_id},
            )
        if not asset.checksum_sha256:
            raise ValidationError(
                "Evidence asset has no checksum to verify before OCR",
                code="VALIDATION_ERROR",
                details={"evidence_asset_id": evidence_asset_id},
            )

        try:
            content = await storage_service().download(asset.storage_key)
        except StorageError as exc:
            logger.warning(
                "fra_ocr from-evidence download failed tenant_id=%s record_id=%s " "evidence_asset_id=%s err=%s",
                tenant_id,
                record_id,
                evidence_asset_id,
                type(exc).__name__,
            )
            raise ExternalServiceError(
                "Could not read the occurrence evidence PDF; try again shortly.",
                code="EXTERNAL_SERVICE_ERROR",
            ) from exc

        if not content:
            raise ValidationError("Evidence PDF is empty", code="VALIDATION_ERROR")
        if len(content) > FRA_OCR_MAX_PDF_BYTES:
            raise ValidationError(
                "PDF file exceeds 25 MiB limit",
                code="VALIDATION_ERROR",
                details={"size_bytes": len(content), "max_bytes": FRA_OCR_MAX_PDF_BYTES},
            )
        if not content.startswith(FRA_OCR_PDF_MAGIC):
            raise ValidationError(
                "File does not look like a PDF",
                code="VALIDATION_ERROR",
                details={"evidence_asset_id": evidence_asset_id},
            )

        checksum = hashlib.sha256(content).hexdigest()
        if checksum != asset.checksum_sha256:
            raise ValidationError(
                "Evidence blob checksum does not match the EvidenceAsset record",
                code="VALIDATION_ERROR",
                details={"evidence_asset_id": evidence_asset_id},
            )

        filename = asset.original_filename or asset.title or f"evidence-{asset.id}.pdf"
        content_type = asset.content_type or "application/pdf"
        extraction = await self._ocr.extract(
            content=content,
            filename=filename,
            content_type=content_type,
        )
        proposed = extraction.to_proposed_json()
        draft = ComplianceScheduleOcrDraft(
            tenant_id=tenant_id,
            requirement_id=requirement.id,
            purpose=FRA_OCR_PURPOSE,
            status=ComplianceOcrDraftStatus.PENDING,
            source_filename=filename,
            source_content_type=content_type,
            source_size_bytes=len(content),
            source_checksum_sha256=checksum,
            source_storage_key=asset.storage_key,
            evidence_asset_id=asset.id,
            extraction_method=extraction.extraction_method,
            ocr_provider_status=extraction.ocr_provider_status,
            page_count=extraction.page_count,
            proposed_json=proposed,
            warnings_json=list(extraction.warnings),
            filing_status=ComplianceOcrFilingStatus.NOT_FILED,
            created_by_id=user_id,
            updated_by_id=user_id,
        )
        self.db.add(draft)
        try:
            await self.db.commit()
        except IntegrityError as exc:
            await self.db.rollback()
            # Must NOT delete asset.storage_key — the occurrence still owns it.
            raise ConflictError(
                "A pending FRA OCR draft already exists for this PDF on this obligation.",
                code="DUPLICATE_ENTITY",
            ) from exc

        await self.db.refresh(draft)
        logger.info(
            "fra_ocr draft created from evidence draft_id=%s requirement_id=%s "
            "record_id=%s evidence_asset_id=%s tenant_id=%s method=%s "
            "provider_status=%s action_count=%s warning_count=%s",
            draft.id,
            requirement.id,
            record_id,
            evidence_asset_id,
            tenant_id,
            draft.extraction_method,
            draft.ocr_provider_status,
            len(proposed.get("actions") or []),
            len(draft.warnings_json or []),
        )
        return draft

    async def get_draft(
        self,
        *,
        draft_id: int,
        tenant_id: int,
    ) -> ComplianceScheduleOcrDraft:
        return await self._load_draft(draft_id=draft_id, tenant_id=tenant_id, for_update=False)

    async def list_drafts(
        self,
        *,
        requirement_id: int,
        tenant_id: int,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[ComplianceScheduleOcrDraft], int]:
        await self._load_fra_requirement(
            requirement_id=requirement_id,
            tenant_id=tenant_id,
            for_update=False,
            allow_inactive=True,
        )
        filters = [
            ComplianceScheduleOcrDraft.tenant_id == tenant_id,
            ComplianceScheduleOcrDraft.requirement_id == requirement_id,
        ]
        if status:
            filters.append(ComplianceScheduleOcrDraft.status == status)

        total = int(
            (
                await self.db.execute(select(func.count()).select_from(ComplianceScheduleOcrDraft).where(*filters))
            ).scalar_one()
        )
        page = max(1, page)
        page_size = min(max(1, page_size), 100)
        offset = (page - 1) * page_size
        result = await self.db.execute(
            select(ComplianceScheduleOcrDraft)
            .where(*filters)
            .order_by(ComplianceScheduleOcrDraft.id.desc())
            .offset(offset)
            .limit(page_size)
        )
        return list(result.scalars().all()), total

    async def apply_confirmed_plan(
        self,
        *,
        draft_id: int,
        tenant_id: int,
        user_id: int,
        next_due_date: date,
        actions: list[dict[str, Any]] | None = None,
        note: str | None = None,
        risk: dict[str, Any] | None = None,
        acknowledged_warnings: bool = False,
        now: datetime | None = None,
    ) -> tuple[ComplianceScheduleOcrDraft, ComplianceRequirement, dict[str, Any]]:
        clock = _utc_now(now)
        draft = await self._load_draft(draft_id=draft_id, tenant_id=tenant_id, for_update=True)
        if draft.status != ComplianceOcrDraftStatus.PENDING:
            raise ConflictError(
                f"FRA OCR draft {draft_id} is {draft.status.value}, not pending",
                code="DUPLICATE_ENTITY",
            )

        requirement = await self._load_fra_requirement(
            requirement_id=draft.requirement_id,
            tenant_id=tenant_id,
            for_update=True,
        )

        today = clock.date()
        due = next_due_date
        if due < _DUE_DATE_FLOOR or due > today + timedelta(days=365 * 10):
            raise ValidationError(
                "next_due_date must be between 2000-01-01 and today + 10 years",
                code="VALIDATION_ERROR",
            )

        applied_warnings: list[str] = []
        if due < today:
            applied_warnings.append("Confirmed next_due_date is in the past.")
        elif due > today + timedelta(days=365 * 5):
            applied_warnings.append("Confirmed next_due_date is more than 5 years ahead.")

        before = requirement.next_due_date
        changed_fields: list[str] = []
        if due != before:
            requirement.next_due_date = due
            changed_fields = ["next_due_date"]
        requirement.updated_by_id = user_id

        actions_list = list(actions or [])
        actions_created = 0
        capa_refs: list[str] = []
        if settings.compliance_schedule_fra_ocr_actions_enabled and actions_list:
            capas = await CAPAAutoService.create_from_fra_ocr_actions(
                self.db,
                draft_id=draft.id,
                requirement=requirement,
                actions=actions_list,
                created_by_id=user_id,
                now=clock,
            )
            actions_created = len(capas)
            capa_refs = [
                str(getattr(capa, "reference_number", "") or "")
                for capa in capas
                if getattr(capa, "reference_number", None)
            ]

        risks_created = 0
        risk_ref: str | None = None
        risk_payload = dict(risk) if isinstance(risk, dict) else None
        if settings.compliance_schedule_fra_ocr_risk_enabled and risk_payload:
            risk_row = await self._create_risk_from_confirm(
                draft=draft,
                requirement=requirement,
                risk=risk_payload,
                user_id=user_id,
                tenant_id=tenant_id,
            )
            if risk_row is not None:
                risks_created = 1
                risk_ref = str(getattr(risk_row, "reference", "") or "") or None

        summary = {
            "requirement_id": requirement.id,
            "next_due_date_before": before.isoformat(),
            "next_due_date_after": due.isoformat(),
            "actions_recorded": len(actions_list),
            "actions_created": actions_created,
            "risks_created": risks_created,
            "changed_fields": changed_fields,
            "warnings": applied_warnings,
        }

        draft.status = ComplianceOcrDraftStatus.CONFIRMED
        draft.confirmed_at = clock
        draft.confirmed_by_id = user_id
        draft.confirmed_json = {
            "next_due_date": due.isoformat(),
            "acknowledged_warnings": acknowledged_warnings,
            "actions": actions_list,
            "note": note,
            "risk": risk_payload,
        }
        draft.applied_json = summary
        draft.updated_by_id = user_id

        await record_audit_event(
            db=self.db,
            event_type="compliance_schedule.requirement_updated",
            entity_type="compliance_requirement",
            entity_id=str(requirement.id),
            entity_name=requirement.reference_number,
            action="update",
            description=f"FRA OCR confirm updated {requirement.reference_number}",
            payload={
                "draft_id": draft.id,
                "next_due_date_before": before.isoformat(),
                "next_due_date_after": due.isoformat(),
            },
            user_id=user_id,
            actor_user_id=user_id,
            changed_fields=changed_fields or None,
            tenant_id=tenant_id,
        )
        await record_audit_event(
            db=self.db,
            event_type="compliance_schedule.fra_ocr_confirmed",
            entity_type="compliance_schedule_ocr_draft",
            entity_id=str(draft.id),
            entity_name=draft.external_id,
            action="update",
            description=f"FRA OCR draft {draft.id} confirmed",
            payload={
                "draft_id": draft.id,
                "requirement_id": requirement.id,
                "next_due_date_before": before.isoformat(),
                "next_due_date_after": due.isoformat(),
                "actions_recorded": len(actions_list),
                "actions_created": actions_created,
                "capa_reference_numbers": capa_refs,
                "risks_created": risks_created,
                "risk_reference": risk_ref,
                "extraction_method": draft.extraction_method,
                "source_checksum_sha256": draft.source_checksum_sha256,
            },
            user_id=user_id,
            actor_user_id=user_id,
            changed_fields=["status", "confirmed_at", "applied_json"],
            tenant_id=tenant_id,
        )

        await self.db.commit()
        await self.db.refresh(draft)
        await self.db.refresh(requirement)

        logger.info(
            "fra_ocr draft confirmed draft_id=%s requirement_id=%s tenant_id=%s "
            "actions_recorded=%s actions_created=%s risks_created=%s changed_fields=%s",
            draft.id,
            requirement.id,
            tenant_id,
            len(actions_list),
            actions_created,
            risks_created,
            changed_fields,
        )
        return draft, requirement, summary

    async def _create_risk_from_confirm(
        self,
        *,
        draft: ComplianceScheduleOcrDraft,
        requirement: ComplianceRequirement,
        risk: dict[str, Any],
        user_id: int,
        tenant_id: int,
    ) -> EnterpriseRisk | None:
        """Create one Enterprise Risk from operator-entered likelihood/impact.

        Returns an existing row when a risk with ``source=fra_ocr_draft:{id}``
        already exists (idempotent). Does not invent scores from OCR proposed
        fields — both scores must be present in ``risk``.
        """
        try:
            likelihood = int(risk["inherent_likelihood"])
            impact = int(risk["inherent_impact"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValidationError(
                "risk.inherent_likelihood and risk.inherent_impact are required (1-5)",
                code="VALIDATION_ERROR",
            ) from exc
        if likelihood < 1 or likelihood > 5 or impact < 1 or impact > 5:
            raise ValidationError(
                "risk likelihood and impact must be integers from 1 to 5",
                code="VALIDATION_ERROR",
            )

        source_key = f"fra_ocr_draft:{int(draft.id)}"
        existing = (
            await self.db.execute(
                select(EnterpriseRisk).where(
                    EnterpriseRisk.tenant_id == tenant_id,
                    EnterpriseRisk.source == source_key,
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            return existing

        title = str(risk.get("title") or "").strip()
        if not title:
            title = f"FRA residual risk — {requirement.reference_number}"
        description = str(risk.get("description") or "").strip()
        if not description:
            description = (
                f"Risk proposed on confirm of FRA OCR draft {draft.id} for "
                f"{requirement.reference_number} ({requirement.title}). "
                "Likelihood and impact were entered by the operator."
            )

        service = RiskService(self.db)
        return await service.create_risk(
            {
                "tenant_id": tenant_id,
                "title": title[:255],
                "description": description[:4000],
                "category": "health_safety",
                "source": source_key,
                "context": f"compliance_requirement:{requirement.id}",
                "inherent_likelihood": likelihood,
                "inherent_impact": impact,
                "residual_likelihood": likelihood,
                "residual_impact": impact,
                "risk_owner_id": requirement.owner_id,
                "status": "active",
                "treatment_strategy": "treat",
            },
            created_by=user_id,
            commit=False,
        )

    async def discard_draft(
        self,
        *,
        draft_id: int,
        tenant_id: int,
        user_id: int,
        reason: Optional[str] = None,
        now: datetime | None = None,
    ) -> ComplianceScheduleOcrDraft:
        clock = _utc_now(now)
        draft = await self._load_draft(draft_id=draft_id, tenant_id=tenant_id, for_update=True)
        if draft.status != ComplianceOcrDraftStatus.PENDING:
            raise ConflictError(
                f"FRA OCR draft {draft_id} is {draft.status.value}, not pending",
                code="DUPLICATE_ENTITY",
            )

        # From-evidence drafts share the occurrence EvidenceAsset blob — never
        # delete it on discard. Upload-created drafts (evidence_asset_id is None)
        # still own their staging blob and clean it up.
        storage_key = draft.source_storage_key
        owns_source_blob = draft.evidence_asset_id is None
        draft.status = ComplianceOcrDraftStatus.DISCARDED
        draft.discarded_at = clock
        draft.updated_by_id = user_id
        if reason:
            confirmed = dict(draft.confirmed_json or {})
            confirmed["discard_reason"] = reason
            draft.confirmed_json = confirmed

        await record_audit_event(
            db=self.db,
            event_type="compliance_schedule.fra_ocr_discarded",
            entity_type="compliance_schedule_ocr_draft",
            entity_id=str(draft.id),
            entity_name=draft.external_id,
            action="update",
            description=f"FRA OCR draft {draft.id} discarded",
            payload={
                "draft_id": draft.id,
                "requirement_id": draft.requirement_id,
                "has_reason": bool(reason),
                "evidence_asset_id": draft.evidence_asset_id,
                "deleted_source_blob": bool(owns_source_blob and storage_key),
            },
            user_id=user_id,
            actor_user_id=user_id,
            changed_fields=["status", "discarded_at"],
            tenant_id=tenant_id,
        )
        await self.db.commit()
        await self.db.refresh(draft)

        if owns_source_blob and storage_key:
            try:
                await storage_service().delete(storage_key)
            except Exception:  # noqa: BLE001
                logger.warning(
                    "fra_ocr discard blob cleanup failed draft_id=%s tenant_id=%s",
                    draft.id,
                    tenant_id,
                )

        logger.info(
            "fra_ocr draft discarded draft_id=%s requirement_id=%s tenant_id=%s",
            draft.id,
            draft.requirement_id,
            tenant_id,
        )
        return draft

    async def file_draft_to_library(
        self,
        *,
        draft_id: int,
        tenant_id: int,
        user: User,
        category_id: int,
        title: Optional[str] = None,
    ) -> FraOcrFilingOutcome:
        draft = await self._load_draft(draft_id=draft_id, tenant_id=tenant_id, for_update=True)
        if draft.status != ComplianceOcrDraftStatus.CONFIRMED:
            raise ConflictError(
                "Only a confirmed FRA OCR draft can be filed to the Library",
                code="DUPLICATE_ENTITY",
            )
        if draft.filing_status == ComplianceOcrFilingStatus.FILED and draft.library_document_id is not None:
            raise ConflictError(
                f"FRA OCR draft {draft_id} is already filed to library document {draft.library_document_id}",
                code="DUPLICATE_ENTITY",
                details={"library_document_id": draft.library_document_id},
            )

        requirement = await self._load_fra_requirement(
            requirement_id=draft.requirement_id,
            tenant_id=tenant_id,
            for_update=False,
            allow_inactive=True,
        )
        category = await load_filing_category(self.db, category_id)
        if getattr(category, "taxonomy_id", None) != FRA_TAXONOMY_ID:
            raise ValidationError(
                f"FRA OCR filing requires a Library category with taxonomy_id {FRA_TAXONOMY_ID}",
                code="VALIDATION_ERROR",
                details={"expected_taxonomy_id": FRA_TAXONOMY_ID},
            )

        if not draft.source_storage_key:
            raise ValidationError(
                "FRA OCR draft has no source storage key to file",
                code="VALIDATION_ERROR",
            )

        try:
            content = await storage_service().download(draft.source_storage_key)
        except StorageError as exc:
            await self._mark_filing_failed(
                draft_id=draft.id,
                tenant_id=tenant_id,
                user_id=user.id,
                message=f"Could not read FRA source {draft.source_storage_key}: {exc}",
            )
            logger.warning(
                "fra_ocr filing could not read source draft_id=%s err=%s",
                draft.id,
                type(exc).__name__,
            )
            raise ExternalServiceError(
                "Could not read the FRA PDF from storage; the draft is marked filing_failed.",
                code="EXTERNAL_SERVICE_ERROR",
            ) from exc

        doc_title = title or draft.source_filename or f"FRA draft {draft.id}"
        site_location_id = requirement.location_id
        reference_number = await ReferenceNumberService.generate(self.db, "document", Document)
        pel_doc_ref = await allocate_pel_doc_ref(self.db, category_id)
        defaults = filing_defaults_for_category(category)

        duplicates = await find_duplicate_approved_candidates(
            self.db,
            tenant_id=tenant_id,
            category_id=category_id,
            site_location_id=site_location_id,
            title=doc_title,
        )
        duplicate_warning_detail = (
            [
                {
                    "document_id": d.document_id,
                    "title": d.title,
                    "reference_number": d.reference_number,
                    "pel_doc_ref": d.pel_doc_ref,
                }
                for d in duplicates
            ]
            if duplicates
            else None
        )

        file_name = draft.source_filename or f"fra-draft-{draft.id}.pdf"
        library_key = (
            f"documents/{datetime.now(timezone.utc).strftime('%Y/%m')}/"
            f"{uuid.uuid4()}/{_safe_storage_filename(file_name)}"
        )

        document = Document(
            tenant_id=tenant_id,
            title=doc_title,
            description=(
                f"Filed from Compliance Schedule FRA OCR draft {draft.id} "
                f"(requirement {requirement.reference_number})."
            ),
            file_name=file_name,
            file_type=FileType.PDF,
            file_size=len(content),
            file_path=library_key,
            mime_type=draft.source_content_type or "application/pdf",
            document_type=DocumentType.RECORD,
            status=DocumentStatus.DRAFT,
            version="1.0",
            reference_number=reference_number,
            category_id=category_id,
            pel_doc_ref=pel_doc_ref,
            site_location_id=site_location_id,
            access_level=defaults.access_level,
            is_statutory=defaults.is_statutory,
            duplicate_warning=bool(duplicates),
            duplicate_warning_detail=duplicate_warning_detail,
            created_by_id=user.id,
        )
        self.db.add(document)
        await self.db.flush()
        self.db.add(
            document_version_service.build_initial_library_version(
                document,
                created_by_id=user.id,
                change_notes=f"Filed from FRA OCR draft {draft.id}",
            )
        )

        try:
            await storage_service().upload(
                storage_key=library_key,
                content=content,
                content_type=draft.source_content_type or "application/pdf",
                metadata={
                    "document_id": str(document.id),
                    "tenant_id": str(tenant_id),
                    "uploaded_by": str(user.id),
                    "file_name": file_name,
                    "fra_ocr_draft_id": str(draft.id),
                },
            )
        except StorageError as exc:
            await self._mark_filing_failed(
                draft_id=draft.id,
                tenant_id=tenant_id,
                user_id=user.id,
                message=f"Could not write library copy to {library_key}: {exc}",
            )
            logger.warning(
                "fra_ocr filing could not write library copy draft_id=%s err=%s",
                draft.id,
                type(exc).__name__,
            )
            raise ExternalServiceError(
                "Could not store the Library copy of the FRA PDF; the draft is marked filing_failed.",
                code="EXTERNAL_SERVICE_ERROR",
            ) from exc

        # Same commit as the Document row — Celery must not see the job early.
        index_job = await maybe_create_filing_index_job(
            self.db,
            document=document,
            created_by_id=user.id,
        )

        draft.library_document_id = document.id
        draft.filing_status = ComplianceOcrFilingStatus.FILED
        draft.filing_error = None
        draft.updated_by_id = user.id

        await record_audit_event(
            db=self.db,
            event_type="compliance_schedule.fra_ocr_filed",
            entity_type="compliance_schedule_ocr_draft",
            entity_id=str(draft.id),
            entity_name=draft.external_id,
            action="update",
            description=f"Filed FRA OCR draft {draft.id} to library document {document.id}",
            payload={
                "library_document_id": document.id,
                "pel_doc_ref": getattr(document, "pel_doc_ref", None),
                "category_id": category_id,
                "requirement_id": requirement.id,
                "index_job_id": index_job.id if index_job is not None else None,
            },
            user_id=user.id,
            actor_user_id=user.id,
            changed_fields=["library_document_id", "filing_status"],
            tenant_id=tenant_id,
        )

        await self.db.commit()
        await self.db.refresh(draft)
        return FraOcrFilingOutcome(
            draft=draft,
            document=document,
            duplicate_warning=bool(duplicates),
            duplicate_warning_detail=duplicate_warning_detail,
            index_job=index_job,
        )

    async def _mark_filing_failed(
        self,
        *,
        draft_id: int,
        tenant_id: int,
        user_id: int,
        message: str,
    ) -> None:
        await self.db.rollback()
        result = await self.db.execute(
            select(ComplianceScheduleOcrDraft).where(
                ComplianceScheduleOcrDraft.id == draft_id,
                ComplianceScheduleOcrDraft.tenant_id == tenant_id,
            )
        )
        draft = result.scalar_one_or_none()
        if draft is None:
            return
        draft.filing_status = ComplianceOcrFilingStatus.FILING_FAILED
        draft.filing_error = message[:FILING_ERROR_MAX_CHARS]
        draft.updated_by_id = user_id
        await self.db.commit()

    async def _load_record(
        self,
        *,
        record_id: int,
        tenant_id: Optional[int],
    ) -> ComplianceRecord:
        query = select(ComplianceRecord).where(ComplianceRecord.id == record_id)
        query = query.where(false()) if tenant_id is None else query.where(ComplianceRecord.tenant_id == tenant_id)
        result = await self.db.execute(query)
        record = result.scalar_one_or_none()
        if record is None:
            raise NotFoundError(
                f"Compliance record {record_id} not found",
                code="ENTITY_NOT_FOUND",
            )
        return record

    async def _load_draft(
        self,
        *,
        draft_id: int,
        tenant_id: Optional[int],
        for_update: bool,
    ) -> ComplianceScheduleOcrDraft:
        query = select(ComplianceScheduleOcrDraft).where(ComplianceScheduleOcrDraft.id == draft_id)
        query = (
            query.where(false())
            if tenant_id is None
            else query.where(ComplianceScheduleOcrDraft.tenant_id == tenant_id)
        )
        if for_update:
            query = query.with_for_update()
        result = await self.db.execute(query)
        draft = result.scalar_one_or_none()
        if draft is None:
            raise NotFoundError(
                f"FRA OCR draft {draft_id} not found",
                code="ENTITY_NOT_FOUND",
            )
        return draft

    async def _load_fra_requirement(
        self,
        *,
        requirement_id: int,
        tenant_id: Optional[int],
        for_update: bool,
        allow_inactive: bool = False,
    ) -> ComplianceRequirement:
        query = (
            select(ComplianceRequirement)
            .options(selectinload(ComplianceRequirement.template))
            .where(ComplianceRequirement.id == requirement_id)
        )
        query = query.where(false()) if tenant_id is None else query.where(ComplianceRequirement.tenant_id == tenant_id)
        if for_update:
            query = query.with_for_update()
        result = await self.db.execute(query)
        requirement = result.scalar_one_or_none()
        if requirement is None:
            raise NotFoundError(
                f"Compliance requirement {requirement_id} not found",
                code="ENTITY_NOT_FOUND",
            )
        if not allow_inactive and not requirement.is_active:
            raise ValidationError(
                "Cannot run FRA OCR on an inactive obligation",
                code="VALIDATION_ERROR",
            )
        if requirement.location_id is None:
            raise ValidationError(
                "FRA OCR is only available for site-scoped Fire Risk Assessment obligations",
                code="VALIDATION_ERROR",
            )
        if not self._is_fra_requirement(requirement):
            raise ValidationError(
                "FRA OCR is only available for fire_risk_assessment / taxonomy 03.01 obligations",
                code="VALIDATION_ERROR",
            )
        return requirement

    @staticmethod
    def _is_fra_requirement(requirement: ComplianceRequirement) -> bool:
        template = requirement.template
        if template is not None and template.template_key == ComplianceScheduleService.FRA_TEMPLATE_KEY:
            return True
        if requirement.template_id is None and requirement.taxonomy_id == FRA_TAXONOMY_ID:
            return True
        return False

    @staticmethod
    def is_fra_ocr_eligible(requirement: ComplianceRequirement) -> bool:
        """Site-scoped active FRA obligation — same gate as draft create/upload.

        Mirrors ``_load_fra_requirement`` predicates (active + location +
        ``_is_fra_requirement``). Safe for response mapping when ``template`` is
        already loaded or explicitly assigned; callers must not rely on lazy IO.
        """
        if not requirement.is_active:
            return False
        if requirement.location_id is None:
            return False
        return ComplianceScheduleFraOcrService._is_fra_requirement(requirement)


def draft_to_response_dict(draft: ComplianceScheduleOcrDraft) -> dict[str, Any]:
    """Map an ORM draft to the FraOcrDraftResponse shape (without pydantic)."""
    fields_raw, actions = _split_proposed(draft.proposed_json if isinstance(draft.proposed_json, dict) else {})

    def _field(raw: Any) -> dict[str, Any]:
        if not isinstance(raw, dict):
            raw = {}
        return {
            "value": raw.get("value"),
            "confidence": raw.get("confidence") or "none",
            "evidence_snippet": raw.get("evidence_snippet"),
        }

    proposed = {
        "assessment_date": _field(fields_raw.get("assessment_date")),
        "next_review_date": _field(fields_raw.get("next_review_date")),
        "review_interval_months": _field(fields_raw.get("review_interval_months")),
        "assessor_name": _field(fields_raw.get("assessor_name")),
        "assessor_organisation": _field(fields_raw.get("assessor_organisation")),
        "premises_name": _field(fields_raw.get("premises_name")),
        "pas79_reference": _field(fields_raw.get("pas79_reference")),
        "overall_risk_rating": _field(fields_raw.get("overall_risk_rating")),
        "risk_vocabulary": fields_raw.get("risk_vocabulary"),
    }
    applied = None
    if draft.applied_json:
        applied_raw = dict(draft.applied_json)
        # Dates may be ISO strings in JSON
        for key in ("next_due_date_before", "next_due_date_after"):
            if isinstance(applied_raw.get(key), str):
                applied_raw[key] = date.fromisoformat(applied_raw[key])
        applied = applied_raw

    return {
        "id": draft.id,
        "external_id": draft.external_id,
        "tenant_id": draft.tenant_id,
        "requirement_id": draft.requirement_id,
        "purpose": draft.purpose,
        "status": draft.status.value if hasattr(draft.status, "value") else draft.status,
        "source_filename": draft.source_filename,
        "source_size_bytes": draft.source_size_bytes,
        "source_checksum_sha256": draft.source_checksum_sha256,
        "evidence_asset_id": draft.evidence_asset_id,
        "extraction_method": draft.extraction_method,
        "ocr_provider_status": draft.ocr_provider_status,
        "page_count": draft.page_count,
        "proposed": proposed,
        "proposed_actions": actions,
        "warnings": list(draft.warnings_json or []),
        "confirmed_at": draft.confirmed_at,
        "confirmed_by_id": draft.confirmed_by_id,
        "applied": applied,
        "library_document_id": draft.library_document_id,
        "filing_status": (draft.filing_status.value if hasattr(draft.filing_status, "value") else draft.filing_status),
        "filing_error": draft.filing_error,
        "created_at": draft.created_at,
        "updated_at": draft.updated_at,
    }


def pages_for(total: int, page_size: int) -> int:
    return max(1, int(math.ceil(total / page_size))) if total else 0
