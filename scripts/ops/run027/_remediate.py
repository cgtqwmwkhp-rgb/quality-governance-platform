"""Governed remediations that clear soft-link refusals before a duplicate audit purge.

``_soft_links`` detects CAPA and compliance-evidence references into doomed findings
and refuses by default. That refusal is correct: neither table has a foreign key, so
a delete would neither cascade nor fail — it would leave governed records pointing
at nothing, or destroy compliance claims as a side effect.

This module is the opt-in path that makes those refusals clearable. It never changes
``SOFT_LINK_DISPOSITIONS``; CAPA and CEL stay ``REFUSE``. What changes is that when
the operator names a survivor and asks for remapping, the soft-link blocker is
*deferred* and this module must either cover every hit row id with a remediation
action or emit its own blocker. Silent reclassification into ``PURGE`` would let
``delete_soft_links`` destroy them.

Finding matching
----------------
Doomed findings are matched to survivor findings on title, description, finding_type
and severity (intersected with reflected columns, normalised through
``_duplicates._normalise``). ``reference_number`` and ``id`` differ per import and
are never keys. Clause coverage lives on the CEL row itself, not on the finding.

CEL "withdraw" means soft-delete (``deleted_at``). CAPA has no withdraw status in
the schema; this script can only reassign ``source_id``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional, Sequence

import sqlalchemy as sa

from scripts.ops.run027._duplicates import LIFECYCLE_IDENTITY_COLUMNS, _normalise, identity_key
from scripts.ops.run027._soft_links import SoftLinkHit

#: Columns that describe the finding itself. Intersected with reflected columns.
FINDING_MATCH_CANDIDATES: tuple[str, ...] = (
    "title",
    "description",
    "finding_type",
    "severity",
)

#: Minimum match columns, beyond nothing, for a finding twin to mean anything.
MIN_FINDING_MATCH_COLUMNS = 2

#: Soft-link tables this module can remediate when the matching flags are on.
REMEDIABLE_SOFT_TABLES: frozenset[str] = frozenset({"compliance_evidence_links", "capa_actions"})


@dataclass(frozen=True)
class FindingMatch:
    """One doomed finding and how it maps onto a survivor finding."""

    doomed_id: int
    survivor_id: Optional[int]
    outcome: str  # MATCHED | UNMAPPABLE | AMBIGUOUS
    match_key: dict[str, Any]
    candidates: tuple[int, ...] = ()


@dataclass(frozen=True)
class EvidenceLinkAction:
    """One compliance_evidence_links row to remap or soft-delete."""

    link_id: int
    disposition: str  # REMAP | WITHDRAW_REDUNDANT | WITHDRAW_UNMAPPABLE | RETAIN_SOFT_DELETED
    entity_type: str
    old_entity_id: str
    new_entity_id: Optional[str]
    clause_id: Optional[str]
    cover_kind: Optional[str]
    doomed_finding_id: Optional[int] = None
    survivor_finding_id: Optional[int] = None
    pre_update: dict[str, Any] = field(default_factory=dict)

    def as_report(self) -> dict[str, Any]:
        return {
            "link_id": self.link_id,
            "disposition": self.disposition,
            "entity_type": self.entity_type,
            "old_entity_id": self.old_entity_id,
            "new_entity_id": self.new_entity_id,
            "clause_id": self.clause_id,
            "cover_kind": self.cover_kind,
            "doomed_finding_id": self.doomed_finding_id,
            "survivor_finding_id": self.survivor_finding_id,
        }


@dataclass(frozen=True)
class CapaReassignAction:
    """One capa_actions row to reassign onto a survivor finding."""

    capa_id: int
    old_source_id: int
    new_source_id: int
    reference_number: Optional[str]
    pre_update: dict[str, Any] = field(default_factory=dict)

    def as_report(self) -> dict[str, Any]:
        return {
            "capa_id": self.capa_id,
            "disposition": "REASSIGN",
            "old_source_id": self.old_source_id,
            "new_source_id": self.new_source_id,
            "reference_number": self.reference_number,
        }


@dataclass
class RemediationPlan:
    """Read-only plan for clearing CEL/CAPA soft-link refusals."""

    finding_matches: list[FindingMatch] = field(default_factory=list)
    evidence_actions: list[EvidenceLinkAction] = field(default_factory=list)
    capa_actions: list[CapaReassignAction] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    named_survivors: list[dict[str, Any]] = field(default_factory=list)
    corroboration: list[dict[str, Any]] = field(default_factory=list)

    def as_report(self) -> dict[str, Any]:
        return {
            "named_survivors": self.named_survivors,
            "corroboration": self.corroboration,
            "finding_matches": [
                {
                    "doomed_id": match.doomed_id,
                    "survivor_id": match.survivor_id,
                    "outcome": match.outcome,
                    "match_key": match.match_key,
                    "candidates": list(match.candidates),
                }
                for match in self.finding_matches
            ],
            "evidence_links": [action.as_report() for action in self.evidence_actions],
            "capa_actions": [action.as_report() for action in self.capa_actions],
            "evidence_summary": _summarise([action.disposition for action in self.evidence_actions]),
            "capa_summary": {"reassign": len(self.capa_actions)},
        }


def _summarise(dispositions: Sequence[str]) -> dict[str, int]:
    out: dict[str, int] = {}
    for disposition in dispositions:
        out[disposition] = out.get(disposition, 0) + 1
    return out


def _finding_match_columns(columns: set[str]) -> tuple[str, ...]:
    return tuple(column for column in FINDING_MATCH_CANDIDATES if column in columns)


def _finding_key(row: dict[str, Any], columns: Sequence[str]) -> tuple[Any, ...]:
    return tuple(_normalise(row.get(column)) for column in columns)


async def _table_columns(db: Any, table: str) -> set[str]:
    def _inspect(sync: Any) -> set[str]:
        inspector = sa.inspect(sync.get_bind())
        if not inspector.has_table(table):
            return set()
        return {column["name"] for column in inspector.get_columns(table)}

    return await db.run_sync(_inspect)


async def resolve_named_survivors(
    db: Any,
    *,
    survivor_references: Sequence[str],
    doomed_references: Sequence[str],
    tenant_id: Optional[int],
) -> tuple[list[dict[str, Any]], list[str]]:
    """Load and authorise --survivor-reference rows.

    Existence, tenant and non-membership in the doomed set are hard blockers — they
    catch the wrong database / self-purge, and ``--allow-no-survivor`` must not
    override them.
    """
    blockers: list[str] = []
    if not survivor_references:
        return [], blockers

    placeholders = ", ".join(f":ref_{index}" for index in range(len(survivor_references)))
    params = {f"ref_{index}": reference for index, reference in enumerate(survivor_references)}
    rows = (
        (
            await db.execute(
                sa.text(
                    f"SELECT * FROM audit_runs WHERE reference_number IN ({placeholders}) "  # noqa: S608
                    "ORDER BY id"
                ),
                params,
            )
        )
        .mappings()
        .all()
    )
    found = [dict(row) for row in rows]
    seen = {str(row.get("reference_number")) for row in found}
    doomed_set = set(doomed_references)

    for reference in survivor_references:
        if reference not in seen:
            blockers.append(
                f"--survivor-reference {reference} does not exist in audit_runs. "
                "Refusing: a mistyped survivor and an already-purged one look identical from here"
            )
        if reference in doomed_set:
            blockers.append(
                f"--survivor-reference {reference} is also named in --reference. "
                "A survivor cannot be purged in the same run"
            )

    if tenant_id is not None:
        for row in found:
            if row.get("tenant_id") != tenant_id:
                blockers.append(
                    f"--survivor-reference {row.get('reference_number')} belongs to tenant "
                    f"{row.get('tenant_id')!r}, not the asserted tenant {tenant_id}"
                )

    return found, blockers


async def corroborate_survivors(
    db: Any,
    *,
    doomed: Sequence[dict[str, Any]],
    survivors: Sequence[dict[str, Any]],
    register: Any,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Content-identity check ignoring lifecycle columns (status, score_percentage).

    Soft: overridable by ``--allow-no-survivor``. Reports which doomed audits share
    content identity with a named survivor once lifecycle columns are stripped.
    """
    report: list[dict[str, Any]] = []
    blockers: list[str] = []
    ignore = LIFECYCLE_IDENTITY_COLUMNS & set(register.identity_columns)

    columns = tuple(column for column in register.identity_columns if column not in ignore)
    for root in doomed:
        key = identity_key(root, register, ignore=ignore)
        matched = [survivor for survivor in survivors if identity_key(survivor, register, ignore=ignore) == key]
        identity = dict(zip(columns, key[1:]))
        report.append(
            {
                "purging": root.get("reference_number"),
                "identity_ignoring_lifecycle": identity,
                "ignored_columns": sorted(ignore),
                "matching_survivors": [
                    {
                        "id": row[register.key_column],
                        "reference": row.get("reference_number"),
                    }
                    for row in matched
                ],
            }
        )
        if not matched:
            blockers.append(
                f"--survivor-reference does not corroborate {root.get('reference_number')}: "
                f"no named survivor shares its content identity once {sorted(ignore)} are "
                f"ignored ({identity}). Confirm the survivor reference against the scanner, "
                "or re-run with --allow-no-survivor only if a named human has accepted that"
            )
    return report, blockers


