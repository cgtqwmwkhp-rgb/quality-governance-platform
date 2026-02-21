"""Add data integrity constraints.

Revision ID: 20260221_integrity
Revises: 20260221_composite_idx
Create Date: 2026-02-21

Adds UNIQUE constraints, CHECK constraints on status fields,
and a version column for optimistic locking on frequently updated tables.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260221_integrity"
down_revision: Union[str, None] = "20260221_composite_idx"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_has_column(conn, table: str, column: str) -> bool:
    result = conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = :t AND column_name = :c"
        ),
        {"t": table, "c": column},
    )
    return result.scalar() is not None


def _safe_create_unique(conn, table: str, column: str, constraint_name: str) -> None:
    """Create unique constraint only if table and column exist."""
    if _table_has_column(conn, table, column):
        try:
            op.create_unique_constraint(constraint_name, table, [column])
        except Exception:
            pass


def _safe_add_check(conn, table: str, constraint_name: str, condition: str) -> None:
    """Add CHECK constraint only if the table exists."""
    result = conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_name = :t"
        ),
        {"t": table},
    )
    if result.scalar():
        try:
            op.create_check_constraint(constraint_name, table, condition)
        except Exception:
            pass


def _safe_add_column(conn, table: str, column_name: str, column: sa.Column) -> None:
    """Add column only if table exists and column doesn't."""
    if not _table_has_column(conn, table, column_name):
        result = conn.execute(
            sa.text(
                "SELECT 1 FROM information_schema.tables WHERE table_name = :t"
            ),
            {"t": table},
        )
        if result.scalar():
            try:
                op.add_column(table, column)
            except Exception:
                pass


def upgrade() -> None:
    conn = op.get_bind()

    # --- UNIQUE constraints ---
    _safe_create_unique(conn, "users", "email", "uq_users_email")
    _safe_create_unique(conn, "incidents", "reference_number", "uq_incidents_reference")
    _safe_create_unique(conn, "risks", "reference_number", "uq_risks_reference")
    _safe_create_unique(conn, "audits", "reference_number", "uq_audits_reference")
    _safe_create_unique(conn, "complaints", "reference_number", "uq_complaints_reference")

    # --- CHECK constraints on status fields ---
    _safe_add_check(
        conn,
        "incidents",
        "ck_incidents_status",
        "status IN ('open', 'investigating', 'resolved', 'closed')",
    )
    _safe_add_check(
        conn,
        "risks",
        "ck_risks_status",
        "status IN ('open', 'mitigating', 'accepted', 'closed')",
    )
    _safe_add_check(
        conn,
        "audits",
        "ck_audits_status",
        "status IN ('planned', 'in_progress', 'completed', 'cancelled')",
    )
    _safe_add_check(
        conn,
        "complaints",
        "ck_complaints_status",
        "status IN ('open', 'investigating', 'resolved', 'closed')",
    )

    # --- Version column for optimistic locking on high-traffic tables ---
    version_col = sa.Column(
        "version", sa.Integer(), nullable=False, server_default="1"
    )
    for table in ("incidents", "risks", "audits", "complaints"):
        _safe_add_column(conn, table, "version", version_col)


def downgrade() -> None:
    conn = op.get_bind()

    for table in ("complaints", "audits", "risks", "incidents"):
        if _table_has_column(conn, table, "version"):
            op.drop_column(table, "version")

    for name in (
        "ck_complaints_status",
        "ck_audits_status",
        "ck_risks_status",
        "ck_incidents_status",
    ):
        try:
            op.drop_constraint(name, name.split("_")[1] + "s")
        except Exception:
            pass

    for name in (
        "uq_complaints_reference",
        "uq_audits_reference",
        "uq_risks_reference",
        "uq_incidents_reference",
        "uq_users_email",
    ):
        try:
            table = name.replace("uq_", "").rsplit("_", 1)[0]
            op.drop_constraint(name, table)
        except Exception:
            pass
