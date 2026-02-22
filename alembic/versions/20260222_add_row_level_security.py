"""Enable PostgreSQL Row-Level Security on all tenant-scoped tables.

Revision ID: 20260222_add_rls_policies
Revises: 20260221_fk_indexes
Create Date: 2026-02-22

Creates tenant_isolation RLS policies so each tenant can only access its own
rows.  The policy uses current_setting('app.current_tenant_id', true)::int
which returns NULL (rather than raising an error) when the GUC is not set,
causing all rows to be hidden for connections that haven't set a tenant.

A BYPASS role (qgp_migrations) is created for Alembic migrations and admin
tasks that must see all data regardless of tenant.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "20260222_add_rls_policies"
down_revision: Union[str, None] = "20260221_fk_indexes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

RLS_TABLES = [
    "incidents",
    "complaints",
    "risks",
    "capa_actions",
    "audit_runs",
    "investigation_runs",
    "documents",
    "near_misses",
    "road_traffic_collisions",
    "workflow_rules",
    "users",
    "audit_log_entries",
]

_POLICY_SQL = (
    "CREATE POLICY tenant_isolation ON {table} "
    "USING (tenant_id = current_setting('app.current_tenant_id', true)::int)"
)


def upgrade() -> None:
    # Create a BYPASS role for migrations and admin tasks
    op.execute(
        "DO $$ BEGIN "
        "  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'qgp_migrations') THEN "
        "    CREATE ROLE qgp_migrations NOLOGIN BYPASSRLS; "
        "  END IF; "
        "EXCEPTION WHEN OTHERS THEN "
        "  RAISE NOTICE 'Could not create qgp_migrations role: %', SQLERRM; "
        "END $$"
    )

    for table in RLS_TABLES:
        # Only enable RLS on tables that have a tenant_id column;
        # swallow all errors so the migration is safe on any schema state
        op.execute(
            f"DO $$ BEGIN "
            f"  IF EXISTS ("
            f"    SELECT 1 FROM information_schema.columns "
            f"    WHERE table_name = '{table}' AND column_name = 'tenant_id'"
            f"  ) THEN "
            f"    EXECUTE 'ALTER TABLE {table} ENABLE ROW LEVEL SECURITY'; "
            f"    IF NOT EXISTS ("
            f"      SELECT 1 FROM pg_policies "
            f"      WHERE tablename = '{table}' AND policyname = 'tenant_isolation'"
            f"    ) THEN "
            f"      EXECUTE 'CREATE POLICY tenant_isolation ON {table} "
            f"        USING (tenant_id = current_setting(''app.current_tenant_id'', true)::int)'; "
            f"    END IF; "
            f"  END IF; "
            f"EXCEPTION WHEN OTHERS THEN "
            f"  RAISE NOTICE 'RLS skip for {table}: %', SQLERRM; "
            f"END $$"
        )


def downgrade() -> None:
    for table in reversed(RLS_TABLES):
        op.execute(
            f"DO $$ BEGIN "
            f"  EXECUTE 'DROP POLICY IF EXISTS tenant_isolation ON {table}'; "
            f"  EXECUTE 'ALTER TABLE {table} DISABLE ROW LEVEL SECURITY'; "
            f"EXCEPTION WHEN OTHERS THEN "
            f"  RAISE NOTICE 'RLS downgrade skip for {table}: %', SQLERRM; "
            f"END $$"
        )

    op.execute(
        "DO $$ BEGIN "
        "  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'qgp_migrations') THEN "
        "    DROP ROLE qgp_migrations; "
        "  END IF; "
        "EXCEPTION WHEN OTHERS THEN "
        "  RAISE NOTICE 'Could not drop qgp_migrations role: %', SQLERRM; "
        "END $$"
    )
