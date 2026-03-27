"""Add unique constraint on investigation source.

Prevents duplicate investigations for the same source record.
Adds a unique index on (assigned_entity_type, assigned_entity_id).

Revision ID: 20260126_inv_unique_src
Revises: 20260126_stage2_inv
Create Date: 2026-01-26 23:00:00.000000
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260126_inv_unique_src"
down_revision: Union[str, None] = "20260126_stage2_inv"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add unique constraint on source record.

    Creates a unique index on (assigned_entity_type, assigned_entity_id) to prevent
    duplicate investigations for the same source record. This enforces the business
    rule that each source record can have at most one investigation.

    First removes any duplicate records, keeping only the most recently created one.
    The constraint is implemented as a unique index rather than a unique constraint
    because PostgreSQL handles them equivalently and indexes are more flexible.
    """
    # First, remove duplicate records keeping only the most recently created one.
    # Use a window function so the cleanup works on both PostgreSQL and SQLite.
    op.execute("""
        WITH ranked_investigations AS (
            SELECT
                id,
                ROW_NUMBER() OVER (
                    PARTITION BY assigned_entity_type, assigned_entity_id
                    ORDER BY
                        CASE WHEN created_at IS NULL THEN 1 ELSE 0 END,
                        created_at DESC,
                        id DESC
                ) AS row_rank
            FROM investigation_runs
        )
        DELETE FROM investigation_runs
        WHERE id IN (
            SELECT id
            FROM ranked_investigations
            WHERE row_rank > 1
        )
    """)

    # Create unique index to prevent duplicate investigations for same source
    op.create_index(
        "uq_investigation_runs_source",
        "investigation_runs",
        ["assigned_entity_type", "assigned_entity_id"],
        unique=True,
    )


def downgrade() -> None:
    """Remove unique constraint on source record."""
    op.drop_index("uq_investigation_runs_source", table_name="investigation_runs")
