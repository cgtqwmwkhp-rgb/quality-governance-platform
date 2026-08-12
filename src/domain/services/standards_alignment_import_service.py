"""Import the PEL-HSEQ-5064 alignment matrix: dry-run diff → accept-each → apply.

Wave 2 PR-C. An alignment verdict decides whether one document can be put in
front of two auditors, so an import is never allowed to land silently: the
operator sees a diff against the edition currently active, accepts or declines
each changed pair, and only the accepted set is written — as a *new* edition,
leaving the old one readable.

Three properties are load-bearing
---------------------------------
**Row verdicts are expanded into pairs.** The workbook prints one verdict per
clause row, which is not true of every pair inside the row. Expansion happens
here, and a pair the source names explicitly overrides the row.

**The most restrictive verdict wins a collision.** Two source rows can describe
the same pair — clause 6.1.3 as a row, and Annex A 5.31 as an EXACT alignment.
Over-claiming a shared requirement is the failure the matrix exists to prevent,
so ties break towards refusing to share evidence.

**Apply is idempotent by checksum.** The checksum is taken over the *resulting*
edge set, not the input file, so re-applying the same payload with the same
acceptances finds the existing edition and writes nothing. Two operators applying
at once are resolved by the partial unique indexes, not by a read-then-write race.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional, Sequence

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.standards_alignment import (
    VERDICT_RESTRICTIVENESS,
    AlignmentEdge,
    AlignmentVerdict,
    MatrixVersion,
    MatrixVersionStatus,
    canonical_alignment_pair,
)

logger = logging.getLogger(__name__)

#: Where the checked-in payload lives, relative to the repository root.
DEFAULT_PAYLOAD_PATH = Path("specs/standards/pel-hseq-5064-alignment-v1.0.json")

_RESTRICTIVENESS_RANK: dict[AlignmentVerdict, int] = {
    verdict: rank for rank, verdict in enumerate(VERDICT_RESTRICTIVENESS)
}


class AlignmentImportError(ValueError):
    """The payload cannot be turned into a coherent edge set."""


def _verdict(raw: Any) -> AlignmentVerdict:
    try:
        return AlignmentVerdict(str(raw).strip().lower())
    except ValueError as exc:
        raise AlignmentImportError(f"Unknown alignment verdict: {raw!r}") from exc


def _clause_key(framework: str, clause_number: str) -> str:
    """Catalogue-shaped clause key, matching ``clauses.catalogue_key`` ("9001-7.2")."""
    return f"{framework.strip().lower()}-{str(clause_number).strip()}"


@dataclass(frozen=True)
class EdgeKey:
    """Identity of one stored pair, and the accept-each unit of work."""

    src_framework: str
    src_clause_key: str
    dst_framework: Optional[str]
    dst_clause_key: Optional[str]

    def as_token(self) -> str:
        """Stable opaque token the API hands out and takes back for acceptance."""
        if self.dst_framework is None:
            return f"{self.src_framework}|{self.src_clause_key}|-|-"
        return f"{self.src_framework}|{self.src_clause_key}|{self.dst_framework}|{self.dst_clause_key}"

    @classmethod
    def from_token(cls, token: str) -> "EdgeKey":
        parts = str(token).split("|")
        if len(parts) != 4:
            raise AlignmentImportError(f"Malformed edge token: {token!r}")
        src_fw, src_key, dst_fw, dst_key = parts
        if dst_fw == "-" and dst_key == "-":
            return cls(src_fw, src_key, None, None)
        return cls(src_fw, src_key, dst_fw, dst_key)


@dataclass
class BuiltEdge:
    """One pair verdict ready to store, with the provenance that produced it."""

    key: EdgeKey
    row_key: str
    clause_ref: str
    title: str
    verdict: AlignmentVerdict
    row_verdict: AlignmentVerdict
    is_pair_override: bool
    src_clause_label: Optional[str] = None
    dst_clause_label: Optional[str] = None
    addition_text: Optional[str] = None
    rationale: Optional[str] = None
    deliverables: Optional[str] = None
    source_sheet: Optional[str] = None
    source_row: Optional[int] = None

    def checksum_tuple(self) -> tuple[Any, ...]:
        """The fields that make two editions of this pair the same edition.

        Provenance (sheet, row number) is excluded on purpose: re-issuing the
        workbook with rows shuffled must not read as a changed verdict.
        """
        return (
            self.key.src_framework,
            self.key.src_clause_key,
            self.key.dst_framework or "",
            self.key.dst_clause_key or "",
            self.verdict.value,
            self.row_verdict.value,
            self.addition_text or "",
            self.clause_ref,
        )


@dataclass
class PlanItem:
    """One line of the dry-run diff."""

    token: str
    change_type: str  # added | changed | unchanged | removed
    src_framework: str
    src_clause_key: str
    dst_framework: Optional[str]
    dst_clause_key: Optional[str]
    clause_ref: str
    title: str
    verdict: Optional[str]
    previous_verdict: Optional[str]
    is_pair_override: bool = False
    addition_text: Optional[str] = None
    rationale: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "token": self.token,
            "change_type": self.change_type,
            "src_framework": self.src_framework,
            "src_clause_key": self.src_clause_key,
            "dst_framework": self.dst_framework,
            "dst_clause_key": self.dst_clause_key,
            "clause_ref": self.clause_ref,
            "title": self.title,
            "verdict": self.verdict.upper() if self.verdict else None,
            "previous_verdict": self.previous_verdict.upper() if self.previous_verdict else None,
            "is_pair_override": self.is_pair_override,
            "addition_text": self.addition_text,
            "rationale": self.rationale,
        }


@dataclass
class ImportPlan:
    """The dry-run result: what would change, and what the source got wrong."""

    source_ref: str
    version_label: str
    title: str
    source_date: Optional[str]
    excluded_frameworks: list[str]
    notes: Optional[str]
    items: list[PlanItem] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    active_version_id: Optional[int] = None
    active_version_label: Optional[str] = None

    @property
    def counts(self) -> dict[str, int]:
        tally = {"added": 0, "changed": 0, "unchanged": 0, "removed": 0}
        for item in self.items:
            tally[item.change_type] = tally.get(item.change_type, 0) + 1
        return tally

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_ref": self.source_ref,
            "version_label": self.version_label,
            "title": self.title,
            "source_date": self.source_date,
            "excluded_frameworks": self.excluded_frameworks,
            "notes": self.notes,
            "active_version_id": self.active_version_id,
            "active_version_label": self.active_version_label,
            "counts": self.counts,
            "items": [item.to_dict() for item in self.items],
            "warnings": self.warnings,
            "dry_run": True,
        }


@dataclass
class ApplyResult:
    matrix_version_id: int
    version_label: str
    source_checksum: str
    edges_written: int
    rows: int
    created: bool
    superseded_version_id: Optional[int] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "matrix_version_id": self.matrix_version_id,
            "version_label": self.version_label,
            "source_checksum": self.source_checksum,
            "edges_written": self.edges_written,
            "rows": self.rows,
            "created": self.created,
            "superseded_version_id": self.superseded_version_id,
            "note": (
                "Alignment verdicts are an imported read-model of "
                f"{self.version_label}. The source document remains the SoR."
            ),
        }


def load_payload(path: Optional[Path] = None) -> dict[str, Any]:
    """Read the checked-in alignment payload."""
    target = path or DEFAULT_PAYLOAD_PATH
    if not target.is_absolute():
        # Resolve against the repository root (four parents up from this module).
        target = Path(__file__).resolve().parents[3] / target
    if not target.exists():
        raise AlignmentImportError(f"Alignment payload not found: {target}")
    with target.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise AlignmentImportError("Alignment payload must be a JSON object")
    return payload


def _unordered_pairs(frameworks: Sequence[str]) -> Iterable[tuple[str, str]]:
    for index, left in enumerate(frameworks):
        for right in frameworks[index + 1 :]:
            yield left, right


def _override_lookup(row: dict[str, Any]) -> dict[frozenset[str], dict[str, Any]]:
    lookup: dict[frozenset[str], dict[str, Any]] = {}
    for override in row.get("pair_overrides") or []:
        left = str(override.get("a", "")).strip().lower()
        right = str(override.get("b", "")).strip().lower()
        if not left or not right:
            continue
        lookup[frozenset({left, right})] = override
    return lookup


def _merge(existing: BuiltEdge, candidate: BuiltEdge) -> BuiltEdge:
    """Keep the more restrictive of two verdicts for the same pair."""
    if _RESTRICTIVENESS_RANK[candidate.verdict] < _RESTRICTIVENESS_RANK[existing.verdict]:
        return candidate
    return existing


def build_edges(payload: dict[str, Any]) -> tuple[list[BuiltEdge], list[str]]:
    """Expand the payload into canonical pair edges. Returns ``(edges, warnings)``."""
    built: dict[EdgeKey, BuiltEdge] = {}
    warnings: list[str] = []

    def add(edge: BuiltEdge) -> None:
        current = built.get(edge.key)
        if current is None:
            built[edge.key] = edge
            return
        winner = _merge(current, edge)
        if winner.verdict is not current.verdict:
            warnings.append(
                f"{edge.clause_ref}: two source rows disagree on "
                f"{edge.key.src_framework} {edge.key.src_clause_key} ↔ "
                f"{edge.key.dst_framework} {edge.key.dst_clause_key} "
                f"({current.verdict.api_value} vs {edge.verdict.api_value}); kept "
                f"{winner.verdict.api_value} as the more restrictive."
            )
        built[edge.key] = winner

    for row in payload.get("rows") or []:
        clause_ref = str(row.get("clause_ref", "")).strip()
        if not clause_ref:
            warnings.append("Skipped a clause row with no clause reference.")
            continue
        row_verdict = _verdict(row.get("verdict"))
        title = str(row.get("title") or clause_ref)
        row_key = str(row.get("row_key") or f"annexsl-{clause_ref}")
        rationale = row.get("trap_note") or row.get("rationale")
        deliverables = row.get("deliverables")
        source_sheet = row.get("source_sheet")
        source_row = row.get("source_row")

        frameworks_raw = row.get("frameworks") or {}
        frameworks = sorted(str(key).strip().lower() for key in frameworks_raw if str(key).strip())
        labels = {str(key).strip().lower(): (frameworks_raw[key] or {}).get("label") for key in frameworks_raw}
        clause_numbers = {
            str(key).strip().lower(): (frameworks_raw[key] or {}).get("clause_number") or clause_ref
            for key in frameworks_raw
        }

        if not frameworks:
            warnings.append(f"{clause_ref}: no frameworks present — no edges built.")
            continue

        if row_verdict is AlignmentVerdict.UNIQUE:
            if len(frameworks) != 1:
                # UNIQUE means exactly one framework asks for it. More than one is a
                # contradiction in the source, and guessing which is right would
                # invent an alignment, so nothing is written for this row.
                warnings.append(
                    f"{clause_ref}: verdict UNIQUE but {len(frameworks)} frameworks "
                    f"are listed ({', '.join(frameworks)}) — row skipped as "
                    "contradictory rather than resolved by guessing."
                )
                continue
            framework = frameworks[0]
            src_fw, src_key, _, _ = canonical_alignment_pair(
                framework, _clause_key(framework, clause_numbers[framework]), None, None
            )
            add(
                BuiltEdge(
                    key=EdgeKey(src_fw, src_key, None, None),
                    row_key=row_key,
                    clause_ref=clause_ref,
                    title=title,
                    verdict=AlignmentVerdict.UNIQUE,
                    row_verdict=AlignmentVerdict.UNIQUE,
                    is_pair_override=False,
                    src_clause_label=labels.get(framework),
                    rationale=rationale,
                    deliverables=deliverables,
                    source_sheet=source_sheet,
                    source_row=source_row,
                )
            )
            continue

        overrides = _override_lookup(row)
        for left, right in _unordered_pairs(frameworks):
            override = overrides.get(frozenset({left, right}))
            verdict = _verdict(override["verdict"]) if override else row_verdict
            addition = override.get("note") if override else row.get("addition_text")
            if not override and row_verdict is AlignmentVerdict.NEAR:
                # A NEAR row's addition is stated in its Why column; that column is
                # what an operator must read before sharing the deliverable.
                addition = row.get("addition_text") or row.get("rationale")

            src_fw, src_key, dst_fw, dst_key = canonical_alignment_pair(
                left,
                _clause_key(left, clause_numbers[left]),
                right,
                _clause_key(right, clause_numbers[right]),
            )
            src_label = labels.get(src_fw)
            dst_label = labels.get(dst_fw) if dst_fw else None
            add(
                BuiltEdge(
                    key=EdgeKey(src_fw, src_key, dst_fw, dst_key),
                    row_key=row_key,
                    clause_ref=clause_ref,
                    title=title,
                    verdict=verdict,
                    row_verdict=row_verdict,
                    is_pair_override=bool(override) and verdict is not row_verdict,
                    src_clause_label=src_label,
                    dst_clause_label=dst_label,
                    addition_text=addition,
                    rationale=rationale,
                    deliverables=deliverables,
                    source_sheet=source_sheet,
                    source_row=source_row,
                )
            )

    for row in payload.get("supplementary_rows") or []:
        clause_ref = str(row.get("clause_ref", "")).strip()
        row_verdict = _verdict(row.get("verdict"))
        title = str(row.get("title") or clause_ref)
        row_key = str(row.get("row_key") or clause_ref)
        for pair in row.get("pairs") or []:
            left = pair.get("a") or []
            right = pair.get("b") or []
            if len(left) != 2 or len(right) != 2:
                warnings.append(f"{clause_ref}: malformed supplementary pair {pair!r} — skipped.")
                continue
            src_fw, src_key, dst_fw, dst_key = canonical_alignment_pair(
                str(left[0]),
                _clause_key(str(left[0]), str(left[1])),
                str(right[0]),
                _clause_key(str(right[0]), str(right[1])),
            )
            if (src_fw, src_key) == (dst_fw, dst_key):
                warnings.append(f"{clause_ref}: supplementary pair {pair!r} refers to itself — skipped.")
                continue
            add(
                BuiltEdge(
                    key=EdgeKey(src_fw, src_key, dst_fw, dst_key),
                    row_key=row_key,
                    clause_ref=clause_ref,
                    title=title,
                    verdict=row_verdict,
                    row_verdict=row_verdict,
                    is_pair_override=False,
                    addition_text=row.get("addition_text"),
                    rationale=row.get("rationale"),
                    deliverables=row.get("deliverables"),
                    source_sheet=row.get("source_sheet"),
                    source_row=row.get("source_row"),
                )
            )

    ordered = sorted(built.values(), key=lambda edge: edge.key.as_token())
    return ordered, warnings


def compute_checksum(
    *,
    source_ref: str,
    version_label: str,
    edges: Sequence[BuiltEdge],
) -> str:
    """SHA-256 over the resulting edge set, so identical outcomes share an edition."""
    material = {
        "source_ref": source_ref,
        "version_label": version_label,
        "edges": sorted(edge.checksum_tuple() for edge in edges),
    }
    encoded = json.dumps(material, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


class StandardsAlignmentImportService:
    """Dry-run, accept-each, apply — for one tenant's alignment matrix."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def _active_version(self, *, tenant_id: int, source_ref: str) -> Optional[MatrixVersion]:
        result = await self.db.execute(
            select(MatrixVersion).where(
                MatrixVersion.tenant_id == tenant_id,
                MatrixVersion.source_ref == source_ref,
                MatrixVersion.status == MatrixVersionStatus.ACTIVE,
                MatrixVersion.deleted_at.is_(None),
            )
        )
        return result.scalars().first()

    async def _edges_for_version(self, *, tenant_id: int, version_id: int) -> list[AlignmentEdge]:
        result = await self.db.execute(
            select(AlignmentEdge).where(
                AlignmentEdge.tenant_id == tenant_id,
                AlignmentEdge.matrix_version_id == version_id,
                AlignmentEdge.deleted_at.is_(None),
            )
        )
        return list(result.scalars().all())

    async def plan(self, *, tenant_id: int, payload: dict[str, Any]) -> ImportPlan:
        """Diff the payload against the active edition. Writes nothing."""
        source_ref = str(payload.get("source_ref") or "").strip()
        if not source_ref:
            raise AlignmentImportError("Payload has no source_ref")

        edges, warnings = build_edges(payload)
        active = await self._active_version(tenant_id=tenant_id, source_ref=source_ref)

        previous: dict[EdgeKey, AlignmentEdge] = {}
        if active is not None:
            for edge in await self._edges_for_version(tenant_id=tenant_id, version_id=active.id):
                previous[
                    EdgeKey(
                        edge.src_framework,
                        edge.src_clause_key,
                        edge.dst_framework,
                        edge.dst_clause_key,
                    )
                ] = edge

        items: list[PlanItem] = []
        for edge in edges:
            existing = previous.get(edge.key)
            if existing is None:
                change_type = "added"
                previous_verdict = None
            else:
                existing_verdict = _coerce_verdict(existing.verdict)
                previous_verdict = existing_verdict.value
                change_type = "unchanged" if existing_verdict is edge.verdict else "changed"
            items.append(
                PlanItem(
                    token=edge.key.as_token(),
                    change_type=change_type,
                    src_framework=edge.key.src_framework,
                    src_clause_key=edge.key.src_clause_key,
                    dst_framework=edge.key.dst_framework,
                    dst_clause_key=edge.key.dst_clause_key,
                    clause_ref=edge.clause_ref,
                    title=edge.title,
                    verdict=edge.verdict.value,
                    previous_verdict=previous_verdict,
                    is_pair_override=edge.is_pair_override,
                    addition_text=edge.addition_text,
                    rationale=edge.rationale,
                )
            )

        incoming_keys = {edge.key for edge in edges}
        for key, edge in previous.items():
            if key in incoming_keys:
                continue
            items.append(
                PlanItem(
                    token=key.as_token(),
                    change_type="removed",
                    src_framework=key.src_framework,
                    src_clause_key=key.src_clause_key,
                    dst_framework=key.dst_framework,
                    dst_clause_key=key.dst_clause_key,
                    clause_ref=edge.clause_ref,
                    title=edge.title,
                    verdict=None,
                    previous_verdict=_coerce_verdict(edge.verdict).value,
                )
            )

        items.sort(key=lambda item: (item.change_type, item.token))
        return ImportPlan(
            source_ref=source_ref,
            version_label=str(payload.get("version_label") or "unversioned"),
            title=str(payload.get("title") or source_ref),
            source_date=payload.get("source_date"),
            excluded_frameworks=[str(x) for x in (payload.get("excluded_frameworks") or [])],
            notes=payload.get("notes"),
            items=items,
            warnings=warnings,
            active_version_id=active.id if active else None,
            active_version_label=active.version_label if active else None,
        )

    async def apply(
        self,
        *,
        tenant_id: int,
        payload: dict[str, Any],
        accepted_tokens: Optional[Sequence[str]] = None,
        imported_by_id: Optional[int] = None,
    ) -> ApplyResult:
        """Write the accepted subset as a new active edition.

        ``accepted_tokens`` is the accept-each gate. ``None`` accepts every item —
        used by the seed path, where the operator has accepted the whole workbook
        by running the seed. A declined *change* keeps the verdict the active
        edition already holds, and a declined *removal* keeps the pair, so
        declining never silently loosens a verdict.
        """
        source_ref = str(payload.get("source_ref") or "").strip()
        if not source_ref:
            raise AlignmentImportError("Payload has no source_ref")
        version_label = str(payload.get("version_label") or "unversioned")

        edges, warnings = build_edges(payload)
        if not edges:
            raise AlignmentImportError("Payload produced no alignment edges: " + ("; ".join(warnings) or "no rows"))

        active = await self._active_version(tenant_id=tenant_id, source_ref=source_ref)
        previous: dict[EdgeKey, AlignmentEdge] = {}
        if active is not None:
            for edge in await self._edges_for_version(tenant_id=tenant_id, version_id=active.id):
                previous[
                    EdgeKey(
                        edge.src_framework,
                        edge.src_clause_key,
                        edge.dst_framework,
                        edge.dst_clause_key,
                    )
                ] = edge

        resulting = self._resolve_accepted(
            incoming=edges,
            previous=previous,
            accepted_tokens=accepted_tokens,
        )
        checksum = compute_checksum(source_ref=source_ref, version_label=version_label, edges=resulting)

        if active is not None and active.source_checksum == checksum:
            # Nothing about the outcome changed. Re-applying must not create a
            # second edition that is identical to the live one.
            return ApplyResult(
                matrix_version_id=active.id,
                version_label=active.version_label,
                source_checksum=checksum,
                edges_written=0,
                rows=len({edge.row_key for edge in resulting}),
                created=False,
            )

        existing = await self.db.execute(
            select(MatrixVersion).where(
                MatrixVersion.tenant_id == tenant_id,
                MatrixVersion.source_ref == source_ref,
                MatrixVersion.source_checksum == checksum,
                MatrixVersion.deleted_at.is_(None),
            )
        )
        already = existing.scalars().first()
        if already is not None:
            return ApplyResult(
                matrix_version_id=already.id,
                version_label=already.version_label,
                source_checksum=checksum,
                edges_written=0,
                rows=len({edge.row_key for edge in resulting}),
                created=False,
            )

        now = datetime.now(timezone.utc)
        version = MatrixVersion(
            tenant_id=tenant_id,
            source_ref=source_ref,
            version_label=version_label,
            title=str(payload.get("title") or source_ref),
            source_date=payload.get("source_date"),
            source_checksum=checksum,
            status=MatrixVersionStatus.DRAFT,
            row_count=len({edge.row_key for edge in resulting}),
            edge_count=len(resulting),
            excluded_frameworks=", ".join(str(x) for x in (payload.get("excluded_frameworks") or [])) or None,
            notes=payload.get("notes"),
            imported_by_id=imported_by_id,
        )
        self.db.add(version)
        try:
            await self.db.flush()
        except IntegrityError as exc:
            await self.db.rollback()
            raise AlignmentImportError(
                "Another import of this matrix landed concurrently. Re-run the "
                "dry-run against the new active edition before applying."
            ) from exc

        for edge in resulting:
            self.db.add(
                AlignmentEdge(
                    tenant_id=tenant_id,
                    matrix_version_id=version.id,
                    row_key=edge.row_key,
                    clause_ref=edge.clause_ref,
                    title=edge.title,
                    src_framework=edge.key.src_framework,
                    src_clause_key=edge.key.src_clause_key,
                    src_clause_label=edge.src_clause_label,
                    dst_framework=edge.key.dst_framework,
                    dst_clause_key=edge.key.dst_clause_key,
                    dst_clause_label=edge.dst_clause_label,
                    verdict=edge.verdict,
                    row_verdict=edge.row_verdict,
                    is_pair_override=edge.is_pair_override,
                    addition_text=edge.addition_text,
                    rationale=edge.rationale,
                    deliverables=edge.deliverables,
                    source_sheet=edge.source_sheet,
                    source_row=edge.source_row,
                )
            )

        superseded_id: Optional[int] = None
        if active is not None:
            superseded_id = active.id
            await self.db.execute(
                update(MatrixVersion)
                .where(MatrixVersion.id == active.id)
                .values(status=MatrixVersionStatus.SUPERSEDED, updated_at=now)
            )

        version.status = MatrixVersionStatus.ACTIVE
        version.activated_at = now

        try:
            await self.db.flush()
        except IntegrityError as exc:
            await self.db.rollback()
            raise AlignmentImportError(
                "Another import activated a matrix edition concurrently. Re-run the "
                "dry-run against the new active edition before applying."
            ) from exc

        logger.info(
            "standards alignment applied: tenant=%s source=%s version=%s edges=%s superseded=%s",
            tenant_id,
            source_ref,
            version_label,
            len(resulting),
            superseded_id,
        )
        return ApplyResult(
            matrix_version_id=version.id,
            version_label=version_label,
            source_checksum=checksum,
            edges_written=len(resulting),
            rows=version.row_count,
            created=True,
            superseded_version_id=superseded_id,
        )

    def _resolve_accepted(
        self,
        *,
        incoming: Sequence[BuiltEdge],
        previous: dict[EdgeKey, AlignmentEdge],
        accepted_tokens: Optional[Sequence[str]],
    ) -> list[BuiltEdge]:
        """Apply the accept-each decisions to produce the edge set to store."""
        if accepted_tokens is None:
            return list(incoming)

        accepted = {str(token) for token in accepted_tokens}
        resulting: list[BuiltEdge] = []
        incoming_by_key = {edge.key: edge for edge in incoming}

        for edge in incoming:
            token = edge.key.as_token()
            existing = previous.get(edge.key)
            if existing is None:
                # Added: only lands if accepted.
                if token in accepted:
                    resulting.append(edge)
                continue
            existing_verdict = _coerce_verdict(existing.verdict)
            if existing_verdict is edge.verdict or token in accepted:
                resulting.append(edge)
                continue
            # Declined change: carry the live verdict forward unchanged.
            resulting.append(_carry_forward(existing, edge))

        for key, existing in previous.items():
            if key in incoming_by_key:
                continue
            if key.as_token() in accepted:
                # Removal accepted — the pair drops out of the new edition.
                continue
            resulting.append(_carry_forward(existing, None))

        return sorted(resulting, key=lambda edge: edge.key.as_token())


def _coerce_verdict(value: Any) -> AlignmentVerdict:
    """Read a verdict that may arrive as the enum or as raw text from the driver."""
    if isinstance(value, AlignmentVerdict):
        return value
    return _verdict(value)


def _carry_forward(existing: AlignmentEdge, incoming: Optional[BuiltEdge]) -> BuiltEdge:
    """Rebuild a stored edge as a BuiltEdge so a declined decision survives intact."""
    return BuiltEdge(
        key=EdgeKey(
            existing.src_framework,
            existing.src_clause_key,
            existing.dst_framework,
            existing.dst_clause_key,
        ),
        row_key=existing.row_key,
        clause_ref=existing.clause_ref,
        title=existing.title,
        verdict=_coerce_verdict(existing.verdict),
        row_verdict=_coerce_verdict(existing.row_verdict),
        is_pair_override=bool(existing.is_pair_override),
        src_clause_label=existing.src_clause_label,
        dst_clause_label=existing.dst_clause_label,
        addition_text=existing.addition_text,
        rationale=existing.rationale,
        deliverables=existing.deliverables,
        source_sheet=incoming.source_sheet if incoming else existing.source_sheet,
        source_row=incoming.source_row if incoming else existing.source_row,
    )
