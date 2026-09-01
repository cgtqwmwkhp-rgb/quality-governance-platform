"""Competence change requests (CB-PR2).

Revision ID: 20260901_comp_cr
Revises: 20260901_pams_comp

Row-first requests to IT-Admin (plant) or HR Advisor (statutory). QGP never
writes PAMS. One open request per cell.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "20260901_comp_cr"
down_revision: Union[str, Sequence[str], None] = "20260901_pams_comp"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(table_name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(table_name)


def upgrade() -> None:
    if _has_table("competence_change_requests"):
        return
    op.create_table(
        "competence_change_requests",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("family", sa.String(length=16), nullable=False),
        sa.Column("engineer_id", sa.Integer(), nullable=False),
        sa.Column("characteristic_key", sa.String(length=80), nullable=False),
        sa.Column("action", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="open"),
        sa.Column("routed_to_email", sa.String(length=255), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("email_sent", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("email_error", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("closed_at", sa.DateTime(), nullable=True),
        sa.Column("close_reason", sa.String(length=80), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_competence_change_requests_tenant_id", "competence_change_requests", ["tenant_id"])
    op.create_index("ix_competence_change_requests_engineer_id", "competence_change_requests", ["engineer_id"])
    op.create_index(
        "uq_competence_change_requests_open_cell",
        "competence_change_requests",
        ["tenant_id", "family", "engineer_id", "characteristic_key"],
        unique=True,
        postgresql_where=sa.text("status = 'open'"),
    )


def downgrade() -> None:
    if not _has_table("competence_change_requests"):
        return
    op.drop_index("uq_competence_change_requests_open_cell", table_name="competence_change_requests")
    op.drop_index("ix_competence_change_requests_engineer_id", table_name="competence_change_requests")
    op.drop_index("ix_competence_change_requests_tenant_id", table_name="competence_change_requests")
    op.drop_table("competence_change_requests")
