"""Add compliance_evidence_links table for ISO evidence mapping.

Revision ID: 20260220_compliance_evidence
Revises: 20260202_fix_inv_action_status
Create Date: 2026-02-20 10:00:00.000000

Provides persistent storage for evidence-to-ISO-clause links,
replacing the mock in-memory approach.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260220_compliance_evidence"
down_revision: Union[str, None] = "20260202_fix_status"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "compliance_evidence_links",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("entity_id", sa.String(100), nullable=False),
        sa.Column("clause_id", sa.String(50), nullable=False),
        sa.Column("linked_by", sa.String(10), nullable=False, server_default="manual"),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("title", sa.String(300), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("created_by_email", sa.String(255), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index("ix_cel_entity_type", "compliance_evidence_links", ["entity_type"])
    op.create_index("ix_cel_clause", "compliance_evidence_links", ["clause_id"])
    op.create_index(
        "ix_cel_entity",
        "compliance_evidence_links",
        ["entity_type", "entity_id"],
    )
    op.create_index(
        "ix_cel_entity_clause",
        "compliance_evidence_links",
        ["entity_type", "entity_id", "clause_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_cel_entity_clause", table_name="compliance_evidence_links")
    op.drop_index("ix_cel_entity", table_name="compliance_evidence_links")
    op.drop_index("ix_cel_clause", table_name="compliance_evidence_links")
    op.drop_index("ix_cel_entity_type", table_name="compliance_evidence_links")
    op.drop_table("compliance_evidence_links")
