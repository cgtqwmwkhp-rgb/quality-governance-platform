"""JL-3: Job cell links (app · external · audit_outcome) + RLS.

Revision ID: 20261020_job_cell_links
Revises: 20261019_job_lifecycle_axes
Create Date: 2026-10-20

Additive cell hyperlink memberships. App / audit_outcome store structured
refs resolved via ``href_registry`` at read time (no parallel URL builders).
External stores https URLs only. Table is created with ``tenant_id`` NOT NULL
and hardened under the same ``NULLIF`` empty-GUC predicate. Registered in
``HARDENING_MIGRATIONS`` / ``RLS_TABLES``.
"""

from __future__ import annotations

import logging
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261020_job_cell_links"
down_revision: Union[str, Sequence[str], None] = "20261019_job_lifecycle_axes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

logger = logging.getLogger("alembic.runtime.migration")

ADOPT_TABLES: tuple[str, ...] = ("job_cell_links",)

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
                problems.append(
                    f"{table}: {label} is {expr!r}, expected it to contain {expected_fragment!r}"
                )

    if problems:
        raise RuntimeError(
            f"{revision} did not achieve the policy state it reported. "
            "Refusing to record this revision as applied.\n  " + "\n  ".join(problems)
        )


def upgrade() -> None:
    if not _table_exists("job_cell_links"):
        op.create_table(
            "job_cell_links",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("tenant_id", sa.Integer(), nullable=False),
            sa.Column("cell_id", sa.Integer(), nullable=False),
            sa.Column("kind", sa.String(length=32), nullable=False),
            sa.Column("label", sa.String(length=300), nullable=False),
            sa.Column("entity_type", sa.String(length=64), nullable=True),
            sa.Column("entity_id", sa.Integer(), nullable=True),
            sa.Column("external_url", sa.String(length=2000), nullable=True),
            sa.Column("audit_run_id", sa.Integer(), nullable=True),
            sa.Column("audit_finding_id", sa.Integer(), nullable=True),
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
            sa.ForeignKeyConstraint(["audit_run_id"], ["audit_runs.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(
                ["audit_finding_id"], ["audit_findings.id"], ondelete="SET NULL"
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.CheckConstraint(
                "kind IN ('app', 'external', 'audit_outcome')",
                name="ck_job_cell_links_kind",
            ),
        )
        op.create_index("ix_job_cell_links_tenant_id", "job_cell_links", ["tenant_id"])
        op.create_index("ix_job_cell_links_cell_id", "job_cell_links", ["cell_id"])
        op.create_index(
            "ix_job_cell_links_tenant_cell_sort",
            "job_cell_links",
            ["tenant_id", "cell_id", "sort_order"],
        )
        op.create_index(
            "ix_job_cell_links_tenant_finding",
            "job_cell_links",
            ["tenant_id", "audit_finding_id"],
        )
        op.create_index("ix_job_cell_links_created_at", "job_cell_links", ["created_at"])

    if not _index_exists("ux_job_cell_links_cell_finding"):
        # One audit_outcome per finding per cell (NULLs allowed for other kinds).
        bind = op.get_bind()
        if bind.dialect.name == "postgresql":
            op.execute(
                sa.text(
                    "CREATE UNIQUE INDEX ux_job_cell_links_cell_finding "
                    "ON job_cell_links (cell_id, audit_finding_id) "
                    "WHERE audit_finding_id IS NOT NULL"
                )
            )
        else:
            op.create_index(
                "ux_job_cell_links_cell_finding",
                "job_cell_links",
                ["cell_id", "audit_finding_id"],
                unique=True,
                sqlite_where=sa.text("audit_finding_id IS NOT NULL"),
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