async def match_findings(
    db: Any,
    *,
    doomed_findings: Sequence[dict[str, Any]],
    survivor_run_ids: Sequence[int],
    tenant_id: Optional[int],
) -> tuple[list[FindingMatch], list[str]]:
    """Map each doomed finding onto zero-or-one survivor finding."""
    blockers: list[str] = []
    columns = await _table_columns(db, "audit_findings")
    if not columns:
        return [], ["audit_findings is not present; cannot match findings for remediation"]

    match_columns = _finding_match_columns(columns)
    if len(match_columns) < MIN_FINDING_MATCH_COLUMNS:
        return [], [
            f"audit_findings only exposes {len(match_columns)} of the match columns "
            f"({', '.join(match_columns) or 'none'}); refusing to guess twins"
        ]

    if not survivor_run_ids:
        return [], ["no survivor run ids available for finding matching"]

    placeholders = ", ".join(f":run_{index}" for index in range(len(survivor_run_ids)))
    params: dict[str, Any] = {f"run_{index}": run_id for index, run_id in enumerate(survivor_run_ids)}
    sql = f"SELECT * FROM audit_findings WHERE run_id IN ({placeholders})"  # noqa: S608
    if tenant_id is not None and "tenant_id" in columns:
        sql += " AND tenant_id = :tenant_id"
        params["tenant_id"] = tenant_id
    sql += " ORDER BY id"

    survivor_rows = [dict(row) for row in (await db.execute(sa.text(sql), params)).mappings().all()]
    by_key: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
    for row in survivor_rows:
        by_key.setdefault(_finding_key(row, match_columns), []).append(row)

    matches: list[FindingMatch] = []
    for doomed in sorted(doomed_findings, key=lambda row: int(row["id"])):
        key = _finding_key(doomed, match_columns)
        candidates = by_key.get(key, [])
        key_report = dict(zip(match_columns, key))
        if not candidates:
            matches.append(
                FindingMatch(
                    doomed_id=int(doomed["id"]),
                    survivor_id=None,
                    outcome="UNMAPPABLE",
                    match_key=key_report,
                )
            )
        elif len(candidates) > 1:
            candidate_ids = tuple(int(row["id"]) for row in candidates)
            matches.append(
                FindingMatch(
                    doomed_id=int(doomed["id"]),
                    survivor_id=None,
                    outcome="AMBIGUOUS",
                    match_key=key_report,
                    candidates=candidate_ids,
                )
            )
            blockers.append(
                f"doomed finding {doomed['id']} matches {len(candidate_ids)} survivor findings "
                f"{list(candidate_ids)} on {key_report}; refusing to guess"
            )
        else:
            matches.append(
                FindingMatch(
                    doomed_id=int(doomed["id"]),
                    survivor_id=int(candidates[0]["id"]),
                    outcome="MATCHED",
                    match_key=key_report,
                    candidates=(int(candidates[0]["id"]),),
                )
            )
    return matches, blockers


