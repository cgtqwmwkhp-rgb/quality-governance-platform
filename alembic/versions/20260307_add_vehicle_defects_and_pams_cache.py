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


def upgrade() -> None:
    op.execute("""
    CREATE TABLE IF NOT EXISTS vehicle_defects (
        id SERIAL PRIMARY KEY,
        tenant_id INTEGER REFERENCES tenants(id),
        pams_table VARCHAR(30) NOT NULL,
        pams_record_id INTEGER NOT NULL,
        check_field VARCHAR(255) NOT NULL,
        check_value VARCHAR(500),
        priority VARCHAR(5) NOT NULL,
        status VARCHAR(20) NOT NULL DEFAULT 'open',
        notes TEXT,
        vehicle_reg VARCHAR(20),
        created_by_id INTEGER REFERENCES users(id),
        assigned_to_email VARCHAR(255),
        created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
        updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
    );
    """)

    op.execute("CREATE INDEX IF NOT EXISTS ix_vehicle_defects_tenant_id ON vehicle_defects(tenant_id);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_vehicle_defects_pams_table ON vehicle_defects(pams_table);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_vehicle_defects_pams_record_id ON vehicle_defects(pams_record_id);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_vehicle_defects_priority ON vehicle_defects(priority);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_vehicle_defects_status ON vehicle_defects(status);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_vehicle_defects_vehicle_reg ON vehicle_defects(vehicle_reg);")

    op.execute("""
    CREATE TABLE IF NOT EXISTS pams_van_checklist_cache (
        id SERIAL PRIMARY KEY,
        pams_id INTEGER NOT NULL UNIQUE,
        raw_data JSONB,
        synced_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
    );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_pams_vc_cache_pams_id ON pams_van_checklist_cache(pams_id);")

    op.execute("""
    CREATE TABLE IF NOT EXISTS pams_van_checklist_monthly_cache (
        id SERIAL PRIMARY KEY,
        pams_id INTEGER NOT NULL UNIQUE,
        raw_data JSONB,
        synced_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
    );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_pams_vcm_cache_pams_id ON pams_van_checklist_monthly_cache(pams_id);")

    op.execute("""
    CREATE TABLE IF NOT EXISTS pams_sync_log (
        id SERIAL PRIMARY KEY,
        table_name VARCHAR(50) NOT NULL,
        rows_synced INTEGER DEFAULT 0,
        defects_detected INTEGER DEFAULT 0,
        status VARCHAR(20) DEFAULT 'success',
        error_message TEXT,
        started_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
        completed_at TIMESTAMP WITHOUT TIME ZONE
    );
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS pams_sync_log;")
    op.execute("DROP TABLE IF EXISTS pams_van_checklist_monthly_cache;")
    op.execute("DROP TABLE IF EXISTS pams_van_checklist_cache;")
    op.execute("DROP TABLE IF EXISTS vehicle_defects;")
