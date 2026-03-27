"""Add rta_running_sheet_entries table for timestamped RTA narrative log.

Revision ID: 20260321_run_sheet
Revises: 20260320_veh_reg
Create Date: 2026-03-21
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260321_run_sheet"
down_revision: Union[str, None] = "20260320_drivers"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _current_timestamp_default() -> sa.TextClause:
    return sa.text("CURRENT_TIMESTAMP")


def _has_table(table_name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(table_name)


def upgrade() -> None:
    if not _has_table("rta_running_sheet_entries"):
        op.create_table(
            "rta_running_sheet_entries",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("rta_id", sa.Integer(), sa.ForeignKey("road_traffic_collisions.id", ondelete="CASCADE"), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("entry_type", sa.String(50), nullable=False, server_default="note"),
            sa.Column("author_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("author_email", sa.String(255), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=_current_timestamp_default()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=_current_timestamp_default()),
            sa.PrimaryKeyConstraint("id"),
        )
    op.execute("CREATE INDEX IF NOT EXISTS ix_rta_running_sheet_rta_id ON rta_running_sheet_entries(rta_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_rta_running_sheet_created ON rta_running_sheet_entries(created_at)")


def downgrade() -> None:
    if _has_table("rta_running_sheet_entries"):
        op.drop_table("rta_running_sheet_entries")
