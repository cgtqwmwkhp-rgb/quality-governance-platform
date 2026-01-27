"""Add source_form_id audit fields for incident routing traceability.

Revision ID: 20260127_source_form
Revises: 20260126_stage2_investigation_enhancements
Create Date: 2026-01-27 10:00:00.000000

This migration adds audit fields to track the source of portal submissions:
- source_form_id: Identifies which portal form was used (incident, near_miss, complaint, rta)
- This enables deterministic tracing from submission to dashboard routing
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260127_source_form"
down_revision = "20260126_stage2_investigation_enhancements"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add source_form_id field to incident-related tables for audit traceability."""
    
    # Add source_form_id to incidents table
    # This tracks which portal form was used (incident, near_miss, rta, complaint)
    op.add_column(
        "incidents",
        sa.Column(
            "source_form_id",
            sa.String(50),
            nullable=True,
            comment="Portal form identifier for routing audit (e.g., 'portal_incident_v1')",
        ),
    )
    
    # Add source_form_id to road_traffic_collisions table
    op.add_column(
        "road_traffic_collisions",
        sa.Column(
            "source_form_id",
            sa.String(50),
            nullable=True,
            comment="Portal form identifier for routing audit (e.g., 'portal_rta_v1')",
        ),
    )
    
    # Add source_form_id to near_misses table
    op.add_column(
        "near_misses",
        sa.Column(
            "source_form_id",
            sa.String(50),
            nullable=True,
            comment="Portal form identifier for routing audit (e.g., 'portal_near_miss_v1')",
        ),
    )
    
    # Add source_form_id to complaints table
    op.add_column(
        "complaints",
        sa.Column(
            "source_form_id",
            sa.String(50),
            nullable=True,
            comment="Portal form identifier for routing audit (e.g., 'portal_complaint_v1')",
        ),
    )
    
    # Create index for source_form_id queries (for audit reports)
    op.create_index(
        "ix_incidents_source_form_id",
        "incidents",
        ["source_form_id"],
        unique=False,
    )
    op.create_index(
        "ix_road_traffic_collisions_source_form_id",
        "road_traffic_collisions",
        ["source_form_id"],
        unique=False,
    )
    op.create_index(
        "ix_near_misses_source_form_id",
        "near_misses",
        ["source_form_id"],
        unique=False,
    )
    op.create_index(
        "ix_complaints_source_form_id",
        "complaints",
        ["source_form_id"],
        unique=False,
    )


def downgrade() -> None:
    """Remove source_form_id fields."""
    # Drop indexes first
    op.drop_index("ix_complaints_source_form_id", table_name="complaints")
    op.drop_index("ix_near_misses_source_form_id", table_name="near_misses")
    op.drop_index("ix_road_traffic_collisions_source_form_id", table_name="road_traffic_collisions")
    op.drop_index("ix_incidents_source_form_id", table_name="incidents")
    
    # Drop columns
    op.drop_column("complaints", "source_form_id")
    op.drop_column("near_misses", "source_form_id")
    op.drop_column("road_traffic_collisions", "source_form_id")
    op.drop_column("incidents", "source_form_id")
