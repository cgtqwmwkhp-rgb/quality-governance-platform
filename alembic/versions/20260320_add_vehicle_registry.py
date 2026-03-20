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


def upgrade() -> None:
    op.execute("""
    CREATE TABLE IF NOT EXISTS vehicle_registry (
        id SERIAL PRIMARY KEY,
        vehicle_reg VARCHAR(20) NOT NULL UNIQUE,
        pams_van_id VARCHAR(50),
        asset_id INTEGER REFERENCES assets(id) ON DELETE SET NULL,
        fleet_status VARCHAR(50) NOT NULL DEFAULT 'active',
        compliance_status VARCHAR(50) NOT NULL DEFAULT 'compliant',
        last_daily_check_at TIMESTAMP WITH TIME ZONE,
        last_monthly_check_at TIMESTAMP WITH TIME ZONE,
        last_daily_check_pass BOOLEAN,
        road_tax_expiry TIMESTAMP WITH TIME ZONE,
        fire_extinguisher_expiry TIMESTAMP WITH TIME ZONE,
        tooling_calibration_expiry TIMESTAMP WITH TIME ZONE,
        assigned_driver_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
        tenant_id INTEGER REFERENCES tenants(id),
        created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
    );
    """)

    op.execute("CREATE INDEX IF NOT EXISTS ix_vehicle_registry_vehicle_reg ON vehicle_registry(vehicle_reg);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_vehicle_registry_pams_van_id ON vehicle_registry(pams_van_id);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_vehicle_registry_fleet_status ON vehicle_registry(fleet_status);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_vehicle_registry_compliance_status ON vehicle_registry(compliance_status);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_vehicle_registry_assigned_driver_id ON vehicle_registry(assigned_driver_id);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_vehicle_registry_tenant_id ON vehicle_registry(tenant_id);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_vehicle_registry_created_at ON vehicle_registry(created_at);")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS vehicle_registry;")
