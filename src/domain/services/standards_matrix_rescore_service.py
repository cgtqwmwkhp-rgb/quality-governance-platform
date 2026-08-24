"""Re-score machine-confirmed document CEL rows after a 5064 matrix import.

Wave 3 PR-E3: when an alignment edition becomes active, existing auto-confirmed
document evidence is re-run through :func:`standards_ingest_gate.evaluate`. Rows
that no longer qualify are demoted to ``proposed`` (Exceptions inbox). Human
confirmer stamps are preserved. Proposed rows are never auto-promoted.

Does not import ``standards_requirement_axis``. Does not flip TrapGuard
``covers_framework``. Does not call cell-aggregate ``get_cell`` / ``get_matrix``.
No Alembic.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.compliance_evidence import ComplianceEvidenceLink, EvidenceLinkMethod, EvidenceLinkStatus
from src.domain.models.governed_knowledge import AiDecisionLog
from src.domain.services.standards_exceptions_gate_reason import (
    EVIDENCE_MAP_ACTION,
    EVIDENCE_MAP_LOG_ENTITY_TYPE,
    evidence_map_log_key,
)
from src.domain.services.standards_ingest_gate import AutoConfirmDecision, StandardsAutoConfirmContext, evaluate

logger = logging.getLogger(__name__)

#: Honest cap so a huge tenant cannot silently skip the rest of the scan.
RESCORE_SCAN_CAP = 5000

RESCORE_TRIGGER = "matrix_import"


def _method_value(linked_by: Any) -> str:
    if linked_by is None:
        return ""
    return str(getattr(linked_by, "value", linked_by)).strip().lower()


def _status_value(status: Any) -> Optional[str]:
    if status is None:
        return None
    return str(getattr(status, "value", status)).strip().lower()


def is_human_confirmed(link: Any) -> bool:
    """D15: a human stamp or a MANUAL link is not the machine path."""
    if getattr(link, "confirmed_by_id", None) is not None:
        return True
    return _method_value(getattr(link, "linked_by", None)) == EvidenceLinkMethod.MANUAL.value


def classify_rescore_target(link: Any) -> str:
    """Return ``human``, ``machine_confirmed``, or ``skip``.

    ``skip`` includes proposed / rejected / needs_review / non-document rows so
    this pass can never auto-promote.
    """
    entity = str(getattr(link, "entity_type", "") or "").strip().lower()
    if entity != "document":
        return "skip"
    if getattr(link, "deleted_at", None) is not None:
        return "skip"
    if is_human_confirmed(link):
        return "human"
    status = _status_value(getattr(link, "status", None))
    auto_applied = bool(getattr(link, "auto_applied", False))
    if status == EvidenceLinkStatus.CONFIRMED.value or auto_applied:
        return "machine_confirmed"
    return "skip"


def apply_demotion(link: Any) -> None:
    """Fail-closed write: machine confirmation is withdrawn. Human stamps untouched."""
    link.status = EvidenceLinkStatus.PROPOSED
    link.auto_applied = False


@dataclass
class RescoreSummary:
    scanned: int = 0
    demoted: int = 0
    kept: int = 0
    preserved_human: int = 0
    skipped: int = 0
    truncated: bool = False
    demotions: list[tuple[Any, AutoConfirmDecision, str]] = field(default_factory=list, repr=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            "scanned": self.scanned,
            "demoted": self.demoted,
            "kept_confirmed": self.kept,
            "preserved_human": self.preserved_human,
            "skipped": self.skipped,
            "truncated": self.truncated,
        }


def rescore_loaded_links(
    links: Sequence[Any],
    *,
    context: Optional[StandardsAutoConfirmContext],
    doc_types: Optional[dict[str, Optional[str]]] = None,
) -> RescoreSummary:
    """Re-evaluate loaded CEL rows. Mutates demoted links in place.

    ``context is None`` is fail-closed (same as ingest): every machine-confirmed
    row demotes. Callers that forgot to load the new edition must not keep stale
    auto-confirms.
    """
    types = doc_types or {}
    summary = RescoreSummary()
    for link in links:
        target = classify_rescore_target(link)
        if target == "skip":
            summary.skipped += 1
            continue
        if target == "human":
            summary.preserved_human += 1
            continue
        summary.scanned += 1
        decision = evaluate(
            confidence=getattr(link, "confidence", None),
            doc_type=types.get(str(getattr(link, "entity_id", "") or "")),
            clause_id=str(getattr(link, "clause_id", "") or ""),
            entity_type="document",
            context=context,
        )
        if decision.auto_confirm:
            summary.kept += 1
            continue
        previous = _previous_status(link)
        apply_demotion(link)
        summary.demoted += 1
        summary.demotions.append((link, decision, previous))
    return summary


def _document_type_value(raw: Any) -> Optional[str]:
    if raw is None:
        return None
    value = getattr(raw, "value", raw)
    text = str(value or "").strip()
    return text or None


async def _doc_types_for_links(
    db: AsyncSession,
    *,
    tenant_id: int,
    links: Sequence[ComplianceEvidenceLink],
) -> dict[str, Optional[str]]:
    """Look up ``documents.document_type`` for numeric entity ids. Missing → omit."""
    ids: list[int] = []
    for link in links:
        try:
            ids.append(int(str(link.entity_id)))
        except (TypeError, ValueError):
            continue
    if not ids:
        return {}
    from src.domain.models.document import Document

    result = await db.execute(
        select(Document.id, Document.document_type).where(
            Document.tenant_id == tenant_id,
            Document.id.in_(ids),
        )
    )
    out: dict[str, Optional[str]] = {}
    for doc_id, document_type in result.all():
        out[str(doc_id)] = _document_type_value(document_type)
    return out


def _previous_status(link: Any) -> str:
    status = _status_value(getattr(link, "status", None))
    if status:
        return status
    if bool(getattr(link, "auto_applied", False)):
        return EvidenceLinkStatus.CONFIRMED.value
    return EvidenceLinkStatus.PROPOSED.value


async def rescore_document_links_after_matrix_change(
    db: AsyncSession,
    *,
    tenant_id: int,
    matrix_version_id: Optional[int] = None,
    matrix_version_label: Optional[str] = None,
    cap: int = RESCORE_SCAN_CAP,
) -> RescoreSummary:
    """Scan live document CEL for this tenant and demote stale machine confirms."""
    context = await StandardsAutoConfirmContext.for_tenant(db, tenant_id)
    result = await db.execute(
        select(ComplianceEvidenceLink)
        .where(
            ComplianceEvidenceLink.tenant_id == tenant_id,
            ComplianceEvidenceLink.deleted_at.is_(None),
            ComplianceEvidenceLink.entity_type == "document",
        )
        .order_by(ComplianceEvidenceLink.id.asc())
        .limit(cap + 1)
    )
    links = list(result.scalars().all())
    truncated = len(links) > cap
    links = links[:cap]
    doc_types = await _doc_types_for_links(db, tenant_id=tenant_id, links=links)
    summary = rescore_loaded_links(links, context=context, doc_types=doc_types)
    summary.truncated = truncated

    for link, decision, previous in summary.demotions:
        # Status already proposed after apply_demotion; log the withdrawn confirm.
        db.add(
            AiDecisionLog(
                tenant_id=tenant_id,
                action=EVIDENCE_MAP_ACTION,
                entity_type=EVIDENCE_MAP_LOG_ENTITY_TYPE,
                entity_id=evidence_map_log_key(link.entity_type, link.entity_id, link.clause_id),
                confidence=link.confidence,
                auto_applied=False,
                payload={
                    "gate_reason": decision.reason,
                    "gate_auto_confirm": False,
                    "rescore": True,
                    "rescore_trigger": RESCORE_TRIGGER,
                    "previous_status": previous,
                    "status": EvidenceLinkStatus.PROPOSED.value,
                    "source_entity_type": link.entity_type,
                    "matrix_version_id": matrix_version_id,
                    "matrix_version_label": matrix_version_label,
                },
            )
        )

    if truncated:
        logger.warning(
            "standards matrix rescore truncated: tenant=%s scanned_cap=%s demoted=%s",
            tenant_id,
            cap,
            summary.demoted,
        )
    else:
        logger.info(
            "standards matrix rescore: tenant=%s scanned=%s demoted=%s kept=%s human=%s skipped=%s version=%s",
            tenant_id,
            summary.scanned,
            summary.demoted,
            summary.kept,
            summary.preserved_human,
            summary.skipped,
            matrix_version_label,
        )
    return summary


async def maybe_rescore_after_apply(
    db: AsyncSession,
    *,
    tenant_id: int,
    created: bool,
    reactivated: bool,
    matrix_version_id: int,
    matrix_version_label: str,
) -> Optional[RescoreSummary]:
    """Run only when the live edition actually changed. Same-checksum apply is a no-op."""
    if not (created or reactivated):
        return None
    return await rescore_document_links_after_matrix_change(
        db,
        tenant_id=tenant_id,
        matrix_version_id=matrix_version_id,
        matrix_version_label=matrix_version_label,
    )