async def _load_evidence_rows(
    db: Any,
    *,
    link_ids: Sequence[Any],
) -> list[dict[str, Any]]:
    if not link_ids:
        return []
    placeholders = ", ".join(f":id_{index}" for index in range(len(link_ids)))
    params = {f"id_{index}": row_id for index, row_id in enumerate(link_ids)}
    rows = (
        (
            await db.execute(
                sa.text(
                    "SELECT * FROM compliance_evidence_links "  # noqa: S608
                    f"WHERE id IN ({placeholders}) ORDER BY id"
                ),
                params,
            )
        )
        .mappings()
        .all()
    )
    return [dict(row) for row in rows]


async def _load_capa_rows(db: Any, *, capa_ids: Sequence[Any]) -> list[dict[str, Any]]:
    if not capa_ids:
        return []
    placeholders = ", ".join(f":id_{index}" for index in range(len(capa_ids)))
    params = {f"id_{index}": row_id for index, row_id in enumerate(capa_ids)}
    rows = (
        (
            await db.execute(
                sa.text(f"SELECT * FROM capa_actions WHERE id IN ({placeholders}) ORDER BY id"),  # noqa: S608
                params,
            )
        )
        .mappings()
        .all()
    )
    return [dict(row) for row in rows]


async def _existing_live_cel_keys(
    db: Any,
    *,
    survivor_entity_ids: Sequence[str],
    entity_type: str,
) -> set[tuple[Any, ...]]:
    """Live (deleted_at IS NULL) CEL unique keys already held by survivor entity ids."""
    if not survivor_entity_ids:
        return set()
    columns = await _table_columns(db, "compliance_evidence_links")
    if not columns:
        return set()

    placeholders = ", ".join(f":eid_{index}" for index in range(len(survivor_entity_ids)))
    params: dict[str, Any] = {f"eid_{index}": entity_id for index, entity_id in enumerate(survivor_entity_ids)}
    params["entity_type"] = entity_type
    where_deleted = "AND deleted_at IS NULL" if "deleted_at" in columns else ""
    rows = (
        (
            await db.execute(
                sa.text(
                    "SELECT tenant_id, entity_type, entity_id, clause_id, cover_kind "
                    "FROM compliance_evidence_links "
                    "WHERE LOWER(CAST(entity_type AS TEXT)) = LOWER(:entity_type) "
                    f"AND entity_id IN ({placeholders}) {where_deleted}"  # noqa: S608
                ),
                params,
            )
        )
        .mappings()
        .all()
    )
    return {
        (
            row.get("tenant_id"),
            str(row.get("entity_type") or "").casefold(),
            str(row.get("entity_id")),
            row.get("clause_id"),
            row.get("cover_kind"),
        )
        for row in rows
    }


