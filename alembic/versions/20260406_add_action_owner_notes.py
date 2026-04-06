"""Add action_owner_notes for time-stamped action commentary.

Revision ID: e4f5a6b7c8d9
Revises: d3e4f5a6b7c8
Create Date: 2026-04-06
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e4f5a6b7c8d9"
down_revision: Union[str, None] = "d3e4f5a6b7c8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "action_owner_notes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("action_key", sa.String(length=64), nullable=False),
        sa.Column("author_id", sa.Integer(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["author_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_action_owner_notes_tenant_id", "action_owner_notes", ["tenant_id"])
    op.create_index("ix_action_owner_notes_action_key", "action_owner_notes", ["action_key"])
    op.create_index("ix_action_owner_notes_author_id", "action_owner_notes", ["author_id"])
    op.create_index(
        "ix_action_owner_notes_tenant_key_created",
        "action_owner_notes",
        ["tenant_id", "action_key", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_action_owner_notes_tenant_key_created", table_name="action_owner_notes")
    op.drop_index("ix_action_owner_notes_author_id", table_name="action_owner_notes")
    op.drop_index("ix_action_owner_notes_action_key", table_name="action_owner_notes")
    op.drop_index("ix_action_owner_notes_tenant_id", table_name="action_owner_notes")
    op.drop_table("action_owner_notes")
