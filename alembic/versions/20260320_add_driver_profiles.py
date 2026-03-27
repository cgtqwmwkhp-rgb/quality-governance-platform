"""Add driver_profiles and driver_acknowledgements tables.

Revision ID: 20260320_drivers
Revises: 20260320_veh_reg
Create Date: 2026-03-20

Creates:
  - driver_profiles: links QGP users to PAMS driver identity
  - driver_acknowledgements: records driver responses to defect/assignment notifications
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260320_drivers"
down_revision: Union[str, None] = "20260320_veh_reg"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _current_timestamp_default() -> sa.TextClause:
    return sa.text("CURRENT_TIMESTAMP")


def _has_table(table_name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(table_name)


def upgrade() -> None:
    if not _has_table("driver_profiles"):
        op.create_table(
            "driver_profiles",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("pams_driver_name", sa.String(255), nullable=True),
            sa.Column("licence_number", sa.String(50), nullable=True),
            sa.Column("licence_expiry", sa.DateTime(timezone=True), nullable=True),
            sa.Column("allocated_vehicle_reg", sa.String(20), sa.ForeignKey("vehicle_registry.vehicle_reg", ondelete="SET NULL"), nullable=True),
            sa.Column("compliance_score", sa.Float(), nullable=False, server_default="100.0"),
            sa.Column("last_check_completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("is_active_driver", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=_current_timestamp_default()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=_current_timestamp_default()),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("user_id"),
        )

    op.execute("CREATE INDEX IF NOT EXISTS ix_driver_profiles_user_id ON driver_profiles(user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_driver_profiles_pams_driver_name ON driver_profiles(pams_driver_name)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_driver_profiles_allocated_vehicle ON driver_profiles(allocated_vehicle_reg)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_driver_profiles_tenant_id ON driver_profiles(tenant_id)")

    if not _has_table("driver_acknowledgements"):
        op.create_table(
            "driver_acknowledgements",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("driver_profile_id", sa.Integer(), sa.ForeignKey("driver_profiles.id", ondelete="CASCADE"), nullable=False),
            sa.Column("entity_type", sa.String(50), nullable=False),
            sa.Column("entity_id", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(50), nullable=False, server_default="pending"),
            sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=_current_timestamp_default()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=_current_timestamp_default()),
            sa.PrimaryKeyConstraint("id"),
        )

    op.execute("CREATE INDEX IF NOT EXISTS ix_driver_ack_profile_id ON driver_acknowledgements(driver_profile_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_driver_ack_entity_type ON driver_acknowledgements(entity_type)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_driver_ack_entity_id ON driver_acknowledgements(entity_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_driver_ack_status ON driver_acknowledgements(status)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_driver_ack_tenant_id ON driver_acknowledgements(tenant_id)")


def downgrade() -> None:
    if _has_table("driver_acknowledgements"):
        op.drop_table("driver_acknowledgements")
    if _has_table("driver_profiles"):
        op.drop_table("driver_profiles")
