"""EXACT shared-apply for Standards matrix cells (Wave 2 PR-D slice 1).

One deliverable that already covers a source clause may be linked onto every
EXACT peer column from the imported PEL-HSEQ-5064 matrix — create-only, with a
scoped soft-delete undo.

NEAR peers are not EXACT. ISO NEAR proposed-share lives in
:class:`NearShareService` (AP-07): same cover gates, never auto-confirm.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.exceptions import BadRequestError, ConflictError, NotFoundError
from src.domain.models.compliance_evidence import (
    ComplianceEvidenceLink,
    EvidenceCoverKind,
    EvidenceLinkMethod,
    EvidenceLinkStatus,
)
from src.domain.services.compliance_evidence_link_writer import (
    create_evidence_links_if_absent,
    soft_delete_evidence_link,
)
from src.domain.services.iso_compliance_service import counts_toward_compliance_coverage
from src.domain.services.standards_cell_aggregate_service import (
    StandardsCellAggregateService,
    clause_match_keys,
    token_matches_clause,
)
from src.domain.services.standards_tech_gap_guard import assess as tech_gap_assess
from src.domain.services.standards_trap_guard import clause_number_from_token

logger = logging.getLogger(__name__)


@dataclass
class ExactSharePlan:
    """Preflight payload merged into ``GET /cell-aggregate`` as ``exact_share``."""

    available: bool
    unavailable_reason: Optional[str] = None
    matrix_version: Optional[str] = None
    matrix_version_id: Optional[int] = None
    source: dict[str, Any] = field(default_factory=dict)
    candidates: list[dict[str, Any]] = field(default_factory=list)
    shareable_links: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "available": self.available,
            "unavailable_reason": self.unavailable_reason,
            "matrix_version": self.matrix_version,
            "matrix_version_id": self.matrix_version_id,
            "source": self.source,
            "candidates": self.candidates,
            "shareable_links": self.shareable_links,
        }


class ExactShareService:
    """Plan / apply / undo EXACT evidence sharing across aligned matrix columns."""

    share_verdict = "EXACT"
    share_label = "EXACT"
    unavailable_no_peers = "no_exact_peers"
    not_peer_reason = "not_exact_peer"
    conflict_prefix = "EXACT_SHARE"

    def __init__(
        self,
        db: AsyncSession,
        *,
        aggregate: Optional[StandardsCellAggregateService] = None,
    ):
        self.db = db
        self.aggregate = aggregate or StandardsCellAggregateService(db)

    def _select_peers(self, annotation: dict[str, Any], *, source_framework: str) -> list[dict[str, Any]]:
        """EXACT peers only. ``source_framework`` is reserved for NEAR ISO-family filtering."""
        if not source_framework:
            return []
        return [
            peer
            for peer in annotation.get("peers") or []
            if str(peer.get("verdict") or "").upper() == self.share_verdict
        ]

    def _share_notes(
        self,
        source_link: ComplianceEvidenceLink,
        resolved: Sequence[dict[str, Any]],
    ) -> Optional[str]:
        """Notes copied onto created peer rows. NEAR overrides this to name the addition."""
        del resolved
        return source_link.notes

    async def plan(
        self,
        *,
        tenant_id: int,
        framework: str,
        clause_number: str,
        source_cell: Optional[Any] = None,
    ) -> ExactSharePlan:
        """Build the EXACT-share preflight for one source cell.

        ``source_cell`` may be a pre-fetched :class:`CellAggregateResult` so the
        route can reuse the cell it already loaded. Candidates still call
        ``get_cell`` once each (bounded by EXACT peer count).
        """
        fw = framework.strip().lower()
        clause = clause_number.strip()
        guard = await self.aggregate.trap_guard(tenant_id)

        if source_cell is None:
            source_cell = await self.aggregate.get_cell(tenant_id=tenant_id, framework=fw, clause_number=clause)

        source_payload = {
            "framework": fw,
            "clause_number": clause,
            "clause_key": f"{fw}-{clause}",
            "cover_blocked": bool(source_cell.cover_blocked),
        }

        if not guard.is_loaded:
            return ExactSharePlan(
                available=False,
                unavailable_reason="matrix_not_loaded",
                source=source_payload,
            )

        annotation = guard.annotate_cell(framework=fw, clause_number=clause)
        peers = self._select_peers(annotation, source_framework=fw)
        if not peers:
            return ExactSharePlan(
                available=False,
                unavailable_reason=self.unavailable_no_peers,
                matrix_version=guard.version_label,
                matrix_version_id=guard.version_id,
                source=source_payload,
            )

        if source_cell.cover_blocked:
            return ExactSharePlan(
                available=False,
                unavailable_reason="source_cover_blocked",
                matrix_version=guard.version_label,
                matrix_version_id=guard.version_id,
                source=source_payload,
                candidates=await self._candidate_rows(tenant_id=tenant_id, peers=peers, entity_type=None),
            )

        conformance = [
            e
            for e in (source_cell.evidence or [])
            if counts_toward_compliance_coverage(e.get("signal_type"), e.get("status"))
        ]
        if not conformance:
            return ExactSharePlan(
                available=False,
                unavailable_reason="no_conformance_evidence",
                matrix_version=guard.version_label,
                matrix_version_id=guard.version_id,
                source=source_payload,
                candidates=await self._candidate_rows(tenant_id=tenant_id, peers=peers, entity_type=None),
            )

        # Prefer the first conformance link's entity type for tech-gap warnings.
        entity_type = str(conformance[0].get("entity_type") or "") or None
        candidates = await self._candidate_rows(tenant_id=tenant_id, peers=peers, entity_type=entity_type)

        shareable_links = await self._shareable_links(
            tenant_id=tenant_id,
            framework=fw,
            clause_number=clause,
            evidence_rows=conformance,
            candidates=candidates,
        )

        eligible = any(c.get("eligible") for c in candidates)
        return ExactSharePlan(
            available=eligible and bool(shareable_links),
            unavailable_reason=None,
            matrix_version=guard.version_label,
            matrix_version_id=guard.version_id,
            source=source_payload,
            candidates=candidates,
            shareable_links=shareable_links,
        )

    async def apply(
        self,
        *,
        tenant_id: int,
        actor_id: Optional[int],
        actor_email: Optional[str],
        source_link_id: int,
        source_framework: str,
        source_clause: str,
        target_frameworks: Sequence[str],
        matrix_version_id: int,
    ) -> dict[str, Any]:
        """Create CEL rows on requested peers for one source link.

        Status is always PROPOSED with auto_applied=True so coverage stays
        honest until an operator confirms (Exceptions inbox). Never CONFIRMED.
        """
        fw = source_framework.strip().lower()
        clause = source_clause.strip()
        targets = sorted({str(t).strip().lower() for t in target_frameworks if str(t).strip()})
        if not targets:
            raise BadRequestError("target_frameworks must name at least one framework")

        guard = await self.aggregate.trap_guard(tenant_id)
        self._assert_matrix_version(guard, matrix_version_id=matrix_version_id)

        source_link = await self._require_shareable_source_link(
            tenant_id=tenant_id,
            source_link_id=source_link_id,
            framework=fw,
            clause_number=clause,
        )

        source_cell = await self.aggregate.get_cell(tenant_id=tenant_id, framework=fw, clause_number=clause)
        if source_cell.cover_blocked:
            raise ConflictError(
                f"{self.share_label} share refused: source cell is cover-blocked",
                code=f"{self.conflict_prefix}_SOURCE_BLOCKED",
                details={"cover_blocked": True},
            )

        annotation = guard.annotate_cell(framework=fw, clause_number=clause)
        peers_by_fw = {
            str(peer["framework"]).strip().lower(): peer for peer in self._select_peers(annotation, source_framework=fw)
        }
        resolved, warnings = await self._resolve_apply_targets(
            tenant_id=tenant_id,
            targets=targets,
            peers_by_fw=peers_by_fw,
            source_entity_type=source_link.entity_type,
        )

        cover_kind = source_link.cover_kind
        if not isinstance(cover_kind, EvidenceCoverKind):
            cover_kind = EvidenceCoverKind(str(cover_kind))

        write = await create_evidence_links_if_absent(
            self.db,
            tenant_id=tenant_id,
            entity_type=source_link.entity_type,
            entity_id=source_link.entity_id,
            clause_ids=[row["clause_key"] for row in resolved],
            cover_kind=cover_kind,
            link_method=EvidenceLinkMethod.MANUAL,
            actor_id=actor_id,
            actor_email=actor_email,
            confidence=source_link.confidence,
            title=source_link.title,
            notes=self._share_notes(source_link, resolved),
            signal_type=source_link.signal_type,
            status=EvidenceLinkStatus.PROPOSED,
            auto_applied=True,
            commit=True,
        )
        return self._apply_response(
            guard_version_label=guard.version_label,
            resolved=resolved,
            write=write,
            warnings=warnings,
        )

    def _assert_matrix_version(self, guard: Any, *, matrix_version_id: int) -> None:
        if not guard.is_loaded:
            raise ConflictError(
                f"{self.share_label} share refused: alignment matrix is not loaded",
                code=f"{self.conflict_prefix}_MATRIX_NOT_LOADED",
            )
        if guard.version_id != matrix_version_id:
            raise ConflictError(
                f"{self.share_label} share refused: matrix edition changed since plan",
                code=f"{self.conflict_prefix}_MATRIX_VERSION_MISMATCH",
                details={
                    "expected_matrix_version_id": matrix_version_id,
                    "active_matrix_version_id": guard.version_id,
                },
            )

    async def _require_shareable_source_link(
        self,
        *,
        tenant_id: int,
        source_link_id: int,
        framework: str,
        clause_number: str,
    ) -> ComplianceEvidenceLink:
        source_link = await self._load_live_link(tenant_id=tenant_id, link_id=source_link_id)
        if source_link is None:
            raise NotFoundError("Source evidence link not found")

        keys = clause_match_keys(framework, clause_number)
        if not token_matches_clause(source_link.clause_id, keys, clause_number):
            raise BadRequestError("Source link does not belong to the requested cell")

        if not counts_toward_compliance_coverage(source_link.signal_type, getattr(source_link, "status", None)):
            raise ConflictError(
                f"{self.share_label} share refused: source link is not conformance evidence",
                code=f"{self.conflict_prefix}_NONCONFORMANCE_SIGNAL",
                details={"signal_type": source_link.signal_type},
            )
        return source_link

    async def _resolve_apply_targets(
        self,
        *,
        tenant_id: int,
        targets: Sequence[str],
        peers_by_fw: dict[str, dict[str, Any]],
        source_entity_type: str,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        blocked_targets: list[dict[str, Any]] = []
        resolved: list[dict[str, Any]] = []
        warnings: list[dict[str, Any]] = []

        for target_fw in targets:
            peer = peers_by_fw.get(target_fw)
            if peer is None:
                blocked_targets.append({"framework": target_fw, "blocked_reasons": [self.not_peer_reason]})
                continue
            peer_clause = self._peer_clause_number(target_fw, peer["clause_key"])
            target_cell = await self.aggregate.get_cell(
                tenant_id=tenant_id, framework=target_fw, clause_number=peer_clause
            )
            reasons = self._cover_block_reasons(target_cell)
            if reasons:
                blocked_targets.append({"framework": target_fw, "blocked_reasons": reasons})
                continue

            tech = tech_gap_assess(
                framework=target_fw,
                clause_number=peer_clause,
                entity_types=[source_entity_type],
            )
            if tech.is_technical and not tech.covered:
                warnings.append({"framework": target_fw, "code": "tech_gap_attestation_missing"})

            resolved.append(
                {
                    "framework": target_fw,
                    "clause_key": peer["clause_key"],
                    "clause_number": peer_clause,
                    "verdict": str(peer.get("verdict") or self.share_verdict).upper(),
                    "addition_text": peer.get("addition_text"),
                }
            )

        if blocked_targets:
            raise ConflictError(
                f"{self.share_label} share refused: {len(blocked_targets)} target(s) ineligible",
                code=f"{self.conflict_prefix}_TARGET_BLOCKED",
                details={"targets": blocked_targets},
            )
        if not resolved:
            raise BadRequestError(f"No eligible {self.share_label} targets to share onto")
        return resolved, warnings

    @staticmethod
    def _peer_clause_number(target_fw: str, clause_key: str) -> str:
        peer_clause = clause_number_from_token(clause_key) or str(clause_key)
        if peer_clause.startswith(f"{target_fw}-"):
            return peer_clause[len(target_fw) + 1 :]
        return peer_clause

    @staticmethod
    def _cover_block_reasons(target_cell: Any) -> list[str]:
        if not target_cell.cover_blocked:
            return []
        open_nc = int((target_cell.summary or {}).get("open_nc_count") or 0)
        open_action = int((target_cell.summary or {}).get("open_action_count") or 0)
        reasons: list[str] = []
        if open_nc > 0:
            reasons.append("target_open_nc")
        if open_action > 0:
            reasons.append("target_open_action")
        if not reasons:
            reasons.append("target_cover_blocked")
        return reasons

    def _apply_response(
        self,
        *,
        guard_version_label: Optional[str],
        resolved: Sequence[dict[str, Any]],
        write: Any,
        warnings: Sequence[dict[str, Any]],
    ) -> dict[str, Any]:
        created_by_clause = {link.clause_id: link for link in write.created}
        existing_by_clause = {link.clause_id: link for link in write.existing}
        created_rows: list[dict[str, Any]] = []
        already_rows: list[dict[str, Any]] = []
        for row in resolved:
            link = created_by_clause.get(row["clause_key"])
            if link is not None:
                created_rows.append(
                    {
                        "link_id": link.id,
                        "framework": row["framework"],
                        "clause_id": row["clause_key"],
                        "verdict": row.get("verdict") or self.share_verdict,
                    }
                )
                continue
            existing = existing_by_clause.get(row["clause_key"])
            already_rows.append(
                {
                    "link_id": existing.id if existing is not None else None,
                    "framework": row["framework"],
                    "clause_id": row["clause_key"],
                }
            )

        applied_at = datetime.now(timezone.utc)
        undo_ids = [row["link_id"] for row in created_rows if row.get("link_id") is not None]
        return {
            "status": "applied",
            "applied_at": applied_at.isoformat(),
            "matrix_version": guard_version_label,
            "created": created_rows,
            "already_linked": already_rows,
            "warnings": list(warnings),
            "undo": {"link_ids": undo_ids, "applied_at": applied_at.isoformat()},
            "sor_note": ("compliance_evidence_links is the only record — undo soft-deletes exactly these ids."),
        }

    async def undo(
        self,
        *,
        tenant_id: int,
        link_ids: Sequence[int],
        applied_at: datetime,
    ) -> dict[str, Any]:
        """Soft-delete links created by a prior apply, skipping modified rows."""
        ids = [int(i) for i in link_ids]
        if not ids:
            raise BadRequestError("link_ids must not be empty")

        if applied_at.tzinfo is None:
            applied_at = applied_at.replace(tzinfo=timezone.utc)

        deleted: list[int] = []
        skipped: list[dict[str, Any]] = []

        for link_id in ids:
            result = await self.db.execute(
                select(ComplianceEvidenceLink).where(
                    ComplianceEvidenceLink.id == link_id,
                    ComplianceEvidenceLink.deleted_at.is_(None),
                    ComplianceEvidenceLink.tenant_id == tenant_id,
                )
            )
            link = result.scalar_one_or_none()
            if link is None:
                skipped.append({"link_id": link_id, "reason": "not_found_or_other_tenant"})
                continue

            updated_at = link.updated_at
            if updated_at is not None:
                if updated_at.tzinfo is None:
                    updated_at = updated_at.replace(tzinfo=timezone.utc)
                # Allow a small clock skew / same-second create; refuse later edits.
                if updated_at > applied_at:
                    skipped.append({"link_id": link_id, "reason": "modified_since_apply"})
                    continue

            removed = await soft_delete_evidence_link(self.db, tenant_id=tenant_id, link_id=link_id, commit=False)
            if removed is None:
                skipped.append({"link_id": link_id, "reason": "not_found_or_other_tenant"})
            else:
                deleted.append(link_id)

        await self.db.commit()
        return {
            "status": "undone",
            "deleted": deleted,
            "skipped": skipped,
        }

    # ------------------------------------------------------------------ helpers

    async def _candidate_rows(
        self,
        *,
        tenant_id: int,
        peers: Sequence[dict[str, Any]],
        entity_type: Optional[str],
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for peer in peers:
            target_fw = str(peer["framework"]).strip().lower()
            peer_key = str(peer["clause_key"])
            peer_clause = clause_number_from_token(peer_key) or peer_key
            if peer_clause.startswith(f"{target_fw}-"):
                peer_clause = peer_clause[len(target_fw) + 1 :]

            cell = await self.aggregate.get_cell(tenant_id=tenant_id, framework=target_fw, clause_number=peer_clause)
            open_nc = int((cell.summary or {}).get("open_nc_count") or 0)
            open_action = int((cell.summary or {}).get("open_action_count") or 0)
            blocked_reasons: list[str] = []
            if cell.cover_blocked:
                if open_nc > 0:
                    blocked_reasons.append("target_open_nc")
                if open_action > 0:
                    blocked_reasons.append("target_open_action")
                if not blocked_reasons:
                    blocked_reasons.append("target_cover_blocked")

            tech_gap_warning = None
            if entity_type:
                tech = tech_gap_assess(
                    framework=target_fw,
                    clause_number=peer_clause,
                    entity_types=[entity_type],
                )
                if tech.is_technical and not tech.covered:
                    tech_gap_warning = "tech_gap_attestation_missing"

            rows.append(
                {
                    "framework": target_fw,
                    "clause_key": peer_key,
                    "clause_number": peer_clause,
                    "verdict": str(peer.get("verdict") or self.share_verdict).upper(),
                    "addition_text": peer.get("addition_text"),
                    "eligible": not blocked_reasons,
                    "blocked_reasons": blocked_reasons,
                    "open_nc_count": open_nc,
                    "open_action_count": open_action,
                    "tech_gap_warning": tech_gap_warning,
                }
            )
        rows.sort(key=lambda item: (item["framework"], item["clause_key"]))
        return rows

    async def _shareable_links(
        self,
        *,
        tenant_id: int,
        framework: str,
        clause_number: str,
        evidence_rows: Sequence[dict[str, Any]],
        candidates: Sequence[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Surface conformance links on the source cell and which peers already have them."""
        out: list[dict[str, Any]] = []
        for row in evidence_rows:
            link_id = row.get("id")
            if link_id is None:
                continue
            link = await self._load_live_link(tenant_id=tenant_id, link_id=int(link_id))
            if link is None:
                continue
            already: list[str] = []
            for candidate in candidates:
                existing = await self.db.execute(
                    select(ComplianceEvidenceLink.id).where(
                        ComplianceEvidenceLink.deleted_at.is_(None),
                        ComplianceEvidenceLink.tenant_id == tenant_id,
                        ComplianceEvidenceLink.entity_type == link.entity_type,
                        ComplianceEvidenceLink.entity_id == link.entity_id,
                        ComplianceEvidenceLink.clause_id == candidate["clause_key"],
                        ComplianceEvidenceLink.cover_kind == link.cover_kind,
                    )
                )
                if existing.scalar_one_or_none() is not None:
                    already.append(candidate["framework"])
            cover_kind = link.cover_kind
            cover_value = cover_kind.value if hasattr(cover_kind, "value") else str(cover_kind)
            out.append(
                {
                    "link_id": link.id,
                    "entity_type": link.entity_type,
                    "entity_id": link.entity_id,
                    "title": link.title,
                    "cover_kind": cover_value,
                    "already_shared_frameworks": already,
                }
            )
        return out

    async def _load_live_link(self, *, tenant_id: int, link_id: int) -> Optional[ComplianceEvidenceLink]:
        result = await self.db.execute(
            select(ComplianceEvidenceLink).where(
                ComplianceEvidenceLink.id == link_id,
                ComplianceEvidenceLink.deleted_at.is_(None),
                ComplianceEvidenceLink.tenant_id == tenant_id,
            )
        )
        return result.scalar_one_or_none()
