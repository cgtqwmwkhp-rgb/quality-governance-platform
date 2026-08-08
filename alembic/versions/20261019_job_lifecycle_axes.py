"""JL-1: Job Lifecycle axes (job_types / lanes / steps / cells) + RLS.

Revision ID: 20261019_job_lifecycle_axes
Revises: 20261018_doc_one_primary
Create Date: 2026-10-19

ADR-0022: Job Type / Lane / Step are JL-owned process axes. Identity is JL
``code`` + tenant scope. Cells hold library document memberships only (no
embedded bodies, no department annotation column). Tables are created with
``tenant_id`` NOT NULL and hardened under the same ``NULLIF`` empty-GUC
predicate as every other post-20260902 tenant table. Registered in
``HARDENING_MIGRATIONS`` / ``RLS_TABLES``.
"""

from __future__ import annotations

import logging
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261019_job_lifecycle_axes"
down_revision: Union[str, Sequence[str], None] = "20261018_doc_one_primary"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

logger = logging.getLogger("alembic.runtime.migration")

ADOPT_TABLES: tuple[str, ...] = (
    "job_types",
    "job_lanes",
    "job_steps",
    "job_cells",
    "job_cell_documents",
)

# Kept as a literal rather than imported from
# src.infrastructure.middleware.tenant_context.TENANT_ISOLATION_PREDICATE, for the
# same reason 20260902_rls_guc_guard / 20261015_document_edges keep their own
# copy: a migration must describe the database as it was at this revision and
# must not change meaning when application code is edited later.
HARDENED_PREDICATE = "tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::int"


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
    for table in ADOPT_TABLES:
        if not _table_exists(table):
            continue
        if any(idx["name"] == index_name for idx in _inspector().get_indexes(table)):
            return True
    return False


def _enable_rls(table: str) -> None:
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


def _create_live_unique_index(name: str, table: str, columns: list[str]) -> None:
    if _index_exists(name):
        return
    bind = op.get_bind()
    cols = ", ".join(columns)
    if bind.dialect.name == "postgresql":
        op.execute(
            sa.text(
                f"CREATE UNIQUE INDEX {name} ON {table} ({cols}) " "WHERE deleted_at IS NULL"
            )
        )
    else:
        op.create_index(
            name,
            table,
            columns,
            unique=True,
            sqlite_where=sa.text("deleted_at IS NULL"),
        )


