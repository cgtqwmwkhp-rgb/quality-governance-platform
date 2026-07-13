"""Add signal_type for operational standards assessment links.

Revision ID: 20260713_op_assess
Revises: 20260713_governed_kb
Create Date: 2026-07-13
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "20260713_op_assess"
down_revision: Union[str, Sequence[str], None] = "20260713_governed_kb"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "compliance_evidence_links",
        sa.Column("signal_type", sa.String(30), nullable=True),
    )
    op.create_index("ix_cel_signal_type", "compliance_evidence_links", ["signal_type"])


def downgrade() -> None:
    op.drop_index("ix_cel_signal_type", table_name="compliance_evidence_links")
    op.drop_column("compliance_evidence_links", "signal_type")
