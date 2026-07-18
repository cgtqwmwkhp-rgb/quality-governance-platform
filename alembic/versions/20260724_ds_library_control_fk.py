"""DS-5: hard FK controlled_documents.library_document_id + soft-match backfill.

Revision ID: 20260724_ds_lib_ctrl_fk
Revises: 20260723_rr_notes_act
Create Date: 2026-07-24
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from src.domain.services.gkb_control_library_link import SOFT_MATCH_BACKFILL_SQL

revision: str = "20260724_ds_lib_ctrl_fk"
down_revision: Union[str, Sequence[str], None] = "20260723_rr_notes_act"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("controlled_documents", sa.Column("library_document_id", sa.Integer(), nullable=True))
    op.create_index(
        "ix_controlled_documents_library_document_id",
        "controlled_documents",
        ["library_document_id"],
    )
    op.create_foreign_key(
        "fk_controlled_documents_library_document_id",
        "controlled_documents",
        "documents",
        ["library_document_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.execute(sa.text(SOFT_MATCH_BACKFILL_SQL))


def downgrade() -> None:
    op.drop_constraint("fk_controlled_documents_library_document_id", "controlled_documents", type_="foreignkey")
    op.drop_index("ix_controlled_documents_library_document_id", table_name="controlled_documents")
    op.drop_column("controlled_documents", "library_document_id")
