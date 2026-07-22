"""Audit branching + reporting: assessment_mode/asset_type/location/customer dimensions,
response applicability, and section applicability rules.

Revision ID: 20260805_audit_branch_rpt
Revises: 20260804_safety_lu
Create Date: 2026-08-05
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260805_audit_branch_rpt"
down_revision: Union[str, Sequence[str], None] = "20260804_safety_lu"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- audit_runs: reporting dimensions ---
    op.add_column("audit_runs", sa.Column("assessment_mode", sa.String(length=50), nullable=True))
    op.add_column(
        "audit_runs",
        sa.Column(
            "asset_type_id",
            sa.Integer(),
            sa.ForeignKey("asset_types.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "audit_runs",
        sa.Column(
            "location_id",
            sa.Integer(),
            sa.ForeignKey("locations.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column("audit_runs", sa.Column("customer_code", sa.String(length=100), nullable=True))

    op.create_index("ix_audit_runs_tenant_asset_type", "audit_runs", ["tenant_id", "asset_type_id"])
    op.create_index("ix_audit_runs_tenant_mode", "audit_runs", ["tenant_id", "assessment_mode"])
    op.create_index("ix_audit_runs_tenant_location_id", "audit_runs", ["tenant_id", "location_id"])

    # --- audit_responses: applicability ---
    op.add_column(
        "audit_responses",
        sa.Column(
            "applicability",
            sa.String(length=40),
            nullable=True,
            server_default="applicable",
        ),
    )
    op.create_check_constraint(
        "ck_audit_responses_applicability",
        "audit_responses",
        "applicability IN ('applicable','not_applicable_by_composition','hidden_by_logic')",
    )

    # --- audit_sections: composition rules ---
    op.add_column("audit_sections", sa.Column("applicability_rules_json", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("audit_sections", "applicability_rules_json")

    op.drop_constraint("ck_audit_responses_applicability", "audit_responses", type_="check")
    op.drop_column("audit_responses", "applicability")

    op.drop_index("ix_audit_runs_tenant_location_id", table_name="audit_runs")
    op.drop_index("ix_audit_runs_tenant_mode", table_name="audit_runs")
    op.drop_index("ix_audit_runs_tenant_asset_type", table_name="audit_runs")
    op.drop_column("audit_runs", "customer_code")
    op.drop_column("audit_runs", "location_id")
    op.drop_column("audit_runs", "asset_type_id")
    op.drop_column("audit_runs", "assessment_mode")
