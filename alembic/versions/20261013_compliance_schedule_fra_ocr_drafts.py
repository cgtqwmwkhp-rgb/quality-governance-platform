"""Create compliance_schedule_ocr_drafts + ENABLE/FORCE tenant_isolation.

Revision ID: 20261013_cs_fra_ocr
Revises: 20261015_document_edges
Create Date: 2026-10-13

Wave 3 FRA / PAS 79 OCR propose→confirm drafts. Tenant-scoped; brought under
the hardened predicate by this revision (tables created after 20260902 cannot
be protected by editing that revision). Registered in HARDENING_MIGRATIONS.
"""

from __future__ import annotations

import logging
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261013_cs_fra_ocr"
down_revision: Union[str, Sequence[str], None] = "20261013_cs_reg_link"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

logger = logging.getLogger("alembic.runtime.migration")

# Kept as a literal rather than imported from
# src.infrastructure.middleware.tenant_context.TENANT_ISOLATION_PREDICATE, for the
# same reason 20260902_rls_guc_guard / 20260913_cs_wave0 keep their own copy: a
# migration must describe the database as it was at this revision and must not
# change meaning when application code is edited later. A unit test asserts the
# two stay identical.
HARDENED_PREDICATE = "tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::int"

ADOPT_TABLES: tuple[str, ...] = ("compliance_schedule_ocr_drafts",)


def _inspector() -> sa.Inspector:
    return sa.inspect(op.get_bind())


def _table_exists(table_name: str) -> bool:
    return _inspector().has_table(table_name)


