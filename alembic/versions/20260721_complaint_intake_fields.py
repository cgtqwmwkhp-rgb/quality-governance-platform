"""Add complaint intake fields for customer, subject, alleged event, channel.

Revision ID: 20260721_cmp_intake
Revises: 20260720_matter_holds
Create Date: 2026-07-21

Wave 1 Complaints create: contract_id, subject_user_id, subject_name,
alleged_event_at, and expand source_type to include in_person.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260721_cmp_intake"
down_revision: Union[str, Sequence[str], None] = "20260720_matter_holds"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "complaints",
        sa.Column("contract_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "complaints",
        sa.Column("subject_user_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "complaints",
        sa.Column("subject_name", sa.String(length=200), nullable=True),
    )
    op.add_column(
        "complaints",
        sa.Column("alleged_event_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_complaints_contract_id",
        "complaints",
        "contracts",
        ["contract_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_complaints_subject_user_id",
        "complaints",
        "users",
        ["subject_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_complaints_contract_id", "complaints", ["contract_id"])
    op.create_index("ix_complaints_subject_user_id", "complaints", ["subject_user_id"])

    op.drop_constraint("ck_complaint_source_type", "complaints", type_="check")
    op.create_check_constraint(
        "ck_complaint_source_type",
        "complaints",
        "source_type IN ('manual', 'email', 'api', 'phone', 'portal', 'in_person')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_complaint_source_type", "complaints", type_="check")
    op.create_check_constraint(
        "ck_complaint_source_type",
        "complaints",
        "source_type IN ('manual', 'email', 'api', 'phone', 'portal')",
    )
    op.drop_index("ix_complaints_subject_user_id", table_name="complaints")
    op.drop_index("ix_complaints_contract_id", table_name="complaints")
    op.drop_constraint("fk_complaints_subject_user_id", "complaints", type_="foreignkey")
    op.drop_constraint("fk_complaints_contract_id", "complaints", type_="foreignkey")
    op.drop_column("complaints", "alleged_event_at")
    op.drop_column("complaints", "subject_name")
    op.drop_column("complaints", "subject_user_id")
    op.drop_column("complaints", "contract_id")
