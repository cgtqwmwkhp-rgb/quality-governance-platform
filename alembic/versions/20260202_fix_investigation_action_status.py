"""Convert investigation_actions status from native ENUM to VARCHAR.

Revision ID: 20260202_fix_status
Revises: 20260201_external_ref
Create Date: 2026-02-02 14:00:00.000000

Root Cause: The model uses native_enum=False but the original migration created
a native PostgreSQL ENUM type. This mismatch can cause issues during INSERT.

This migration:
1. Adds a new VARCHAR column for status
2. Copies existing data
3. Drops the ENUM column
4. Renames the VARCHAR column
5. Drops the ENUM type

Rollback: alembic downgrade 20260201_external_ref
Note: Rollback will recreate the native ENUM type.
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260202_fix_status"
down_revision = "20260201_external_ref"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Convert status column from native ENUM to VARCHAR."""
    # Step 1: Add new VARCHAR column
    op.add_column(
        "investigation_actions",
        sa.Column("status_new", sa.String(50), nullable=True, server_default="open"),
    )

    # Step 2: Copy data - cast ENUM to text
    op.execute("UPDATE investigation_actions SET status_new = status::text WHERE status IS NOT NULL")

    # Step 3: Drop the old ENUM column
    op.drop_column("investigation_actions", "status")

    # Step 4: Rename new column to status
    op.alter_column("investigation_actions", "status_new", new_column_name="status")

    # Step 5: Drop the ENUM type (cleanup)
    op.execute("DROP TYPE IF EXISTS investigationactionstatus")

    # Step 6: Re-create index on status if it existed
    op.create_index(
        "ix_investigation_actions_status",
        "investigation_actions",
        ["status"],
    )


def downgrade() -> None:
    """Revert to native ENUM type."""
    # Step 1: Re-create the ENUM type
    op.execute(
        "CREATE TYPE investigationactionstatus AS ENUM "
        "('open', 'in_progress', 'pending_verification', 'completed', 'cancelled')"
    )

    # Step 2: Add new ENUM column
    op.add_column(
        "investigation_actions",
        sa.Column(
            "status_new",
            sa.Enum(
                "open",
                "in_progress",
                "pending_verification",
                "completed",
                "cancelled",
                name="investigationactionstatus",
            ),
            nullable=True,
            server_default="open",
        ),
    )

    # Step 3: Copy data
    op.execute(
        "UPDATE investigation_actions SET status_new = status::investigationactionstatus " "WHERE status IS NOT NULL"
    )

    # Step 4: Drop VARCHAR column
    op.drop_index("ix_investigation_actions_status", table_name="investigation_actions")
    op.drop_column("investigation_actions", "status")

    # Step 5: Rename
    op.alter_column("investigation_actions", "status_new", new_column_name="status")

    # Step 6: Recreate index
    op.create_index(
        "ix_investigation_actions_status",
        "investigation_actions",
        ["status"],
    )
