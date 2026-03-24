"""Add governed runner-sheet tables for cases.

Revision ID: 20260324_case_runner_sheets
Revises: 20260322_workforce_resp_uniques
Create Date: 2026-03-24
"""

from typing import Sequence, Union

from alembic import op

revision: str = "20260324_case_runner_sheets"
down_revision: Union[str, None] = "20260322_workforce_resp_uniques"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "CREATE TABLE IF NOT EXISTS incident_running_sheet_entries ("
        "id SERIAL PRIMARY KEY, "
        "tenant_id INTEGER REFERENCES tenants(id), "
        "incident_id INTEGER NOT NULL REFERENCES incidents(id) ON DELETE CASCADE, "
        "content TEXT NOT NULL, "
        "entry_type VARCHAR(50) NOT NULL DEFAULT 'note', "
        "author_id INTEGER REFERENCES users(id), "
        "author_email VARCHAR(255), "
        "created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), "
        "updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()"
        ")"
    )
    op.execute(
        "CREATE TABLE IF NOT EXISTS complaint_running_sheet_entries ("
        "id SERIAL PRIMARY KEY, "
        "tenant_id INTEGER REFERENCES tenants(id), "
        "complaint_id INTEGER NOT NULL REFERENCES complaints(id) ON DELETE CASCADE, "
        "content TEXT NOT NULL, "
        "entry_type VARCHAR(50) NOT NULL DEFAULT 'note', "
        "author_id INTEGER REFERENCES users(id), "
        "author_email VARCHAR(255), "
        "created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), "
        "updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()"
        ")"
    )
    op.execute(
        "CREATE TABLE IF NOT EXISTS near_miss_running_sheet_entries ("
        "id SERIAL PRIMARY KEY, "
        "tenant_id INTEGER REFERENCES tenants(id), "
        "near_miss_id INTEGER NOT NULL REFERENCES near_misses(id) ON DELETE CASCADE, "
        "content TEXT NOT NULL, "
        "entry_type VARCHAR(50) NOT NULL DEFAULT 'note', "
        "author_id INTEGER REFERENCES users(id), "
        "author_email VARCHAR(255), "
        "created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), "
        "updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()"
        ")"
    )
    op.execute(
        "ALTER TABLE rta_running_sheet_entries ADD COLUMN IF NOT EXISTS tenant_id INTEGER REFERENCES tenants(id)"
    )
    op.execute(
        "UPDATE rta_running_sheet_entries e "
        "SET tenant_id = r.tenant_id "
        "FROM road_traffic_collisions r "
        "WHERE e.rta_id = r.id AND e.tenant_id IS NULL"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_incident_running_sheet_incident_id "
        "ON incident_running_sheet_entries(incident_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_incident_running_sheet_created " "ON incident_running_sheet_entries(created_at)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_inc_run_sheet_tenant_incident "
        "ON incident_running_sheet_entries(tenant_id, incident_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_complaint_running_sheet_complaint_id "
        "ON complaint_running_sheet_entries(complaint_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_complaint_running_sheet_created "
        "ON complaint_running_sheet_entries(created_at)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_cmp_run_sheet_tenant_complaint "
        "ON complaint_running_sheet_entries(tenant_id, complaint_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_near_miss_running_sheet_near_miss_id "
        "ON near_miss_running_sheet_entries(near_miss_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_near_miss_running_sheet_created "
        "ON near_miss_running_sheet_entries(created_at)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_nm_run_sheet_tenant_near_miss "
        "ON near_miss_running_sheet_entries(tenant_id, near_miss_id)"
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_rta_running_sheet_tenant ON rta_running_sheet_entries(tenant_id)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_rta_running_sheet_tenant_rta " "ON rta_running_sheet_entries(tenant_id, rta_id)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_rta_running_sheet_tenant_rta")
    op.execute("DROP INDEX IF EXISTS ix_rta_running_sheet_tenant")
    op.execute("ALTER TABLE rta_running_sheet_entries DROP COLUMN IF EXISTS tenant_id")
    op.execute("DROP TABLE IF EXISTS near_miss_running_sheet_entries")
    op.execute("DROP TABLE IF EXISTS complaint_running_sheet_entries")
    op.execute("DROP TABLE IF EXISTS incident_running_sheet_entries")
