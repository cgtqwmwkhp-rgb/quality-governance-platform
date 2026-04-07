"""Fix ISO 27001 ORM schema drift across four tables + add missing tenant_id.

Revision ID: iso27001_schema_drift_02
Revises: iso27001_controls_cols_01
Create Date: 2026-04-07

Four ISO 27001 tables were created by the original 2026-01-20 migration with a
different column structure than the current SQLAlchemy ORM models.  Any attempt
to INSERT into these tables via the ORM raises UndefinedColumnError in production.

Additionally, three tables were never given tenant_id by the 20260308 migration
(which only covered the plural-named tables that existed at that point):
  - information_security_risks
  - security_incidents
  - supplier_security_assessments

Tables fixed here:
  1. security_incidents             – tenant_id + 7 missing ORM columns
  2. access_control_records         – 7 missing ORM columns (incl. non-nullable system_name)
  3. business_continuity_plans      – 17 missing ORM columns (incl. non-nullable name/rto_hours/rpo_hours)
  4. supplier_security_assessments  – tenant_id + 3 missing ORM columns
  5. information_security_risks     – tenant_id

All add_column calls are guarded by _column_exists() for full idempotency.
All new columns are nullable (or have a server_default) so the migration is
safe against existing rows.
"""

from __future__ import annotations

from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "iso27001_schema_drift_02"
down_revision: Union[str, None] = "iso27001_controls_cols_01"
branch_labels = None
depends_on = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _column_exists(table: str, column: str) -> bool:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    return column in {c["name"] for c in insp.get_columns(table)}


def _table_exists(table: str) -> bool:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    return insp.has_table(table)


def _add_if_missing(table: str, column_name: str, column_def: sa.Column) -> None:
    if _table_exists(table) and not _column_exists(table, column_name):
        op.add_column(table, column_def)


# ---------------------------------------------------------------------------
# Column definitions per table
# ---------------------------------------------------------------------------

