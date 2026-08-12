"""Standards ingest auto-confirm gate (Wave 3 PR-E slice 1).

Machine confirmation of document→clause evidence links requires **all** of:

* confidence ≥ :data:`STANDARDS_AUTO_CONFIRM_THRESHOLD` (0.98)
* an imported alignment matrix that carries an **EXACT** row verdict for the clause
* the target cell is not cover-blocked (open NC **or** open action)

Fail-closed: if no matrix is loaded, nothing auto-confirms. TrapGuard's own
default with an empty matrix is *permit* (correct for display narrowing); this
gate's job is different — EXACT is a positive requirement.

Open findings/actions are loaded **without** the cell-aggregate ``limit(500)``
cap so a truncated read cannot miss an open NC and wrongly confirm. That makes
this gate one-directionally stricter than ``get_cell`` on huge tenants.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.audit import AuditFinding
from src.domain.models.capa import CAPAAction
from src.domain.services.standards_cell_aggregate_service import (
    OPEN_ACTION_STATUSES,
    OPEN_FINDING_STATUSES,
    any_token_matches,
    clause_match_keys,
    is_nc_finding,
    status_value,
    survives_trap_guard,
)
from src.domain.services.standards_trap_guard import TrapGuard, clause_number_from_token, framework_from_clause_token

logger = logging.getLogger(__name__)

#: Standards ingest machine-confirm threshold. Deliberately separate from
#: ``governed_knowledge_service.AUTO_CONFIRM_THRESHOLD`` (0.85), which
#: ``regulatory_watch_service`` still imports for CAPA auto-create.
STANDARDS_AUTO_CONFIRM_THRESHOLD = 0.98

STRICT_DOC_TYPES = frozenset({"rams", "coshh", "msds", "sds", "ram", "method_statement"})


@dataclass(frozen=True)
class AutoConfirmDecision:
    """One clause's gate outcome."""

    auto_confirm: bool
    reason: str
    confidence: float
    framework: Optional[str] = None
    clause_number: Optional[str] = None
    row_verdict: Optional[str] = None


@dataclass
class CoverBlockIndex:
    """In-memory open-NC / open-action index for one tenant snapshot.

    Built once per job (or once per map-evidence request). Answers whether a
    cell is cover-blocked without issuing ``get_cell`` per clause.
    """

    guard: TrapGuard
    #: (kind, tokens, status) for open NC findings / open actions.
    _open_nc_tokens: list[tuple[list[Any], str]] = field(default_factory=list)
    _open_action_tokens: list[tuple[list[Any], str]] = field(default_factory=list)

    @classmethod
    async def for_tenant(cls, db: AsyncSession, tenant_id: int, *, guard: TrapGuard) -> "CoverBlockIndex":
        index = cls(guard=guard)

        findings = (
            (
                await db.execute(
                    select(AuditFinding).where(AuditFinding.tenant_id == tenant_id).order_by(AuditFinding.id.desc())
                )
            )
            .scalars()
            .all()
        )
        for finding in findings:
            if status_value(finding.status) not in OPEN_FINDING_STATUSES:
                continue
            if not is_nc_finding(getattr(finding, "finding_type", None)):
                continue
            tokens = list(finding.clause_ids_json_legacy or [])
            if tokens:
                index._open_nc_tokens.append((tokens, status_value(finding.status)))

        actions = (
            (
                await db.execute(
                    select(CAPAAction).where(CAPAAction.tenant_id == tenant_id).order_by(CAPAAction.id.desc())
                )
            )
            .scalars()
            .all()
        )
        for action in actions:
            if status_value(action.status) not in OPEN_ACTION_STATUSES:
                continue
            ref = action.clause_reference
            iso = action.iso_standard
            action_tokens: list[str] = []
            if ref:
                action_tokens.extend(part.strip() for part in str(ref).replace(";", ",").split(",") if part.strip())
            if iso and ref:
                action_tokens.append(f"{iso}-{ref}")
            if action_tokens:
                index._open_action_tokens.append((action_tokens, status_value(action.status)))

        return index

    def blocked_for(self, framework: str, clause_number: str) -> Optional[str]:
        """Return a cover-block reason token, or None when the cell is clear."""
        fw = (framework or "").strip().lower()
        clause = str(clause_number or "").strip()
        keys = clause_match_keys(fw, clause)
        blocked: list[dict[str, Any]] = []

        for tokens, _status in self._open_nc_tokens:
            if not any_token_matches(tokens, keys, clause):
                continue
            if not survives_trap_guard(
                guard=self.guard,
                framework=fw,
                clause_number=clause,
                tokens=tokens,
                keys=keys,
                blocked=blocked,
                source="finding",
                record={},
            ):
                continue
            return "cover_blocked_open_nc"

        for tokens, _status in self._open_action_tokens:
            if not any_token_matches(tokens, keys, clause):
                continue
            if not survives_trap_guard(
                guard=self.guard,
                framework=fw,
                clause_number=clause,
                tokens=tokens,
                keys=keys,
                blocked=blocked,
                source="action",
                record={},
            ):
                continue
            return "cover_blocked_open_action"

        return None


