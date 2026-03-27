"""Add vehicle_registry table and VEHICLE_DEFECT CAPA source.

Revision ID: 20260320_veh_reg
Revises: 20260307_veh_def
Create Date: 2026-03-20

Creates:
  - vehicle_registry: first-class vehicle identity for fleet governance
  - Adds 'vehicle_defect' to capa_actions.source_type allowed values
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260320_veh_reg"
down_revision: Union[str, None] = "20260307_veh_def"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _current_timestamp_default() -> sa.TextClause:
    return sa.text("CURRENT_TIMESTAMP")


def _has_table(table_name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(table_name)


def upgrade() -> None:
    if not _has_table("vehicle_registry"):
        op.create_table(
            "vehicle_registry",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("vehicle_reg", sa.String(20), nullable=False),
            sa.Column("pams_van_id", sa.String(50), nullable=True),
            sa.Column("asset_id", sa.Integer(), sa.ForeignKey("assets.id", ondelete="SET NULL"), nullable=True),
            sa.Column("fleet_status", sa.String(50), nullable=False, server_default="active"),
            sa.Column("compliance_status", sa.String(50), nullable=False, server_default="compliant"),
            sa.Column("last_daily_check_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_monthly_check_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_daily_check_pass", sa.Boolean(), nullable=True),
            sa.Column("road_tax_expiry", sa.DateTime(timezone=True), nullable=True),
            sa.Column("fire_extinguisher_expiry", sa.DateTime(timezone=True), nullable=True),
            sa.Column("tooling_calibration_expiry", sa.DateTime(timezone=True), nullable=True),
            sa.Column("assigned_driver_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=_current_timestamp_default()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=_current_timestamp_default()),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("vehicle_reg"),
        )

    op.execute("CREATE INDEX IF NOT EXISTS ix_vehicle_registry_vehicle_reg ON vehicle_registry(vehicle_reg)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_vehicle_registry_pams_van_id ON vehicle_registry(pams_van_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_vehicle_registry_fleet_status ON vehicle_registry(fleet_status)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_vehicle_registry_compliance_status ON vehicle_registry(compliance_status)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_vehicle_registry_assigned_driver_id ON vehicle_registry(assigned_driver_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_vehicle_registry_tenant_id ON vehicle_registry(tenant_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_vehicle_registry_created_at ON vehicle_registry(created_at)")


def downgrade() -> None:
    if _has_table("vehicle_registry"):
        op.drop_table("vehicle_registry")
