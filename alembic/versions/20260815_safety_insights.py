"""Safety Insights Analyst run/theme/dimension tables.

Revision ID: 20260815_safety_insights
Revises: 20260814_hs_lessons
Create Date: 2026-08-15
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260815_safety_insights"
down_revision: Union[str, Sequence[str], None] = "20260814_hs_lessons"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "safety_insight_runs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="queued"),
        sa.Column("progress_pct", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("progress_message", sa.String(255), nullable=True),
        sa.Column("scope", sa.String(20), nullable=False, server_default="org"),
        sa.Column("topic_query", sa.String(500), nullable=True),
        sa.Column("modules_json", sa.JSON(), nullable=False),
        sa.Column("date_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("date_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("min_cluster_size", sa.Integer(), nullable=False, server_default="2"),
        sa.Column("include_synthesis", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("include_benchmark", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("models_used_json", sa.JSON(), nullable=True),
        sa.Column("corpus_summary_json", sa.JSON(), nullable=True),
        sa.Column("ratios_json", sa.JSON(), nullable=True),
        sa.Column("quality_scorecard_json", sa.JSON(), nullable=True),
        sa.Column("synthesis_text", sa.Text(), nullable=True),
        sa.Column("benchmarks_json", sa.JSON(), nullable=True),
        sa.Column("synthesis_available", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("research_available", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("error_code", sa.String(100), nullable=True),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("updated_by_id", sa.Integer(), nullable=True),
    )
    op.create_index("ix_safety_insight_runs_tenant_id", "safety_insight_runs", ["tenant_id"])
    op.create_index("ix_safety_insight_runs_status", "safety_insight_runs", ["status"])
    op.create_index("ix_safety_insight_runs_tenant_status", "safety_insight_runs", ["tenant_id", "status"])
    op.create_index("ix_safety_insight_runs_tenant_created", "safety_insight_runs", ["tenant_id", "created_at"])

    op.create_table(
        "safety_insight_themes",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "run_id",
            sa.Integer(),
            sa.ForeignKey("safety_insight_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("label", sa.String(300), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("module_scope", sa.String(50), nullable=True),
        sa.Column("case_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("share", sa.Float(), nullable=True),
        sa.Column("velocity", sa.String(20), nullable=True),
        sa.Column("severity_overlay", sa.String(50), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_safety_insight_themes_run", "safety_insight_themes", ["run_id"])
    op.create_index("ix_safety_insight_themes_tenant_id", "safety_insight_themes", ["tenant_id"])

    op.create_table(
        "safety_insight_theme_cases",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "theme_id",
            sa.Integer(),
            sa.ForeignKey("safety_insight_themes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "run_id",
            sa.Integer(),
            sa.ForeignKey("safety_insight_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("module", sa.String(30), nullable=False),
        sa.Column("case_id", sa.Integer(), nullable=False),
        sa.Column("reference_number", sa.String(50), nullable=False),
    )
    op.create_index("ix_safety_insight_theme_cases_theme", "safety_insight_theme_cases", ["theme_id"])
    op.create_index("ix_safety_insight_theme_cases_case", "safety_insight_theme_cases", ["module", "case_id"])
    op.create_index("ix_safety_insight_theme_cases_run_id", "safety_insight_theme_cases", ["run_id"])
    op.create_index("ix_safety_insight_theme_cases_tenant_id", "safety_insight_theme_cases", ["tenant_id"])

    op.create_table(
        "safety_insight_dimensions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "run_id",
            sa.Integer(),
            sa.ForeignKey("safety_insight_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("dimension_type", sa.String(30), nullable=False),
        sa.Column("dimension_key", sa.String(300), nullable=False),
        sa.Column("case_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("case_refs_json", sa.JSON(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "ix_safety_insight_dimensions_run_type",
        "safety_insight_dimensions",
        ["run_id", "dimension_type"],
    )
    op.create_index("ix_safety_insight_dimensions_tenant_id", "safety_insight_dimensions", ["tenant_id"])


def downgrade() -> None:
    op.drop_table("safety_insight_dimensions")
    op.drop_table("safety_insight_theme_cases")
    op.drop_table("safety_insight_themes")
    op.drop_table("safety_insight_runs")
