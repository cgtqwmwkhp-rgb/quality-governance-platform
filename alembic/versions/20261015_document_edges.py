"""Doc Graph Wave 0: create document_edges + ENABLE/FORCE tenant_isolation.

Revision ID: 20261015_document_edges
Revises: 20261014_doc_graph_pins
Create Date: 2026-10-15

Authored library Document↔Document edges (ADR-0021). Table is created with
``tenant_id`` NOT NULL and hardened under the same ``NULLIF`` empty-GUC
predicate as every other post-20260902 tenant table. Registered in
``HARDENING_MIGRATIONS`` / ``RLS_TABLES``.
"""

from __future__ import annotations

import logging
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261015_document_edges"
down_revision: Union[str, Sequence[str], None] = "20261014_doc_graph_pins"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

logger = logging.getLogger("alembic.runtime.migration")

TABLE = "document_edges"

# Kept as a literal rather than imported from
# src.infrastructure.middleware.tenant_context.TENANT_ISOLATION_PREDICATE, for the
# same reason 20260902_rls_guc_guard / 20260913_cs_wave0 keep their own copy: a
# migration must describe the database as it was at this revision and must not
# change meaning when application code is edited later. A unit test asserts the
# two stay identical.
HARDENED_PREDICATE = "tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::int"

ADOPT_TABLES: tuple[str, ...] = ("document_edges",)

LIVE_UNIQUE_INDEX_DDL = (
    f"CREATE UNIQUE INDEX ux_document_edges_tenant_src_dst_type_live ON {TABLE} "
    "(tenant_id, src_document_id, dst_document_id, edge_type) "
    "WHERE deleted_at IS NULL"
)


def _inspector() -> sa.Inspector:
    return sa.inspect(op.get_bind())


def _table_exists(table_name: str) -> bool:
    return _inspector().has_table(table_name)


def _index_exists(index_name: str) -> bool:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        return bool(
            bind.execute(
                sa.text("SELECT 1 FROM pg_class WHERE relkind = 'i' AND relname = :name"),
                {"name": index_name},
            ).fetchone()
        )
    if not _table_exists(TABLE):
        return False
    return any(idx["name"] == index_name for idx in _inspector().get_indexes(TABLE))


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
        sa.text("""
            SELECT c.relname AS table_name,
                   c.relrowsecurity AS enabled,
                   c.relforcerowsecurity AS forced,
                   pg_get_expr(p.polqual, p.polrelid) AS using_expr,
                   pg_get_expr(p.polwithcheck, p.polrelid) AS check_expr
            FROM pg_class AS c
            JOIN pg_namespace AS n ON n.oid = c.relnamespace
            LEFT JOIN pg_policy AS p ON p.polrelid = c.oid AND p.polname = 'tenant_isolation'
            WHERE n.nspname = current_schema() AND c.relname = ANY(:tables)
            """),
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


def _create_table() -> None:
    op.create_table(
        TABLE,
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("src_document_id", sa.Integer(), nullable=False),
        sa.Column("dst_document_id", sa.Integer(), nullable=False),
        sa.Column("src_pel_doc_ref", sa.String(length=30), nullable=True),
        sa.Column("dst_pel_doc_ref", sa.String(length=30), nullable=True),
        sa.Column("edge_type", sa.String(length=32), nullable=False),
        sa.Column(
            "is_primary_parent",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default=sa.text("'proposed'"),
            nullable=False,
        ),
        sa.Column(
            "created_method",
            sa.String(length=20),
            server_default=sa.text("'manual'"),
            nullable=False,
        ),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("confirmed_by_id", sa.Integer(), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cited_document_version_id", sa.Integer(), nullable=True),
        sa.Column("chunk_id", sa.Integer(), nullable=True),
        sa.Column("char_start", sa.Integer(), nullable=True),
        sa.Column("char_end", sa.Integer(), nullable=True),
        sa.Column("quote_hash", sa.String(length=64), nullable=True),
        sa.Column("citation_text", sa.Text(), nullable=True),
        sa.Column("cited_version", sa.String(length=50), nullable=True),
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
        sa.CheckConstraint(
            "edge_type IN ('implements', 'requires_record', 'references', "
            "'related_to', 'conflicts_with')",
            name="ck_document_edges_edge_type",
        ),
        sa.CheckConstraint(
            "status IN ('proposed', 'confirmed', 'rejected', 'needs_review')",
            name="ck_document_edges_status",
        ),
        sa.CheckConstraint(
            "created_method IN ('manual', 'ai', 'extracted', 'heuristic', 'auto')",
            name="ck_document_edges_created_method",
        ),
        sa.CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name="ck_document_edges_confidence",
        ),
        sa.CheckConstraint(
            "src_document_id <> dst_document_id",
            name="ck_document_edges_no_self_loop",
        ),
        sa.CheckConstraint(
            "(edge_type = 'implements') OR (is_primary_parent = false)",
            name="ck_document_edges_primary_parent_implements_only",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["src_document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["dst_document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["confirmed_by_id"], ["users.id"]),
        sa.ForeignKeyConstraint(
            ["cited_document_version_id"],
            ["document_versions.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(["chunk_id"], ["document_chunks.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_document_edges_tenant_id", TABLE, ["tenant_id"])
    op.create_index("ix_document_edges_tenant_src", TABLE, ["tenant_id", "src_document_id"])
    op.create_index("ix_document_edges_tenant_dst", TABLE, ["tenant_id", "dst_document_id"])
    op.create_index(
        "ix_document_edges_tenant_type_status",
        TABLE,
        ["tenant_id", "edge_type", "status"],
    )
    op.create_index("ix_document_edges_deleted_at", TABLE, ["deleted_at"])


def upgrade() -> None:
    if _table_exists(TABLE):
        logger.info("%s: %s already present — skipping create", revision, TABLE)
    else:
        _create_table()

    if op.get_bind().dialect.name == "postgresql":
        if not _index_exists("ux_document_edges_tenant_src_dst_type_live"):
            op.execute(sa.text(LIVE_UNIQUE_INDEX_DDL))
    else:
        if not _index_exists("ux_document_edges_tenant_src_dst_type_live"):
            op.create_index(
                "ux_document_edges_tenant_src_dst_type_live",
                TABLE,
                ["tenant_id", "src_document_id", "dst_document_id", "edge_type"],
                unique=True,
                sqlite_where=sa.text("deleted_at IS NULL"),
            )

    protected = [table for table in ADOPT_TABLES if _table_exists(table)]
    for table in protected:
        _enable_rls(table)

    if protected and op.get_bind().dialect.name == "postgresql":
        _assert_policies_match(protected, "NULLIF")
        logger.info("%s: tenant_isolation enabled and forced on %s", revision, ", ".join(protected))
    elif not protected:
        logger.warning("%s: ADOPT_TABLES missing at upgrade time — nothing hardened", revision)


def downgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        for table in reversed(ADOPT_TABLES):
            if _table_exists(table):
                op.execute(sa.text(f"DROP POLICY IF EXISTS tenant_isolation ON {table}"))
                op.execute(sa.text(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY"))
                op.execute(sa.text(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY"))

    if not _table_exists(TABLE):
        return

    for name in (
        "ux_document_edges_tenant_src_dst_type_live",
        "ix_document_edges_deleted_at",
        "ix_document_edges_tenant_type_status",
        "ix_document_edges_tenant_dst",
        "ix_document_edges_tenant_src",
        "ix_document_edges_tenant_id",
    ):
        if _index_exists(name):
            op.drop_index(name, table_name=TABLE)
    op.drop_table(TABLE)
