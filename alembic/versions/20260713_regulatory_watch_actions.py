"""GKB WL2: regulatory watch impacts → real Actions (owner/due/resolve).

Revision ID: 20260713_rw_actions
Revises: 20260713_op_assess
Create Date: 2026-07-13

- Adds CAPASource.regulatory_watch enum value
- Adds action_id / owner_id / due_date / resolve columns on regulatory_watch_impacts
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260713_rw_actions"
down_revision: Union[str, Sequence[str], None] = "20260713_op_assess"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        result = conn.execute(sa.text("SELECT 1 FROM pg_type WHERE typname = 'capasource'")).fetchone()
        if result:
            try:
                op.execute("ALTER TYPE capasource ADD VALUE IF NOT EXISTS 'regulatory_watch'")
            except Exception:
                pass

    with op.batch_alter_table("regulatory_watch_impacts") as batch:
        batch.add_column(sa.Column("action_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("owner_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("due_date", sa.DateTime(), nullable=True))
        batch.add_column(sa.Column("resolved_at", sa.DateTime(), nullable=True))
        batch.add_column(sa.Column("resolved_by_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("resolution_notes", sa.Text(), nullable=True))
        batch.create_foreign_key(
            "fk_rwi_action_id",
            "capa_actions",
            ["action_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch.create_foreign_key("fk_rwi_owner_id", "users", ["owner_id"], ["id"])
        batch.create_foreign_key("fk_rwi_resolved_by_id", "users", ["resolved_by_id"], ["id"])
        batch.create_index("ix_rwi_action", ["action_id"])


def downgrade() -> None:
    with op.batch_alter_table("regulatory_watch_impacts") as batch:
        batch.drop_index("ix_rwi_action")
        batch.drop_constraint("fk_rwi_resolved_by_id", type_="foreignkey")
        batch.drop_constraint("fk_rwi_owner_id", type_="foreignkey")
        batch.drop_constraint("fk_rwi_action_id", type_="foreignkey")
        batch.drop_column("resolution_notes")
        batch.drop_column("resolved_by_id")
        batch.drop_column("resolved_at")
        batch.drop_column("due_date")
        batch.drop_column("owner_id")
        batch.drop_column("action_id")