def _cel_unique_key(row: dict[str, Any], new_entity_id: str) -> tuple[Any, ...]:
    return (
        row.get("tenant_id"),
        str(row.get("entity_type") or "").casefold(),
        new_entity_id,
        row.get("clause_id"),
        row.get("cover_kind"),
    )


async def plan_evidence_remediation(
    db: Any,
    *,
    soft_hits: Sequence[SoftLinkHit],
    finding_matches: Sequence[FindingMatch],
    survivor_run_id: Optional[int],
    withdraw_unmappable: bool,
    expect_count: Optional[int],
) -> tuple[list[EvidenceLinkAction], list[str]]:
    """Plan CEL remaps and soft-deletes. Read-only."""
    blockers: list[str] = []
    hits = [hit for hit in soft_hits if hit.table == "compliance_evidence_links"]
    link_ids = [row_id for hit in hits for row_id in hit.row_ids]
    rows = await _load_evidence_rows(db, link_ids=link_ids)

    live_rows = [row for row in rows if row.get("deleted_at") is None]
    if expect_count is not None and len(live_rows) != expect_count:
        blockers.append(
            f"--expect-evidence-links {expect_count} but found {len(live_rows)} live "
            f"compliance_evidence_links row(s) referencing the purge set "
            f"(plus {len(rows) - len(live_rows)} already soft-deleted). "
            "Re-run the dry run and pass the live count"
        )

    match_by_doomed = {match.doomed_id: match for match in finding_matches}
    survivor_finding_ids = sorted(
        {str(match.survivor_id) for match in finding_matches if match.survivor_id is not None}
    )
    if survivor_run_id is not None:
        survivor_finding_ids.append(str(survivor_run_id))

    projected_keys = await _existing_live_cel_keys(
        db,
        survivor_entity_ids=sorted(set(survivor_finding_ids)),
        entity_type="audit_finding",
    )
    # Also load keys for audit_run entity type against the survivor run.
    if survivor_run_id is not None:
        projected_keys |= await _existing_live_cel_keys(
            db,
            survivor_entity_ids=[str(survivor_run_id)],
            entity_type="audit_run",
        )

    actions: list[EvidenceLinkAction] = []
    for row in sorted(rows, key=lambda item: int(item["id"])):
        entity_type = str(row.get("entity_type") or "")
        old_entity_id = str(row.get("entity_id"))
        if row.get("deleted_at") is not None:
            actions.append(
                EvidenceLinkAction(
                    link_id=int(row["id"]),
                    disposition="RETAIN_SOFT_DELETED",
                    entity_type=entity_type,
                    old_entity_id=old_entity_id,
                    new_entity_id=None,
                    clause_id=row.get("clause_id"),
                    cover_kind=row.get("cover_kind"),
                    pre_update=dict(row),
                )
            )
            continue

        if entity_type.casefold() == "audit_run":
            if survivor_run_id is None:
                blockers.append(
                    f"compliance_evidence_links#{row['id']} points at an audit_run but no "
                    "survivor run id is available"
                )
                continue
            new_entity_id = str(survivor_run_id)
            doomed_finding_id = None
            survivor_finding_id = None
        elif entity_type.casefold() == "audit_finding":
            try:
                doomed_finding_id = int(old_entity_id)
            except (TypeError, ValueError):
                blockers.append(
                    f"compliance_evidence_links#{row['id']} has non-integer entity_id " f"{old_entity_id!r}; refusing"
                )
                continue
            match = match_by_doomed.get(doomed_finding_id)
            if match is None or match.outcome == "UNMAPPABLE":
                if withdraw_unmappable:
                    actions.append(
                        EvidenceLinkAction(
                            link_id=int(row["id"]),
                            disposition="WITHDRAW_UNMAPPABLE",
                            entity_type=entity_type,
                            old_entity_id=old_entity_id,
                            new_entity_id=None,
                            clause_id=row.get("clause_id"),
                            cover_kind=row.get("cover_kind"),
                            doomed_finding_id=doomed_finding_id,
                            pre_update=dict(row),
                        )
                    )
                else:
                    blockers.append(
                        f"compliance_evidence_links#{row['id']} points at doomed finding "
                        f"{doomed_finding_id} which has no matching survivor finding. "
                        "Re-run with --withdraw-unmappable-evidence to soft-delete it, "
                        "or fix the finding correspondence first"
                    )
                continue
            if match.outcome == "AMBIGUOUS":
                # Already blocked in match_findings; skip emitting a duplicate action.
                continue
            assert match.survivor_id is not None
            new_entity_id = str(match.survivor_id)
            survivor_finding_id = match.survivor_id
        else:
            blockers.append(
                f"compliance_evidence_links#{row['id']} has unsupported entity_type " f"{entity_type!r} for remediation"
            )
            continue

        key = _cel_unique_key(row, new_entity_id)
        if key in projected_keys:
            actions.append(
                EvidenceLinkAction(
                    link_id=int(row["id"]),
                    disposition="WITHDRAW_REDUNDANT",
                    entity_type=entity_type,
                    old_entity_id=old_entity_id,
                    new_entity_id=new_entity_id,
                    clause_id=row.get("clause_id"),
                    cover_kind=row.get("cover_kind"),
                    doomed_finding_id=doomed_finding_id if entity_type.casefold() == "audit_finding" else None,
                    survivor_finding_id=survivor_finding_id,
                    pre_update=dict(row),
                )
            )
        else:
            projected_keys.add(key)
            actions.append(
                EvidenceLinkAction(
                    link_id=int(row["id"]),
                    disposition="REMAP",
                    entity_type=entity_type,
                    old_entity_id=old_entity_id,
                    new_entity_id=new_entity_id,
                    clause_id=row.get("clause_id"),
                    cover_kind=row.get("cover_kind"),
                    doomed_finding_id=doomed_finding_id if entity_type.casefold() == "audit_finding" else None,
                    survivor_finding_id=survivor_finding_id,
                    pre_update=dict(row),
                )
            )

    return actions, blockers


