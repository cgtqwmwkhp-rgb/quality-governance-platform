"""Constrain ``created_by_id`` / ``updated_by_id`` to ``users`` on 30 tables.

Revision ID: 20260902_attrib_fk
Revises: 20260902_attrib_cols
Create Date: 2026-09-02

Why this exists
---------------
``AuditTrailMixin`` declares::

    created_by_id: Mapped[Optional[int]] = mapped_column(nullable=True)
    updated_by_id: Mapped[Optional[int]] = mapped_column(nullable=True)

Two plain integers. No ``ForeignKey``. So every table that takes its attribution
columns from the mixin alone — rather than redeclaring ``created_by_id`` with an
explicit ``ForeignKey("users.id")``, as 23 models do — reached production with
attribution that the database does not enforce. ``created_by_id`` can name a
user id that has never existed, and nothing objects: not the ORM, not the
database, and not ``alembic check``, which strips ``CreateForeignKeyOp`` under
``ALEMBIC_FILTER_FK_TENANT_INDEX_DRIFT=1``.

54 columns across 30 tables, measured from ``pg_constraint`` on a database at
``20260902_attrib_cols``. The list is enumerated from the catalogue rather than
from ``Base.metadata`` on purpose: ``compliance_evidence_links.created_by_id``
does not come from the mixin at all, and a model-driven sweep of mixin subclasses
would have missed it.

This will refuse to run on a database holding an orphan
------------------------------------------------------
By design, and the same design as #1398. ``ADD CONSTRAINT ... FOREIGN KEY``
validates every existing row, so on a database where some ``created_by_id``
points at a deleted user the ``ALTER TABLE`` aborts — mid-migration, with the
transaction rolled back and no explanation of which table or how many rows. That
is the failure this migration exists to convert into a readable one.

So ``upgrade()`` counts the orphans first and, if there are any, raises
:class:`AttributionOrphanRowsError` naming every table, column and count, and the
read-only script to run. It does not null them out and it does not delete them.
An orphaned ``created_by_id`` is evidence about a governance record — most likely
a user who was hard-deleted rather than deactivated — and discarding it to make a
deploy proceed destroys the only trace of who acted. Deciding what a specific
orphan should become is a human act with evidence behind it.

Verified, and not verified
--------------------------
The 54 columns and the absence of any foreign key on them were verified against a
PostgreSQL database built by this repository's own alembic chain. Whether
*production* holds orphans was **not** verified: production is unreachable from
where this was written. On the migration-built database the orphan count is 0,
which proves the constraint is addable to a clean schema and proves nothing about
production. Run the inventory against staging and production before deploying.

Row-level security caveat
-------------------------
Several of these tables — and ``users`` itself — are under ``FORCE ROW LEVEL
SECURITY``. For a role that neither bypasses RLS nor owns a matching
``app.current_tenant_id``, two things go wrong at once: the scan of the child
table sees a subset of rows, and the ``users`` subquery the orphan test depends
on may return nothing at all, which would report *every* attributed row as an
orphan. Meanwhile ``ADD CONSTRAINT`` ignores RLS entirely and validates the whole
heap. A count taken by such a role is wrong in both directions, so ``upgrade()``
refuses to run on one rather than acting on it.

Reversibility
-------------
Fully reversible. ``downgrade`` drops the constraints this revision names and
touches no data, because this revision writes none.
"""

from __future__ import annotations

import logging
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "20260902_attrib_fk"
down_revision: Union[str, Sequence[str], None] = "20260902_attrib_cols"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

logger = logging.getLogger("alembic.runtime.migration")

ATTRIBUTION_TARGET = "users"

