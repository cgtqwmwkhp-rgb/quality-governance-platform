"""Add H&S KPI reporting-period inputs.

Revision ID: 20260809_hs_kpi_periods
Revises: 20260808_hs_injury
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260809_hs_kpi_periods"
down_revision: Union[str, Sequence[str], None] = "20260808_hs_injury"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "hs_reporting_periods",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("reporting_year", sa.Integer(), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("average_fte", sa.Float(), nullable=False),
        sa.Column("hours_per_fte_year", sa.Float(), nullable=False, server_default="2124"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "reporting_year", name="uq_hs_period_tenant_year"),
    )
    op.create_index("ix_hs_reporting_periods_tenant_id", "hs_reporting_periods", ["tenant_id"])


def downgrade() -> None:
    op.drop_index("ix_hs_reporting_periods_tenant_id", table_name="hs_reporting_periods")
    op.drop_table("hs_reporting_periods")
