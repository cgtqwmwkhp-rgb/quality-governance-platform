"""Add CAPASource.compliance_record; create Compliance Schedule tables + RLS.

Revision ID: 20260913_cs_wave0
Revises: 20260912_clear_junctions
Create Date: 2026-09-13

Wave 0 foundations:

1. Add ``compliance_record`` to the PostgreSQL ``capasource`` enum (irreversible;
   writer lands in Wave 2 — label cannot be referenced in the same Alembic
   transaction that adds it when the type pre-exists).
2. Create ``compliance_requirement_templates`` (global, tenant_id NULL),
   ``compliance_requirements`` and ``compliance_records`` (tenant_id NOT NULL).
3. ENABLE + FORCE ``tenant_isolation`` on the two tenant tables. Templates are
   deliberately not RLS'd: NULL ``tenant_id`` rows would be invisible under the
   standard predicate.
4. Seed templates idempotently from ``specs/compliance-schedule/catalogue.json``.
"""

from __future__ import annotations

import logging
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260913_cs_wave0"
down_revision: Union[str, Sequence[str], None] = "20260912_clear_junctions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

logger = logging.getLogger("alembic.runtime.migration")

# Predicate matches ``TENANT_ISOLATION_PREDICATE`` in tenant_context.py
# (NULLIF empty-GUC guard).
_POLICY_PREDICATE = "tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::int"

RLS_TABLES = (
    "compliance_requirements",
    "compliance_records",
)


def _inspector() -> sa.Inspector:
    return sa.inspect(op.get_bind())


def _table_exists(table_name: str) -> bool:
    return _inspector().has_table(table_name)


def _add_capasource_label() -> None:
    conn = op.get_bind()
    if conn.dialect.name != "postgresql":
        return

    result = conn.execute(sa.text("SELECT 1 FROM pg_type WHERE typname = 'capasource'")).fetchone()
    if result:
        try:
            op.execute("ALTER TYPE capasource ADD VALUE IF NOT EXISTS 'compliance_record'")
        except Exception:
            pass


