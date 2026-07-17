"""EMP-W1: engineer PAMS technician sync fields.

Revision ID: 20260722_emp_pams
Revises: 20260721_cmp_intake
Create Date: 2026-07-22

- engineers.user_id nullable (unique preserved; PG allows multiple NULLs)
- display_name, pams_technician_id columns
- partial unique (tenant_id, pams_technician_id) where pams_technician_id IS NOT NULL
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260722_emp_pams"
down_revision: Union[str, Sequence[str], None] = "20260721_cmp_intake"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("engineers", sa.Column("display_name", sa.String(length=200), nullable=True))
    op.add_column("engineers", sa.Column("pams_technician_id", sa.Integer(), nullable=True))
    op.alter_column("engineers", "user_id", existing_type=sa.Integer(), nullable=True)
    op.create_index(
        "uq_engineers_tenant_pams_technician_id",
        "engineers",
        ["tenant_id", "pams_technician_id"],
        unique=True,
        postgresql_where=sa.text("pams_technician_id IS NOT NULL"),
        sqlite_where=sa.text("pams_technician_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_engineers_tenant_pams_technician_id", table_name="engineers")
    op.alter_column("engineers", "user_id", existing_type=sa.Integer(), nullable=False)
    op.drop_column("engineers", "pams_technician_id")
    op.drop_column("engineers", "display_name")
