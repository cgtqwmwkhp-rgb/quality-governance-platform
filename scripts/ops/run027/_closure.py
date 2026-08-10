"""Everything that belongs to an audit run, found from the database rather than assumed.

Purging an audit "as if it never existed" needs an answer to a question the models
cannot be trusted to give: what actually points at this row? Two independent
mechanisms are needed, because this schema links records in two different ways and
only one of them is a foreign key.

Foreign keys — walked transitively
----------------------------------
:func:`descendant_closure` starts at the doomed ``audit_runs`` rows and repeatedly
asks the database's own catalogue what references the tables it has reached, so a
grandchild is found without anybody listing it. That matters here: an imported
audit owns ``external_audit_import_jobs`` rows, those own
``external_audit_import_drafts`` and ``external_audit_records`` rows, and a
hand-written table list would have stopped one level short.

Reflection rather than the model files, for the reason
``scripts/ops/run025/_dependencies.py`` sets out at length: ``ondelete`` is
database-side behaviour, this repository has documented cases of models and schema
disagreeing, and a cascade that exists only in the database will still fire.

Cascades are not relied on to do the deleting. ``external_audit_records.audit_run_id``
has no ``ondelete`` clause at all, so it is ``NO ACTION``: deleting an imported
audit run and trusting the cascade does not purge the record, it raises a foreign
key violation and rolls the whole thing back. Every row is therefore deleted
explicitly, children first, in an order computed by
``scripts.ops.run025._dependencies.deletion_order``.

Discovery is not permission
---------------------------
Finding a referencing row does not settle what to do with it. ``audit_responses``
is part of the audit and should go with it; ``job_cell_links`` is production job
data that merely mentions the audit and must not. So reflection supplies the
graph and :data:`AUDIT_RUN_CHILD_DISPOSITIONS` — reviewed by a human, table by
table — supplies the decision.

A table found in the graph with no entry in that map is a **refusal**, not a
default. Both available defaults are unacceptable: treat it as purgeable and the
script destroys records nobody classified, treat it as detachable and it silently
leaves dangling references. Refusing means the next release that adds a table
referencing ``audit_runs`` stops this script until somebody classifies it, which
is the only outcome that keeps the reviewed list honest as the schema moves.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional, Sequence

import sqlalchemy as sa

from scripts.ops.run025._dependencies import InboundRef, RowKey, dependent_ids, inbound_refs, single_column_primary_keys


class Disposition(str, Enum):
    """What a human decided should happen to rows in a referencing table.

    ``DETACH`` only applies to foreign keys, since there is no column to null on a
    soft reference. ``RETAIN`` only applies to soft references, since a foreign key
    cannot be left pointing at a deleted row.
    """

    #: The row is part of the audit record. Delete it.
    PURGE = "purge"
    #: The row is a separate record that merely references the audit. Leave it,
    #: and report the ``SET NULL`` the delete will perform on it.
    DETACH = "detach"
    #: The row references the purged row and is deliberately left doing so, because
    #: outliving its subject is the point of it. Reported, never a defect.
    RETAIN = "retain"
    #: The row must not be destroyed or silently rewritten by this script.
    REFUSE = "refuse"


@dataclass(frozen=True)
class ChildDisposition:
    table: str
    disposition: Disposition
    rationale: str


def _d(table: str, disposition: Disposition, rationale: str) -> tuple[str, ChildDisposition]:
    return table, ChildDisposition(table=table, disposition=disposition, rationale=rationale)


#: Reviewed, table by table, against ``src/domain/models`` on 2026-08-10.
#:
#: The rationale is stored rather than described in a comment because it is the
#: thing an auditor asks for: not "was this row deleted" but "who decided it could
#: be, and on what grounds". It is copied into the manifest for that reason.
AUDIT_RUN_CHILD_DISPOSITIONS: dict[str, ChildDisposition] = dict(
    (
        _d(
            "audit_responses",
            Disposition.PURGE,
            "The answers given during this audit. They have no meaning apart from the run "
            "and are unique per (run_id, question_id), so they cannot be reattached elsewhere.",
        ),
        _d(
            "audit_findings",
            Disposition.PURGE,
            "Findings raised by this audit. A duplicate import's findings are themselves "
            "duplicates; leaving them would leave nonconformities attributed to an audit "
            "that no longer exists.",
        ),
        _d(
            "audit_finding_risks",
            Disposition.PURGE,
            "Junction rows only. Deleting them unlinks the finding from an enterprise risk; "
            "the risk row itself is untouched and is reported as collateral so a human can "
            "decide whether a risk escalated from a duplicate should also be withdrawn.",
        ),
        _d(
            "external_audit_import_jobs",
            Disposition.PURGE,
            "The OCR/import job that produced this run. Its idempotency key is unique on "
            "(audit_run_id, source_document_asset_id, source_checksum_sha256), so it belongs "
            "to exactly this run and keeping it would block a clean re-import of the same report.",
        ),
        _d(
            "external_audit_import_drafts",
            Disposition.PURGE,
            "Reviewable finding drafts belonging to the import job. Not a register in their "
            "own right; they exist only to be promoted into audit_findings.",
        ),
        _d(
            "external_audit_records",
            Disposition.PURGE,
            "The cross-scheme summary row for this import, which is what makes the duplicate "
            "visible on dashboards. Its FK carries no ondelete clause, so it must be deleted "
            "explicitly or it blocks the purge outright.",
        ),
        _d(
            "job_cell_links",
            Disposition.DETACH,
            "Production job-lifecycle data. It references the audit but is not part of it, and "
            "both FKs are SET NULL, so the link clears and the job cell survives.",
        ),
    )
)


@dataclass
class Closure:
    """The full reviewed effect of deleting a set of root rows."""

    #: Rows to delete, including the roots.
    purge_keys: set[RowKey] = field(default_factory=set)
    #: ``(child, parent)`` pairs, for ordering the delete children-first.
    edges: list[tuple[RowKey, RowKey]] = field(default_factory=list)
    #: One entry per referencing row found, whatever its disposition.
    found: list[dict[str, Any]] = field(default_factory=list)
    #: Rows outside the purge set whose FK column the delete will set to NULL.
    detached: list[dict[str, Any]] = field(default_factory=list)
    #: Reasons the purge must not proceed.
    blockers: list[str] = field(default_factory=list)
    #: Primary key column per table in :attr:`purge_keys`, reflected while walking.
    #:
    #: Every table in this schema happens to call it ``id``, but the snapshot and the
    #: delete are driven from this rather than from that assumption. A table whose key
    #: is named something else would otherwise be selected by the reflected key and
    #: then deleted by a hardcoded ``WHERE id = ...`` — which on PostgreSQL raises
    #: ``UndefinedColumn`` mid-purge, and on a table that happens to *have* an
    #: unrelated ``id`` column would delete the wrong row.
    key_columns: dict[str, str] = field(default_factory=dict)

    def rows_per_table(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for table, _row_id in self.purge_keys:
            counts[table] = counts.get(table, 0) + 1
        return dict(sorted(counts.items()))

    def ids_for(self, table: str) -> list[int]:
        return sorted(row_id for found_table, row_id in self.purge_keys if found_table == table)


def _record(ref: InboundRef, parent_id: Any, child_id: Any, disposition: str) -> dict[str, Any]:
    return {
        "child": f"{ref.child_table}#{child_id}",
        "parent": f"{ref.parent_table}#{parent_id}",
        "reference": ref.describe(),
        "constraint": ref.constraint,
        "on_delete": ref.on_delete,
        "disposition": disposition,
    }


def _apply_disposition(
    closure: Closure,
    *,
    ref: InboundRef,
    parent_table: str,
    parent_id: Any,
    child_ids: list[Any],
    rule: Optional[ChildDisposition],
    key_column: str,
) -> list[Any]:
    """Record the effect of one foreign key on one parent row.

    Returns the child ids that join the purge set, so the caller can queue them for
    their own dependency walk. Everything else — refusals, ``SET NULL`` notes, the
    per-row inventory — is appended to ``closure`` in place.
    """
    if rule is None:
        closure.blockers.append(
            f"{len(child_ids)} row(s) in {ref.child_table} reference {parent_table}#{parent_id} "
            f"via {ref.describe()}, and no reviewed disposition exists for that table. "
            "Classify it in AUDIT_RUN_CHILD_DISPOSITIONS before purging: deleting it unreviewed "
            "would destroy records nobody approved, and leaving it would orphan references to a "
            "row that no longer exists"
        )
        closure.found.extend(_record(ref, parent_id, child_id, "UNCLASSIFIED") for child_id in child_ids)
        return []

    closure.found.extend(_record(ref, parent_id, child_id, rule.disposition.value) for child_id in child_ids)

    if rule.disposition is Disposition.REFUSE:
        closure.blockers.append(
            f"{len(child_ids)} row(s) in {ref.child_table} reference {parent_table}#{parent_id} "
            f"and that table is marked must-not-touch: {rule.rationale}"
        )
        return []

    if rule.disposition is Disposition.DETACH:
        # A detach is only actually a detach if the database will null the column. If
        # the foreign key cascades, the "surviving" row is destroyed instead, and the
        # classification is wrong rather than merely optimistic.
        if ref.deletes_child:
            closure.blockers.append(
                f"{ref.child_table} is classified detach, but {ref.describe()} would DELETE "
                f"{len(child_ids)} row(s) by cascade. The classification and the schema disagree; "
                "one of them is wrong"
            )
            return []
        if ref.blocks_parent:
            closure.blockers.append(
                f"{ref.child_table} is classified detach, but {ref.describe()} neither cascades nor "
                f"nulls, so {len(child_ids)} row(s) will make the delete fail. Clear the reference "
                "by hand first"
            )
            return []
        closure.detached.extend(
            {
                "row": f"{ref.child_table}#{child_id}",
                "column_set_to_null": f"{ref.child_table}.{ref.child_column}",
                "was_pointing_at": f"{parent_table}#{parent_id}",
                "rationale": rule.rationale,
            }
            for child_id in child_ids
        )
        return []

    closure.key_columns[ref.child_table] = key_column
    queued: list[Any] = []
    for child_id in child_ids:
        child_key: RowKey = (ref.child_table, child_id)
        closure.edges.append((child_key, (parent_table, parent_id)))
        if child_key not in closure.purge_keys:
            closure.purge_keys.add(child_key)
            queued.append(child_id)
    return queued


async def descendant_closure(
    db: Any,
    *,
    roots: Sequence[RowKey],
    dispositions: Optional[dict[str, ChildDisposition]] = None,
) -> Closure:
    """Every row that must be deleted so ``roots`` can be, or a reason it cannot.

    Read-only. Breadth-first over reflected foreign keys: each table added to the
    closure is itself interrogated for inbound references, which is what reaches
    ``external_audit_records`` two levels below the audit run.
    """
    policy = AUDIT_RUN_CHILD_DISPOSITIONS if dispositions is None else dispositions
    closure = Closure(purge_keys=set(roots))

    # Tables whose primary key we have already resolved, and rows whose children we
    # have already looked for. Without the latter a diamond in the FK graph would
    # re-walk the same subtree, and a cycle would not terminate at all.
    primary_keys: dict[str, Optional[str]] = {}
    expanded: set[RowKey] = set()
    unaddressable: set[str] = set()

    frontier: dict[str, list[Any]] = {}
    for table, row_id in roots:
        frontier.setdefault(table, []).append(row_id)

    # The root tables' own keys, so the map covers every table in purge_keys and not
    # only the children discovered below.
    for table in frontier:
        resolved_root = await db.run_sync(single_column_primary_keys, [table])
        key = resolved_root[table]
        primary_keys[table] = key
        if key is None:
            closure.blockers.append(
                f"{table} has no single-column primary key, so its rows cannot be individually " "deleted or recorded"
            )
        else:
            closure.key_columns[table] = key

    while frontier:
        next_frontier: dict[str, list[Any]] = {}
        refs_by_parent = await db.run_sync(inbound_refs, sorted(frontier))

        for parent_table, parent_ids in sorted(frontier.items()):
            for ref in refs_by_parent.get(parent_table, []):
                if ref.child_table not in primary_keys:
                    resolved = await db.run_sync(single_column_primary_keys, [ref.child_table])
                    primary_keys[ref.child_table] = resolved[ref.child_table]
                key_column = primary_keys[ref.child_table]

                if key_column is None:
                    # No single-column key, so its rows cannot be addressed
                    # individually — not deleted by key, not recorded in the
                    # manifest by key, not re-verified afterwards. Reported once
                    # per table rather than guessed at.
                    if ref.child_table not in unaddressable:
                        unaddressable.add(ref.child_table)
                        closure.blockers.append(
                            f"{ref.child_table} references {parent_table} via {ref.describe()} but has no "
                            "single-column primary key, so its rows cannot be individually deleted or "
                            "recorded. Resolve by hand"
                        )
                    continue

                for parent_id in parent_ids:
                    child_ids = await dependent_ids(db, ref, parent_id, key_column=key_column)
                    if not child_ids:
                        continue

                    for child_id in _apply_disposition(
                        closure,
                        ref=ref,
                        parent_table=parent_table,
                        parent_id=parent_id,
                        child_ids=child_ids,
                        rule=policy.get(ref.child_table),
                        key_column=key_column,
                    ):
                        next_frontier.setdefault(ref.child_table, []).append(child_id)

            expanded.update((parent_table, parent_id) for parent_id in parent_ids)

        # Only rows we have not already expanded, so a diamond does not re-walk.
        frontier = {
            table: [row_id for row_id in ids if (table, row_id) not in expanded] for table, ids in next_frontier.items()
        }
        frontier = {table: ids for table, ids in frontier.items() if ids}

    return closure


async def row_snapshots(
    db: Any,
    keys: Sequence[RowKey],
    key_columns: dict[str, str],
) -> dict[str, list[dict[str, Any]]]:
    """Every column of every row about to be deleted, grouped by table.

    A projection would be smaller and useless: this is the only remaining record of
    what was destroyed, so it has to be complete enough to reconstruct the rows from.
    Table and key names come from the reflected closure; ids are bound parameters.
    """
    by_table: dict[str, list[Any]] = {}
    for table, row_id in keys:
        by_table.setdefault(table, []).append(row_id)

    out: dict[str, list[dict[str, Any]]] = {}
    for table, ids in sorted(by_table.items()):
        primary_key = key_columns[table]
        placeholders = ", ".join(f":id_{index}" for index in range(len(ids)))
        params = {f"id_{index}": row_id for index, row_id in enumerate(ids)}
        rows = (
            (
                await db.execute(
                    sa.text(
                        f"SELECT * FROM {table} WHERE {primary_key} IN ({placeholders}) "  # noqa: S608
                        f"ORDER BY {primary_key}"
                    ),
                    params,
                )
            )
            .mappings()
            .all()
        )
        out[table] = [dict(row) for row in rows]
    return out
