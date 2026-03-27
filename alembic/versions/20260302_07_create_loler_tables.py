"""Create LOLER 1998 thorough examination tables.

Revision ID: 20260302_loler
Revises: 20260302_induct
Create Date: 2026-03-02 11:00:00.000000

Creates loler_examinations and loler_defects tables for LOLER
thorough examination records.
"""

from alembic import op
import sqlalchemy as sa

revision = "20260302_loler"
down_revision = "20260302_induct"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "loler_examinations",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("external_id", sa.String(36), nullable=False),
        sa.Column("reference_number", sa.String(20), unique=True, nullable=False, index=True),
        sa.Column("asset_id", sa.Integer(), sa.ForeignKey("assets.id"), nullable=False),
        sa.Column("examination_type", sa.String(50), nullable=False, server_default="thorough_examination"),
        sa.Column("examination_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("next_examination_due", sa.DateTime(timezone=True), nullable=True),
        sa.Column("competent_person_name", sa.String(200), nullable=False),
        sa.Column("competent_person_employer", sa.String(200), nullable=True),
        sa.Column("competent_person_qualification", sa.String(200), nullable=True),
        sa.Column("safe_working_load", sa.Float(), nullable=True),
        sa.Column("swl_unit", sa.String(20), nullable=True),
        sa.Column("safe_to_operate", sa.Boolean(), server_default="true"),
        sa.Column("conditions_of_use", sa.Text(), nullable=True),
        sa.Column("employer_name", sa.String(200), nullable=True),
        sa.Column("employer_address", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("examiner_signature", sa.Text(), nullable=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("updated_by_id", sa.Integer(), nullable=True),
        sa.UniqueConstraint("external_id", name="uq_loler_examinations_external_id"),
    )
    op.create_index("ix_loler_examinations_asset_id", "loler_examinations", ["asset_id"])
    op.create_index("ix_loler_examinations_external_id", "loler_examinations", ["external_id"])
    op.create_index("ix_loler_examinations_tenant_id", "loler_examinations", ["tenant_id"])

    op.create_table(
        "loler_defects",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("examination_id", sa.Integer(), sa.ForeignKey("loler_examinations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("location_on_equipment", sa.String(200), nullable=True),
        sa.Column("remedial_action", sa.Text(), nullable=True),
        sa.Column("timescale", sa.String(100), nullable=True),
        sa.Column("capa_id", sa.Integer(), sa.ForeignKey("capa_actions.id"), nullable=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=True),
        sa.Column("resolved", sa.Boolean(), server_default="false"),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_loler_defects_examination_id", "loler_defects", ["examination_id"])
    op.create_index("ix_loler_defects_tenant_id", "loler_defects", ["tenant_id"])


def downgrade() -> None:
    op.drop_table("loler_defects")
    op.drop_table("loler_examinations")
