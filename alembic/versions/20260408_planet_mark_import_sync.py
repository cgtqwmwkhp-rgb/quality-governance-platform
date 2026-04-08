"""Planet Mark import sync: add FK/provenance columns for audit→carbon linkage.

Revision ID: pm_import_sync_01
Revises: pm_enhancements_01
Create Date: 2026-04-08

Adds columns to enable the audit import pipeline to populate and link to
the Planet Mark carbon domain:

  - external_audit_records.carbon_reporting_year_id  (FK to carbon_reporting_year)
  - external_audit_records.scope_1_co2e              (extracted Scope 1 tCO2e)
  - external_audit_records.scope_2_co2e              (extracted Scope 2 tCO2e)
  - external_audit_records.scope_3_co2e              (extracted Scope 3 tCO2e)
  - Composite index on (scheme, tenant_id) for fast planet_mark queries

  - emission_sources.source_import_job_id  (provenance FK back to import job)
  - emission_sources.is_imported_aggregate  (flag for auto-imported aggregate rows)

  - improvement_actions.source_import_job_id  (provenance FK back to import job)
"""

from alembic import op
import sqlalchemy as sa

revision = "pm_import_sync_01"
down_revision = "pm_enhancements_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── external_audit_records enhancements ────────────────────────────────
    op.add_column(
        "external_audit_records",
        sa.Column(
            "carbon_reporting_year_id",
            sa.Integer(),
            sa.ForeignKey("carbon_reporting_year.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "external_audit_records",
        sa.Column("scope_1_co2e", sa.Float(), nullable=True),
    )
    op.add_column(
        "external_audit_records",
        sa.Column("scope_2_co2e", sa.Float(), nullable=True),
    )
    op.add_column(
        "external_audit_records",
        sa.Column("scope_3_co2e", sa.Float(), nullable=True),
    )
    # Composite index for the common "scheme + tenant" filter query
    op.create_index(
        "ix_external_audit_records_scheme_tenant",
        "external_audit_records",
        ["scheme", "tenant_id"],
    )

    # ── emission_sources provenance columns ────────────────────────────────
    op.add_column(
        "emission_sources",
        sa.Column(
            "source_import_job_id",
            sa.Integer(),
            sa.ForeignKey("external_audit_import_jobs.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "emission_sources",
        sa.Column(
            "is_imported_aggregate",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.create_index(
        "ix_emission_sources_import_job",
        "emission_sources",
        ["source_import_job_id"],
    )

    # ── improvement_actions provenance column ──────────────────────────────
    op.add_column(
        "improvement_actions",
        sa.Column(
            "source_import_job_id",
            sa.Integer(),
            sa.ForeignKey("external_audit_import_jobs.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_improvement_actions_import_job",
        "improvement_actions",
        ["source_import_job_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_improvement_actions_import_job", table_name="improvement_actions")
    op.drop_column("improvement_actions", "source_import_job_id")

    op.drop_index("ix_emission_sources_import_job", table_name="emission_sources")
    op.drop_column("emission_sources", "is_imported_aggregate")
    op.drop_column("emission_sources", "source_import_job_id")

    op.drop_index("ix_external_audit_records_scheme_tenant", table_name="external_audit_records")
    op.drop_column("external_audit_records", "scope_3_co2e")
    op.drop_column("external_audit_records", "scope_2_co2e")
    op.drop_column("external_audit_records", "scope_1_co2e")
    op.drop_column("external_audit_records", "carbon_reporting_year_id")