def _create_tables() -> None:
    if not _table_exists("job_types"):
        op.create_table(
            "job_types",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("tenant_id", sa.Integer(), nullable=False),
            sa.Column("code", sa.String(length=64), nullable=False),
            sa.Column("name", sa.String(length=200), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("sort_order", sa.Integer(), server_default=sa.text("0"), nullable=False),
            sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
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
            sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_job_types_tenant_id", "job_types", ["tenant_id"])
        op.create_index("ix_job_types_tenant_sort", "job_types", ["tenant_id", "sort_order"])
        op.create_index("ix_job_types_deleted_at", "job_types", ["deleted_at"])

    if not _table_exists("job_lanes"):
        op.create_table(
            "job_lanes",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("tenant_id", sa.Integer(), nullable=False),
            sa.Column("job_type_id", sa.Integer(), nullable=False),
            sa.Column("code", sa.String(length=64), nullable=False),
            sa.Column("name", sa.String(length=200), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("sort_order", sa.Integer(), server_default=sa.text("0"), nullable=False),
            sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
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
            sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
            sa.ForeignKeyConstraint(["job_type_id"], ["job_types.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_job_lanes_tenant_id", "job_lanes", ["tenant_id"])
        op.create_index("ix_job_lanes_job_type_id", "job_lanes", ["job_type_id"])
        op.create_index(
            "ix_job_lanes_tenant_type_sort",
            "job_lanes",
            ["tenant_id", "job_type_id", "sort_order"],
        )
        op.create_index("ix_job_lanes_deleted_at", "job_lanes", ["deleted_at"])

    if not _table_exists("job_steps"):
        op.create_table(
            "job_steps",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("tenant_id", sa.Integer(), nullable=False),
            sa.Column("job_type_id", sa.Integer(), nullable=False),
            sa.Column("code", sa.String(length=64), nullable=False),
            sa.Column("name", sa.String(length=200), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("sort_order", sa.Integer(), server_default=sa.text("0"), nullable=False),
            sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
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
            sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
            sa.ForeignKeyConstraint(["job_type_id"], ["job_types.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_job_steps_tenant_id", "job_steps", ["tenant_id"])
        op.create_index("ix_job_steps_job_type_id", "job_steps", ["job_type_id"])
        op.create_index(
            "ix_job_steps_tenant_type_sort",
            "job_steps",
            ["tenant_id", "job_type_id", "sort_order"],
        )
        op.create_index("ix_job_steps_deleted_at", "job_steps", ["deleted_at"])

    if not _table_exists("job_cells"):
        op.create_table(
            "job_cells",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("tenant_id", sa.Integer(), nullable=False),
            sa.Column("job_type_id", sa.Integer(), nullable=False),
            sa.Column("lane_id", sa.Integer(), nullable=False),
            sa.Column("step_id", sa.Integer(), nullable=False),
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
            sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
            sa.ForeignKeyConstraint(["job_type_id"], ["job_types.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["lane_id"], ["job_lanes.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["step_id"], ["job_steps.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_job_cells_tenant_id", "job_cells", ["tenant_id"])
        op.create_index("ix_job_cells_job_type_id", "job_cells", ["job_type_id"])
        op.create_index("ix_job_cells_tenant_lane", "job_cells", ["tenant_id", "lane_id"])
        op.create_index("ix_job_cells_tenant_step", "job_cells", ["tenant_id", "step_id"])
        op.create_index("ix_job_cells_deleted_at", "job_cells", ["deleted_at"])

    if not _table_exists("job_cell_documents"):
        op.create_table(
            "job_cell_documents",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("tenant_id", sa.Integer(), nullable=False),
            sa.Column("cell_id", sa.Integer(), nullable=False),
            sa.Column("library_document_id", sa.Integer(), nullable=False),
            sa.Column("sort_order", sa.Integer(), server_default=sa.text("0"), nullable=False),
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
            sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
            sa.ForeignKeyConstraint(["cell_id"], ["job_cells.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["library_document_id"], ["documents.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("cell_id", "library_document_id", name="ux_job_cell_documents_cell_doc"),
        )
        op.create_index("ix_job_cell_documents_tenant_id", "job_cell_documents", ["tenant_id"])
        op.create_index("ix_job_cell_documents_cell_id", "job_cell_documents", ["cell_id"])
        op.create_index(
            "ix_job_cell_documents_tenant_doc",
            "job_cell_documents",
            ["tenant_id", "library_document_id"],
        )
        op.create_index(
            "ix_job_cell_documents_tenant_cell_sort",
            "job_cell_documents",
            ["tenant_id", "cell_id", "sort_order"],
        )


def upgrade() -> None:
    _create_tables()

    _create_live_unique_index("ux_job_types_tenant_code_live", "job_types", ["tenant_id", "code"])
    _create_live_unique_index(
        "ux_job_lanes_tenant_type_code_live",
        "job_lanes",
        ["tenant_id", "job_type_id", "code"],
    )
    _create_live_unique_index(
        "ux_job_steps_tenant_type_code_live",
        "job_steps",
        ["tenant_id", "job_type_id", "code"],
    )
    _create_live_unique_index(
        "ux_job_cells_tenant_type_lane_step_live",
        "job_cells",
        ["tenant_id", "job_type_id", "lane_id", "step_id"],
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

    for table in reversed(ADOPT_TABLES):
        if _table_exists(table):
            op.drop_table(table)
