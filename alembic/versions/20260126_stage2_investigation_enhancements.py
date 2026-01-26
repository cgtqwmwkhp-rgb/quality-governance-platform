"""Stage 2 Investigation enhancements.

Adds:
- Source snapshot fields to investigation_runs
- Optimistic locking (version field)
- Investigation level (LOW/MEDIUM/HIGH)
- Approval workflow fields
- investigation_comments table
- investigation_revision_events table
- investigation_customer_packs table

Revision ID: 20260126_stage2_inv
Revises: 20260126_evidence_assets
Create Date: 2026-01-26 18:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260126_stage2_inv"
down_revision: Union[str, None] = "20260126_evidence_assets"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add Stage 2 investigation enhancements."""

    # === Add new columns to investigation_runs ===

    # Investigation level (determines required sections)
    op.add_column(
        "investigation_runs",
        sa.Column("level", sa.String(20), nullable=True),
    )

    # Source snapshot fields (Mapping Contract v1)
    op.add_column(
        "investigation_runs",
        sa.Column("source_schema_version", sa.String(20), nullable=True),
    )
    op.add_column(
        "investigation_runs",
        sa.Column("source_snapshot", sa.JSON(), nullable=True),
    )
    op.add_column(
        "investigation_runs",
        sa.Column("mapping_log", sa.JSON(), nullable=True),
    )

    # Optimistic locking
    op.add_column(
        "investigation_runs",
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
    )

    # Approval workflow
    op.add_column(
        "investigation_runs",
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "investigation_runs",
        sa.Column("approved_by_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "investigation_runs",
        sa.Column("rejection_reason", sa.Text(), nullable=True),
    )

    # Add foreign key for approved_by
    op.create_foreign_key(
        "fk_investigation_runs_approved_by",
        "investigation_runs",
        "users",
        ["approved_by_id"],
        ["id"],
    )

    # === Create investigation_comments table ===
    op.create_table(
        "investigation_comments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "investigation_id",
            sa.Integer(),
            sa.ForeignKey("investigation_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("section_id", sa.String(50), nullable=True),
        sa.Column("field_id", sa.String(50), nullable=True),
        sa.Column(
            "parent_comment_id",
            sa.Integer(),
            sa.ForeignKey("investigation_comments.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("author_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_investigation_comments_investigation_id",
        "investigation_comments",
        ["investigation_id"],
    )
    op.create_index(
        "ix_investigation_comments_author_id",
        "investigation_comments",
        ["author_id"],
    )

    # === Create investigation_revision_events table ===
    op.create_table(
        "investigation_revision_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "investigation_id",
            sa.Integer(),
            sa.ForeignKey("investigation_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("field_path", sa.String(200), nullable=True),
        sa.Column("old_value", sa.JSON(), nullable=True),
        sa.Column("new_value", sa.JSON(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("actor_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_investigation_revision_events_investigation_id",
        "investigation_revision_events",
        ["investigation_id"],
    )
    op.create_index(
        "ix_investigation_revision_events_event_type",
        "investigation_revision_events",
        ["event_type"],
    )

    # === Create investigation_customer_packs table ===
    op.create_table(
        "investigation_customer_packs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "investigation_id",
            sa.Integer(),
            sa.ForeignKey("investigation_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("pack_uuid", sa.String(36), unique=True, nullable=False),
        sa.Column("audience", sa.String(50), nullable=False),
        sa.Column("content", sa.JSON(), nullable=False),
        sa.Column("redaction_log", sa.JSON(), nullable=True),
        sa.Column("included_assets", sa.JSON(), nullable=True),
        sa.Column("checksum_sha256", sa.String(64), nullable=False),
        sa.Column("generated_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("generated_by_role", sa.String(100), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_investigation_customer_packs_investigation_id",
        "investigation_customer_packs",
        ["investigation_id"],
    )
    op.create_index(
        "ix_investigation_customer_packs_pack_uuid",
        "investigation_customer_packs",
        ["pack_uuid"],
        unique=True,
    )
    op.create_index(
        "ix_investigation_customer_packs_audience",
        "investigation_customer_packs",
        ["audience"],
    )


def downgrade() -> None:
    """Remove Stage 2 investigation enhancements."""

    # Drop tables
    op.drop_index("ix_investigation_customer_packs_audience", table_name="investigation_customer_packs")
    op.drop_index("ix_investigation_customer_packs_pack_uuid", table_name="investigation_customer_packs")
    op.drop_index("ix_investigation_customer_packs_investigation_id", table_name="investigation_customer_packs")
    op.drop_table("investigation_customer_packs")

    op.drop_index("ix_investigation_revision_events_event_type", table_name="investigation_revision_events")
    op.drop_index("ix_investigation_revision_events_investigation_id", table_name="investigation_revision_events")
    op.drop_table("investigation_revision_events")

    op.drop_index("ix_investigation_comments_author_id", table_name="investigation_comments")
    op.drop_index("ix_investigation_comments_investigation_id", table_name="investigation_comments")
    op.drop_table("investigation_comments")

    # Drop foreign key and columns from investigation_runs
    op.drop_constraint("fk_investigation_runs_approved_by", "investigation_runs", type_="foreignkey")

    op.drop_column("investigation_runs", "rejection_reason")
    op.drop_column("investigation_runs", "approved_by_id")
    op.drop_column("investigation_runs", "approved_at")
    op.drop_column("investigation_runs", "version")
    op.drop_column("investigation_runs", "mapping_log")
    op.drop_column("investigation_runs", "source_snapshot")
    op.drop_column("investigation_runs", "source_schema_version")
    op.drop_column("investigation_runs", "level")
