"""TrapGuard: refuse to share evidence across a clause number that only looks shared.

Wave 2 PR-C. The trap this guards is stated on sheet 07 of PEL-HSEQ-5064: five
standards use clause number 6.1.2 for five entirely different requirements. An
aspects and impacts register does not identify hazards; a hazard identification
does not perform a business impact analysis. Reading across the *number* is how an
integrated management system fails an audit.

Why the guard is needed here specifically
-----------------------------------------
:mod:`src.domain.services.standards_cell_aggregate_service` matches stored clause
tokens onto matrix cells deliberately tolerantly, so that a link written as
``iso9001:7.5``, ``9001-7.5`` or ``Clause 7.5`` all find the ISO 9001 7.5 cell.
That tolerance includes a suffix rule, and the suffix rule is framework-blind: a
link recorded against ``14001-9.1.2`` (evaluation of compliance) also matches the
ISO 9001 9.1.2 cell (customer satisfaction), which shares the number and nothing
else. Left alone, the aggregate would paint ISO 9001 9.1.2 as covered on the
strength of an environmental compliance record. That is not a display bug — it is
the matrix inventing coverage that does not exist.

So the guard is applied where the match is decided, not where it is displayed.

What it does not do
-------------------
It does not create, delete or rewrite evidence links, and it does not change any
verdict computation. It answers one question — *may these two clauses share
evidence?* — from imported alignment edges, and drops matches that would answer it
wrongly. When no matrix edition has been imported it permits everything and says
so, because a guard with no data must not silently blank a working matrix.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any, Iterable, Optional, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.standards_alignment import (
    SHAREABLE_VERDICTS,
    VERDICT_RESTRICTIVENESS,
    AlignmentEdge,
    AlignmentVerdict,
    MatrixVersion,
    MatrixVersionStatus,
    canonical_alignment_pair,
)

logger = logging.getLogger(__name__)

#: Framework ids that may prefix a stored clause token. Kept here rather than
#: imported from ``standards_cell_aggregate_service`` so the dependency runs one
#: way only (the aggregate imports this module). A unit test asserts this matches
#: the aggregate's ``FRAMEWORK_ALIASES`` keys exactly.
ALIGNMENT_FRAMEWORK_IDS: tuple[str, ...] = (
    "9001",
    "14001",
    "45001",
    "27001",
    "22301",
    # Cyber Essentials / Cyber Essentials Plus (NCSC scheme).
    "ce",
    "cep",
    "iip",
    "pm",
    "chas",
    "ssip",
    "uvdb",
)

#: ``iso9001:7.5`` and ``9001-7.5`` name the same framework.
_ISO_PREFIX = re.compile(r"^iso[\s_]?(\d{4,5})$")

_RESTRICTIVENESS_RANK: dict[AlignmentVerdict, int] = {
    verdict: rank for rank, verdict in enumerate(VERDICT_RESTRICTIVENESS)
}


def framework_from_clause_token(token: Any) -> Optional[str]:
    """The framework a stored clause token declares, or None if it names none.

    ``"14001-9.1.2"`` → ``"14001"``; ``"iso9001:7.5"`` → ``"9001"``;
    ``"7.5"`` → ``None`` (a bare clause number commits to no framework, so it
    cannot be cross-framework and is never blocked).
    """
    if token is None:
        return None
    text = str(token).strip().lower()
    if not text:
        return None
    for separator in ("-", ":", "/"):
        if separator not in text:
            continue
        head = text.split(separator, 1)[0].strip()
        if not head:
            continue
        if head in ALIGNMENT_FRAMEWORK_IDS:
            return head
        iso_match = _ISO_PREFIX.match(head)
        if iso_match and iso_match.group(1) in ALIGNMENT_FRAMEWORK_IDS:
            return iso_match.group(1)
    return None


def clause_number_from_token(token: Any) -> str:
    """The clause part of a stored token, with any framework prefix removed."""
    text = str(token or "").strip().lower()
    if not text:
        return ""
    for separator in ("-", ":", "/"):
        if separator in text:
            head, tail = text.split(separator, 1)
            if head in ALIGNMENT_FRAMEWORK_IDS or _ISO_PREFIX.match(head):
                return tail.strip()
    return text


def clause_key(framework: str, clause_number: str) -> str:
    """Catalogue-shaped key, matching ``clauses.catalogue_key`` ("9001-7.2")."""
    return f"{(framework or '').strip().lower()}-{str(clause_number or '').strip()}"


@dataclass(frozen=True)
class ShareDecision:
    """Whether two clauses may share one piece of evidence, and on what terms."""

    allowed: bool
    verdict: Optional[AlignmentVerdict]
    reason: str
    #: The addition a NEAR verdict requires the shared deliverable to carry.
    addition_text: Optional[str] = None
    clause_ref: Optional[str] = None

    @property
    def verdict_token(self) -> Optional[str]:
        return self.verdict.api_value if self.verdict else None

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "verdict": self.verdict_token,
            "reason": self.reason,
            "addition_text": self.addition_text,
            "clause_ref": self.clause_ref,
        }


class TrapGuard:
    """Answers alignment questions from one tenant's active matrix edition.

    Built by :meth:`for_tenant`, which loads the active edition once. Instances are
    read-only snapshots — hold one for the duration of a request, not across
    requests, so a re-import is picked up on the next call.
    """

    def __init__(
        self,
        *,
        edges: Sequence[AlignmentEdge] = (),
        version: Optional[MatrixVersion] = None,
    ):
        self._version = version
        self._pairs: dict[tuple[str, str, str, str], AlignmentEdge] = {}
        self._unique: dict[tuple[str, str], AlignmentEdge] = {}
        self._rows: dict[str, AlignmentEdge] = {}

        for edge in edges:
            verdict = _verdict_of(edge)
            if edge.dst_framework is None or edge.dst_clause_key is None:
                self._unique[(edge.src_framework, edge.src_clause_key)] = edge
            else:
                key = (
                    edge.src_framework,
                    edge.src_clause_key,
                    edge.dst_framework,
                    edge.dst_clause_key,
                )
                self._pairs[key] = edge
            # Row verdict for display: keep the most restrictive verdict seen on
            # the row, which is what a reader needs warning about.
            current = self._rows.get(edge.clause_ref)
            if current is None or _RESTRICTIVENESS_RANK[verdict] < _RESTRICTIVENESS_RANK[_verdict_of(current)]:
                self._rows[edge.clause_ref] = edge

    # ------------------------------------------------------------------ loading

    @classmethod
    async def for_tenant(cls, db: AsyncSession, tenant_id: int, *, source_ref: Optional[str] = None) -> "TrapGuard":
        """Load the active matrix edition for a tenant. Empty guard when none."""
        version_query = select(MatrixVersion).where(
            MatrixVersion.tenant_id == tenant_id,
            MatrixVersion.status == MatrixVersionStatus.ACTIVE,
            MatrixVersion.deleted_at.is_(None),
        )
        if source_ref:
            version_query = version_query.where(MatrixVersion.source_ref == source_ref)
        version_query = version_query.order_by(MatrixVersion.id.desc())
        version = (await db.execute(version_query)).scalars().first()
        if version is None:
            return cls()

        edges = (
            (
                await db.execute(
                    select(AlignmentEdge).where(
                        AlignmentEdge.tenant_id == tenant_id,
                        AlignmentEdge.matrix_version_id == version.id,
                        AlignmentEdge.deleted_at.is_(None),
                    )
                )
            )
            .scalars()
            .all()
        )
        return cls(edges=list(edges), version=version)

    # ----------------------------------------------------------------- querying

    @property
    def is_loaded(self) -> bool:
        """False when no matrix edition is active, so the guard has no opinion."""
        return self._version is not None

    @property
    def version_label(self) -> Optional[str]:
        if self._version is None:
            return None
        return f"{self._version.source_ref} v{self._version.version_label}"

    @property
    def version_id(self) -> Optional[int]:
        """Active matrix edition id, or None when no edition is loaded."""
        if self._version is None:
            return None
        return getattr(self._version, "id", None)

    @property
    def edge_count(self) -> int:
        return len(self._pairs) + len(self._unique)

    def edge_for(
        self,
        src_framework: str,
        src_clause: str,
        dst_framework: str,
        dst_clause: str,
    ) -> Optional[AlignmentEdge]:
        """The stored edge for one unordered clause pair, if the matrix has one."""
        src_fw, src_key, dst_fw, dst_key = canonical_alignment_pair(
            src_framework,
            clause_key(src_framework, src_clause),
            dst_framework,
            clause_key(dst_framework, dst_clause),
        )
        if dst_fw is None or dst_key is None:
            return None
        return self._pairs.get((src_fw, src_key, dst_fw, dst_key))

    def unique_edge_for(self, framework: str, clause_number: str) -> Optional[AlignmentEdge]:
        """The UNIQUE edge for a clause, if the matrix says only one framework asks."""
        return self._unique.get(((framework or "").strip().lower(), clause_key(framework, clause_number)))

    def row_verdict(self, clause_ref: str) -> Optional[AlignmentVerdict]:
        """The most restrictive verdict on a printed matrix row, for display."""
        edge = self._rows.get(str(clause_ref).strip())
        return _verdict_of(edge) if edge is not None else None

    def _row_verdict_for_refs(self, clause_refs: Iterable[str]) -> Optional[AlignmentVerdict]:
        """Most restrictive row verdict across the printed rows these refs name.

        A cell is addressed by its framework-local clause number, which is not always
        the printed ``clause_ref`` ``_rows`` is keyed by (e.g. ISO 45001 puts 6.3 at
        8.1.3). Resolving through the edges that actually touched the cell keeps the
        warning on the row the clause is really on.
        """
        best: Optional[AlignmentVerdict] = None
        for clause_ref in clause_refs:
            candidate = self.row_verdict(clause_ref)
            if candidate is None:
                continue
            if best is None or _RESTRICTIVENESS_RANK[candidate] < _RESTRICTIVENESS_RANK[best]:
                best = candidate
        return best

    def may_share_evidence(
        self,
        *,
        src_framework: str,
        src_clause: str,
        dst_framework: str,
        dst_clause: str,
    ) -> ShareDecision:
        """May one piece of evidence serve both clauses?

        The default when the matrix says nothing is *permit*: this guard narrows
        an existing tolerant match, and a guard with no data must not blank a
        working matrix. Every refusal is therefore backed by an imported verdict.
        """
        src_fw = (src_framework or "").strip().lower()
        dst_fw = (dst_framework or "").strip().lower()

        if src_fw == dst_fw and str(src_clause).strip() == str(dst_clause).strip():
            return ShareDecision(True, None, "same clause")

        if not self.is_loaded:
            return ShareDecision(
                True,
                None,
                "no alignment matrix imported — no alignment opinion available",
            )

        edge = self.edge_for(src_fw, src_clause, dst_fw, dst_clause)
        if edge is not None:
            verdict = _verdict_of(edge)
            if verdict in SHAREABLE_VERDICTS:
                return ShareDecision(
                    True,
                    verdict,
                    (
                        "EXACT: one deliverable satisfies both"
                        if verdict is AlignmentVerdict.EXACT
                        else "NEAR: one deliverable works only if it carries the addition"
                    ),
                    addition_text=edge.addition_text,
                    clause_ref=edge.clause_ref,
                )
            return ShareDecision(
                False,
                verdict,
                (
                    f"{verdict.api_value}: clause {edge.clause_ref} is shared by number "
                    "only — the requirement and the evidence differ"
                ),
                addition_text=edge.addition_text,
                clause_ref=edge.clause_ref,
            )

        # No pair edge. A UNIQUE clause has no counterpart at all, so a
        # cross-framework claim against it is exactly the trap.
        unique = self.unique_edge_for(src_fw, src_clause) or self.unique_edge_for(dst_fw, dst_clause)
        if unique is not None:
            return ShareDecision(
                False,
                AlignmentVerdict.UNIQUE,
                (
                    f"UNIQUE: clause {unique.clause_ref} is asked for by "
                    f"{unique.src_framework} only, so no other framework's evidence "
                    "can serve it"
                ),
                clause_ref=unique.clause_ref,
            )

        return ShareDecision(
            True,
            None,
            "matrix has no verdict for this pair — not treated as aligned or as a trap",
        )

    # ------------------------------------------------------- aggregate guarding

    def filter_cross_framework_tokens(
        self,
        *,
        framework: str,
        clause_number: str,
        tokens: Iterable[Any],
    ) -> tuple[list[Any], list[dict[str, Any]]]:
        """Split matched clause tokens into kept and blocked-by-trap.

        A token that names no framework is always kept: a bare ``7.5`` commits to
        nothing, so it cannot be a cross-framework claim. A token naming *this*
        framework is always kept. Only a token naming a different framework is
        tested against the matrix, and only a DIFFERENT or UNIQUE verdict blocks it.
        """
        kept: list[Any] = []
        blocked: list[dict[str, Any]] = []
        if not self.is_loaded:
            return list(tokens), blocked

        cell_fw = (framework or "").strip().lower()
        for token in tokens:
            token_fw = framework_from_clause_token(token)
            if token_fw is None or token_fw == cell_fw:
                kept.append(token)
                continue
            decision = self.may_share_evidence(
                src_framework=token_fw,
                src_clause=clause_number_from_token(token) or clause_number,
                dst_framework=cell_fw,
                dst_clause=clause_number,
            )
            if decision.allowed:
                kept.append(token)
                continue
            blocked.append(
                {
                    "token": str(token),
                    "token_framework": token_fw,
                    "verdict": decision.verdict_token,
                    "reason": decision.reason,
                    "clause_ref": decision.clause_ref,
                }
            )
        return kept, blocked

    def annotate_cell(self, *, framework: str, clause_number: str) -> dict[str, Any]:
        """Alignment context for one matrix cell, for the shell and hover preview."""
        cell_fw = (framework or "").strip().lower()
        clause = str(clause_number or "").strip()
        unique = self.unique_edge_for(cell_fw, clause)

        peers: list[dict[str, Any]] = []
        matched_refs: set[str] = set()
        target_key = clause_key(cell_fw, clause)
        for (src_fw, src_key, dst_fw, dst_key), edge in self._pairs.items():
            if (src_fw, src_key) == (cell_fw, target_key):
                peer_fw, peer_key = dst_fw, dst_key
            elif (dst_fw, dst_key) == (cell_fw, target_key):
                peer_fw, peer_key = src_fw, src_key
            else:
                continue
            verdict = _verdict_of(edge)
            matched_refs.add(edge.clause_ref)
            peers.append(
                {
                    "framework": peer_fw,
                    "clause_key": peer_key,
                    "verdict": verdict.api_value,
                    "shareable": verdict in SHAREABLE_VERDICTS,
                    "addition_text": edge.addition_text,
                }
            )
        peers.sort(key=lambda item: (item["framework"], item["clause_key"]))

        if unique is not None:
            matched_refs.add(unique.clause_ref)

        row_verdict = self._row_verdict_for_refs(matched_refs)
        if row_verdict is None:
            # No edge touched this cell: fall back to the printed reference, which
            # is all an un-relocated clause ever needed.
            row_verdict = self.row_verdict(clause)
        trap_peers = [peer for peer in peers if not peer["shareable"]]
        return {
            "matrix_version": self.version_label,
            "matrix_loaded": self.is_loaded,
            "row_verdict": row_verdict.api_value if row_verdict else None,
            "is_trap_row": bool(trap_peers) or unique is not None,
            "is_unique": unique is not None,
            "unique_reason": unique.rationale if unique is not None else None,
            "peers": peers,
            "trap_peer_count": len(trap_peers),
        }


def _verdict_of(edge: AlignmentEdge) -> AlignmentVerdict:
    value = edge.verdict
    if isinstance(value, AlignmentVerdict):
        return value
    return AlignmentVerdict(str(value).strip().lower())
