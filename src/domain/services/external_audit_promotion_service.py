"""Promotion, scheme sync, and reconciliation for external audit import."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, TypedDict, cast

from sqlalchemy import func, select, update
from sqlalchemy.exc import OperationalError, ProgrammingError

from src.domain.exceptions import ConflictError, ValidationError
from src.domain.models.audit import AuditFinding, AuditRun, AuditStatus
from src.domain.models.capa import CAPAAction, CAPASource
from src.domain.models.compliance_evidence import ComplianceEvidenceLink, EvidenceLinkMethod
from src.domain.models.external_audit_import import (
    ExternalAuditDraft,
    ExternalAuditDraftStatus,
    ExternalAuditImportJob,
    ExternalAuditImportStatus,
)
from src.domain.models.external_audit_record import ExternalAuditRecord
from src.domain.models.planet_mark import CarbonReportingYear, EmissionSource
from src.domain.models.planet_mark import ImprovementAction as PlanetMarkImprovementAction
from src.domain.models.planet_mark import Scope3CategoryData
from src.domain.models.risk_register import EnterpriseRisk
from src.domain.models.uvdb_achilles import UVDBAudit
from src.domain.services.audit_risk_gate import RISK_CREATING_FINDING_TYPES, should_create_risk
from src.domain.services.audit_service import AuditService
from src.domain.services.planet_mark_service import SCOPE3_CATEGORIES, PlanetMarkService
from src.domain.services.reference_number import ReferenceNumberService
from src.infrastructure.cache.redis_cache import invalidate_tenant_cache
from src.infrastructure.monitoring.azure_monitor import record_external_audit_promote_outcome

if TYPE_CHECKING:
    from src.domain.services.external_audit_import_service import ExternalAuditImportService

logger = logging.getLogger(__name__)

# In-process outcome counters — observable without App Insights, asserted by unit tests.
# Keys: promote completed|partial|all_failed|error and uvdb_sync ok|skipped|n_a|failed|already_synced|synced
_PROMOTION_OUTCOME_COUNTERS: dict[str, int] = {}


def get_promotion_outcome_counters() -> dict[str, int]:
    """Return a copy of in-process promote / uvdb_sync outcome counters."""
    return dict(_PROMOTION_OUTCOME_COUNTERS)


def reset_promotion_outcome_counters() -> None:
    """Reset in-process counters (tests only)."""
    _PROMOTION_OUTCOME_COUNTERS.clear()


def _bump_outcome_counter(kind: str, outcome: str) -> None:
    key = f"{kind}:{outcome}"
    _PROMOTION_OUTCOME_COUNTERS[key] = _PROMOTION_OUTCOME_COUNTERS.get(key, 0) + 1


def _record_promote_outcome(outcome: str) -> None:
    _bump_outcome_counter("promote", outcome)
    try:
        record_external_audit_promote_outcome(outcome)
    except Exception:
        logger.debug("Promote outcome metric skipped", exc_info=True)


def _record_uvdb_sync_outcome(outcome: str) -> None:
    """Record UVDB sync outcome as a distinct counter + OTel promote tag uvdb_sync:<outcome>."""
    _bump_outcome_counter("uvdb_sync", outcome)
    try:
        record_external_audit_promote_outcome(f"uvdb_sync:{outcome}")
    except Exception:
        logger.debug("UVDB sync outcome metric skipped", exc_info=True)


class PromotionResult(TypedDict):
    promoted_findings: list[int]
    document_clause_ids: set[str]
    failed_drafts: list[dict[str, object]]


class ExternalAuditPromotionService:
    """Materialize accepted drafts, sync specialist schemes, and build proof matrices."""

    def __init__(self, host: "ExternalAuditImportService") -> None:
        self.host = host

    @property
    def db(self):
        return self.host.db

    _ACTION_FINDING_TYPES = RISK_CREATING_FINDING_TYPES

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

    async def get_promotion_reconciliation(self, *, job_id: int, tenant_id: int | None) -> dict[str, object]:
        job = await self.host.get_job(job_id=job_id, tenant_id=tenant_id)
        effective_tenant_id = job.tenant_id or tenant_id
        run = await self.host._get_run(audit_run_id=job.audit_run_id, tenant_id=effective_tenant_id)
        drafts = await self.host.list_job_drafts(job_id=job_id, tenant_id=effective_tenant_id)
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

    async def _finalize_promotion_pipeline(
        self,
        *,
        job: ExternalAuditImportJob,
        run: AuditRun,
        drafts: list[ExternalAuditDraft],
        accepted: list[ExternalAuditDraft],
        user_id: int,
        resolved_tenant_id: int,
    ) -> ExternalAuditImportJob:
        """Materialize drafts, link evidence, scheme sync, reconciliation, and persist job summary."""
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
                async with self.db.begin_nested():
                    await self.host._link_source_document_evidence(
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
            async with self.db.begin_nested():
                scheme_alignment = await self.host._sync_scheme_records(
                    job=job,
                    run=run,
                    tenant_id=resolved_tenant_id,
                    drafts=reconciled_drafts,
                )
            self._emit_uvdb_sync_metric(job=job, run=run, scheme_alignment=scheme_alignment)
        except Exception as sync_exc:
            logger.warning("Scheme record sync failed (non-fatal): %s", sync_exc, exc_info=True)
            scheme_alignment = {"status": "sync_failed", "error": str(sync_exc)[:200]}
            if self._is_uvdb_scheme(job, run):
                _record_uvdb_sync_outcome("failed")
            else:
                _record_uvdb_sync_outcome("n_a")

        # Surface Planet Mark sync outcome explicitly in promotion summary
        pm_sync = (scheme_alignment or {}).get("planet_mark_sync", {})
        if isinstance(pm_sync, dict) and pm_sync:
            pm_sync_status = str(pm_sync.get("status", "unknown"))
        elif (job.detected_scheme or "").lower() == "planet_mark":
            pm_sync_status = "sync_failed" if (scheme_alignment or {}).get("status") == "sync_failed" else "skipped"
        else:
            pm_sync_status = "not_applicable"

        reconciliation: dict[str, object] = {}
        try:
            async with self.db.begin_nested():
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
            "planet_mark_sync_status": pm_sync_status,
            "planet_mark_sync_detail": pm_sync if isinstance(pm_sync, dict) else {},
            "uvdb_sync_status": (
                str((scheme_alignment or {}).get("status") or "unknown")
                if self._is_uvdb_scheme(job, run)
                else "n_a"
            ),
            "uvdb_audit_id": (scheme_alignment or {}).get("uvdb_audit_id"),
        }
        await self.db.flush()
        await self.db.refresh(job)
        try:
            _record_promote_outcome("partial" if failed_drafts else "completed")
        except Exception:
            logger.debug("Promote outcome metric skipped", exc_info=True)
        return job

    async def promote_job(self, *, job_id: int, tenant_id: int | None, user_id: int) -> ExternalAuditImportJob:
        """Materialize accepted drafts into live findings, then scheme sync and reconciliation.

        **Idempotency / retries:** Drafts that already have ``promoted_finding_id`` are skipped.
        If promotion fails, the job returns to ``review_required``; fixing drafts and calling
        promote again is safe and does not duplicate findings for already-promoted rows.
        """
        job = await self.host.get_job(job_id=job_id, tenant_id=tenant_id)
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
            job = await self.host.get_job(job_id=job_id, tenant_id=effective_tenant_id)
            if job.status == ExternalAuditImportStatus.COMPLETED:
                return job
            if job.status == ExternalAuditImportStatus.PROMOTING:
                raise ConflictError("Import job promotion is already in progress")
            raise ValidationError("Import job must be in review_required state before promotion")

        job = await self.host.get_job(job_id=job_id, tenant_id=effective_tenant_id)
        drafts = await self.host.list_job_drafts(job_id=job_id, tenant_id=effective_tenant_id)
        accepted = [draft for draft in drafts if draft.status == ExternalAuditDraftStatus.ACCEPTED]
        if not accepted:
            job.status = ExternalAuditImportStatus.REVIEW_REQUIRED
            job.updated_by_id = user_id
            await self.db.flush()
            raise ValidationError("At least one draft must be accepted before promotion")

        run = await self.host._get_run(audit_run_id=job.audit_run_id, tenant_id=effective_tenant_id)
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
            job = await self._finalize_promotion_pipeline(
                job=job,
                run=run,
                drafts=drafts,
                accepted=accepted,
                user_id=user_id,
                resolved_tenant_id=resolved_tenant_id,
            )
        except ValidationError as exc:
            logger.warning(
                "Promotion validation failure for job %s: %s",
                job_id,
                exc.message,
                extra={"draft_count": len(exc.details.get("failed_drafts", [])) if exc.details else 0},
            )
            try:
                _record_promote_outcome("all_failed")
            except Exception:
                logger.debug("Promote outcome metric skipped", exc_info=True)
            try:
                await self._recover_job_after_promotion_failure(job_id=job_id, user_id=user_id, exc=exc)
            except Exception as cleanup_exc:
                logger.warning("Could not persist promotion error for job %s: %s", job_id, cleanup_exc)
            raise
        except Exception as exc:
            logger.error("Promotion failed for job %s: %s", job_id, exc, exc_info=True)
            try:
                _record_promote_outcome("error")
            except Exception:
                logger.debug("Promote outcome metric skipped", exc_info=True)
            try:
                await self._recover_job_after_promotion_failure(job_id=job_id, user_id=user_id, exc=exc)
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

    async def _recover_job_after_promotion_failure(
        self,
        *,
        job_id: int,
        user_id: int,
        exc: BaseException,
    ) -> None:
        """Rollback, return job to review_required, and persist a short warning for operators."""
        await self.db.rollback()
        job_reload = await self.db.execute(select(ExternalAuditImportJob).where(ExternalAuditImportJob.id == job_id))
        job_row = job_reload.scalar_one_or_none()
        if job_row is None:
            return
        job_row.status = ExternalAuditImportStatus.REVIEW_REQUIRED
        job_row.updated_by_id = user_id
        existing_warnings = list(job_row.processing_warnings_json or [])
        existing_warnings.append(f"Promotion failed: {str(exc)[:300]}")
        job_row.processing_warnings_json = existing_warnings
        await self.db.flush()
        await self.db.commit()

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
                    requires_action = draft.finding_type in self._ACTION_FINDING_TYPES
                    normalized_severity = (draft.severity or "medium").strip().lower()
                    finding_data: dict = {
                        "title": draft.title,
                        "description": draft.description,
                        "severity": normalized_severity,
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
                    finding_id = await self.host._resolve_persisted_finding_id(
                        finding_id=getattr(finding, "id", None), tenant_id=draft_tid
                    )
                    await self.host._link_evidence_for_finding(
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
                logger.error(
                    "Failed to promote draft id=%s error_type=%s: %s",
                    draft.id,
                    type(exc).__name__,
                    exc,
                    exc_info=True,
                )
                draft.status = ExternalAuditDraftStatus.DRAFT
                existing_notes = draft.review_notes or ""
                draft.review_notes = f"{existing_notes}\n\nPromotion failed: {str(exc)[:200]}".strip()
                failed_drafts.append(
                    {
                        "draft_id": draft.id,
                        "title": draft.title,
                        "finding_type": draft.finding_type,
                        "severity": draft.severity,
                        "error": str(exc)[:300],
                        "error_type": type(exc).__name__,
                    }
                )

        if failed_drafts and not promoted_findings:
            first = failed_drafts[0]
            raise ValidationError(
                f"All {len(failed_drafts)} accepted draft(s) failed to materialize into live findings. "
                f"First draft id={first.get('draft_id')}: {first.get('error', 'unknown error')}",
                details={
                    "failed_total": len(failed_drafts),
                    "failed_drafts": failed_drafts[:20],
                },
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

    def _build_promotion_summary(self, *, findings: list) -> dict[str, object]:
        action_candidates = sum(
            1 for finding in findings if getattr(finding, "finding_type", "") in self._ACTION_FINDING_TYPES
        )
        risk_candidates = sum(1 for finding in findings if should_create_risk(finding))
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
        job = await self.host.get_job(job_id=job_id, tenant_id=tenant_id)
        drafts = await self.host.list_job_drafts(job_id=job_id, tenant_id=tenant_id)
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

        # Run Planet Mark domain sync (idempotent) regardless of whether the
        # ExternalAuditRecord already exists, so that re-promotion always
        # re-hydrates the Planet Mark domain tables.
        pm_sync_result: dict[str, object] = {}
        if self._is_planet_mark_scheme(job):
            pm_sync_result = await self._sync_planet_mark(
                job=job,
                run=run,
                tenant_id=tenant_id,
            )

        if existing is not None:
            logger.info(
                "ExternalAuditRecord for job %s already exists — updating PM linkage fields",
                job.id,
            )
            # Patch in the PM carbon year linkage so the frontend can display scope summaries
            pm_data_ex = (job.provenance_json or {}).get("planet_mark_carbon") or {}
            if pm_sync_result.get("year_id"):
                existing.carbon_reporting_year_id = pm_sync_result["year_id"]  # type: ignore[assignment]
            if pm_data_ex.get("scope_1_co2e_tonnes") is not None:
                existing.scope_1_co2e = pm_data_ex["scope_1_co2e_tonnes"]  # type: ignore[assignment]
            if pm_data_ex.get("scope_2_co2e_tonnes") is not None:
                existing.scope_2_co2e = pm_data_ex["scope_2_co2e_tonnes"]  # type: ignore[assignment]
            if pm_data_ex.get("scope_3_co2e_tonnes") is not None:
                existing.scope_3_co2e = pm_data_ex["scope_3_co2e_tonnes"]  # type: ignore[assignment]
            await self.db.flush()

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
                "planet_mark_sync": pm_sync_result,
                "home_route": home_route,
                "home_label": home_label,
            }

        # Extract carbon scope values for the record if available
        pm_data = (job.provenance_json or {}).get("planet_mark_carbon") or {}
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
            # Planet Mark specific fields
            carbon_reporting_year_id=pm_sync_result.get("year_id"),  # type: ignore[arg-type]
            scope_1_co2e=pm_data.get("scope_1_co2e_tonnes"),  # type: ignore[arg-type]
            scope_2_co2e=pm_data.get("scope_2_co2e_tonnes"),  # type: ignore[arg-type]
            scope_3_co2e=pm_data.get("scope_3_co2e_tonnes"),  # type: ignore[arg-type]
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
            "planet_mark_sync": pm_sync_result,
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

    def _emit_uvdb_sync_metric(
        self,
        *,
        job: ExternalAuditImportJob,
        run: AuditRun,
        scheme_alignment: dict[str, object] | None,
    ) -> None:
        """Make UVDB sync outcomes observable (counter + OTel), not log-only."""
        if not self._is_uvdb_scheme(job, run):
            _record_uvdb_sync_outcome("n_a")
            return
        alignment = scheme_alignment or {}
        status = str(alignment.get("status") or "")
        uvdb_audit_id = alignment.get("uvdb_audit_id")
        if status == "sync_failed":
            _record_uvdb_sync_outcome("failed")
        elif status == "already_synced":
            _record_uvdb_sync_outcome("already_synced" if uvdb_audit_id else "missing")
        elif status == "synced" and uvdb_audit_id:
            _record_uvdb_sync_outcome("synced")
        elif uvdb_audit_id:
            _record_uvdb_sync_outcome("ok")
        else:
            _record_uvdb_sync_outcome("missing")

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

    @staticmethod
    def _is_planet_mark_scheme(job: ExternalAuditImportJob) -> bool:
        """Return True when the import job is a Planet Mark certification report."""
        detected = (job.detected_scheme or "").strip().lower()
        if detected == "planet_mark":
            return True
        provenance = job.provenance_json or {}
        declared_info = provenance.get("declared_vs_detected", {})
        if isinstance(declared_info, dict):
            declared = str(declared_info.get("declared_assurance_scheme", "")).lower()
            if "planet mark" in declared or "planet_mark" in declared:
                return True
        return False

    # Certification status mapping: Planet Mark language → internal enum
    _PM_OUTCOME_TO_CERT_STATUS: dict[str, str] = {
        "certified": "certified",
        "in_progress": "submitted",
        "not_certified": "draft",
    }

    async def _sync_planet_mark(
        self,
        *,
        job: ExternalAuditImportJob,
        run: AuditRun,
        tenant_id: int | None,
    ) -> dict[str, object]:
        """Sync extracted Planet Mark carbon data into the Planet Mark domain tables.

        Creates or updates a CarbonReportingYear and related EmissionSource /
        ImprovementAction records.  All writes run inside the caller's transaction
        so a failure rolls back the whole Planet Mark sync block.

        Returns a result dict with sync metadata; never raises (returns
        {"status": "no_carbon_data"} when provenance contains no carbon fields).
        """
        import re as _re

        pm_data: dict = (job.provenance_json or {}).get("planet_mark_carbon") or {}

        has_any_emission = any(
            pm_data.get(k) is not None
            for k in ("scope_1_co2e_tonnes", "scope_2_co2e_tonnes", "scope_3_co2e_tonnes", "total_co2e_tonnes")
        )
        if not has_any_emission:
            logger.info("Planet Mark sync skipped for job %s — no carbon data extracted", job.id)
            return {"status": "no_carbon_data"}

        raw_label = pm_data.get("reporting_year_label") or job.scheme_version or ""
        year_label = str(raw_label).strip() or "Imported"
        yr_num_match = _re.search(r"(\d{4})", year_label)
        year_number = int(yr_num_match.group(1)) if yr_num_match else datetime.utcnow().year
        if not _re.search(r"^YE\d{4}$", year_label):
            year_label = f"YE{year_number}"

        year, created_year = await self._resolve_or_create_pm_year(
            pm_data=pm_data,
            year_label=year_label,
            year_number=year_number,
            tenant_id=tenant_id,
            run=run,
        )
        sources_created = await self._sync_pm_emission_sources(pm_data=pm_data, year=year, job=job, tenant_id=tenant_id)
        actions_created = await self._sync_pm_improvement_actions(
            pm_data=pm_data, year=year, job=job, tenant_id=tenant_id
        )

        await PlanetMarkService.recalculate_year_totals(self.db, year)
        await self.db.flush()

        logger.info(
            "Planet Mark sync complete: job=%s year_id=%s created_year=%s sources=%s actions=%s",
            job.id,
            year.id,
            created_year,
            sources_created,
            actions_created,
        )
        return {
            "status": "synced",
            "year_id": year.id,
            "year_label": year_label,
            "created_year": created_year,
            "sources_created": sources_created,
            "actions_created": actions_created,
        }

    @staticmethod
    def _parse_naive_date(s: object) -> datetime | None:
        if not s:
            return None
        try:
            return datetime.strptime(str(s), "%Y-%m-%d")
        except ValueError:
            return None

    async def _resolve_or_create_pm_year(
        self,
        *,
        pm_data: dict,
        year_label: str,
        year_number: int,
        tenant_id: int | None,
        run: AuditRun,
    ) -> tuple[CarbonReportingYear, bool]:
        """Return (CarbonReportingYear, created_new) — idempotent."""
        period_start = self._parse_naive_date(pm_data.get("period_start")) or datetime(year_number, 1, 1)
        period_end = self._parse_naive_date(pm_data.get("period_end")) or datetime(year_number, 12, 31)
        cert_date = self._parse_naive_date(pm_data.get("certification_date"))
        expiry_date = self._parse_naive_date(pm_data.get("expiry_date"))
        fte = pm_data.get("fte_count") or 0
        cert_num = pm_data.get("certification_number")
        raw_outcome = str(pm_data.get("outcome_status") or "").lower()
        cert_status = self._PM_OUTCOME_TO_CERT_STATUS.get(raw_outcome, "draft")

        existing = (
            await self.db.execute(
                select(CarbonReportingYear).where(
                    CarbonReportingYear.tenant_id == tenant_id,
                    CarbonReportingYear.year_label == year_label,
                )
            )
        ).scalar_one_or_none()

        if existing is None:
            existing = (
                await self.db.execute(
                    select(CarbonReportingYear).where(
                        CarbonReportingYear.tenant_id == tenant_id,
                        CarbonReportingYear.year_number == year_number,
                    )
                )
            ).scalar_one_or_none()

        if existing is None:
            year = CarbonReportingYear(  # type: ignore[misc]
                tenant_id=tenant_id,
                year_label=year_label,
                year_number=year_number,
                period_start=period_start,
                period_end=period_end,
                average_fte=float(fte) if fte else 0.0,
                organization_name=run.title or "Imported Organisation",
                certification_status=cert_status,
                certificate_number=cert_num,
                certification_date=cert_date,
                expiry_date=expiry_date,
            )
            self.db.add(year)
            await self.db.flush()
            for cat in SCOPE3_CATEGORIES:
                self.db.add(
                    Scope3CategoryData(  # type: ignore[misc]
                        reporting_year_id=year.id,
                        tenant_id=tenant_id,
                        category_number=cat["number"],
                        category_name=cat["name"],
                        category_description=cat["description"],
                        is_relevant=True,
                        is_measured=False,
                    )
                )
            logger.info("Planet Mark sync: created CarbonReportingYear id=%s label=%s", year.id, year_label)
            return year, True

        # Always overwrite with imported values — the import is the authoritative source
        if cert_status and cert_status != "draft":
            existing.certification_status = cert_status
        if cert_date:
            existing.certification_date = cert_date
        if expiry_date:
            existing.expiry_date = expiry_date
        if cert_num:
            existing.certificate_number = cert_num
        if fte:
            existing.average_fte = float(fte)
        if period_start:
            existing.period_start = period_start
        if period_end:
            existing.period_end = period_end
        logger.info("Planet Mark sync: updating existing CarbonReportingYear id=%s", existing.id)
        return existing, False

    async def _sync_pm_emission_sources(
        self,
        *,
        pm_data: dict,
        year: CarbonReportingYear,
        job: ExternalAuditImportJob,
        tenant_id: int | None,
    ) -> int:
        """Create aggregate EmissionSource records for each scope; return count."""
        scope_map = {
            "scope_1": ("scope_1_co2e_tonnes", "Scope 1 — Direct Emissions (Imported)"),
            "scope_2": ("scope_2_co2e_tonnes", "Scope 2 — Indirect Energy (Imported)"),
            "scope_3": ("scope_3_co2e_tonnes", "Scope 3 — Value Chain (Imported)"),
        }
        sources_created = 0
        for scope_key, (data_key, source_name) in scope_map.items():
            co2e = pm_data.get(data_key)
            if co2e is None or float(co2e) <= 0:
                continue
            for old_agg in (
                (
                    await self.db.execute(
                        select(EmissionSource).where(
                            EmissionSource.reporting_year_id == year.id,
                            EmissionSource.scope == scope_key,
                            EmissionSource.is_imported_aggregate == True,  # noqa: E712
                            EmissionSource.source_import_job_id == job.id,
                        )
                    )
                )
                .scalars()
                .all()
            ):
                await self.db.delete(old_agg)

            has_real = (
                await self.db.execute(
                    select(EmissionSource).where(
                        EmissionSource.reporting_year_id == year.id,
                        EmissionSource.scope == scope_key,
                        EmissionSource.is_imported_aggregate == False,  # noqa: E712
                    )
                )
            ).scalars().first() is not None

            if not has_real:
                self.db.add(
                    EmissionSource(  # type: ignore[misc]
                        tenant_id=tenant_id,
                        reporting_year_id=year.id,
                        source_name=source_name,
                        source_category="imported",
                        scope=scope_key,
                        activity_type="imported_aggregate",
                        activity_value=float(co2e),
                        activity_unit="tCO2e",
                        emission_factor=1.0,
                        emission_factor_unit="tCO2e",
                        emission_factor_source="Planet Mark Import",
                        co2e_tonnes=float(co2e),
                        data_quality_level="estimated",
                        data_quality_score=2,
                        is_imported_aggregate=True,
                        source_import_job_id=job.id,
                        data_notes=(
                            f"Auto-imported from Planet Mark audit report (job id={job.id}). "
                            "Replace with per-source data for full detail."
                        ),
                    )
                )
                sources_created += 1

        dq_1_2 = pm_data.get("data_quality_scope_1_2")
        dq_3 = pm_data.get("data_quality_scope_3")
        if dq_1_2 is not None:
            year.scope_1_data_quality = min(int(dq_1_2), 16)
            year.scope_2_data_quality = min(int(dq_1_2), 16)
        if dq_3 is not None:
            year.scope_3_data_quality = min(int(dq_3), 16)

        # Populate scope_2_location_based as well as market-based when available
        scope_2_loc = pm_data.get("scope_2_location_co2e_tonnes") or pm_data.get("scope_2_co2e_tonnes")
        if scope_2_loc is not None:
            year.scope_2_location = float(scope_2_loc)

        # Populate Scope 3 aggregate into the "Other/Unattributed" category (category 15)
        # so that the Scope 3 breakdown tab is non-empty even for aggregate imports
        scope_3_total = pm_data.get("scope_3_co2e_tonnes")
        if scope_3_total is not None and float(scope_3_total) > 0:
            other_cat = (
                await self.db.execute(
                    select(Scope3CategoryData).where(
                        Scope3CategoryData.reporting_year_id == year.id,
                        Scope3CategoryData.category_number == 15,
                    )
                )
            ).scalar_one_or_none()
            if other_cat is not None:
                other_cat.total_co2e = float(scope_3_total)
                other_cat.is_measured = True
                other_cat.calculation_method = "spend_based"
                other_cat.category_description = (
                    "Aggregate Scope 3 from Planet Mark import. " "Break down by category to improve data quality."
                )
            else:
                self.db.add(
                    Scope3CategoryData(  # type: ignore[misc]
                        reporting_year_id=year.id,
                        tenant_id=year.tenant_id,
                        category_number=15,
                        category_name="Other (Unattributed Scope 3)",
                        category_description=(
                            "Aggregate Scope 3 from Planet Mark import. "
                            "Break down by category to improve data quality."
                        ),
                        is_relevant=True,
                        is_measured=True,
                        total_co2e=float(scope_3_total),
                        calculation_method="spend_based",
                    )
                )

        await self.db.flush()
        return sources_created

    async def _sync_pm_improvement_actions(
        self,
        *,
        pm_data: dict,
        year: CarbonReportingYear,
        job: ExternalAuditImportJob,
        tenant_id: int | None,
    ) -> int:
        """Create ImprovementAction records from PM data or job summary; return count."""
        raw_actions: list = pm_data.get("improvement_actions") or []
        if not raw_actions and job.improvement_summary_json:
            raw_actions = [
                {"title": item.get("title", "Improvement action"), "target_scope": None, "deadline": None}
                for item in (job.improvement_summary_json or [])[:20]
                if isinstance(item, dict) and item.get("title")
            ]

        actions_created = 0
        for action_data in raw_actions[:20]:
            if not isinstance(action_data, dict):
                continue
            title = str(action_data.get("title", "")).strip()[:300]
            if not title:
                continue

            dup = (
                await self.db.execute(
                    select(PlanetMarkImprovementAction).where(
                        PlanetMarkImprovementAction.reporting_year_id == year.id,
                        PlanetMarkImprovementAction.action_title == title,
                    )
                )
            ).scalar_one_or_none()
            if dup is not None:
                continue

            count = (
                await self.db.execute(
                    select(func.count())
                    .select_from(PlanetMarkImprovementAction)
                    .where(PlanetMarkImprovementAction.reporting_year_id == year.id)
                )
            ).scalar_one()
            action_id = f"IMP-{(count + 1):03d}"

            time_bound: datetime | None = None
            deadline_str = action_data.get("deadline")
            if deadline_str:
                for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y"):
                    try:
                        time_bound = datetime.strptime(str(deadline_str), fmt)
                        break
                    except ValueError:
                        continue
            if time_bound is None:
                # Default to end of current year if no deadline extracted
                time_bound = datetime(year.year_number + 1, 12, 31) if year.year_number else datetime(2026, 12, 31)

            specific_text = (
                str(action_data.get("specific") or action_data.get("description") or title).strip()[:2000] or title
            )
            measurable_text = str(action_data.get("measurable") or action_data.get("metric") or "").strip()[:2000]
            if not measurable_text:
                reduction_pct = action_data.get("expected_reduction_pct")
                measurable_text = (
                    f"Achieve {reduction_pct}% reduction in targeted emissions"
                    if reduction_pct
                    else "Reduction to be quantified"
                )

            self.db.add(
                PlanetMarkImprovementAction(  # type: ignore[misc]
                    tenant_id=tenant_id,
                    reporting_year_id=year.id,
                    action_id=action_id,
                    action_title=title,
                    specific=specific_text,
                    measurable=measurable_text,
                    target_scope=action_data.get("target_scope"),
                    status="planned",
                    progress_percent=0,
                    source_import_job_id=job.id,
                    expected_reduction_pct=action_data.get("expected_reduction_pct"),
                    time_bound=time_bound,
                    achievable_owner=str(action_data.get("owner") or "To be assigned")[:255],
                    relevant=str(action_data.get("relevant") or "").strip()[:2000] or None,
                    scheduled_month=None,
                )
            )
            actions_created += 1

        await self.db.flush()
        return actions_created


__all__ = ["PromotionResult", "ExternalAuditPromotionService"]