def _enable_rls(table: str) -> None:
    """ENABLE + FORCE row-level security on ``table`` and install the policy.

    ENABLE alone exempts the table owner, which is every identity the migrations
    run as, so FORCE is what makes the policy bind. WITH CHECK carries the same
    predicate as USING so a write cannot land in a tenant the caller is not
    serving; a policy with only USING filters reads and permits any INSERT.
    """
    conn = op.get_bind()
    if conn.dialect.name != "postgresql":
        return
    op.execute(sa.text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))
    op.execute(sa.text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY"))
    op.execute(sa.text(f"DROP POLICY IF EXISTS tenant_isolation ON {table}"))
    op.execute(
        sa.text(
            f"CREATE POLICY tenant_isolation ON {table} "
            f"USING ({HARDENED_PREDICATE}) WITH CHECK ({HARDENED_PREDICATE})"
        )
    )


def _assert_policies_match(tables: Sequence[str], expected_fragment: str) -> None:
    """Re-read pg_policy and raise unless every table really carries the predicate."""
    bind = op.get_bind()
    rows = bind.execute(
        sa.text("""
            SELECT c.relname AS table_name,
                   c.relrowsecurity AS enabled,
                   c.relforcerowsecurity AS forced,
                   pg_get_expr(p.polqual, p.polrelid) AS using_expr,
                   pg_get_expr(p.polwithcheck, p.polrelid) AS check_expr
            FROM pg_class AS c
            JOIN pg_namespace AS n ON n.oid = c.relnamespace
            LEFT JOIN pg_policy AS p ON p.polrelid = c.oid AND p.polname = 'tenant_isolation'
            WHERE n.nspname = current_schema() AND c.relname = ANY(:tables)
            """),
        {"tables": list(tables)},
    ).mappings()
    state = {row["table_name"]: row for row in rows}

    problems: list[str] = []
    for table in tables:
        row = state.get(table)
        if row is None:
            problems.append(f"{table}: relation not visible in current_schema()")
            continue
        if not row["enabled"] or not row["forced"]:
            problems.append(f"{table}: enabled={row['enabled']} forced={row['forced']} (both must be true)")
        for label in ("using_expr", "check_expr"):
            expr = row[label]
            if expr is None:
                problems.append(f"{table}: tenant_isolation has no {label}")
            elif expected_fragment not in expr:
                problems.append(f"{table}: {label} is {expr!r}, expected it to contain {expected_fragment!r}")

    if problems:
        raise RuntimeError(
            f"{revision} did not achieve the policy state it reported. "
            "Refusing to record this revision as applied.\n  " + "\n  ".join(problems)
        )


def _create_drafts() -> None:
    op.create_table(
        "compliance_schedule_ocr_drafts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("external_id", sa.String(length=36), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("requirement_id", sa.Integer(), nullable=False),
        sa.Column("purpose", sa.String(length=32), nullable=False, server_default="fra_pas79"),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="pending"),
        sa.Column("source_filename", sa.String(length=255), nullable=True),
        sa.Column("source_content_type", sa.String(length=100), nullable=True),
        sa.Column("source_size_bytes", sa.Integer(), nullable=True),
        sa.Column("source_checksum_sha256", sa.String(length=64), nullable=False),
        sa.Column("source_storage_key", sa.String(length=500), nullable=True),
        sa.Column("extraction_method", sa.String(length=64), nullable=True),
        sa.Column("ocr_provider_status", sa.String(length=50), nullable=True),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column("proposed_json", postgresql.JSONB().with_variant(sa.JSON(), "sqlite"), nullable=False),
        sa.Column("warnings_json", postgresql.JSONB().with_variant(sa.JSON(), "sqlite"), nullable=True),
        sa.Column("confirmed_json", postgresql.JSONB().with_variant(sa.JSON(), "sqlite"), nullable=True),
        sa.Column("applied_json", postgresql.JSONB().with_variant(sa.JSON(), "sqlite"), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confirmed_by_id", sa.Integer(), nullable=True),
        sa.Column("discarded_at", sa.DateTime(timezone=True), nullable=True),
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
            "status IN ('pending', 'confirmed', 'discarded')",
            name="ck_cs_ocr_drafts_status",
        ),
        sa.CheckConstraint(
            "filing_status IN ('not_filed', 'filed', 'filing_failed')",
            name="ck_cs_ocr_drafts_filing_status",
        ),
        sa.CheckConstraint("purpose IN ('fra_pas79')", name="ck_cs_ocr_drafts_purpose"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["updated_by_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["confirmed_by_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(
            ["requirement_id"],
            ["compliance_requirements.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["library_document_id"], ["documents.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_compliance_schedule_ocr_drafts_tenant_id", "compliance_schedule_ocr_drafts", ["tenant_id"])
    op.create_index(
        "ix_compliance_schedule_ocr_drafts_external_id",
        "compliance_schedule_ocr_drafts",
        ["external_id"],
        unique=True,
    )
    op.create_index(
        "ix_compliance_schedule_ocr_drafts_requirement_id",
        "compliance_schedule_ocr_drafts",
        ["requirement_id"],
    )
    op.create_index("ix_compliance_schedule_ocr_drafts_status", "compliance_schedule_ocr_drafts", ["status"])
    op.create_index(
        "ix_compliance_schedule_ocr_drafts_source_checksum_sha256",
        "compliance_schedule_ocr_drafts",
        ["source_checksum_sha256"],
    )
    op.create_index(
        "ix_compliance_schedule_ocr_drafts_library_document_id",
        "compliance_schedule_ocr_drafts",
        ["library_document_id"],
    )
    op.create_index(
        "ix_compliance_schedule_ocr_drafts_created_at",
        "compliance_schedule_ocr_drafts",
        ["created_at"],
    )
    op.create_index(
        "ix_cs_ocr_drafts_tenant_status",
        "compliance_schedule_ocr_drafts",
        ["tenant_id", "status"],
    )
    # Partial unique: one pending draft per (tenant, requirement, checksum).
    op.create_index(
        "uq_cs_ocr_drafts_pending_source",
        "compliance_schedule_ocr_drafts",
        ["tenant_id", "requirement_id", "source_checksum_sha256"],
        unique=True,
        postgresql_where=sa.text("status = 'pending'"),
        sqlite_where=sa.text("status = 'pending'"),
    )


def upgrade() -> None:
    if not _table_exists("compliance_schedule_ocr_drafts"):
        _create_drafts()
    else:
        logger.info("%s: compliance_schedule_ocr_drafts already present — skipping create", revision)

    protected = [table for table in ADOPT_TABLES if _table_exists(table)]
    for table in protected:
        _enable_rls(table)

    if protected and op.get_bind().dialect.name == "postgresql":
        _assert_policies_match(protected, "NULLIF")
        logger.info("%s: tenant_isolation enabled and forced on %s", revision, ", ".join(protected))


def downgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        for table in reversed(ADOPT_TABLES):
            if _table_exists(table):
                op.execute(sa.text(f"DROP POLICY IF EXISTS tenant_isolation ON {table}"))
                op.execute(sa.text(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY"))
                op.execute(sa.text(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY"))

    if _table_exists("compliance_schedule_ocr_drafts"):
        op.drop_table("compliance_schedule_ocr_drafts")
