"""Standards Wave 2 PR-C: matrix_versions + alignment_edges under tenant_isolation.

Revision ID: 20261105_standards_alignment
Revises: 20261104_lib_cut1b_drop
Create Date: 2026-11-05

The imported PEL-HSEQ-5064 alignment matrix (ADR: Standards Wave 2). Both tables
are created with ``tenant_id`` NOT NULL and hardened under the same ``NULLIF``
empty-GUC predicate as every other post-20260902 tenant table. Registered in
``HARDENING_MIGRATIONS`` / ``RLS_TABLES``.

Uniqueness worth reading twice
------------------------------
``alignment_edges`` needs *two* partial unique indexes, not one. A pair edge is
keyed on both endpoints, but a ``UNIQUE`` verdict has no destination and NULLs do
not collide in a PostgreSQL unique index — so a single index over the six columns
would silently permit unlimited duplicate UNIQUE rows for the same clause. The
second index keys those rows on the source endpoint alone, with
``dst_framework IS NULL`` in the predicate so the two indexes partition the table
rather than overlap.

``matrix_versions`` carries the import idempotency anchor: one live row per
``(tenant_id, source_ref, source_checksum)``. Re-importing byte-identical content
therefore cannot create a second edition even if two operators apply at once —
the second transaction loses the insert and the service re-reads the winner.

Why no CHECK on pair ordering
-----------------------------
Edges are stored once per unordered pair, ordered by
``(framework, clause_key)``. That ordering is applied in Python
(``canonical_alignment_pair``) and asserted by a unit test rather than by a CHECK
constraint, because ``<`` on text in PostgreSQL depends on the database collation:
a constraint whose truth changes with ``lc_collate`` would make this migration
mean different things on two servers that both report success.
"""

from __future__ import annotations

import logging
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "20261105_standards_alignment"
down_revision: Union[str, Sequence[str], None] = "20261104_lib_cut1b_drop"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

logger = logging.getLogger("alembic.runtime.migration")

VERSIONS_TABLE = "matrix_versions"
EDGES_TABLE = "alignment_edges"

# Kept as a literal rather than imported from
# src.infrastructure.middleware.tenant_context.TENANT_ISOLATION_PREDICATE, for the
# same reason 20260902_rls_guc_guard / 20261015_document_edges keep their own
# copy: a migration must describe the database as it was at this revision and must
# not change meaning when application code is edited later. A unit test asserts
# the two stay identical.
HARDENED_PREDICATE = "tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::int"

ADOPT_TABLES: tuple[str, ...] = ("matrix_versions", "alignment_edges")

_VERDICT_VALUES = "'exact', 'near', 'different', 'unique'"
_STATUS_VALUES = "'draft', 'active', 'superseded'"

# (index_name, table, columns, predicate)
PARTIAL_UNIQUE_INDEXES: tuple[tuple[str, str, tuple[str, ...], str], ...] = (
    (
        "ux_matrix_versions_tenant_ref_checksum_live",
        VERSIONS_TABLE,
        ("tenant_id", "source_ref", "source_checksum"),
        "deleted_at IS NULL",
    ),
    (
        "ux_matrix_versions_one_active_live",
        VERSIONS_TABLE,
        ("tenant_id", "source_ref"),
        "status = 'active' AND deleted_at IS NULL",
    ),
    (
        "ux_alignment_edges_pair_live",
        EDGES_TABLE,
        (
            "tenant_id",
            "matrix_version_id",
            "src_framework",
            "src_clause_key",
            "dst_framework",
            "dst_clause_key",
        ),
        "deleted_at IS NULL AND dst_framework IS NOT NULL",
    ),
    (
        "ux_alignment_edges_unique_live",
        EDGES_TABLE,
        ("tenant_id", "matrix_version_id", "src_framework", "src_clause_key"),
        "deleted_at IS NULL AND dst_framework IS NULL",
    ),
)

PLAIN_INDEXES: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("ix_matrix_versions_tenant_id", VERSIONS_TABLE, ("tenant_id",)),
    ("ix_matrix_versions_tenant_status", VERSIONS_TABLE, ("tenant_id", "status")),
    ("ix_matrix_versions_deleted_at", VERSIONS_TABLE, ("deleted_at",)),
    ("ix_alignment_edges_tenant_id", EDGES_TABLE, ("tenant_id",)),
    (
        "ix_alignment_edges_tenant_version_row",
        EDGES_TABLE,
        ("tenant_id", "matrix_version_id", "row_key"),
    ),
    ("ix_alignment_edges_tenant_src", EDGES_TABLE, ("tenant_id", "src_framework", "src_clause_key")),
    ("ix_alignment_edges_tenant_dst", EDGES_TABLE, ("tenant_id", "dst_framework", "dst_clause_key")),
    ("ix_alignment_edges_tenant_verdict", EDGES_TABLE, ("tenant_id", "verdict")),
    ("ix_alignment_edges_deleted_at", EDGES_TABLE, ("deleted_at",)),
)


