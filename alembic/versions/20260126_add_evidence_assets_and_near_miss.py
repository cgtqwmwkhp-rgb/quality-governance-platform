"""Add evidence_assets table and NEAR_MISS investigation support.

Revision ID: 20260126_evidence_assets
Revises: 20260122_azure_oid
Create Date: 2026-01-26 17:00:00.000000

This migration:
1. Creates the evidence_assets table for unified attachment management
2. NEAR_MISS enum value support is automatic (native_enum=False uses VARCHAR)
3. Adds indexes for efficient querying

Stage 0.5 Blocker Remediation:
- Fixes RTA photo persistence (OPTION 1: Shared EvidenceAssets module)
- Enables Near Miss → Investigation support
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260126_evidence_assets"
down_revision: Union[str, None] = "20260122_azure_oid"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create evidence_assets table for unified attachment management."""
    # Create evidence_assets table
    op.create_table(
        "evidence_assets",
        # Primary key
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        # Storage reference
        sa.Column("storage_key", sa.String(500), nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=True),
        sa.Column("content_type", sa.String(100), nullable=False),
        sa.Column("file_size_bytes", sa.Integer(), nullable=True),
        sa.Column("checksum_sha256", sa.String(64), nullable=True),
        # Asset classification (VARCHAR for enum since native_enum=False)
        sa.Column("asset_type", sa.String(50), nullable=False, server_default="other"),
        # Source linkage (polymorphic association)
        sa.Column("source_module", sa.String(50), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        # Optional secondary linkage to investigation
        sa.Column(
            "linked_investigation_id",
            sa.Integer(),
            sa.ForeignKey("investigation_runs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        # Metadata
        sa.Column("title", sa.String(300), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("captured_by_role", sa.String(100), nullable=True),
        # GPS/Location metadata
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("location_description", sa.String(500), nullable=True),
        # Render hints
        sa.Column("render_hint", sa.String(50), nullable=True),
        sa.Column("thumbnail_storage_key", sa.String(500), nullable=True),
        # Extended metadata (JSON)
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        # Visibility and customer pack rules (VARCHAR for enum)
        sa.Column("visibility", sa.String(50), nullable=False, server_default="internal_customer"),
        sa.Column("contains_pii", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("redaction_required", sa.Boolean(), nullable=False, server_default="false"),
        # Retention (VARCHAR for enum)
        sa.Column("retention_policy", sa.String(50), nullable=False, server_default="standard"),
        sa.Column("retention_expires_at", sa.DateTime(timezone=True), nullable=True),
        # Soft delete
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "deleted_by_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        # Audit trail (from AuditTrailMixin)
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("updated_by_id", sa.Integer(), nullable=True),
        # Timestamps (from TimestampMixin)
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
        # Primary key constraint
        sa.PrimaryKeyConstraint("id"),
    )

    # Create indexes for efficient querying
    op.create_index(
        "ix_evidence_assets_storage_key",
        "evidence_assets",
        ["storage_key"],
        unique=True,
    )
    op.create_index(
        "ix_evidence_assets_source",
        "evidence_assets",
        ["source_module", "source_id"],
    )
    op.create_index(
        "ix_evidence_assets_type",
        "evidence_assets",
        ["asset_type"],
    )
    op.create_index(
        "ix_evidence_assets_visibility",
        "evidence_assets",
        ["visibility"],
    )
    op.create_index(
        "ix_evidence_assets_linked_investigation_id",
        "evidence_assets",
        ["linked_investigation_id"],
    )
    op.create_index(
        "ix_evidence_assets_source_module",
        "evidence_assets",
        ["source_module"],
    )
    op.create_index(
        "ix_evidence_assets_source_id",
        "evidence_assets",
        ["source_id"],
    )


def downgrade() -> None:
    """Drop evidence_assets table."""
    # Drop indexes
    op.drop_index("ix_evidence_assets_source_id", table_name="evidence_assets")
    op.drop_index("ix_evidence_assets_source_module", table_name="evidence_assets")
    op.drop_index("ix_evidence_assets_linked_investigation_id", table_name="evidence_assets")
    op.drop_index("ix_evidence_assets_visibility", table_name="evidence_assets")
    op.drop_index("ix_evidence_assets_type", table_name="evidence_assets")
    op.drop_index("ix_evidence_assets_source", table_name="evidence_assets")
    op.drop_index("ix_evidence_assets_storage_key", table_name="evidence_assets")

    # Drop table
    op.drop_table("evidence_assets")
