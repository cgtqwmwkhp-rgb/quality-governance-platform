"""JL-UX-W5: job_type_baselines snapshot table + RLS.

Revision ID: 20261023_job_type_baselines
Revises: 20261022_job_cell_req_ev
Create Date: 2026-10-23

Additive. One new table that freezes a JobType pack's axes and nest edges at
time T as a JSON snapshot. Live ``job_types`` / lanes / steps / cells / links
remain the source of truth for edit — a baseline is never a fork, and editing
always targets the live tip.

Registered in ``HARDENING_MIGRATIONS`` / ``RLS_TABLES`` under the same
``NULLIF`` empty-GUC predicate as every other post-20260902 tenant table.
"""

from __future__ import annotations

import logging
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261023_job_type_baselines"
down_revision: Union[str, Sequence[str], None] = "20261022_job_cell_req_ev"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

logger = logging.getLogger("alembic.runtime.migration")

ADOPT_TABLES: tuple[str, ...] = ("job_type_baselines",)

HARDENED_PREDICATE = "tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::int"


def _json_type() -> sa.types.TypeEngine:
    """JSONB on PostgreSQL; plain JSON for SQLite (local / unit migration runners)."""
    return postgresql.JSONB(astext_type=sa.Text()) if op.get_bind().dialect.name == "postgresql" else sa.JSON()


def _inspector() -> sa.Inspector:
    return sa.inspect(op.get_bind())


def _table_exists(table_name: str) -> bool:
    return _inspector().has_table(table_name)


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
                problems.append(
                    f"{table}: {label} is {expr!r}, expected it to contain {expected_fragment!r}"
                )

    if problems:
        raise RuntimeError(
            f"{revision} did not achieve the policy state it reported. "
            "Refusing to record this revision as applied.\n  " + "\n  ".join(problems)
        )


def upgrade() -> None:
    if not _table_exists("job_type_baselines"):
        op.create_table(
            "job_type_baselines",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("tenant_id", sa.Integer(), nullable=False),
            sa.Column("job_type_id", sa.Integer(), nullable=False),
            sa.Column("label", sa.String(length=200), nullable=True),
            sa.Column("note", sa.Text(), nullable=True),
            sa.Column("created_by_id", sa.Integer(), nullable=True),
            sa.Column("snapshot", _json_type(), nullable=False),
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
            sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_job_type_baselines_tenant_id", "job_type_baselines", ["tenant_id"])
        op.create_index("ix_job_type_baselines_job_type_id", "job_type_baselines", ["job_type_id"])
        op.create_index(
            "ix_job_type_baselines_tenant_type_created",
            "job_type_baselines",
            ["tenant_id", "job_type_id", "created_at"],
        )
        op.create_index("ix_job_type_baselines_created_at", "job_type_baselines", ["created_at"])

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