async def plan_capa_remediation(
    db: Any,
    *,
    soft_hits: Sequence[SoftLinkHit],
    finding_matches: Sequence[FindingMatch],
    expect_ids: Optional[Sequence[int]],
) -> tuple[list[CapaReassignAction], list[str]]:
    """Plan CAPA source_id reassignments. Read-only. No withdraw path."""
    blockers: list[str] = []
    hits = [hit for hit in soft_hits if hit.table == "capa_actions"]
    capa_ids = [int(row_id) for hit in hits for row_id in hit.row_ids]
    rows = await _load_capa_rows(db, capa_ids=capa_ids)

    found_ids = sorted(int(row["id"]) for row in rows)
    if expect_ids is not None:
        expected = sorted(int(value) for value in expect_ids)
        if found_ids != expected:
            blockers.append(
                f"--expect-capa-action set {expected} does not equal the CAPAs referencing "
                f"doomed findings {found_ids}. Name every id exactly — a subset or "
                "superset means the operator and the database disagree"
            )

    match_by_doomed = {match.doomed_id: match for match in finding_matches}
    # Projected (tenant_id, source_id) occupancy after reassignment.
    projected: dict[tuple[Any, Any], int] = {}
    # Existing CAPAs already on survivor findings (queried).
    survivor_ids = sorted({match.survivor_id for match in finding_matches if match.survivor_id})
    if survivor_ids:
        placeholders = ", ".join(f":sid_{index}" for index in range(len(survivor_ids)))
        params = {f"sid_{index}": sid for index, sid in enumerate(survivor_ids)}
        existing = (
            (
                await db.execute(
                    sa.text(
                        "SELECT id, tenant_id, source_id FROM capa_actions "
                        "WHERE LOWER(CAST(source_type AS TEXT)) = 'audit_finding' "
                        f"AND source_id IN ({placeholders})"  # noqa: S608
                    ),
                    params,
                )
            )
            .mappings()
            .all()
        )
        for row in existing:
            projected[(row.get("tenant_id"), int(row["source_id"]))] = int(row["id"])

    actions: list[CapaReassignAction] = []
    for row in sorted(rows, key=lambda item: int(item["id"])):
        old_source_id = int(row["source_id"])
        match = match_by_doomed.get(old_source_id)
        if match is None or match.outcome == "UNMAPPABLE":
            blockers.append(
                f"capa_actions#{row['id']} ({row.get('reference_number')}) points at doomed "
                f"finding {old_source_id} which has no matching survivor finding. "
                "There is no CAPA withdraw in this script — withdraw or re-source it "
                "through the CAPA process, then re-run the dry run"
            )
            continue
        if match.outcome == "AMBIGUOUS":
            continue
        assert match.survivor_id is not None
        key = (row.get("tenant_id"), match.survivor_id)
        occupant = projected.get(key)
        if occupant is not None and occupant != int(row["id"]):
            blockers.append(
                f"capa_actions#{row['id']} and capa_actions#{occupant} would both point at "
                f"survivor finding {match.survivor_id} after reassignment; the "
                "(tenant_id, source_id) unique rule allows only one. Resolve by hand"
            )
            continue
        projected[key] = int(row["id"])
        actions.append(
            CapaReassignAction(
                capa_id=int(row["id"]),
                old_source_id=old_source_id,
                new_source_id=match.survivor_id,
                reference_number=row.get("reference_number"),
                pre_update=dict(row),
            )
        )
    return actions, blockers