#: ``{table: (column, ...)}`` for every attribution column that exists in the
#: database with no foreign key to ``users``, measured from ``pg_constraint``.
#:
#: Tables absent here already have the constraint, from an explicit
#: ``sa.ForeignKey`` in the migration that created them. This is additive only:
#: nothing in this revision alters or drops an existing constraint.
TARGET_COLUMNS: dict[str, tuple[str, ...]] = {
    "assessment_runs": ("created_by_id", "updated_by_id"),
    "asset_types": ("created_by_id", "updated_by_id"),
    "assets": ("created_by_id", "updated_by_id"),
    "audit_challenge_sessions": ("created_by_id", "updated_by_id"),
    "audit_findings": ("updated_by_id",),
    "audit_runs": ("updated_by_id",),
    "audit_templates": ("updated_by_id",),
    "complaint_actions": ("created_by_id", "updated_by_id"),
    "complaints": ("created_by_id", "updated_by_id"),
    # Not a mixin subclass; its created_by_id was declared directly on the model.
    "compliance_evidence_links": ("created_by_id",),
    "documents": ("updated_by_id",),
    "engineers": ("created_by_id", "updated_by_id"),
    "evidence_assets": ("created_by_id", "updated_by_id"),
    "external_audit_import_drafts": ("created_by_id", "updated_by_id"),
    "external_audit_import_jobs": ("created_by_id", "updated_by_id"),
    "incident_actions": ("created_by_id", "updated_by_id"),
    "incidents": ("created_by_id", "updated_by_id"),
    "induction_runs": ("created_by_id", "updated_by_id"),
    "investigation_runs": ("created_by_id", "updated_by_id"),
    "investigation_templates": ("created_by_id", "updated_by_id"),
    "locations": ("created_by_id", "updated_by_id"),
    "loler_examinations": ("created_by_id", "updated_by_id"),
    "policies": ("created_by_id", "updated_by_id"),
    "policy_versions": ("created_by_id", "updated_by_id"),
    "risk_controls": ("created_by_id", "updated_by_id"),
    "risks": ("updated_by_id",),
    "road_traffic_collisions": ("created_by_id", "updated_by_id"),
    "rta_actions": ("created_by_id", "updated_by_id"),
    "safety_insight_runs": ("created_by_id", "updated_by_id"),
    "training_tickets": ("created_by_id", "updated_by_id"),
}


class AttributionOrphanRowsError(RuntimeError):
    """Raised when an attribution column names a user that does not exist."""


class AttributionScopeInvisibleError(RuntimeError):
    """Raised when row-level security would corrupt the orphan count."""


def constraint_name(table: str, column: str) -> str:
    return f"fk_{table}_{column}"


