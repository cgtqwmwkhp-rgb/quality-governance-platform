"""Compliance Evidence Link (CEL) Entity360 producer — origin ``cel`` (X-3).

Emits clause-coverage hops for case / finding / risk subjects from live
``compliance_evidence_links`` rows. Documents are intentionally unsupported:
``entity_type='document'`` collides ``documents.id`` with ``evidence_assets.id``
on the audit-import path, so a document CEL hop would be a false conformance
claim. Training / induction subjects are deferred (UUID ids vs int hop contract).

Skipped entirely while ``entity_360_satellites`` is off.
"""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import select

from src.core.config import settings
from src.domain.models.compliance_evidence import ComplianceEvidenceLink, EvidenceLinkStatus, EvidenceSignalType
from src.domain.services.entity_360.types import ProducerResult, make_hop
from src.domain.services.href_registry import clause_evidence_href

_SUPPORTED = frozenset(
    {
        "incident",
        "near_miss",
        "rta",
        "complaint",
        "risk",
        "audit_finding",
    }
)

_RELATION_BY_SIGNAL = {
    EvidenceSignalType.EVIDENCE.value: "clause_evidence",
    EvidenceSignalType.NONCONFORMITY.value: "clause_nonconformity",
    EvidenceSignalType.GAP.value: "clause_gap",
    EvidenceSignalType.OPPORTUNITY.value: "clause_opportunity",
}


def _clamp_confidence(raw: Any) -> Optional[float]:
    """Drop out-of-range CEL confidence — hop schema enforces 0..1."""
    if raw is None:
        return None
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    if value < 0.0 or value > 1.0:
        return None
    return value


def _relation_for_signal(signal_type: Optional[str]) -> str:
    if signal_type is None:
        return "clause_evidence"
    key = str(signal_type).strip().lower()
    return _RELATION_BY_SIGNAL.get(key, "clause_evidence")


def _clause_title(clause_id: str) -> Optional[str]:
    try:
        from src.domain.services.iso_compliance_service import ISOComplianceService

        clause = ISOComplianceService().get_clause(clause_id)
    except Exception:  # noqa: BLE001 — catalogue lookup is best-effort
        return None
    if clause is None:
        return None
    return getattr(clause, "title", None)


class ComplianceEvidenceProducer:
    """CEL → evidence_link hops for satellite subjects (bidirectional lists)."""

    origin = "cel"

    def supports(self, entity_type: str) -> bool:
        return entity_type.strip().lower() in _SUPPORTED

    async def produce(
        self,
        *,
        db: Any,
        tenant_id: int,
        entity_type: str,
        entity_id: int,
        user: Any,
    ) -> ProducerResult:
        _ = user
        if not settings.entity_360_satellites_enabled:
            return ProducerResult(
                origin=self.origin,
                status="skipped",
                reason="entity_360_satellites disabled",
            )

        key = entity_type.strip().lower()
        if key not in _SUPPORTED:
            return ProducerResult(origin=self.origin, status="skipped", reason="unsupported")

        try:
            result = await db.execute(
                select(ComplianceEvidenceLink).where(
                    ComplianceEvidenceLink.tenant_id == tenant_id,
                    ComplianceEvidenceLink.entity_type == key,
                    ComplianceEvidenceLink.entity_id == str(entity_id),
                    ComplianceEvidenceLink.deleted_at.is_(None),
                    (
                        ComplianceEvidenceLink.status.is_(None)
                        | (ComplianceEvidenceLink.status != EvidenceLinkStatus.REJECTED)
                    ),
                )
            )
            links = list(result.scalars().all())
        except Exception as exc:  # noqa: BLE001 — producer isolation
            return ProducerResult(
                origin=self.origin,
                status="error",
                reason=f"cel: {exc}",
            )

        downstream: list[dict[str, Any]] = []
        for link in links:
            clause_id = str(link.clause_id or "").strip()
            if not clause_id:
                continue
            status_val = link.effective_status
            status_str = status_val.value if hasattr(status_val, "value") else str(status_val)
            title = link.title or _clause_title(clause_id)
            downstream.append(
                make_hop(
                    source_type="evidence_link",
                    source_id=int(link.id),
                    title=title,
                    reference=clause_id,
                    href=clause_evidence_href(clause_id),
                    direction="downstream",
                    relation=_relation_for_signal(
                        link.signal_type.value if hasattr(link.signal_type, "value") else link.signal_type
                    ),
                    depth=1,
                    origin="cel",
                    status=status_str,
                    confidence=_clamp_confidence(link.confidence),
                    edge_id=int(link.id),
                    version_pin=getattr(link, "document_version_id", None),
                )
            )

        return ProducerResult(
            origin=self.origin,
            status="ok",
            upstream=[],
            downstream=downstream,
        )


__all__ = ["ComplianceEvidenceProducer"]
