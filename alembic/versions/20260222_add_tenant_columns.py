"""Add tenant_id column to all tenant-scoped tables.

Revision ID: 20260222_tenant_cols
Revises: 20260222_user_mfa
Create Date: 2026-02-22

Multi-tenancy columns were added to SQLAlchemy models but the existing
tables created by the initial migration were never altered.  This
migration idempotently adds tenant_id (nullable FK to tenants) to every
table that defines it in the model layer.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "20260222_tenant_cols"
down_revision: Union[str, None] = "20260222_user_mfa"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLES_NEEDING_TENANT_ID = [
    "users",
    "incidents",
    "complaints",
    "risks",
    "near_misses",
    "road_traffic_collisions",
    "rta_actions",
    "documents",
    "policies",
    "audit_templates",
    "audit_runs",
    "audit_findings",
    "investigation_runs",
    "workflow_rules",
    "sla_configurations",
    "sla_tracking",
    "escalation_levels",
    "key_risk_indicators",
    "kri_alerts",
    "information_assets",
    "information_security_risks",
    "security_incidents",
    "supplier_security_assessments",
    "form_templates",
    "contracts",
    "system_settings",
    "lookup_options",
    "evidence_assets",
    "compliance_evidence_links",
    "signature_requests",
    "signatures",
    "signature_templates",
    "signature_audit_logs",
    "copilot_sessions",
    "copilot_feedback",
    "risks_v2",
    "bow_tie_elements",
    "capa_actions",
]


def upgrade() -> None:
    for table in TABLES_NEEDING_TENANT_ID:
        op.execute(
            f"DO $$ BEGIN "
            f"  IF EXISTS ("
            f"    SELECT 1 FROM information_schema.tables "
            f"    WHERE table_name = '{table}'"
            f"  ) AND NOT EXISTS ("
            f"    SELECT 1 FROM information_schema.columns "
            f"    WHERE table_name = '{table}' AND column_name = 'tenant_id'"
            f"  ) THEN "
            f"    EXECUTE 'ALTER TABLE {table} ADD COLUMN tenant_id INTEGER'; "
            f"    IF EXISTS ("
            f"      SELECT 1 FROM information_schema.tables "
            f"      WHERE table_name = 'tenants'"
            f"    ) THEN "
            f"      BEGIN "
            f"        EXECUTE 'ALTER TABLE {table} "
            f"          ADD CONSTRAINT fk_{table}_tenant "
            f"          FOREIGN KEY (tenant_id) REFERENCES tenants(id)'; "
            f"      EXCEPTION WHEN OTHERS THEN NULL; "
            f"      END; "
            f"    END IF; "
            f"    EXECUTE 'CREATE INDEX IF NOT EXISTS ix_{table}_tenant_id "
            f"      ON {table}(tenant_id)'; "
            f"  END IF; "
            f"EXCEPTION WHEN OTHERS THEN "
            f"  RAISE NOTICE 'tenant_id skip for {table}: %', SQLERRM; "
            f"END $$"
        )


def downgrade() -> None:
    for table in reversed(TABLES_NEEDING_TENANT_ID):
        op.execute(
            f"DO $$ BEGIN "
            f"  IF EXISTS ("
            f"    SELECT 1 FROM information_schema.columns "
            f"    WHERE table_name = '{table}' AND column_name = 'tenant_id'"
            f"  ) THEN "
            f"    EXECUTE 'ALTER TABLE {table} DROP COLUMN tenant_id CASCADE'; "
            f"  END IF; "
            f"EXCEPTION WHEN OTHERS THEN "
            f"  RAISE NOTICE 'tenant_id downgrade skip for {table}: %', SQLERRM; "
            f"END $$"
        )
