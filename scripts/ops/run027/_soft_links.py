"""References to an audit that are not foreign keys, and so are invisible to reflection.

:mod:`scripts.ops.run027._closure` walks foreign keys, and would leave this schema's
second linking mechanism entirely unexamined. Two forms of it exist:

Polymorphic ``entity_type`` / ``entity_id``
    ``notifications``, ``assignments`` and the hash-chained ``audit_log_entries``
    all address a record by a type name and a *stringified* id. There is no
    constraint, so deleting ``audit_findings#412`` leaves every row saying
    ``('audit_finding', '412')`` behind, pointing at nothing. Nothing fails; the
    application simply starts rendering links to a record that is not there.

Typed ``source_type`` / ``source_id``
    ``capa_actions`` records where a corrective action came from with an enum and a
    bare integer — the ``ck_capa_actions_gt_source_id`` check constraint requires
    ``source_id`` when ``source_type`` is ``audit_finding``, but no foreign key
    enforces that it resolves. A CAPA raised from a finding therefore survives the
    finding silently.

The tables are found by reflection, not listed here: any table carrying an
``entity_type``/``entity_id`` pair is interrogated. Eighteen such tables exist
today, only some of them ever hold audit rows, and which ones is a question about
data rather than about code — so it is asked of the database. What is listed here
is the *disposition*, for the same reason as in ``_closure``: discovery is not
permission, and a table found holding references with no reviewed decision
attached is a refusal rather than a default.

``audit_log_entries`` is the one table deliberately marked ``RETAIN``. It is an
append-only hash chain, and each entry's ``entry_hash`` is computed over the
previous one, so deleting the entries describing a purged audit does not tidy the
trail — it breaks verification for every entry written afterwards, and it destroys
the only evidence that the audit ever existed or that this purge happened. Those
rows are meant to survive their subject. The purge writes a new entry instead.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Sequence

import sqlalchemy as sa

from scripts.ops.run025._dependencies import RowKey
from scripts.ops.run027._closure import ChildDisposition, Disposition

#: ``entity_type`` strings that address a row in each purgeable table.
#:
#: Deliberately narrow. ``audit_finding`` is the only value any writer in ``src/``
#: actually uses, and ``audit_run`` is the canonical singular of the table, which is
#: what this package's own trail entries use.
#:
#: Wider guesses — ``audit``, ``finding``, ``auditrun`` — were tried and removed. A
#: hit here can *delete* a row, and these values live in an unconstrained free-text
#: column shared by every entity family in the schema, so a speculative alias that
#: happened to match another family's numeric id would destroy an unrelated record.
#: Missing a legacy alias leaves a dangling reference, which is a reporting gap;
#: inventing one loses data. The asymmetry decides it.
#:
#: Matching is exact and case-insensitive.
ENTITY_TYPE_ALIASES: dict[str, tuple[str, ...]] = {
    "audit_runs": ("audit_run",),
    "audit_findings": ("audit_finding",),
}

#: Non-FK references that use a column pair other than ``entity_type``/``entity_id``.
#: Reflection cannot infer these, so each is named.
TYPED_LINKS: tuple[tuple[str, str, str, str], ...] = (
    # (table, type column, id column, table the id points into)
    ("capa_actions", "source_type", "source_id", "audit_findings"),
)

#: How a human decided each soft-linking table should be treated.
SOFT_LINK_DISPOSITIONS: dict[str, ChildDisposition] = {
    "notifications": ChildDisposition(
        table="notifications",
        disposition=Disposition.PURGE,
        rationale=(
            "In-app delivery artefact. No reference number, no statutory role, and its only "
            "content is a link to the purged record, which would 404."
        ),
    ),
    "assignments": ChildDisposition(
        table="assignments",
        disposition=Disposition.PURGE,
        rationale=(
            "An allocation of work on a record that will not exist. Keeping it leaves somebody "
            "owning a finding nobody can open."
        ),
    ),
    "audit_log_entries": ChildDisposition(
        table="audit_log_entries",
        disposition=Disposition.RETAIN,
        rationale=(
            "Append-only hash chain. Entries are chained by entry_hash/previous_hash, so deleting "
            "these would break verification of every later entry and destroy the evidence that the "
            "audit existed and was purged. The trail is meant to outlive its subject."
        ),
    ),
    "ai_decision_logs": ChildDisposition(
        table="ai_decision_logs",
        disposition=Disposition.RETAIN,
        rationale=(
            "A record of what an automated system decided about this record and how confident it "
            "was. Like the audit trail, its value is in being the account of a decision that was "
            "taken, which does not stop being true when the subject is deleted."
        ),
    ),
    "capa_actions": ChildDisposition(
        table="capa_actions",
        disposition=Disposition.REFUSE,
        rationale=(
            "A corrective action is a governed register entry with its own CAPA reference number, "
            "owner, due date and verification history. It may have been worked, and its reference "
            "may already appear in an external auditor's notes. It must be withdrawn or reassigned "
            "to the surviving audit through its own process, not destroyed as a side effect of "
            "deduplicating an audit."
        ),
    ),
    "compliance_evidence_links": ChildDisposition(
        table="compliance_evidence_links",
        disposition=Disposition.REFUSE,
        rationale=(
            "This link is what makes an ISO clause count as covered. Removing it changes the "
            "tenant's stated compliance position, and it may be the only evidence covering that "
            "clause; leaving it dangling overstates coverage with evidence that no longer exists. "
            "Either outcome is a decision about a compliance claim, so a human repoints it at the "
            "surviving audit or withdraws it deliberately."
        ),
    ),
    # Classified REFUSE here while the *foreign keys* on the same table are DETACH in
    # AUDIT_RUN_CHILD_DISPOSITIONS, which looks contradictory and is not. The two
    # describe different columns with different guarantees: audit_run_id and
    # audit_finding_id are real foreign keys declared SET NULL, so the database clears
    # them and the job cell survives intact. The kind="app" entity_type/entity_id pair
    # is a hand-built link with no constraint behind it, so nothing clears it and the
    # job cell would keep offering somebody a link to a deleted audit.
    "job_cell_links": ChildDisposition(
        table="job_cell_links",
        disposition=Disposition.REFUSE,
        rationale=(
            "Production job-lifecycle data. Somebody deliberately linked a job cell to this audit, "
            "and unlike the audit_run_id foreign key on the same table this link has no ON DELETE "
            "behaviour to clear it. Repoint it at the surviving audit or remove it deliberately."
        ),
    ),
}


@dataclass(frozen=True)
class SoftLinkHit:
    """Rows in one table that reference one purged row without a foreign key."""

    table: str
    #: Resolved when the hit was found, and reused verbatim by
    #: :func:`delete_soft_links`. Re-reflecting it at delete time would let a table
    #: be selected under one key and deleted under another.
    key_column: str
    type_column: str
    id_column: str
    entity_type: str
    target: str
    row_ids: tuple[Any, ...]
    disposition: Disposition
    rationale: str

    def as_report(self) -> dict[str, Any]:
        return {
            "table": self.table,
            "matched_on": f"{self.type_column}={self.entity_type!r} AND {self.id_column}=<id>",
            "points_at": self.target,
            "row_count": len(self.row_ids),
            "row_ids": list(self.row_ids),
            "disposition": self.disposition.value,
            "rationale": self.rationale,
        }


def _polymorphic_tables(sync_session: Any) -> list[tuple[str, str]]:
    """Tables carrying an ``entity_type``/``entity_id`` pair, with their key column."""
    inspector = sa.inspect(sync_session.get_bind())
    out: list[tuple[str, str]] = []
    for table in inspector.get_table_names():
        columns = {column["name"] for column in inspector.get_columns(table)}
        if {"entity_type", "entity_id"} <= columns:
            keys = inspector.get_pk_constraint(table).get("constrained_columns") or []
            out.append((table, keys[0] if len(keys) == 1 else ""))
    return sorted(out)


def _id_is_text(sync_session: Any, table: str, column: str) -> bool:
    """Whether ``column`` stores ids as text.

    ``notifications.entity_id`` is ``VARCHAR(36)`` and ``capa_actions.source_id`` is
    ``INTEGER``. Binding an int against the former matches nothing on PostgreSQL
    rather than erroring, which would report "no notifications reference this
    audit" and be believed. So the parameter type is taken from the column.
    """
    inspector = sa.inspect(sync_session.get_bind())
    for info in inspector.get_columns(table):
        if info["name"] == column:
            return isinstance(info["type"], sa.String) or "CHAR" in str(info["type"]).upper()
    return True


async def _matching_ids(
    db: Any,
    *,
    table: str,
    key_column: str,
    type_column: str,
    id_column: str,
    entity_type: str,
    target_ids: Sequence[Any],
    id_is_text: bool,
) -> list[Any]:
    """Keys of rows in ``table`` whose soft reference resolves to a purged row."""
    placeholders = ", ".join(f":target_{index}" for index in range(len(target_ids)))
    params: dict[str, Any] = {"entity_type": entity_type}
    params.update({f"target_{index}": (str(value) if id_is_text else value) for index, value in enumerate(target_ids)})
    # Identifiers come from the inspector and module literals; values are bound.
    #
    # LOWER() because these are free-text markers written by a dozen call sites
    # rather than a constrained enum. CAST AS TEXT rather than AS VARCHAR because
    # ``capa_actions.source_type`` is a PostgreSQL enum and enum-to-varchar is not a
    # permitted cast there, while enum-to-text is; SQLite accepts TEXT too. The
    # ``ck_capa_actions_gt_source_id`` check constraint in ``capa.py`` casts the same
    # column the same way, for the same reason.
    return list(
        (
            await db.execute(
                sa.text(
                    f"SELECT {key_column} FROM {table} "  # noqa: S608
                    f"WHERE LOWER(CAST({type_column} AS TEXT)) = :entity_type "
                    f"AND {id_column} IN ({placeholders}) ORDER BY {key_column}"
                ),
                params,
            )
        )
        .scalars()
        .all()
    )


async def soft_link_hits(
    db: Any,
    *,
    purge_keys: Sequence[RowKey],
    dispositions: Optional[dict[str, ChildDisposition]] = None,
    remediable: frozenset[str] = frozenset(),
) -> tuple[list[SoftLinkHit], list[str]]:
    """Non-FK references into the purge set, and any reason they block the purge.

    Read-only. Returns ``(hits, blockers)``; a hit whose table has no reviewed
    disposition contributes a blocker, so an unclassified table cannot be swept or
    silently orphaned.

    ``remediable`` is the set of REFUSE tables the caller has opted to clear via
    :mod:`scripts.ops.run027._remediate`. Hits against those tables are still
    recorded with ``disposition=refuse`` — the disposition is never rewritten to
    ``purge``, because that would let :func:`delete_soft_links` destroy them —
    but the soft-link blocker is deferred. Ownership of covering every hit row id
    then passes to the remediation planner. An empty ``remediable`` set (the
    default) keeps behaviour byte-identical to the pre-remediation script.
    """
    policy = SOFT_LINK_DISPOSITIONS if dispositions is None else dispositions

    targets: dict[str, list[Any]] = {}
    for table, row_id in purge_keys:
        targets.setdefault(table, []).append(row_id)

    specs: list[tuple[str, str, str, str, str]] = []
    for table, key_column in await db.run_sync(_polymorphic_tables):
        specs.append((table, key_column, "entity_type", "entity_id", ""))
    reflected = {table for table, _key, _t, _i, _p in specs}
    for table, type_column, id_column, points_into in TYPED_LINKS:
        keys = await db.run_sync(lambda sync, name=table: _table_key(sync, name))
        if keys is None:
            continue
        specs.append((table, keys, type_column, id_column, points_into))

    hits: list[SoftLinkHit] = []
    blockers: list[str] = []
    unaddressable: set[str] = set()

    for table, key_column, type_column, id_column, points_into in specs:
        if not key_column:
            if table not in unaddressable:
                unaddressable.add(table)
                blockers.append(
                    f"{table} holds {type_column}/{id_column} references but has no single-column "
                    "primary key, so its rows cannot be individually reported or deleted. Resolve by hand"
                )
            continue

        id_is_text = await db.run_sync(lambda sync, t=table, c=id_column: _id_is_text(sync, t, c))

        # A typed link points into one known table; a polymorphic one could address
        # any of them, so every alias is tried.
        scoped = {points_into: targets.get(points_into, [])} if points_into else targets

        for target_table, row_ids in sorted(scoped.items()):
            if not row_ids:
                continue
            for alias in ENTITY_TYPE_ALIASES.get(target_table, ()):
                matched = await _matching_ids(
                    db,
                    table=table,
                    key_column=key_column,
                    type_column=type_column,
                    id_column=id_column,
                    entity_type=alias,
                    target_ids=row_ids,
                    id_is_text=id_is_text,
                )
                if not matched:
                    continue

                rule = policy.get(table)
                if rule is None:
                    blockers.append(
                        f"{len(matched)} row(s) in {table} reference {target_table} as "
                        f"{type_column}={alias!r}, and no reviewed disposition exists for that table. "
                        "Classify it in SOFT_LINK_DISPOSITIONS before purging: there is no foreign key "
                        "here, so the delete will neither cascade nor fail — it will just leave these "
                        "rows pointing at nothing"
                    )
                    continue

                hits.append(
                    SoftLinkHit(
                        table=table,
                        key_column=key_column,
                        type_column=type_column,
                        id_column=id_column,
                        entity_type=alias,
                        target=target_table,
                        row_ids=tuple(matched),
                        disposition=rule.disposition,
                        rationale=rule.rationale,
                    )
                )
                if rule.disposition is Disposition.REFUSE and table not in remediable:
                    blockers.append(
                        f"{len(matched)} row(s) in {table} reference {target_table} as "
                        f"{type_column}={alias!r} and that table is marked must-not-touch. "
                        f"{rule.rationale} Row ids: {list(matched)}"
                    )

    if reflected and "audit_log_entries" not in reflected:
        blockers.append(
            "audit_log_entries was not found among the reflected entity_type/entity_id tables. "
            "That is the hash-chained trail this purge is required to write to; refusing rather "
            "than proceeding without one"
        )

    return hits, blockers


def _table_key(sync_session: Any, table: str) -> Optional[str]:
    inspector = sa.inspect(sync_session.get_bind())
    if not inspector.has_table(table):
        return None
    keys = inspector.get_pk_constraint(table).get("constrained_columns") or []
    return keys[0] if len(keys) == 1 else ""


async def delete_soft_links(db: Any, hits: Sequence[SoftLinkHit]) -> dict[str, int]:
    """Delete the rows from hits marked ``PURGE``. Leaves every other disposition alone.

    Deletes by primary key only, using the keys recorded when the hit was found,
    rather than re-running the ``entity_type``/``entity_id`` predicate. Re-running it
    would delete whatever matches *now*, which is not necessarily what the operator
    read in the dry run.
    """
    deleted: dict[str, int] = {}
    for hit in hits:
        if hit.disposition is not Disposition.PURGE:
            continue
        placeholders = ", ".join(f":id_{index}" for index in range(len(hit.row_ids)))
        params = {f"id_{index}": row_id for index, row_id in enumerate(hit.row_ids)}
        result = await db.execute(
            sa.text(f"DELETE FROM {hit.table} WHERE {hit.key_column} IN ({placeholders})"),  # noqa: S608
            params,
        )
        deleted[hit.table] = deleted.get(hit.table, 0) + (result.rowcount or 0)
    return deleted