async def plan_remediation(
    db: Any,
    *,
    soft_hits: Sequence[SoftLinkHit],
    doomed_roots: Sequence[dict[str, Any]],
    doomed_findings: Sequence[dict[str, Any]],
    survivor_references: Sequence[str],
    doomed_references: Sequence[str],
    tenant_id: Optional[int],
    register: Any,
    remap_evidence: bool,
    expect_evidence_links: Optional[int],
    withdraw_unmappable_evidence: bool,
    reassign_capa: bool,
    expect_capa_ids: Optional[Sequence[int]],
) -> RemediationPlan:
    """Build the full remediation plan. Read-only."""
    plan = RemediationPlan()

    survivors, auth_blockers = await resolve_named_survivors(
        db,
        survivor_references=list(survivor_references),
        doomed_references=list(doomed_references),
        tenant_id=tenant_id,
    )
    plan.blockers.extend(auth_blockers)
    plan.named_survivors = [
        {
            "id": row["id"],
            "reference": row.get("reference_number"),
            "title": row.get("title"),
            "status": str(row.get("status")),
            "score_percentage": row.get("score_percentage"),
            "created_at": row.get("created_at"),
        }
        for row in survivors
    ]

    if survivor_references and not auth_blockers and register is not None:
        corroboration, corr_blockers = await corroborate_survivors(
            db, doomed=doomed_roots, survivors=survivors, register=register
        )
        plan.corroboration = corroboration
        plan.blockers.extend(corr_blockers)

    if not survivors:
        if remap_evidence or reassign_capa:
            plan.blockers.append(
                "--remap-evidence-links / --reassign-capa-to-survivor require "
                "--survivor-reference so the script knows which audit to repoint at"
            )
        return plan

    survivor_run_ids = [int(row["id"]) for row in survivors]
    matches, match_blockers = await match_findings(
        db,
        doomed_findings=doomed_findings,
        survivor_run_ids=survivor_run_ids,
        tenant_id=tenant_id,
    )
    plan.finding_matches = matches
    plan.blockers.extend(match_blockers)

    if remap_evidence:
        evidence_actions, evidence_blockers = await plan_evidence_remediation(
            db,
            soft_hits=soft_hits,
            finding_matches=matches,
            survivor_run_id=survivor_run_ids[0] if len(survivor_run_ids) == 1 else None,
            withdraw_unmappable=withdraw_unmappable_evidence,
            expect_count=expect_evidence_links,
        )
        if expect_evidence_links is None:
            live = sum(1 for action in evidence_actions if action.disposition != "RETAIN_SOFT_DELETED")
            # Also count rows that produced blockers rather than actions.
            evidence_hit_ids = {
                row_id for hit in soft_hits if hit.table == "compliance_evidence_links" for row_id in hit.row_ids
            }
            if evidence_hit_ids and expect_evidence_links is None:
                plan.blockers.append(
                    f"--remap-evidence-links requires --expect-evidence-links N so a human "
                    f"confirms the live hit count (currently {live} actionable / "
                    f"{len(evidence_hit_ids)} soft-link hit id(s)). Re-run passing that number"
                )
        plan.evidence_actions = evidence_actions
        plan.blockers.extend(evidence_blockers)
        # For multi-survivor cases, audit_run-level CEL needs an explicit single target.
        if (
            any(hit.entity_type == "audit_run" for hit in soft_hits if hit.table == "compliance_evidence_links")
            and len(survivor_run_ids) != 1
        ):
            plan.blockers.append(
                "compliance_evidence_links includes entity_type='audit_run' rows, but "
                f"{len(survivor_run_ids)} --survivor-reference values were given; name exactly "
                "one so the script knows which run id to repoint at"
            )

    if reassign_capa:
        if expect_capa_ids is None:
            capa_hit_ids = sorted(
                int(row_id) for hit in soft_hits if hit.table == "capa_actions" for row_id in hit.row_ids
            )
            plan.blockers.append(
                "--reassign-capa-to-survivor requires --expect-capa-action ID for every CAPA "
                f"referencing a doomed finding (currently {capa_hit_ids}). Name each id explicitly"
            )
        capa_actions, capa_blockers = await plan_capa_remediation(
            db,
            soft_hits=soft_hits,
            finding_matches=matches,
            expect_ids=expect_capa_ids,
        )
        plan.capa_actions = capa_actions
        plan.blockers.extend(capa_blockers)

    # Coverage check: every remediable soft-hit row id must appear in an action
    # (or already be soft-deleted / blocked). Gaps mean deferral dropped a refusal.
    if remap_evidence:
        covered = {action.link_id for action in plan.evidence_actions}
        for hit in soft_hits:
            if hit.table != "compliance_evidence_links":
                continue
            missing = [row_id for row_id in hit.row_ids if int(row_id) not in covered]
            if missing and not any("compliance_evidence_links#" in blocker for blocker in plan.blockers):
                # Ambiguous matches leave rows uncovered but already blocked above.
                if any(match.outcome == "AMBIGUOUS" for match in matches):
                    continue
                plan.blockers.append(
                    f"remediation plan does not cover compliance_evidence_links row ids "
                    f"{missing}; refusing rather than leaving them dangling"
                )

    if reassign_capa and expect_capa_ids is not None:
        covered = {action.capa_id for action in plan.capa_actions}
        for hit in soft_hits:
            if hit.table != "capa_actions":
                continue
            missing = [int(row_id) for row_id in hit.row_ids if int(row_id) not in covered]
            if missing and not plan.blockers:
                plan.blockers.append(f"remediation plan does not cover capa_actions row ids {missing}")

    return plan


