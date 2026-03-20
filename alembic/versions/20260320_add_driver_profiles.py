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


def upgrade() -> None:
    op.execute("""
    CREATE TABLE IF NOT EXISTS driver_profiles (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
        pams_driver_name VARCHAR(255),
        licence_number VARCHAR(50),
        licence_expiry TIMESTAMP WITH TIME ZONE,
        allocated_vehicle_reg VARCHAR(20) REFERENCES vehicle_registry(vehicle_reg) ON DELETE SET NULL,
        compliance_score FLOAT NOT NULL DEFAULT 100.0,
        last_check_completed_at TIMESTAMP WITH TIME ZONE,
        is_active_driver BOOLEAN NOT NULL DEFAULT TRUE,
        tenant_id INTEGER REFERENCES tenants(id),
        created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
    );
    """)

    op.execute("CREATE INDEX IF NOT EXISTS ix_driver_profiles_user_id ON driver_profiles(user_id);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_driver_profiles_pams_driver_name ON driver_profiles(pams_driver_name);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_driver_profiles_allocated_vehicle ON driver_profiles(allocated_vehicle_reg);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_driver_profiles_tenant_id ON driver_profiles(tenant_id);")

    op.execute("""
    CREATE TABLE IF NOT EXISTS driver_acknowledgements (
        id SERIAL PRIMARY KEY,
        driver_profile_id INTEGER NOT NULL REFERENCES driver_profiles(id) ON DELETE CASCADE,
        entity_type VARCHAR(50) NOT NULL,
        entity_id INTEGER NOT NULL,
        status VARCHAR(50) NOT NULL DEFAULT 'pending',
        acknowledged_at TIMESTAMP WITH TIME ZONE,
        notes TEXT,
        tenant_id INTEGER REFERENCES tenants(id),
        created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
    );
    """)

    op.execute("CREATE INDEX IF NOT EXISTS ix_driver_ack_profile_id ON driver_acknowledgements(driver_profile_id);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_driver_ack_entity_type ON driver_acknowledgements(entity_type);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_driver_ack_entity_id ON driver_acknowledgements(entity_id);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_driver_ack_status ON driver_acknowledgements(status);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_driver_ack_tenant_id ON driver_acknowledgements(tenant_id);")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS driver_acknowledgements;")
    op.execute("DROP TABLE IF EXISTS driver_profiles;")