@dataclass
class StandardsAutoConfirmContext:
    """Per-tenant snapshot reused across every clause in one mapping pass."""

    guard: TrapGuard
    cover: CoverBlockIndex

    @classmethod
    async def for_tenant(cls, db: AsyncSession, tenant_id: int) -> "StandardsAutoConfirmContext":
        guard = await TrapGuard.for_tenant(db, tenant_id)
        cover = await CoverBlockIndex.for_tenant(db, tenant_id, guard=guard)
        return cls(guard=guard, cover=cover)

    @property
    def matrix_loaded(self) -> bool:
        return self.guard.is_loaded

    @property
    def matrix_version(self) -> Optional[str]:
        return self.guard.version_label


def _normalize_confidence(confidence: Optional[float]) -> float:
    if confidence is None:
        return 0.0
    if confidence > 1.0:
        return confidence / 100.0
    return float(confidence)


def evaluate(
    *,
    confidence: Optional[float],
    doc_type: Optional[str],
    clause_id: str,
    entity_type: str = "document",
    force_proposed: bool = False,
    context: Optional[StandardsAutoConfirmContext] = None,
) -> AutoConfirmDecision:
    """Decide whether a mapping may machine-confirm.

    ``context is None`` is fail-closed (never auto-confirm) so a caller that
    forgets to build the gate cannot accidentally restore the old 0.85 path.
    """
    norm = _normalize_confidence(confidence)
    fw = framework_from_clause_token(clause_id)
    clause_number = clause_number_from_token(clause_id)

    if force_proposed or entity_type != "document":
        return AutoConfirmDecision(
            auto_confirm=False,
            reason="operational_entity" if entity_type != "document" else "force_proposed",
            confidence=norm,
            framework=fw,
            clause_number=clause_number,
        )

    doc_normalized = (doc_type or "").lower().replace("-", "_").replace(" ", "_")
    if doc_normalized in STRICT_DOC_TYPES:
        return AutoConfirmDecision(
            auto_confirm=False,
            reason="strict_doc_type",
            confidence=norm,
            framework=fw,
            clause_number=clause_number,
        )

    if norm < STANDARDS_AUTO_CONFIRM_THRESHOLD:
        return AutoConfirmDecision(
            auto_confirm=False,
            reason="below_threshold",
            confidence=norm,
            framework=fw,
            clause_number=clause_number,
        )

    if context is None or not context.matrix_loaded:
        return AutoConfirmDecision(
            auto_confirm=False,
            reason="matrix_not_loaded",
            confidence=norm,
            framework=fw,
            clause_number=clause_number,
        )

    if not fw or not clause_number:
        return AutoConfirmDecision(
            auto_confirm=False,
            reason="unparseable_clause",
            confidence=norm,
            framework=fw,
            clause_number=clause_number,
        )

    annotation = context.guard.annotate_cell(framework=fw, clause_number=clause_number)
    row_verdict = annotation.get("row_verdict")
    if annotation.get("is_unique"):
        return AutoConfirmDecision(
            auto_confirm=False,
            reason="alignment_unique",
            confidence=norm,
            framework=fw,
            clause_number=clause_number,
            row_verdict=row_verdict,
        )
    if row_verdict == "DIFFERENT":
        return AutoConfirmDecision(
            auto_confirm=False,
            reason="alignment_different",
            confidence=norm,
            framework=fw,
            clause_number=clause_number,
            row_verdict=row_verdict,
        )
    if row_verdict == "NEAR":
        return AutoConfirmDecision(
            auto_confirm=False,
            reason="alignment_near_requires_addition",
            confidence=norm,
            framework=fw,
            clause_number=clause_number,
            row_verdict=row_verdict,
        )
    if row_verdict != "EXACT":
        # No printed row / unknown clause — not EXACT.
        return AutoConfirmDecision(
            auto_confirm=False,
            reason="alignment_not_exact",
            confidence=norm,
            framework=fw,
            clause_number=clause_number,
            row_verdict=row_verdict,
        )

    block_reason = context.cover.blocked_for(fw, clause_number)
    if block_reason:
        return AutoConfirmDecision(
            auto_confirm=False,
            reason=block_reason,
            confidence=norm,
            framework=fw,
            clause_number=clause_number,
            row_verdict=row_verdict,
        )

    return AutoConfirmDecision(
        auto_confirm=True,
        reason="auto_confirmed",
        confidence=norm,
        framework=fw,
        clause_number=clause_number,
        row_verdict=row_verdict,
    )