async def apply_remediation(db: Any, plan: RemediationPlan) -> dict[str, int]:
    """Apply CEL/CAPA remediations. Does not commit."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    counts = {
        "compliance_evidence_links_remapped": 0,
        "compliance_evidence_links_withdrawn": 0,
        "capa_actions_reassigned": 0,
    }

    cel_columns = await _table_columns(db, "compliance_evidence_links")
    has_updated_at = "updated_at" in cel_columns
    has_deleted_at = "deleted_at" in cel_columns

    for action in plan.evidence_actions:
        if action.disposition == "REMAP":
            set_clause = "entity_id = :new_entity_id"
            params: dict[str, Any] = {
                "new_entity_id": action.new_entity_id,
                "link_id": action.link_id,
            }
            if has_updated_at:
                set_clause += ", updated_at = :now"
                params["now"] = now
            where = "id = :link_id"
            if has_deleted_at:
                where += " AND deleted_at IS NULL"
            result = await db.execute(
                sa.text(f"UPDATE compliance_evidence_links SET {set_clause} WHERE {where}"),  # noqa: S608
                params,
            )
            if (result.rowcount or 0) != 1:
                raise RuntimeError(
                    f"REMAP compliance_evidence_links#{action.link_id} affected " f"{result.rowcount} rows, expected 1"
                )
            counts["compliance_evidence_links_remapped"] += 1
        elif action.disposition in {"WITHDRAW_REDUNDANT", "WITHDRAW_UNMAPPABLE"}:
            if not has_deleted_at:
                raise RuntimeError("compliance_evidence_links has no deleted_at column; cannot soft-delete")
            set_clause = "deleted_at = :now"
            params = {"now": now, "link_id": action.link_id}
            if has_updated_at:
                set_clause += ", updated_at = :now"
            result = await db.execute(
                sa.text(
                    f"UPDATE compliance_evidence_links SET {set_clause} "  # noqa: S608
                    "WHERE id = :link_id AND deleted_at IS NULL"
                ),
                params,
            )
            if (result.rowcount or 0) != 1:
                raise RuntimeError(
                    f"WITHDRAW compliance_evidence_links#{action.link_id} affected "
                    f"{result.rowcount} rows, expected 1"
                )
            counts["compliance_evidence_links_withdrawn"] += 1

    for capa_action in plan.capa_actions:
        result = await db.execute(
            sa.text(
                "UPDATE capa_actions SET source_id = :new_source_id WHERE id = :capa_id "
                "AND LOWER(CAST(source_type AS TEXT)) = 'audit_finding' "
                "AND source_id = :old_source_id"
            ),
            {
                "new_source_id": capa_action.new_source_id,
                "capa_id": capa_action.capa_id,
                "old_source_id": capa_action.old_source_id,
            },
        )
        if (result.rowcount or 0) != 1:
            raise RuntimeError(
                f"REASSIGN capa_actions#{capa_action.capa_id} affected {result.rowcount} rows, expected 1"
            )
        counts["capa_actions_reassigned"] += 1

    return counts


async def verify_remediation(
    db: Any,
    *,
    doomed_finding_ids: Sequence[int],
    doomed_run_ids: Sequence[int],
    remediation: RemediationPlan,
) -> None:
    """Prove soft refs no longer point at doomed rows. Raises RuntimeError on failure."""
    if doomed_finding_ids:
        placeholders = ", ".join(f":fid_{index}" for index in range(len(doomed_finding_ids)))
        finding_params: dict[str, Any] = {
            f"fid_{index}": str(finding_id) for index, finding_id in enumerate(doomed_finding_ids)
        }
        columns = await _table_columns(db, "compliance_evidence_links")
        if columns:
            where_deleted = "AND deleted_at IS NULL" if "deleted_at" in columns else ""
            residual = (
                (
                    await db.execute(
                        sa.text(
                            "SELECT id FROM compliance_evidence_links "
                            "WHERE LOWER(CAST(entity_type AS TEXT)) = 'audit_finding' "
                            f"AND entity_id IN ({placeholders}) {where_deleted}"  # noqa: S608
                        ),
                        finding_params,
                    )
                )
                .scalars()
                .all()
            )
            if residual:
                raise RuntimeError(f"live compliance_evidence_links still point at doomed findings: {list(residual)}")

        capa_params: dict[str, Any] = {
            f"sid_{index}": finding_id for index, finding_id in enumerate(doomed_finding_ids)
        }
        capa_placeholders = ", ".join(f":sid_{index}" for index in range(len(doomed_finding_ids)))
        if await _table_columns(db, "capa_actions"):
            residual_capa = (
                (
                    await db.execute(
                        sa.text(
                            "SELECT id FROM capa_actions "
                            "WHERE LOWER(CAST(source_type AS TEXT)) = 'audit_finding' "
                            f"AND source_id IN ({capa_placeholders})"  # noqa: S608
                        ),
                        capa_params,
                    )
                )
                .scalars()
                .all()
            )
            if residual_capa:
                raise RuntimeError(f"capa_actions still point at doomed findings: {list(residual_capa)}")

    if doomed_run_ids:
        columns = await _table_columns(db, "compliance_evidence_links")
        if columns:
            placeholders = ", ".join(f":rid_{index}" for index in range(len(doomed_run_ids)))
            run_params: dict[str, Any] = {f"rid_{index}": str(run_id) for index, run_id in enumerate(doomed_run_ids)}
            where_deleted = "AND deleted_at IS NULL" if "deleted_at" in columns else ""
            residual = (
                (
                    await db.execute(
                        sa.text(
                            "SELECT id FROM compliance_evidence_links "
                            "WHERE LOWER(CAST(entity_type AS TEXT)) = 'audit_run' "
                            f"AND entity_id IN ({placeholders}) {where_deleted}"  # noqa: S608
                        ),
                        run_params,
                    )
                )
                .scalars()
                .all()
            )
            if residual:
                raise RuntimeError(f"live compliance_evidence_links still point at doomed runs: {list(residual)}")

    # Duplicate live CEL keys among remapped targets.
    remapped_targets = sorted(
        {
            action.new_entity_id
            for action in remediation.evidence_actions
            if action.disposition == "REMAP" and action.new_entity_id is not None
        }
    )
    if remapped_targets:
        placeholders = ", ".join(f":eid_{index}" for index in range(len(remapped_targets)))
        remap_params: dict[str, Any] = {f"eid_{index}": entity_id for index, entity_id in enumerate(remapped_targets)}
        rows = (
            (
                await db.execute(
                    sa.text(
                        "SELECT tenant_id, entity_type, entity_id, clause_id, cover_kind, "
                        "COUNT(*) AS n FROM compliance_evidence_links "
                        f"WHERE entity_id IN ({placeholders}) AND deleted_at IS NULL "  # noqa: S608
                        "GROUP BY tenant_id, entity_type, entity_id, clause_id, cover_kind "
                        "HAVING COUNT(*) > 1"
                    ),
                    remap_params,
                )
            )
            .mappings()
            .all()
        )
        if rows:
            raise RuntimeError(f"duplicate live CEL keys after remap: {[dict(row) for row in rows]}")

    # Duplicate CAPA (tenant_id, source_id) among reassigned set.
    new_sources = sorted({action.new_source_id for action in remediation.capa_actions})
    if new_sources:
        placeholders = ", ".join(f":sid_{index}" for index in range(len(new_sources)))
        capa_dup_params: dict[str, Any] = {f"sid_{index}": source_id for index, source_id in enumerate(new_sources)}
        rows = (
            (
                await db.execute(
                    sa.text(
                        "SELECT tenant_id, source_id, COUNT(*) AS n FROM capa_actions "
                        "WHERE LOWER(CAST(source_type AS TEXT)) = 'audit_finding' "
                        f"AND source_id IN ({placeholders}) "  # noqa: S608
                        "GROUP BY tenant_id, source_id HAVING COUNT(*) > 1"
                    ),
                    capa_dup_params,
                )
            )
            .mappings()
            .all()
        )
        if rows:
            raise RuntimeError(f"duplicate CAPA source assignments after reassign: {[dict(row) for row in rows]}")