def _inspector() -> sa.Inspector:
    return sa.inspect(op.get_bind())


def _is_postgres() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def _table_exists(table_name: str) -> bool:
    return _inspector().has_table(table_name)


def _index_exists(index_name: str, table_name: str) -> bool:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        return bool(
            bind.execute(
                sa.text("SELECT 1 FROM pg_class WHERE relkind = 'i' AND relname = :name"),
                {"name": index_name},
            ).fetchone()
        )
    if not _table_exists(table_name):
        return False
    return any(idx["name"] == index_name for idx in _inspector().get_indexes(table_name))


def _enable_rls(table: str) -> None:
    """ENABLE + FORCE row-level security on ``table`` and install the policy."""
    conn = op.get_bind()
    if conn.dialect.name != "postgresql":
        return
    op.execute(sa.text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))
    op.execute(sa.text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY"))
    op.execute(sa.text(f"DROP POLICY IF EXISTS tenant_isolation ON {table}"))
    op.execute(
        sa.text(
            f"CREATE POLICY tenant_isolation ON {table} "
            f"USING ({HARDENED_PREDICATE}) WITH CHECK ({HARDENED_PREDICATE})"
        )
    )


def _assert_policies_match(tables: Sequence[str], expected_fragment: str) -> None:
    """Re-read pg_policy and raise unless every table really carries the predicate."""
    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            """
            SELECT c.relname AS table_name,
                   c.relrowsecurity AS enabled,
                   c.relforcerowsecurity AS forced,
                   pg_get_expr(p.polqual, p.polrelid) AS using_expr,
                   pg_get_expr(p.polwithcheck, p.polrelid) AS check_expr
            FROM pg_class AS c
            JOIN pg_namespace AS n ON n.oid = c.relnamespace
            LEFT JOIN pg_policy AS p ON p.polrelid = c.oid AND p.polname = 'tenant_isolation'
            WHERE n.nspname = current_schema() AND c.relname = ANY(:tables)
            """
        ),
        {"tables": list(tables)},
    ).mappings()
    state = {row["table_name"]: row for row in rows}

    problems: list[str] = []
    for table in tables:
        row = state.get(table)
        if row is None:
            problems.append(f"{table}: relation not visible in current_schema()")
            continue
        if not row["enabled"] or not row["forced"]:
            problems.append(f"{table}: enabled={row['enabled']} forced={row['forced']} (both must be true)")
        for label in ("using_expr", "check_expr"):
            expr = row[label]
            if expr is None:
                problems.append(f"{table}: tenant_isolation has no {label}")
            elif expected_fragment not in expr:
                problems.append(f"{table}: {label} is {expr!r}, expected it to contain {expected_fragment!r}")

    if problems:
        raise RuntimeError(
            f"{revision} did not achieve the policy state it reported. "
            "Refusing to record this revision as applied.\n  " + "\n  ".join(problems)
        )


def _assert_unique_indexes_match() -> None:
    """Re-read pg_index and raise unless each partial unique index really constrains."""
    bind = op.get_bind()
    problems: list[str] = []
    for index_name, _table, columns, predicate_fragment in PARTIAL_UNIQUE_INDEXES:
        row = (
            bind.execute(
                sa.text(
                    """
                    SELECT i.indisunique AS is_unique,
                           i.indisvalid  AS is_valid,
                           pg_get_expr(i.indpred, i.indrelid) AS predicate,
                           pg_get_indexdef(i.indexrelid)      AS definition
                    FROM pg_index AS i
                    JOIN pg_class AS c ON c.oid = i.indexrelid
                    WHERE c.relname = :name
                    """
                ),
                {"name": index_name},
            )
            .mappings()
            .fetchone()
        )
        if row is None:
            problems.append(f"{index_name}: absent from pg_index")
            continue
        if not row["is_unique"]:
            problems.append(f"{index_name}: not UNIQUE, so it constrains nothing")
        if not row["is_valid"]:
            problems.append(f"{index_name}: INVALID and will not be enforced")
        if row["predicate"] is None:
            problems.append(
                f"{index_name}: has no partial predicate, so it would apply to every "
                "row rather than the intended subset"
            )
        definition = row["definition"] or ""
        for column in columns:
            if column not in definition:
                problems.append(f"{index_name}: definition {definition!r} is missing column {column!r}")

    if problems:
        raise RuntimeError(
            f"{revision} did not achieve the index state it reported. "
            "Refusing to record this revision as applied.\n  " + "\n  ".join(problems)
        )


