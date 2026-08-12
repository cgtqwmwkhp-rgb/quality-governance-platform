"""Alignment-aware read model for the Standards matrix clause axis.

Wave 2 PR-C. The matrix shell shipped in PR-A with a hardcoded list of nine
clauses; this service is what replaces it. Rows are derived from the imported
alignment edges rather than stored separately, so the clause axis and the verdicts
painted on it can never drift apart.

Honest empty
------------
With no matrix edition imported this returns ``rows: []`` and
``matrix_loaded: false``. The caller is expected to fall back to its own static
axis and say so — an empty grid would read as "no clauses apply", which is a
different and false claim.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.standards_alignment import (
    SHAREABLE_VERDICTS,
    VERDICT_RESTRICTIVENESS,
    AlignmentEdge,
    AlignmentVerdict,
    MatrixVersion,
    MatrixVersionStatus,
)

logger = logging.getLogger(__name__)

_RESTRICTIVENESS_RANK: dict[AlignmentVerdict, int] = {
    verdict: rank for rank, verdict in enumerate(VERDICT_RESTRICTIVENESS)
}


def _verdict_of(edge: AlignmentEdge) -> AlignmentVerdict:
    value = edge.verdict
    if isinstance(value, AlignmentVerdict):
        return value
    return AlignmentVerdict(str(value).strip().lower())


def _row_verdict_of(edge: AlignmentEdge) -> AlignmentVerdict:
    value = edge.row_verdict
    if isinstance(value, AlignmentVerdict):
        return value
    return AlignmentVerdict(str(value).strip().lower())


def _clause_number(clause_key: str, framework: str) -> str:
    """``"9001-7.2"`` → ``"7.2"``. Clause keys are framework-prefixed catalogue keys."""
    prefix = f"{framework}-"
    if clause_key.startswith(prefix):
        return clause_key[len(prefix) :]
    return clause_key


class StandardsAlignmentReadService:
    """Reads the active alignment edition into matrix-shaped rows."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def _active_version(self, tenant_id: int) -> Optional[MatrixVersion]:
        result = await self.db.execute(
            select(MatrixVersion)
            .where(
                MatrixVersion.tenant_id == tenant_id,
                MatrixVersion.status == MatrixVersionStatus.ACTIVE,
                MatrixVersion.deleted_at.is_(None),
            )
            .order_by(MatrixVersion.id.desc())
        )
        return result.scalars().first()

    async def catalogue(
        self,
        *,
        tenant_id: int,
        framework: Optional[str] = None,
        verdict: Optional[str] = None,
    ) -> dict[str, Any]:
        """Clause rows with their verdicts, framework coverage, and trap flags."""
        version = await self._active_version(tenant_id)
        if version is None:
            return {
                "matrix_loaded": False,
                "matrix_version": None,
                "rows": [],
                "frameworks": [],
                "excluded_frameworks": [],
                "fallback_note": (
                    "No alignment matrix edition has been imported for this tenant. "
                    "The clause axis shown is the shell's own static list, not "
                    "imported data."
                ),
            }

        edges = list(
            (
                await self.db.execute(
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

        framework_filter = (framework or "").strip().lower() or None
        verdict_filter: Optional[AlignmentVerdict] = None
        if verdict:
            try:
                verdict_filter = AlignmentVerdict(str(verdict).strip().lower())
            except ValueError:
                verdict_filter = None

        rows: dict[str, dict[str, Any]] = {}
        frameworks_seen: set[str] = set()

        for edge in edges:
            edge_verdict = _verdict_of(edge)
            endpoints = [(edge.src_framework, edge.src_clause_key, edge.src_clause_label)]
            if edge.dst_framework and edge.dst_clause_key:
                endpoints.append((edge.dst_framework, edge.dst_clause_key, edge.dst_clause_label))

            for fw, _key, _label in endpoints:
                frameworks_seen.add(fw)

            if framework_filter and all(fw != framework_filter for fw, _k, _l in endpoints):
                continue

            row = rows.get(edge.row_key)
            if row is None:
                row = {
                    "id": edge.row_key,
                    "kind": "standard",
                    "row_key": edge.row_key,
                    "clauseNumber": edge.clause_ref,
                    "title": edge.title,
                    "row_verdict": _row_verdict_of(edge).api_value,
                    "verdict": edge_verdict.api_value,
                    "_verdict_rank": _RESTRICTIVENESS_RANK[edge_verdict],
                    "is_trap": False,
                    "has_unique": False,
                    "addition_text": edge.addition_text,
                    "rationale": edge.rationale,
                    "deliverables": edge.deliverables,
                    "frameworks": {},
                    "pair_count": 0,
                    "trap_pair_count": 0,
                }
                rows[edge.row_key] = row

            # The row's headline verdict is the most restrictive one on it: a row
            # containing one DIFFERENT pair is a row a reader must not skim.
            rank = _RESTRICTIVENESS_RANK[edge_verdict]
            if rank < row["_verdict_rank"]:
                row["_verdict_rank"] = rank
                row["verdict"] = edge_verdict.api_value

            row["pair_count"] += 1
            if edge_verdict not in SHAREABLE_VERDICTS:
                row["is_trap"] = True
                row["trap_pair_count"] += 1
            if edge_verdict is AlignmentVerdict.UNIQUE:
                row["has_unique"] = True

            for fw, key, label in endpoints:
                entry = row["frameworks"].setdefault(
                    fw,
                    {
                        "clause_key": key,
                        "clause_number": _clause_number(key, fw),
                        "label": label,
                        "verdicts": [],
                    },
                )
                if edge_verdict.api_value not in entry["verdicts"]:
                    entry["verdicts"].append(edge_verdict.api_value)

        ordered = sorted(rows.values(), key=lambda row: _clause_sort_key(row["clauseNumber"]))
        if verdict_filter is not None:
            ordered = [row for row in ordered if row["verdict"] == verdict_filter.api_value]
        for row in ordered:
            row.pop("_verdict_rank", None)

        return {
            "matrix_loaded": True,
            "matrix_version": f"{version.source_ref} v{version.version_label}",
            "matrix_version_id": version.id,
            "source_date": version.source_date,
            "rows": ordered,
            "frameworks": sorted(frameworks_seen),
            "excluded_frameworks": [
                part.strip() for part in (version.excluded_frameworks or "").split(",") if part.strip()
            ],
            "row_count": len(ordered),
            "edge_count": len(edges),
            "sor_note": (
                f"Verdicts are an imported read-model of {version.source_ref} "
                f"v{version.version_label}. The source report remains the SoR."
            ),
        }


def _clause_sort_key(clause_ref: str) -> tuple[Any, ...]:
    """Sort 4.1 before 4.2 before 10.1, and keep non-numeric refs together at the end."""
    text = str(clause_ref or "").strip()
    parts = text.split(".")
    numeric: list[int] = []
    for part in parts:
        if part.isdigit():
            numeric.append(int(part))
        else:
            # "A.5.31" / "IIP 3" — no numeric lead, so sort after the clause axis.
            return (1, text)
    return (0, tuple(numeric))
