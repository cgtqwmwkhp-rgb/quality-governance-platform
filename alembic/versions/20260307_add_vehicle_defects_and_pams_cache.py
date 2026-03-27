"""Add vehicle_defects and PAMS cache tables.

Revision ID: 20260307_veh_def
Revises: 20260308_fk_fix
Create Date: 2026-03-07

Creates:
  - vehicle_defects: governance defect assessments against PAMS checklist items
  - pams_van_checklist_cache: local mirror of PAMS vanchecklist
  - pams_van_checklist_monthly_cache: local mirror of PAMS vanchecklistmonthly
  - pams_sync_log: observability for sync runs
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260307_veh_def"
down_revision: Union[str, None] = "20260308_fk_fix"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _current_timestamp_default() -> sa.TextClause:
    return sa.text("CURRENT_TIMESTAMP")


def _has_table(table_name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(table_name)


def upgrade() -> None:
    if not _has_table("vehicle_defects"):
        op.create_table(
            "vehicle_defects",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=True),
            sa.Column("pams_table", sa.String(30), nullable=False),
            sa.Column("pams_record_id", sa.Integer(), nullable=False),
            sa.Column("check_field", sa.String(255), nullable=False),
            sa.Column("check_value", sa.String(500), nullable=True),
            sa.Column("priority", sa.String(5), nullable=False),
            sa.Column("status", sa.String(20), nullable=False, server_default="open"),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("vehicle_reg", sa.String(20), nullable=True),
            sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("assigned_to_email", sa.String(255), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=_current_timestamp_default(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), server_default=_current_timestamp_default(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )
    op.execute("CREATE INDEX IF NOT EXISTS ix_vehicle_defects_tenant_id ON vehicle_defects(tenant_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_vehicle_defects_pams_table ON vehicle_defects(pams_table)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_vehicle_defects_pams_record_id ON vehicle_defects(pams_record_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_vehicle_defects_priority ON vehicle_defects(priority)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_vehicle_defects_status ON vehicle_defects(status)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_vehicle_defects_vehicle_reg ON vehicle_defects(vehicle_reg)")

    if not _has_table("pams_van_checklist_cache"):
        op.create_table(
            "pams_van_checklist_cache",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("pams_id", sa.Integer(), nullable=False),
            sa.Column("raw_data", sa.JSON(), nullable=True),
            sa.Column("synced_at", sa.DateTime(), server_default=_current_timestamp_default(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("pams_id"),
        )
    op.execute("CREATE INDEX IF NOT EXISTS ix_pams_vc_cache_pams_id ON pams_van_checklist_cache(pams_id)")

    if not _has_table("pams_van_checklist_monthly_cache"):
        op.create_table(
            "pams_van_checklist_monthly_cache",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("pams_id", sa.Integer(), nullable=False),
            sa.Column("raw_data", sa.JSON(), nullable=True),
            sa.Column("synced_at", sa.DateTime(), server_default=_current_timestamp_default(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("pams_id"),
        )
    op.execute("CREATE INDEX IF NOT EXISTS ix_pams_vcm_cache_pams_id ON pams_van_checklist_monthly_cache(pams_id)")

    if not _has_table("pams_sync_log"):
        op.create_table(
            "pams_sync_log",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("table_name", sa.String(50), nullable=False),
            sa.Column("rows_synced", sa.Integer(), server_default="0", nullable=True),
            sa.Column("defects_detected", sa.Integer(), server_default="0", nullable=True),
            sa.Column("status", sa.String(20), server_default="success", nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("started_at", sa.DateTime(), server_default=_current_timestamp_default(), nullable=True),
            sa.Column("completed_at", sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )


def downgrade() -> None:
    if _has_table("pams_sync_log"):
        op.drop_table("pams_sync_log")
    if _has_table("pams_van_checklist_monthly_cache"):
        op.drop_table("pams_van_checklist_monthly_cache")
    if _has_table("pams_van_checklist_cache"):
        op.drop_table("pams_van_checklist_cache")
    if _has_table("vehicle_defects"):
        op.drop_table("vehicle_defects")