def _create_matrix_versions() -> None:
    op.create_table(
        VERSIONS_TABLE,
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("source_ref", sa.String(length=40), nullable=False),
        sa.Column("version_label", sa.String(length=20), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("source_date", sa.String(length=20), nullable=True),
        sa.Column("source_checksum", sa.String(length=64), nullable=False),
        sa.Column(
            "status",
            sa.String(length=16),
            server_default=sa.text("'draft'"),
            nullable=False,
        ),
        sa.Column("row_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("edge_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("excluded_frameworks", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("imported_by_id", sa.Integer(), nullable=True),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(f"status IN ({_STATUS_VALUES})", name="ck_matrix_versions_status"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["imported_by_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def _create_alignment_edges() -> None:
    op.create_table(
        EDGES_TABLE,
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("matrix_version_id", sa.Integer(), nullable=False),
        sa.Column("row_key", sa.String(length=64), nullable=False),
        sa.Column("clause_ref", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("src_framework", sa.String(length=24), nullable=False),
        sa.Column("src_clause_key", sa.String(length=50), nullable=False),
        sa.Column("src_clause_label", sa.String(length=200), nullable=True),
        sa.Column("dst_framework", sa.String(length=24), nullable=True),
        sa.Column("dst_clause_key", sa.String(length=50), nullable=True),
        sa.Column("dst_clause_label", sa.String(length=200), nullable=True),
        sa.Column("verdict", sa.String(length=12), nullable=False),
        sa.Column("row_verdict", sa.String(length=12), nullable=False),
        sa.Column(
            "is_pair_override",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("addition_text", sa.Text(), nullable=True),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("deliverables", sa.Text(), nullable=True),
        sa.Column("source_sheet", sa.String(length=64), nullable=True),
        sa.Column("source_row", sa.Integer(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(f"verdict IN ({_VERDICT_VALUES})", name="ck_alignment_edges_verdict"),
        sa.CheckConstraint(f"row_verdict IN ({_VERDICT_VALUES})", name="ck_alignment_edges_row_verdict"),
        sa.CheckConstraint(
            "(verdict = 'unique' AND dst_framework IS NULL AND dst_clause_key IS NULL) "
            "OR (verdict <> 'unique' AND dst_framework IS NOT NULL AND dst_clause_key IS NOT NULL)",
            name="ck_alignment_edges_unique_has_no_pair",
        ),
        sa.CheckConstraint(
            "dst_framework IS NULL OR src_framework <> dst_framework OR src_clause_key <> dst_clause_key",
            name="ck_alignment_edges_no_self_pair",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["matrix_version_id"], ["matrix_versions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )


def _create_indexes() -> None:
    for index_name, table, columns in PLAIN_INDEXES:
        if not _index_exists(index_name, table):
            op.create_index(index_name, table, list(columns))

    for index_name, table, columns, predicate in PARTIAL_UNIQUE_INDEXES:
        if _index_exists(index_name, table):
            continue
        if _is_postgres():
            column_list = ", ".join(columns)
            op.execute(
                sa.text(f"CREATE UNIQUE INDEX {index_name} ON {table} ({column_list}) WHERE {predicate}")
            )
        else:
            op.create_index(
                index_name,
                table,
                list(columns),
                unique=True,
                sqlite_where=sa.text(predicate),
            )


def upgrade() -> None:
    if _table_exists(VERSIONS_TABLE):
        logger.info("%s: %s already present — skipping create", revision, VERSIONS_TABLE)
    else:
        _create_matrix_versions()

    if _table_exists(EDGES_TABLE):
        logger.info("%s: %s already present — skipping create", revision, EDGES_TABLE)
    else:
        _create_alignment_edges()

    _create_indexes()

    if _is_postgres():
        _assert_unique_indexes_match()

    protected = [table for table in ADOPT_TABLES if _table_exists(table)]
    for table in protected:
        _enable_rls(table)

    if protected and _is_postgres():
        _assert_policies_match(protected, "NULLIF")
        logger.info("%s: tenant_isolation enabled and forced on %s", revision, ", ".join(protected))
    elif not protected:
        logger.warning("%s: ADOPT_TABLES missing at upgrade time — nothing hardened", revision)


def downgrade() -> None:
    if _is_postgres():
        for table in reversed(ADOPT_TABLES):
            if _table_exists(table):
                op.execute(sa.text(f"DROP POLICY IF EXISTS tenant_isolation ON {table}"))
                op.execute(sa.text(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY"))
                op.execute(sa.text(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY"))

    for index_name, table, _columns, _predicate in reversed(PARTIAL_UNIQUE_INDEXES):
        if _table_exists(table) and _index_exists(index_name, table):
            op.drop_index(index_name, table_name=table)
    for index_name, table, _columns in reversed(PLAIN_INDEXES):
        if _table_exists(table) and _index_exists(index_name, table):
            op.drop_index(index_name, table_name=table)

    # Child first: alignment_edges holds the FK onto matrix_versions.
    if _table_exists(EDGES_TABLE):
        op.drop_table(EDGES_TABLE)
    if _table_exists(VERSIONS_TABLE):
        op.drop_table(VERSIONS_TABLE)