# 1. security_incidents — tenant_id + 7 new ORM columns
_SECURITY_INCIDENTS_COLS = [
    (
        "tenant_id",
        sa.Column(
            "tenant_id",
            sa.Integer(),
            sa.ForeignKey("tenants.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
    ),
    ("priority", sa.Column("priority", sa.String(50), nullable=True, server_default="medium")),
    ("affected_users", sa.Column("affected_users", sa.Integer(), nullable=True)),
    ("attack_vector", sa.Column("attack_vector", sa.String(255), nullable=True)),
    ("indicators_of_compromise", sa.Column("indicators_of_compromise", sa.JSON(), nullable=True)),
    (
        "regulatory_notification_required",
        sa.Column(
            "regulatory_notification_required",
            sa.Boolean(),
            nullable=True,
            server_default="false",
        ),
    ),
    (
        "regulatory_notification_date",
        sa.Column("regulatory_notification_date", sa.DateTime(), nullable=True),
    ),
    ("regulatory_body", sa.Column("regulatory_body", sa.String(255), nullable=True)),
]

# 2. access_control_records — tenant_id + 7 new ORM columns
#    system_name is NOT NULL in ORM but already has existing rows → add as nullable first
#    (application layer ensures system_name is always provided on new inserts)
#    tenant_id was never added by 20260308 because the table was still named
#    access_control_record (singular) at that time.
_ACCESS_CONTROL_COLS = [
    (
        "tenant_id",
        sa.Column(
            "tenant_id",
            sa.Integer(),
            sa.ForeignKey("tenants.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
    ),
    ("system_name", sa.Column("system_name", sa.String(255), nullable=True)),
    ("user_role", sa.Column("user_role", sa.String(100), nullable=True)),
    ("access_method", sa.Column("access_method", sa.String(100), nullable=True)),
    ("granted_by", sa.Column("granted_by", sa.String(255), nullable=True)),
    ("reviewed_by", sa.Column("reviewed_by", sa.String(255), nullable=True)),
    ("status", sa.Column("status", sa.String(50), nullable=True, server_default="active")),
    (
        "asset_id",
        sa.Column(
            "asset_id",
            sa.Integer(),
            sa.ForeignKey("information_assets.id", ondelete="SET NULL"),
            nullable=True,
        ),
    ),
]

# 3. business_continuity_plans — tenant_id + 17 new ORM columns
#    name (was plan_name), rto_hours, rpo_hours are effectively required by ORM
#    but we add as nullable here; application ensures values on new rows
#    tenant_id was never added by 20260308 because the table was still named
#    business_continuity_plan (singular) at that time.
_BCP_COLS = [
    (
        "tenant_id",
        sa.Column(
            "tenant_id",
            sa.Integer(),
            sa.ForeignKey("tenants.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
    ),
    ("name", sa.Column("name", sa.String(255), nullable=True)),
    ("rto_hours", sa.Column("rto_hours", sa.Integer(), nullable=True)),
    ("rpo_hours", sa.Column("rpo_hours", sa.Integer(), nullable=True)),
    ("mtpd_hours", sa.Column("mtpd_hours", sa.Integer(), nullable=True)),
    ("covered_systems", sa.Column("covered_systems", sa.JSON(), nullable=True)),
    ("covered_processes", sa.Column("covered_processes", sa.JSON(), nullable=True)),
    ("activation_criteria", sa.Column("activation_criteria", sa.Text(), nullable=True)),
    ("notification_procedures", sa.Column("notification_procedures", sa.Text(), nullable=True)),
    ("resumption_procedures", sa.Column("resumption_procedures", sa.Text(), nullable=True)),
    (
        "plan_owner_id",
        sa.Column(
            "plan_owner_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    ),
    ("plan_owner_name", sa.Column("plan_owner_name", sa.String(255), nullable=True)),
    ("team_members", sa.Column("team_members", sa.JSON(), nullable=True)),
    ("escalation_contacts", sa.Column("escalation_contacts", sa.JSON(), nullable=True)),
    ("last_test_type", sa.Column("last_test_type", sa.String(100), nullable=True)),
    ("last_test_result", sa.Column("last_test_result", sa.String(50), nullable=True)),
    ("test_frequency_months", sa.Column("test_frequency_months", sa.Integer(), nullable=True, server_default="12")),
    ("effective_date", sa.Column("effective_date", sa.DateTime(), nullable=True)),
]

# 4. supplier_security_assessments — tenant_id + 3 new ORM columns
_SUPPLIER_COLS = [
    (
        "tenant_id",
        sa.Column(
            "tenant_id",
            sa.Integer(),
            sa.ForeignKey("tenants.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
    ),
    ("findings_details", sa.Column("findings_details", sa.JSON(), nullable=True)),
    ("risk_accepted", sa.Column("risk_accepted", sa.Boolean(), nullable=True, server_default="false")),
    ("risk_accepted_by", sa.Column("risk_accepted_by", sa.String(255), nullable=True)),
]

# 5. information_security_risks — missing tenant_id only
_ISR_COLS = [
    (
        "tenant_id",
        sa.Column(
            "tenant_id",
            sa.Integer(),
            sa.ForeignKey("tenants.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
    ),
]


# ---------------------------------------------------------------------------
# Upgrade / downgrade
# ---------------------------------------------------------------------------


def _set_server_default_if_missing(table: str, column: str, server_default: str) -> None:
    """Add a server_default to an existing NOT NULL column that has none."""
    if not _table_exists(table) or not _column_exists(table, column):
        return
    op.execute(f"ALTER TABLE {table} ALTER COLUMN {column} SET DEFAULT {server_default}")


def upgrade() -> None:
    for col_name, col_def in _SECURITY_INCIDENTS_COLS:
        _add_if_missing("security_incidents", col_name, col_def)

    # security_incidents.notification_required was created NOT NULL without a
    # server_default — add one so new ORM inserts that don't supply this legacy
    # field don't fail with NotNullViolationError.
    _set_server_default_if_missing("security_incidents", "notification_required", "false")

    for col_name, col_def in _ACCESS_CONTROL_COLS:
        _add_if_missing("access_control_records", col_name, col_def)

    # access_control_records.resource_type was created NOT NULL without a default
    _set_server_default_if_missing("access_control_records", "resource_type", "'system'")

    for col_name, col_def in _BCP_COLS:
        _add_if_missing("business_continuity_plans", col_name, col_def)

    # business_continuity_plans.plan_name was created NOT NULL without a default
    _set_server_default_if_missing("business_continuity_plans", "plan_name", "''")

    for col_name, col_def in _SUPPLIER_COLS:
        _add_if_missing("supplier_security_assessments", col_name, col_def)

    for col_name, col_def in _ISR_COLS:
        _add_if_missing("information_security_risks", col_name, col_def)


def downgrade() -> None:
    # Drop in reverse — all columns are nullable so no data loss
    for col_name, _ in reversed(_ISR_COLS):
        if _table_exists("information_security_risks") and _column_exists("information_security_risks", col_name):
            op.drop_column("information_security_risks", col_name)

    for col_name, _ in reversed(_SUPPLIER_COLS):
        if _table_exists("supplier_security_assessments") and _column_exists("supplier_security_assessments", col_name):
            op.drop_column("supplier_security_assessments", col_name)

    for col_name, _ in reversed(_BCP_COLS):
        if _table_exists("business_continuity_plans") and _column_exists("business_continuity_plans", col_name):
            op.drop_column("business_continuity_plans", col_name)

    for col_name, _ in reversed(_ACCESS_CONTROL_COLS):
        if _table_exists("access_control_records") and _column_exists("access_control_records", col_name):
            op.drop_column("access_control_records", col_name)

    for col_name, _ in reversed(_SECURITY_INCIDENTS_COLS):
        if _table_exists("security_incidents") and _column_exists("security_incidents", col_name):
            op.drop_column("security_incidents", col_name)
