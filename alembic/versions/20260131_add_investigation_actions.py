"""Add investigation_actions table to fix 'Cannot add action' defect.

Revision ID: 20260131_inv_actions
Revises: 20260127_source_form
Create Date: 2026-01-31 20:00:00.000000

Root Cause: The UI attempted to add actions to investigations, but the backend
only supported actions for incidents, RTAs, and complaints - NOT investigations.

This migration adds the investigation_actions table, following the same pattern
as incident_actions, rta_actions, and complaint_actions tables.

Rollback: alembic downgrade 20260127_source_form
Data Loss Warning: Rollback drops all investigation_actions data.
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260131_inv_actions"
down_revision = "20260127_source_form"
branch_labels = None
depends_on = None


def _current_timestamp_default() -> sa.TextClause:
    return sa.text("CURRENT_TIMESTAMP")


def _has_index(table_name: str, index_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table(table_name):
        return False
    return any(index["name"] == index_name for index in inspector.get_indexes(table_name))


def upgrade() -> None:
    """Create investigation_actions table."""
    op.create_table(
        "investigation_actions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("investigation_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("action_type", sa.String(length=50), server_default="corrective", nullable=True),
        sa.Column("priority", sa.String(length=20), server_default="medium", nullable=True),
        sa.Column("owner_id", sa.Integer(), nullable=True),
        sa.Column(
            "status",
            sa.Enum("open", "in_progress", "pending_verification", "completed", "cancelled", name="investigationactionstatus"),
            server_default="open",
            nullable=True,
        ),
        sa.Column("due_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("verified_by_id", sa.Integer(), nullable=True),
        sa.Column("completion_notes", sa.Text(), nullable=True),
        sa.Column("verification_notes", sa.Text(), nullable=True),
        sa.Column("effectiveness_review_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("effectiveness_notes", sa.Text(), nullable=True),
        sa.Column("is_effective", sa.Boolean(), nullable=True),
        # Timestamps (from TimestampMixin)
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=_current_timestamp_default(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=_current_timestamp_default(), nullable=True),
        # Reference number (from ReferenceNumberMixin)
        sa.Column("reference_number", sa.String(length=50), nullable=True),
        # Audit trail (from AuditTrailMixin)
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("updated_by_id", sa.Integer(), nullable=True),
        # Primary key
        sa.PrimaryKeyConstraint("id"),
        # Foreign keys
        sa.ForeignKeyConstraint(
            ["investigation_id"],
            ["investigation_runs.id"],
            name="fk_investigation_actions_investigation_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], name="fk_investigation_actions_owner_id"),
        sa.ForeignKeyConstraint(["verified_by_id"], ["users.id"], name="fk_investigation_actions_verified_by_id"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], name="fk_investigation_actions_created_by_id"),
        sa.ForeignKeyConstraint(["updated_by_id"], ["users.id"], name="fk_investigation_actions_updated_by_id"),
    )

    # Create indexes
    op.create_index("ix_investigation_actions_investigation_id", "investigation_actions", ["investigation_id"])
    op.create_index("ix_investigation_actions_status", "investigation_actions", ["status"])
    op.create_index("ix_investigation_actions_owner_id", "investigation_actions", ["owner_id"])
    op.create_index("ix_investigation_actions_due_date", "investigation_actions", ["due_date"])


def downgrade() -> None:
    """Drop investigation_actions table.
    
    WARNING: This drops all investigation action data permanently.
    """
    if _has_index("investigation_actions", "ix_investigation_actions_due_date"):
        op.drop_index("ix_investigation_actions_due_date", table_name="investigation_actions")
    if _has_index("investigation_actions", "ix_investigation_actions_owner_id"):
        op.drop_index("ix_investigation_actions_owner_id", table_name="investigation_actions")
    if _has_index("investigation_actions", "ix_investigation_actions_status"):
        op.drop_index("ix_investigation_actions_status", table_name="investigation_actions")
    if _has_index("investigation_actions", "ix_investigation_actions_investigation_id"):
        op.drop_index("ix_investigation_actions_investigation_id", table_name="investigation_actions")
    if sa.inspect(op.get_bind()).has_table("investigation_actions"):
        op.drop_table("investigation_actions")
    
    # Drop the enum type
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP TYPE IF EXISTS investigationactionstatus")
