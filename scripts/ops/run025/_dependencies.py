"""Foreign-key facts needed before deleting a row, read from the live database.

Deleting an orphaned case is only safe if you know what points at it. The model
files are not a reliable source for that: ``ondelete`` is a database-side
behaviour, this repository already demonstrates that models and schema disagree,
and a cascade rule that exists in the database but not the model will still fire.
So every fact here is reflected from the database the script is actually pointed
at, via the SQLAlchemy inspector, which keeps the same code path working against
SQLite in tests.

The three behaviours that matter, and why each is a refusal rather than a warning:

``CASCADE``
    Deleting the parent silently deletes the child. If that child is not itself
    scheduled for deletion, the operation removes more than was reviewed. In a
    register under ISO 9001/45001 that is destruction of a record nobody approved.

``SET NULL`` / ``SET DEFAULT``
    Deleting the parent silently *mutates* a row outside the reviewed set. Quieter
    than a cascade and harder to notice afterwards, because row counts do not move.

``NO ACTION`` / ``RESTRICT``
    Deleting the parent fails. Better to say so during the dry run than to have a
    statutory reference — a RIDDOR submission, say — abort the operator's session
    halfway through.

Identifiers interpolated into SQL here come from the inspector, i.e. from the
database's own catalogue, never from argv.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Optional, Sequence

import sqlalchemy as sa

#: ``ondelete`` values that destroy the referencing row along with its parent.
DESTRUCTIVE = frozenset({"CASCADE"})
#: ``ondelete`` values that quietly rewrite the referencing row.
MUTATING = frozenset({"SET NULL", "SET DEFAULT"})

RowKey = tuple[str, int]


@dataclass(frozen=True)
class InboundRef:
    """One foreign key pointing *at* a table we intend to delete from."""

    constraint: str
    child_table: str
    child_column: str
    parent_table: str
    on_delete: str

    @property
    def deletes_child(self) -> bool:
        return self.on_delete in DESTRUCTIVE

    @property
    def mutates_child(self) -> bool:
        return self.on_delete in MUTATING

    @property
    def blocks_parent(self) -> bool:
        return not self.deletes_child and not self.mutates_child

    def describe(self) -> str:
        return f"{self.child_table}.{self.child_column} -> {self.parent_table} ON DELETE {self.on_delete}"


def _normalise_on_delete(options: dict[str, Any] | None) -> str:
    raw = (options or {}).get("ondelete")
    if not raw:
        # PostgreSQL and SQLite both default to NO ACTION when the clause is absent.
        return "NO ACTION"
    return str(raw).strip().upper()


def inbound_refs(sync_session: Any, parents: Sequence[str]) -> dict[str, list[InboundRef]]:
    """Every foreign key in the database that references one of ``parents``.

    Scans all tables rather than only the parents, because inbound references are
    declared on the child side and there is no way to enumerate them from the
    parent.
    """
    inspector = sa.inspect(sync_session.get_bind())
    wanted = set(parents)
    found: dict[str, list[InboundRef]] = {parent: [] for parent in wanted}

    for child_table in inspector.get_table_names():
        for fk in inspector.get_foreign_keys(child_table):
            parent = fk.get("referred_table")
            if parent not in wanted:
                continue
            for column in fk.get("constrained_columns") or []:
                found[parent].append(
                    InboundRef(
                        constraint=fk.get("name") or f"(unnamed on {child_table})",
                        child_table=child_table,
                        child_column=column,
                        parent_table=parent,
                        on_delete=_normalise_on_delete(fk.get("options")),
                    )
                )
    return found


def single_column_primary_keys(sync_session: Any, tables: Sequence[str]) -> dict[str, Optional[str]]:
    """Single-column primary key per table, or ``None`` when there isn't one.

    A row can only be addressed individually — deleted by key, recorded in a
    manifest by key, re-verified by key — if it has one of these. A table without
    one has to be reported, never swept with a predicate, so "no key" is a normal
    answer that the caller is expected to turn into a refusal.
    """
    inspector = sa.inspect(sync_session.get_bind())
    present = set(inspector.get_table_names())
    keys: dict[str, Optional[str]] = {}
    for table in tables:
        if table not in present:
            keys[table] = None
            continue
        columns = inspector.get_pk_constraint(table).get("constrained_columns") or []
        keys[table] = columns[0] if len(columns) == 1 else None
    return keys


async def dependent_ids(db: Any, ref: InboundRef, parent_id: int, *, key_column: str = "id") -> list[Any]:
    """Primary keys of rows referencing ``parent_id`` through ``ref``.

    ``key_column`` defaults to ``id`` because every table in this schema happens to
    have one, but it is a parameter rather than an assumption: a junction table
    added later with a composite key would otherwise make this raise
    ``UndefinedColumn`` from inside a dependency scan, which reads like a broken
    script rather than the "I cannot check this table" it actually is. Callers
    resolve the real key with :func:`single_column_primary_keys` first.
    """
    sql = sa.text(  # noqa: S608
        f"SELECT {key_column} FROM {ref.child_table} WHERE {ref.child_column} = :parent_id ORDER BY {key_column}"
    )
    return list((await db.execute(sql, {"parent_id": parent_id})).scalars().all())


def deletion_order(candidates: Iterable[RowKey], edges: Iterable[tuple[RowKey, RowKey]]) -> list[RowKey]:
    """Order rows so a child is always deleted before the parent it references.

    ``edges`` are ``(child, parent)`` pairs. Enforcing the order in code rather
    than documenting it means an operator cannot get it wrong, and it means the
    delete never depends on a cascade firing to succeed — if a cascade would have
    removed something unreviewed, the caller has already refused by then.

    Raises on a cycle rather than picking an arbitrary order. A cycle among rows
    we intend to delete means the schema permits mutual references, and that
    needs a human to look at it, not a heuristic.
    """
    remaining = set(candidates)
    # For each row, the rows inside the set that reference it. A row may only be
    # deleted once that set is empty, which puts children ahead of parents.
    referenced_by: dict[RowKey, set[RowKey]] = {row: set() for row in remaining}
    for child, parent in edges:
        if child in remaining and parent in remaining:
            referenced_by[parent].add(child)

    ordered: list[RowKey] = []
    while remaining:
        ready = sorted(row for row in remaining if not (referenced_by[row] & remaining))
        if not ready:
            raise RuntimeError(f"circular foreign-key references among rows to delete: {sorted(remaining)}")
        for row in ready:
            ordered.append(row)
            remaining.discard(row)
    return ordered