def _present_targets() -> dict[str, tuple[str, ...]]:
    """Targets that exist on this database and are still unconstrained."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    constrained = _constrained_columns()

    present: dict[str, tuple[str, ...]] = {}
    for table, columns in TARGET_COLUMNS.items():
        if not inspector.has_table(table):
            continue
        actual = {column["name"] for column in inspector.get_columns(table)}
        wanted = tuple(column for column in columns if column in actual and (table, column) not in constrained)
        if wanted:
            present[table] = wanted
    return present


def _constrained_columns() -> set[tuple[str, str]]:
    """``{(table, column)}`` already covered by a foreign key to ``users``.

    Read from ``pg_constraint`` so a column that is one member of a composite
    foreign key counts as covered, and so a constraint under a name this
    revision does not use is still recognised. Makes ``upgrade`` idempotent.
    """
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        # SQLite reflection reports foreign keys per column adequately for the
        # only thing this fallback needs: not adding a duplicate.
        inspector = sa.inspect(bind)
        covered: set[tuple[str, str]] = set()
        for table in TARGET_COLUMNS:
            if not inspector.has_table(table):
                continue
            for fk in inspector.get_foreign_keys(table):
                if fk.get("referred_table") == ATTRIBUTION_TARGET:
                    covered.update((table, column) for column in fk.get("constrained_columns") or ())
        return covered

    rows = bind.execute(
        sa.text("""
            SELECT src.relname AS table_name, att.attname AS column_name
            FROM pg_constraint AS con
            JOIN pg_class AS src ON src.oid = con.conrelid
            JOIN pg_class AS tgt ON tgt.oid = con.confrelid
            JOIN pg_namespace AS ns ON ns.oid = src.relnamespace
            JOIN unnest(con.conkey) WITH ORDINALITY AS ck(attnum, ord) ON TRUE
            JOIN pg_attribute AS att
              ON att.attrelid = con.conrelid AND att.attnum = ck.attnum
            WHERE con.contype = 'f'
              AND ns.nspname = current_schema()
              AND tgt.relname = :target
            """),
        {"target": ATTRIBUTION_TARGET},
    )
    return {(row.table_name, row.column_name) for row in rows}


def _assert_orphans_are_visible(targets: dict[str, tuple[str, ...]]) -> None:
    """Refuse to trust an orphan count that row-level security may have filtered.

    Two distinct hazards, and the second is the dangerous one. If the child table
    is under FORCE RLS the scan misses rows, and the count under-reports. If
    ``users`` is under FORCE RLS the ``NOT EXISTS`` subquery may match nothing,
    and the count over-reports — potentially flagging every attributed row in the
    database as an orphan and refusing a migration that would have succeeded.
    Either way ``ADD CONSTRAINT`` ignores RLS and validates the real heap, so a
    count taken by such a role tells us nothing about whether it will succeed.
    """
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    role = bind.execute(sa.text("SELECT current_user")).scalar()
    bypasses = bind.execute(
        sa.text("SELECT COALESCE(bool_or(rolsuper OR rolbypassrls), false) FROM pg_roles WHERE rolname = current_user")
    ).scalar()
    if bypasses:
        return

    forced_in_schema = set(bind.execute(sa.text("""
                SELECT c.relname
                FROM pg_class AS c
                JOIN pg_namespace AS n ON n.oid = c.relnamespace
                WHERE n.nspname = current_schema()
                  AND c.relforcerowsecurity
                """)).scalars().all())
    forced = forced_in_schema.intersection(set(targets) | {ATTRIBUTION_TARGET})
    if not forced:
        return

    raise AttributionScopeInvisibleError(
        "Refusing to run: this connection cannot be trusted to count orphaned attribution.\n"
        f"  role            : {role}\n"
        f"  FORCE RLS tables: {', '.join(sorted(forced))}\n"
        f"If {ATTRIBUTION_TARGET} is in that list, the NOT EXISTS subquery this migration uses "
        "may match no user at all and report every attributed row as an orphan. If a child "
        "table is in it, the scan misses rows and the count under-reports. ADD CONSTRAINT "
        "ignores RLS and validates the whole heap either way.\n"
        "Re-run migrations as a role with rolsuper or rolbypassrls."
    )


def _orphan_counts(targets: dict[str, tuple[str, ...]]) -> dict[tuple[str, str], int]:
    """Rows per target whose attribution names a user that does not exist."""
    bind = op.get_bind()
    counts: dict[tuple[str, str], int] = {}
    for table, columns in targets.items():
        for column in columns:
            # Identifiers come from TARGET_COLUMNS, a module-level literal, and are
            # filtered through the inspector before reaching here. No caller input.
            result = bind.execute(
                sa.text(
                    f'SELECT count(*) FROM "{table}" AS t '  # noqa: S608
                    f'WHERE t."{column}" IS NOT NULL AND NOT EXISTS ('
                    f'SELECT 1 FROM "{ATTRIBUTION_TARGET}" AS u WHERE u.id = t."{column}")'
                )
            )
            counts[(table, column)] = int(result.scalar() or 0)
    return counts


def upgrade() -> None:
    targets = _present_targets()
    if not targets:
        logger.warning("Skipping %s: every attribution column is already constrained.", revision)
        return

    _assert_orphans_are_visible(targets)

    orphaned = {key: count for key, count in _orphan_counts(targets).items() if count}
    if orphaned:
        detail = "\n".join(
            f"    {table}.{column}: {count} row(s)" for (table, column), count in sorted(orphaned.items())
        )
        raise AttributionOrphanRowsError(
            "Refusing to add a foreign key over rows whose attribution names a user that "
            "does not exist.\n"
            f"{detail}\n"
            "ADD CONSTRAINT would abort on these anyway; this stops with the table, column "
            "and count instead of a driver error.\n"
            "This migration will not null them out and will not delete them. An orphaned "
            "created_by_id is the only remaining trace of who acted on a governance record, "
            "most likely a user hard-deleted rather than deactivated, and discarding it to "
            "let a deploy proceed destroys evidence.\n"
            "Next steps:\n"
            "  1. env -u DATABASE_URL -u PRODDB -u STAGING_DB DATABASE_URL=<dsn> \\\n"
            "       python -m scripts.ops.run026.audit_attribution_schema --json\n"
            "  2. Establish what each orphaned id referred to, with a named human on the "
            "record. Re-creating the user with its original id preserves the attribution; "
            "nulling the column discards it.\n"
            "  3. Repair, then re-run this migration. It is idempotent."
        )

    created: list[str] = []
    for table, columns in sorted(targets.items()):
        for column in columns:
            op.create_foreign_key(
                constraint_name(table, column),
                table,
                ATTRIBUTION_TARGET,
                [column],
                ["id"],
            )
            created.append(f"{table}.{column}")

    logger.info("%s: constrained %d attribution column(s) to %s.", revision, len(created), ATTRIBUTION_TARGET)


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    for table, columns in TARGET_COLUMNS.items():
        if not inspector.has_table(table):
            continue
        existing = {fk.get("name") for fk in inspector.get_foreign_keys(table)}
        for column in columns:
            name = constraint_name(table, column)
            if name in existing:
                op.drop_constraint(name, table, type_="foreignkey")
