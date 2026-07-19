"""Add document-level progress counters to index_jobs (O-14 bulk reprocess).

Revision ID: 20260719_index_job_doc_prog
Revises: 20260728_campaign_sig_disp
Create Date: 2026-07-19
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260719_index_job_doc_prog"
down_revision: Union[str, Sequence[str], None] = "20260728_campaign_sig_disp"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "index_jobs",
        sa.Column("documents_processed", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "index_jobs",
        sa.Column("documents_succeeded", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "index_jobs",
        sa.Column("documents_failed", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("index_jobs", "documents_failed")
    op.drop_column("index_jobs", "documents_succeeded")
    op.drop_column("index_jobs", "documents_processed")
