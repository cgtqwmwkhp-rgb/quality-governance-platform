"""R5: OCR artifacts table for page-level consensus persistence.

Revision ID: 20260717_ocr_artifacts
Revises: 20260716_partner_webhooks
Create Date: 2026-07-17

Chained after Wave5 (#1013) ``20260716_partner_webhooks``.
Sibling lanes may rebase; down_revision is exclusive to this chain head.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "20260717_ocr_artifacts"
down_revision: Union[str, Sequence[str], None] = "20260716_partner_webhooks"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ocr_artifacts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("pipeline_version", sa.String(length=32), nullable=False),
        sa.Column("job_ref", sa.String(length=64), nullable=True),
        sa.Column("draft_ref", sa.String(length=64), nullable=True),
        sa.Column("tier", sa.String(length=16), nullable=False, server_default="advisory"),
        sa.Column("override_status", sa.String(length=16), nullable=False, server_default="none"),
        sa.Column("override_note", sa.Text(), nullable=True),
        sa.Column("overridden_by", sa.String(length=128), nullable=True),
        sa.Column("overridden_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ocr_artifacts_tenant_id", "ocr_artifacts", ["tenant_id"])
    op.create_index("ix_ocr_artifacts_job_page", "ocr_artifacts", ["job_ref", "page_number"])
    op.create_index("ix_ocr_artifacts_draft_page", "ocr_artifacts", ["draft_ref", "page_number"])
    op.create_index("ix_ocr_artifacts_tenant_job", "ocr_artifacts", ["tenant_id", "job_ref"])


def downgrade() -> None:
    op.drop_index("ix_ocr_artifacts_tenant_job", table_name="ocr_artifacts")
    op.drop_index("ix_ocr_artifacts_draft_page", table_name="ocr_artifacts")
    op.drop_index("ix_ocr_artifacts_job_page", table_name="ocr_artifacts")
    op.drop_index("ix_ocr_artifacts_tenant_id", table_name="ocr_artifacts")
    op.drop_table("ocr_artifacts")
