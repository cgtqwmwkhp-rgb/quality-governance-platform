"""Exceptions inbox gate-reason triage (Wave 3 PR-E2).

PR-E writes ``payload.gate_reason`` onto ``ai_decision_logs`` for
``action=evidence_map``. The inbox previously dropped that, so operators
could not triage the fail-closed flood. This module attaches the latest
logged reason onto CEL rows without a schema change.

Does not import ``standards_requirement_axis``. Does not touch TrapGuard.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable, Optional, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.compliance_evidence import ComplianceEvidenceLink
from src.domain.models.governed_knowledge import AiDecisionLog

# Reasons PR-E's ``evaluate()`` actually emits. Unknown query values 400.
INGEST_GATE_REASONS = frozenset(
    {
        "below_threshold",
        "matrix_not_loaded",
        "strict_doc_type",
        "operational_entity",
        "force_proposed",
        "unparseable_clause",
        "alignment_unique",
        "alignment_different",
        "alignment_near_requires_addition",
        "alignment_not_exact_for_framework",
        "alignment_not_exact",
        "cover_blocked_open_nc",
        "cover_blocked_open_action",
        "auto_confirmed",
    }
)

EVIDENCE_MAP_ACTION = "evidence_map"
EVIDENCE_MAP_LOG_ENTITY_TYPE = "compliance_evidence_link"


def evidence_map_log_key(entity_type: str, entity_id: str, clause_id: str) -> str:
    """Match ``GovernedKnowledgeService._persist_mapping`` decision-log identity."""
    return f"{entity_type}:{entity_id}:{clause_id}"


def gate_reason_from_payload(payload: Any) -> Optional[str]:
    """Return a non-empty logged reason, or None. Never invent a token."""
    if not isinstance(payload, dict):
        return None
    raw = payload.get("gate_reason")
    if not isinstance(raw, str):
        return None
    reason = raw.strip()
    return reason or None


def latest_gate_reasons_by_log_key(logs: Iterable[AiDecisionLog]) -> dict[str, str]:
    """First-seen wins. Callers must pass logs newest-first (id desc)."""
    out: dict[str, str] = {}
    for log in logs:
        key = getattr(log, "entity_id", None)
        if not isinstance(key, str) or not key or key in out:
            continue
        reason = gate_reason_from_payload(getattr(log, "payload", None))
        if reason:
            out[key] = reason
    return out


def is_known_ingest_gate_reason(raw: Optional[str]) -> bool:
    if not raw:
        return False
    return raw.strip() in INGEST_GATE_REASONS


def filter_links_by_gate_reason(
    links: Sequence[ComplianceEvidenceLink],
    reasons: dict[int, Optional[str]],
    wanted: str,
) -> list[ComplianceEvidenceLink]:
    """Keep rows whose attached reason equals ``wanted``. Missing reason excluded."""
    return [link for link in links if reasons.get(link.id) == wanted]


def sort_inbox_page_for_triage(
    links: Sequence[ComplianceEvidenceLink],
) -> list[ComplianceEvidenceLink]:
    """Within the existing ≤200 page: confidence DESC, then created_at DESC.

    Null confidence sorts last so near-threshold proposals surface first.
    """

    def _key(link: ComplianceEvidenceLink) -> tuple[bool, float, float]:
        conf = getattr(link, "confidence", None)
        created = getattr(link, "created_at", None)
        ts = created.timestamp() if isinstance(created, datetime) else 0.0
        missing = conf is None
        conf_rank = -float(conf) if conf is not None else 0.0
        return (missing, conf_rank, -ts)

    return sorted(links, key=_key)


async def gate_reasons_for_links(
    db: AsyncSession,
    *,
    tenant_id: int,
    links: Sequence[ComplianceEvidenceLink],
) -> dict[int, Optional[str]]:
    """Latest evidence_map gate_reason per CEL id. Missing log → None."""
    if not links:
        return {}
    keys = {evidence_map_log_key(link.entity_type, link.entity_id, link.clause_id) for link in links}
    result = await db.execute(
        select(AiDecisionLog)
        .where(
            AiDecisionLog.tenant_id == tenant_id,
            AiDecisionLog.action == EVIDENCE_MAP_ACTION,
            AiDecisionLog.entity_type == EVIDENCE_MAP_LOG_ENTITY_TYPE,
            AiDecisionLog.entity_id.in_(keys),
        )
        .order_by(AiDecisionLog.id.desc())
    )
    latest = latest_gate_reasons_by_log_key(result.scalars().all())
    return {
        link.id: latest.get(evidence_map_log_key(link.entity_type, link.entity_id, link.clause_id)) for link in links
    }
