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

Why the policy DDL is here and not in the hardening migration (C-27)
-------------------------------------------------------------------
``20260902_rls_guc_guard`` is where the ``NULLIF`` empty-GUC guard was introduced,
and it names the 23 tables that existed at that revision. It cannot be the place
these two are hardened, for two independent reasons: it is already applied in
staging and production, so editing its table tuples changes nothing there; and
every table it names has to exist at *its* point in the chain or its own
``_tables_with_tenant_id`` filter skips the name without protecting anything.
These tables are created eleven revisions later, here.

So a table created after 20260902 has to be brought under the hardened predicate
by the revision that creates it, and registered in ``HARDENING_MIGRATIONS`` in
``tests/unit/test_run026_rls_least_privilege.py``. That registry is what keeps
``RLS_TABLES`` from claiming protection nothing supplies. The conventions it
enforces — a ``HARDENED_PREDICATE`` literal identical to
``TENANT_ISOLATION_PREDICATE``, ENABLE + FORCE, USING *and* WITH CHECK, no
swallowed failures, and a re-read of ``pg_policy`` that raises rather than
reporting a success it did not achieve — are followed below for the same reason
20260902 follows them: an ``IF EXISTS`` guard plus a swallowed exception is
exactly how ``controlled_documents`` went three months with no policy.
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

# Kept as a literal rather than imported from
# src.infrastructure.middleware.tenant_context.TENANT_ISOLATION_PREDICATE, for the
# same reason 20260902_rls_guc_guard keeps its own copy: a migration must describe
# the database as it was at this revision and must not change meaning when
# application code is edited later. A unit test asserts the two stay identical.
HARDENED_PREDICATE = "tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::int"

# The tables this revision brings under tenant_isolation: they are created here,
# so they need ENABLE + FORCE as well as the policy. Named to match the
# ``ADOPT_TABLES`` vocabulary of 20260902_rls_guc_guard, which is the constant the
# coverage registry in tests/unit/test_run026_rls_least_privilege.py reads.
#
# compliance_requirement_templates is deliberately absent: its tenant_id is always
# NULL by design, and the tenant_isolation predicate is unsatisfiable for a NULL
# tenant_id, so a policy would make the global catalogue invisible to every tenant
# rather than isolating anything.
ADOPT_TABLES: tuple[str, ...] = (
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
    # TimestampMixin declares created_at with index=True; the other two tables
    # already carry theirs. Omitting it here was drift the ratchet caught.
    op.create_index(
        "ix_compliance_requirement_templates_created_at",
        "compliance_requirement_templates",
        ["created_at"],
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
    )
    op.create_index("ix_compliance_requirements_tenant_id", "compliance_requirements", ["tenant_id"])
    op.create_index(
        "ix_compliance_requirements_reference_number",
        "compliance_requirements",
        ["reference_number"],
    )
    # unique=True, not a separate UniqueConstraint: the ORM declares external_id
    # with unique=True *and* index=True, which SQLAlchemy renders as one unique
    # index named ix_<table>_<column>. A UniqueConstraint plus a plain index is a
    # different schema and shows up as drift (drop constraint, drop index, create
    # unique index) even though it enforces the same thing.
    op.create_index(
        "ix_compliance_requirements_external_id",
        "compliance_requirements",
        ["external_id"],
        unique=True,
    )
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
    )
    op.create_index("ix_compliance_records_tenant_id", "compliance_records", ["tenant_id"])
    op.create_index("ix_compliance_records_reference_number", "compliance_records", ["reference_number"])
    # unique=True for the same reason as ix_compliance_requirements_external_id.
    op.create_index("ix_compliance_records_external_id", "compliance_records", ["external_id"], unique=True)
    op.create_index("ix_compliance_records_requirement_id", "compliance_records", ["requirement_id"])
    op.create_index("ix_compliance_records_due_date", "compliance_records", ["due_date"])
    op.create_index(
        "ix_compliance_records_library_document_id",
        "compliance_records",
        ["library_document_id"],
    )
    op.create_index("ix_compliance_records_created_at", "compliance_records", ["created_at"])


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
    """Re-read pg_policy and raise unless every table really carries the predicate.

    ``expected_fragment`` is matched against the normalised expression PostgreSQL
    stores, not against the SQL sent above, so a statement that parsed without
    taking effect cannot satisfy this. Copied in shape from
    20260902_rls_guc_guard: a migration that can report a policy state it did not
    reach is how ``controlled_documents`` spent three months unprotected while its
    migration logged success.
    """
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

    protected = [table for table in ADOPT_TABLES if _table_exists(table)]
    for table in protected:
        _enable_rls(table)

    if protected and op.get_bind().dialect.name == "postgresql":
        # "NULLIF" is the part that distinguishes the hardened predicate from the
        # legacy one, and it survives PostgreSQL's normalisation of the expression.
        _assert_policies_match(protected, "NULLIF")
        logger.info("%s: tenant_isolation enabled and forced on %s", revision, ", ".join(protected))

    if _table_exists("compliance_requirement_templates"):
        _seed_templates()


def downgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        for table in reversed(ADOPT_TABLES):
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
