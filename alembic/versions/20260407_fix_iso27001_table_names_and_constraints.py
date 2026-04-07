"""Fix ISO 27001 table names from singular to plural, fix constraints.

Revision ID: iso27001_table_fix_01
Revises: f6e5d4c3b2a1
Create Date: 2026-04-07

FIX-ISO-01: Rename remaining ISO 27001 tables from singular to plural to
match ORM __tablename__ declarations:
  - iso27001_control        → iso27001_controls
  - soa_control_entry       → soa_control_entries
  - information_security_risk → information_security_risks
  - security_incident       → security_incidents
  - access_control_record   → access_control_records
  - business_continuity_plan → business_continuity_plans
  - supplier_security_assessment → supplier_security_assessments

FIX-ISO-05: Change iso27001_controls.control_id from globally unique to
composite unique per-tenant (control_id, tenant_id) so that all tenants
can have their own copy of the 93 Annex A controls.

The information_asset → information_assets rename was already handled by
20260405_align_information_assets_table_with_orm.py.
statement_of_applicability needed no rename (already correct).
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "iso27001_table_fix_01"
down_revision: Union[str, None] = "f6e5d4c3b2a1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Mapping of old singular name → new plural name
RENAMES: list[tuple[str, str]] = [
    ("iso27001_control", "iso27001_controls"),
    ("soa_control_entry", "soa_control_entries"),
    ("information_security_risk", "information_security_risks"),
    ("security_incident", "security_incidents"),
    ("access_control_record", "access_control_records"),
    ("business_continuity_plan", "business_continuity_plans"),
    ("supplier_security_assessment", "supplier_security_assessments"),
]


def _table_exists(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def _has_column(table: str, column: str) -> bool:
    if not _table_exists(table):
        return False
    return column in {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def _has_unique_constraint(table: str, name: str) -> bool:
    if not _table_exists(table):
        return False
    try:
        constraints = sa.inspect(op.get_bind()).get_unique_constraints(table)
        return any(c.get("name") == name for c in constraints)
    except Exception:
        return False


def upgrade() -> None:
    bind = op.get_bind()
    is_pg = bind.dialect.name == "postgresql"

    # ── Step 1: Rename tables from singular to plural ────────────────────────
    for old, new in RENAMES:
        if _table_exists(old) and not _table_exists(new):
            op.rename_table(old, new)

    # ── Step 2: Fix iso27001_controls.control_id uniqueness ─────────────────
    # The original migration added a global UNIQUE on control_id, which prevents
    # seeding the same 93 Annex A controls for more than one tenant.
    # We drop the global unique and add a composite unique (control_id, tenant_id).
    if not _table_exists("iso27001_controls"):
        return

    if is_pg:
        # Add tenant_id column if missing (needed for composite constraint)
        if not _has_column("iso27001_controls", "tenant_id"):
            op.add_column(
                "iso27001_controls",
                sa.Column(
                    "tenant_id",
                    sa.Integer(),
                    sa.ForeignKey("tenants.id", ondelete="SET NULL"),
                    nullable=True,
                    index=True,
                ),
            )
            op.execute("CREATE INDEX IF NOT EXISTS ix_iso27001_controls_tenant_id " "ON iso27001_controls (tenant_id)")

        # Drop the global unique constraint on control_id.
        # Use ALTER TABLE … DROP CONSTRAINT IF EXISTS (never aborts the transaction,
        # unlike op.drop_constraint() which raises a SQL error when the constraint
        # is missing and puts asyncpg into InFailedSQLTransactionError state).
        op.execute("ALTER TABLE iso27001_controls " "DROP CONSTRAINT IF EXISTS uq_iso27001_controls_control_id")
        op.execute("ALTER TABLE iso27001_controls " "DROP CONSTRAINT IF EXISTS iso27001_control_control_id_key")
        # Also drop as plain index in case PostgreSQL stored it as an index object.
        op.execute("DROP INDEX IF EXISTS iso27001_control_control_id_key")
        op.execute("DROP INDEX IF EXISTS uq_iso27001_controls_control_id")
        # Catch any auto-generated name: drop every single-column unique on control_id.
        op.execute("""
            DO $$
            DECLARE r RECORD;
            BEGIN
                FOR r IN
                    SELECT tc.constraint_name
                    FROM information_schema.table_constraints tc
                    JOIN information_schema.key_column_usage kcu
                        ON tc.constraint_name = kcu.constraint_name
                        AND tc.table_schema = kcu.table_schema
                    WHERE tc.table_name = 'iso27001_controls'
                      AND tc.constraint_type = 'UNIQUE'
                      AND kcu.column_name = 'control_id'
                      AND tc.table_schema = current_schema()
                      AND NOT EXISTS (
                        SELECT 1 FROM information_schema.key_column_usage kcu2
                        WHERE kcu2.constraint_name = tc.constraint_name
                          AND kcu2.table_schema = tc.table_schema
                          AND kcu2.column_name = 'tenant_id'
                      )
                LOOP
                    EXECUTE 'ALTER TABLE iso27001_controls DROP CONSTRAINT '
                        || quote_ident(r.constraint_name);
                END LOOP;
            END$$;
            """)

        # Create composite unique: one control_id per tenant
        if not _has_unique_constraint("iso27001_controls", "uq_iso27001_controls_control_id_tenant"):
            op.create_unique_constraint(
                "uq_iso27001_controls_control_id_tenant",
                "iso27001_controls",
                ["control_id", "tenant_id"],
            )


def downgrade() -> None:
    bind = op.get_bind()
    is_pg = bind.dialect.name == "postgresql"

    if is_pg and _table_exists("iso27001_controls"):
        # Revert to global unique (best-effort; duplicate data may prevent this).
        # Use IF EXISTS to avoid transaction-aborting errors.
        op.execute("ALTER TABLE iso27001_controls " "DROP CONSTRAINT IF EXISTS uq_iso27001_controls_control_id_tenant")
        if not _has_unique_constraint("iso27001_controls", "uq_iso27001_controls_control_id"):
            op.create_unique_constraint("uq_iso27001_controls_control_id", "iso27001_controls", ["control_id"])

    # Rename tables back (reverse order)
    for old, new in reversed(RENAMES):
        if _table_exists(new) and not _table_exists(old):
            op.rename_table(new, old)
