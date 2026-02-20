"""Add Enterprise Risk Register tables (risks_v2 and related).

Revision ID: 20260220_enterprise_rr
Revises: 20260220_archive
Create Date: 2026-02-20
"""

import sqlalchemy as sa

from alembic import op

revision = "20260220_enterprise_rr"
down_revision = "20260220_archive"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "risks_v2",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("reference", sa.String(50), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("subcategory", sa.String(100), nullable=True),
        sa.Column("tags", sa.JSON(), nullable=True),
        sa.Column("source", sa.String(100), nullable=True),
        sa.Column("context", sa.Text(), nullable=True),
        sa.Column("affected_objectives", sa.JSON(), nullable=True),
        sa.Column("department", sa.String(100), nullable=True),
        sa.Column("location", sa.String(255), nullable=True),
        sa.Column("process", sa.String(255), nullable=True),
        sa.Column("inherent_likelihood", sa.Integer(), nullable=False),
        sa.Column("inherent_impact", sa.Integer(), nullable=False),
        sa.Column("inherent_score", sa.Integer(), nullable=False),
        sa.Column("residual_likelihood", sa.Integer(), nullable=False),
        sa.Column("residual_impact", sa.Integer(), nullable=False),
        sa.Column("residual_score", sa.Integer(), nullable=False),
        sa.Column("target_likelihood", sa.Integer(), nullable=True),
        sa.Column("target_impact", sa.Integer(), nullable=True),
        sa.Column("target_score", sa.Integer(), nullable=True),
        sa.Column("risk_appetite", sa.String(50), server_default="cautious"),
        sa.Column("appetite_threshold", sa.Integer(), server_default="12"),
        sa.Column("is_within_appetite", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("treatment_strategy", sa.String(50), server_default="treat"),
        sa.Column("treatment_plan", sa.Text(), nullable=True),
        sa.Column("treatment_status", sa.String(50), nullable=True),
        sa.Column("treatment_cost", sa.Float(), nullable=True),
        sa.Column("treatment_benefit", sa.Text(), nullable=True),
        sa.Column(
            "risk_owner_id",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column("risk_owner_name", sa.String(255), nullable=True),
        sa.Column(
            "delegate_id",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column("status", sa.String(50), server_default="identified"),
        sa.Column("review_frequency_days", sa.Integer(), server_default="90"),
        sa.Column("last_review_date", sa.DateTime(), nullable=True),
        sa.Column("next_review_date", sa.DateTime(), nullable=True),
        sa.Column("review_notes", sa.Text(), nullable=True),
        sa.Column("is_escalated", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("escalation_reason", sa.Text(), nullable=True),
        sa.Column("escalation_date", sa.DateTime(), nullable=True),
        sa.Column("linked_incidents", sa.JSON(), nullable=True),
        sa.Column("linked_audits", sa.JSON(), nullable=True),
        sa.Column("linked_actions", sa.JSON(), nullable=True),
        sa.Column("identified_date", sa.DateTime(), server_default=sa.text("now()")),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()")),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "created_by",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("reference"),
    )
    op.create_index("ix_risks_v2_category", "risks_v2", ["category"])
    op.create_index("ix_risks_v2_department", "risks_v2", ["department"])
    op.create_index("ix_risks_v2_status", "risks_v2", ["status"])

    op.create_table(
        "enterprise_risk_controls",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("reference", sa.String(50), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("control_type", sa.String(50), nullable=False),
        sa.Column("control_nature", sa.String(50), nullable=False),
        sa.Column("effectiveness", sa.String(50), server_default="effective"),
        sa.Column("effectiveness_score", sa.Integer(), server_default="3"),
        sa.Column(
            "control_owner_id",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column("control_owner_name", sa.String(255), nullable=True),
        sa.Column("last_test_date", sa.DateTime(), nullable=True),
        sa.Column("test_result", sa.String(50), nullable=True),
        sa.Column("next_test_date", sa.DateTime(), nullable=True),
        sa.Column("standard_clauses", sa.JSON(), nullable=True),
        sa.Column("evidence_required", sa.JSON(), nullable=True),
        sa.Column("evidence_location", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("implementation_status", sa.String(50), server_default="implemented"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("reference"),
    )

    op.create_table(
        "risk_control_mappings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "risk_id",
            sa.Integer(),
            sa.ForeignKey("risks_v2.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "control_id",
            sa.Integer(),
            sa.ForeignKey("enterprise_risk_controls.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("contribution", sa.String(50), server_default="partial"),
        sa.Column("reduces_likelihood", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("reduces_impact", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("reduction_value", sa.Integer(), server_default="1"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_risk_control_mappings_risk_id", "risk_control_mappings", ["risk_id"])
    op.create_index("ix_risk_control_mappings_control_id", "risk_control_mappings", ["control_id"])

    op.create_table(
        "bow_tie_elements",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "risk_id",
            sa.Integer(),
            sa.ForeignKey("risks_v2.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("element_type", sa.String(50), nullable=False),
        sa.Column("position", sa.String(50), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("barrier_type", sa.String(50), nullable=True),
        sa.Column(
            "linked_control_id",
            sa.Integer(),
            sa.ForeignKey("enterprise_risk_controls.id"),
            nullable=True,
        ),
        sa.Column("effectiveness", sa.String(50), nullable=True),
        sa.Column("order_index", sa.Integer(), server_default="0"),
        sa.Column("is_escalation_factor", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_bow_tie_elements_risk_id", "bow_tie_elements", ["risk_id"])

    op.create_table(
        "enterprise_key_risk_indicators",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "risk_id",
            sa.Integer(),
            sa.ForeignKey("risks_v2.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("metric_type", sa.String(50), nullable=False),
        sa.Column("green_threshold", sa.Float(), nullable=False),
        sa.Column("amber_threshold", sa.Float(), nullable=False),
        sa.Column("red_threshold", sa.Float(), nullable=False),
        sa.Column("threshold_direction", sa.String(20), server_default="above"),
        sa.Column("current_value", sa.Float(), nullable=True),
        sa.Column("current_status", sa.String(20), nullable=True),
        sa.Column("last_updated", sa.DateTime(), nullable=True),
        sa.Column("data_source", sa.String(255), nullable=True),
        sa.Column("calculation_method", sa.Text(), nullable=True),
        sa.Column("update_frequency", sa.String(50), server_default="monthly"),
        sa.Column("historical_values", sa.JSON(), nullable=True),
        sa.Column("alert_enabled", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("alert_recipients", sa.JSON(), nullable=True),
        sa.Column("last_alert_sent", sa.DateTime(), nullable=True),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_enterprise_kri_risk_id", "enterprise_key_risk_indicators", ["risk_id"])

    op.create_table(
        "risk_assessment_history",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "risk_id",
            sa.Integer(),
            sa.ForeignKey("risks_v2.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("assessment_date", sa.DateTime(), server_default=sa.text("now()")),
        sa.Column(
            "assessed_by",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column("inherent_likelihood", sa.Integer(), nullable=False),
        sa.Column("inherent_impact", sa.Integer(), nullable=False),
        sa.Column("inherent_score", sa.Integer(), nullable=False),
        sa.Column("residual_likelihood", sa.Integer(), nullable=False),
        sa.Column("residual_impact", sa.Integer(), nullable=False),
        sa.Column("residual_score", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("treatment_strategy", sa.String(50), nullable=False),
        sa.Column("assessment_notes", sa.Text(), nullable=True),
        sa.Column("changes_since_last", sa.Text(), nullable=True),
        sa.Column("control_effectiveness", sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_risk_assessment_history_risk_id", "risk_assessment_history", ["risk_id"])

    op.create_table(
        "risk_appetite_statements",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("appetite_level", sa.String(50), nullable=False),
        sa.Column("max_inherent_score", sa.Integer(), server_default="25"),
        sa.Column("max_residual_score", sa.Integer(), server_default="12"),
        sa.Column("escalation_threshold", sa.Integer(), server_default="16"),
        sa.Column("statement", sa.Text(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("approved_by", sa.String(255), nullable=True),
        sa.Column("approved_date", sa.DateTime(), nullable=True),
        sa.Column("next_review_date", sa.DateTime(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("category"),
    )


def downgrade() -> None:
    op.drop_table("risk_appetite_statements")
    op.drop_index("ix_risk_assessment_history_risk_id", table_name="risk_assessment_history")
    op.drop_table("risk_assessment_history")
    op.drop_index("ix_enterprise_kri_risk_id", table_name="enterprise_key_risk_indicators")
    op.drop_table("enterprise_key_risk_indicators")
    op.drop_index("ix_bow_tie_elements_risk_id", table_name="bow_tie_elements")
    op.drop_table("bow_tie_elements")
    op.drop_index("ix_risk_control_mappings_control_id", table_name="risk_control_mappings")
    op.drop_index("ix_risk_control_mappings_risk_id", table_name="risk_control_mappings")
    op.drop_table("risk_control_mappings")
    op.drop_table("enterprise_risk_controls")
    op.drop_index("ix_risks_v2_status", table_name="risks_v2")
    op.drop_index("ix_risks_v2_department", table_name="risks_v2")
    op.drop_index("ix_risks_v2_category", table_name="risks_v2")
    op.drop_table("risks_v2")