def _create_templates() -> None:
    op.create_table(
        "compliance_requirement_templates",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("template_key", sa.String(length=80), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("taxonomy_id", sa.String(length=20), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("regulatory_basis", sa.String(length=255), nullable=True),
        sa.Column("frequency_months", sa.Integer(), nullable=True),
        sa.Column("frequency_days", sa.Integer(), nullable=True),
        sa.Column("anchor", sa.String(length=50), nullable=False),
        sa.Column("statutory", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "anchor IN ('completion', 'schedule')",
            name="ck_compliance_requirement_templates_anchor",
        ),
        sa.CheckConstraint(
            "frequency_months IS NOT NULL OR frequency_days IS NOT NULL",
            name="ck_compliance_requirement_templates_frequency",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("template_key", name="uq_compliance_requirement_templates_key"),
    )
    op.create_index(
        "ix_compliance_requirement_templates_tenant_id",
        "compliance_requirement_templates",
        ["tenant_id"],
    )
    op.create_index(
        "ix_compliance_requirement_templates_template_key",
        "compliance_requirement_templates",
        ["template_key"],
    )
    op.create_index(
        "ix_compliance_requirement_templates_taxonomy_id",
        "compliance_requirement_templates",
        ["taxonomy_id"],
    )
    op.create_index(
        "ix_compliance_requirement_templates_is_active",
        "compliance_requirement_templates",
        ["is_active"],
    )


def _create_requirements() -> None:
    op.create_table(
        "compliance_requirements",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("external_id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("reference_number", sa.String(length=50), nullable=False),
        sa.Column("template_id", sa.Integer(), nullable=True),
        sa.Column("location_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("taxonomy_id", sa.String(length=20), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("regulatory_basis", sa.String(length=255), nullable=True),
        sa.Column("frequency_months", sa.Integer(), nullable=True),
        sa.Column("frequency_days", sa.Integer(), nullable=True),
        sa.Column("anchor", sa.String(length=50), nullable=False),
        sa.Column("statutory", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("next_due_date", sa.Date(), nullable=False),
        sa.Column("last_completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("owner_id", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("updated_by_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "anchor IN ('completion', 'schedule')",
            name="ck_compliance_requirements_anchor",
        ),
        sa.CheckConstraint(
            "frequency_months IS NOT NULL OR frequency_days IS NOT NULL",
            name="ck_compliance_requirements_frequency",
        ),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["updated_by_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["location_id"], ["locations.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["template_id"],
            ["compliance_requirement_templates.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "reference_number",
            name="uq_compliance_requirements_tenant_reference",
        ),
        sa.UniqueConstraint("external_id"),
    )
    op.create_index("ix_compliance_requirements_tenant_id", "compliance_requirements", ["tenant_id"])
    op.create_index(
        "ix_compliance_requirements_reference_number",
        "compliance_requirements",
        ["reference_number"],
    )
    op.create_index("ix_compliance_requirements_external_id", "compliance_requirements", ["external_id"])
    op.create_index("ix_compliance_requirements_template_id", "compliance_requirements", ["template_id"])
    op.create_index("ix_compliance_requirements_location_id", "compliance_requirements", ["location_id"])
    op.create_index("ix_compliance_requirements_taxonomy_id", "compliance_requirements", ["taxonomy_id"])
    op.create_index("ix_compliance_requirements_next_due_date", "compliance_requirements", ["next_due_date"])
    op.create_index("ix_compliance_requirements_owner_id", "compliance_requirements", ["owner_id"])
    op.create_index("ix_compliance_requirements_is_active", "compliance_requirements", ["is_active"])
    op.create_index("ix_compliance_requirements_deleted_at", "compliance_requirements", ["deleted_at"])
    op.create_index("ix_compliance_requirements_created_at", "compliance_requirements", ["created_at"])


def _create_records() -> None:
    op.create_table(
        "compliance_records",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("external_id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("reference_number", sa.String(length=50), nullable=False),
        sa.Column("requirement_id", sa.Integer(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("outcome", sa.String(length=50), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("check_passed", sa.Boolean(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("library_document_id", sa.Integer(), nullable=True),
        sa.Column(
            "filing_status",
            sa.String(length=50),
            nullable=False,
            server_default="not_filed",
        ),
        sa.Column("filing_error", sa.Text(), nullable=True),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("updated_by_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "outcome IN ('completed', 'missed')",
            name="ck_compliance_records_outcome",
        ),
        sa.CheckConstraint(
            "filing_status IN ('not_filed', 'filed', 'filing_failed')",
            name="ck_compliance_records_filing_status",
        ),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["updated_by_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(
            ["requirement_id"],
            ["compliance_requirements.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["library_document_id"], ["documents.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "reference_number",
            name="uq_compliance_records_tenant_reference",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "requirement_id",
            "due_date",
            name="uq_compliance_records_tenant_requirement_due",
        ),
        sa.UniqueConstraint("external_id"),
    )
    op.create_index("ix_compliance_records_tenant_id", "compliance_records", ["tenant_id"])
    op.create_index("ix_compliance_records_reference_number", "compliance_records", ["reference_number"])
    op.create_index("ix_compliance_records_external_id", "compliance_records", ["external_id"])
    op.create_index("ix_compliance_records_requirement_id", "compliance_records", ["requirement_id"])
    op.create_index("ix_compliance_records_due_date", "compliance_records", ["due_date"])
    op.create_index(
        "ix_compliance_records_library_document_id",
        "compliance_records",
        ["library_document_id"],
    )
    op.create_index("ix_compliance_records_created_at", "compliance_records", ["created_at"])


def _enable_rls(table: str) -> None:
    conn = op.get_bind()
    if conn.dialect.name != "postgresql":
        return
    op.execute(sa.text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))
    op.execute(sa.text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY"))
    op.execute(sa.text(f"DROP POLICY IF EXISTS tenant_isolation ON {table}"))
    op.execute(
        sa.text(
            f"CREATE POLICY tenant_isolation ON {table} "
            f"USING ({_POLICY_PREDICATE}) WITH CHECK ({_POLICY_PREDICATE})"
        )
    )


def _seed_templates() -> None:
    from src.domain.data.compliance_schedule_catalogue import upsert_compliance_templates

    count = upsert_compliance_templates(op.get_bind())
    logger.info("%s: upserted %d compliance requirement templates", revision, count)


def upgrade() -> None:
    _add_capasource_label()

    if not _table_exists("compliance_requirement_templates"):
        _create_templates()
    else:
        logger.info("%s: compliance_requirement_templates already present — skipping create", revision)

    if not _table_exists("compliance_requirements"):
        _create_requirements()
    else:
        logger.info("%s: compliance_requirements already present — skipping create", revision)

    if not _table_exists("compliance_records"):
        _create_records()
    else:
        logger.info("%s: compliance_records already present — skipping create", revision)

    for table in RLS_TABLES:
        if _table_exists(table):
            _enable_rls(table)

    if _table_exists("compliance_requirement_templates"):
        _seed_templates()


def downgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        for table in reversed(RLS_TABLES):
            if _table_exists(table):
                op.execute(sa.text(f"DROP POLICY IF EXISTS tenant_isolation ON {table}"))
                op.execute(sa.text(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY"))
                op.execute(sa.text(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY"))

    if _table_exists("compliance_records"):
        op.drop_table("compliance_records")
    if _table_exists("compliance_requirements"):
        op.drop_table("compliance_requirements")
    if _table_exists("compliance_requirement_templates"):
        op.drop_table("compliance_requirement_templates")
    # capasource ADD VALUE cannot be reversed
