"""Make every tenant_isolation policy survive an empty tenant GUC, and cover the
two tables that silently never got a policy at all.

Revision ID: 20260902_rls_guc_guard
Revises: 20260901_case_tenant_nn
Create Date: 2026-09-02

Why this exists (C-27, part 1 of 2)
-----------------------------------
The application connects as a role holding ``rolbypassrls``. PostgreSQL skips
row-level security entirely for such a role, so all 21 deployed
``tenant_isolation`` policies currently enforce nothing for the application. They
have therefore never been executed in anger, and two defects survived in them.

**Defect 1 — the predicate fails loud, not closed.** Every policy reads::

    tenant_id = current_setting('app.current_tenant_id', true)::int

``apply_tenant_guc`` binds that GUC with ``set_config(name, value, true)``, which
is transaction-local. When the transaction ends, PostgreSQL restores the *session*
value of the GUC — and for a custom GUC that was only ever set transaction-locally
that restored value is the **empty string**, not "unset". This was verified on
PostgreSQL 14 for the COMMIT, ROLLBACK and ``DISCARD ALL`` paths; SQLAlchemy's
pool uses ROLLBACK on connection return, so it is the normal path, not a corner.

``''::int`` raises 22P02 ``invalid_text_representation``. So on any pooled
connection that has already served one tenant-scoped request, the next query
against an RLS table by a caller with no tenant does not return zero rows — it
raises, and aborts the surrounding transaction, so every following statement in
that session fails too. Only a connection that has *never* bound the GUC returns
NULL and fails closed, which is why every docstring in this area claims "unset GUC
fails closed": that is true exactly once per connection.

``NULLIF(current_setting(...), '')`` collapses both the never-set (NULL) and the
reverted (``''``) cases to NULL, so the predicate is unsatisfiable and the row is
filtered instead of the query exploding. Isolation semantics are unchanged for a
GUC that *is* set.

**Defect 2 — two tables in the registry have no policy.**
``RLS_TABLES`` names 23 tables; only 21 have one. ``20260711_rls_docs_exp`` tried
to protect ``controlled_documents`` and ``controlled_document_versions``, but its
immediate child revision ``20260711_ctl_docs_create`` is what *creates*
``controlled_documents``. The tables did not exist yet, the migration's
``IF EXISTS`` guard skipped them, its ``EXCEPTION WHEN OTHERS ... RAISE NOTICE``
swallowed the miss, and nothing has protected them since. Both now carry a NOT
NULL ``tenant_id``, so they can be brought under the same policy here.

Blast radius of this migration: none today
------------------------------------------
While the application bypasses RLS, changing a policy predicate and adding two
policies cannot change what the application sees. That is deliberate — this lands
ahead of any connection-role change so the predicates are already correct when
enforcement is switched on. See docs/governance/rls-least-privilege-rollout.md for
the ordering requirement.

Deliberately not swallowing failures
------------------------------------
The earlier migrations in this family wrap each table in
``EXCEPTION WHEN OTHERS THEN RAISE NOTICE``, which is exactly how the two missing
policies went unnoticed for three months. This migration inspects the schema in
Python, skips only tables that genuinely have no ``tenant_id`` column, and then
**re-reads pg_policy and raises** if any table it claimed to protect is not
actually protected. A migration that cannot report success it did not achieve is
the whole point.
"""

from __future__ import annotations

import logging
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260902_rls_guc_guard"
down_revision: Union[str, Sequence[str], None] = "20260901_case_tenant_nn"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

logger = logging.getLogger("alembic.runtime.migration")

# Kept as a literal rather than imported from
# src.infrastructure.middleware.tenant_context.TENANT_ISOLATION_PREDICATE: a
# migration must describe the database as it was at this revision and must not
# change meaning when application code is edited later. A unit test asserts the
# two stay identical.
HARDENED_PREDICATE = "tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::int"

# The predicate as every policy carried it before this revision, restored on
# downgrade so the rollback is a true inverse.
LEGACY_PREDICATE = "tenant_id = current_setting('app.current_tenant_id', true)::int"

# The 21 tables that already have a tenant_isolation policy: predicate rewrite
# only. ENABLE / FORCE are already set and are left alone.
REWRITE_TABLES: tuple[str, ...] = (
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
    "policies",
    "audit_findings",
    "investigation_actions",
    "incident_actions",
    "complaint_actions",
    "rta_actions",
    "document_versions",
    "risks_v2",
    "evidence_assets",
)

# The two tables 20260711_rls_docs_exp intended to protect and missed. These need
# ENABLE + FORCE as well as the policy.
ADOPT_TABLES: tuple[str, ...] = (
    "controlled_documents",
    "controlled_document_versions",
)

ALL_TABLES: tuple[str, ...] = REWRITE_TABLES + ADOPT_TABLES


def _tables_with_tenant_id(tables: Sequence[str]) -> list[str]:
    """Subset of ``tables`` that exists here and carries a ``tenant_id`` column.

    A table absent from this database is not a failure — the chain is applied to
    partially-built databases during downgrade tests. A table that is present but
    has no ``tenant_id`` cannot carry this policy at all, and is reported.
    """
    inspector = sa.inspect(op.get_bind())
    present = set(inspector.get_table_names())
    keep: list[str] = []
    for table in tables:
        if table not in present:
            logger.info("%s: %s absent from this database, nothing to do", revision, table)
            continue
        if "tenant_id" not in {column["name"] for column in inspector.get_columns(table)}:
            logger.warning("%s: %s has no tenant_id column, cannot carry tenant_isolation", revision, table)
            continue
        keep.append(table)
    return keep


def _write_policy(table: str, predicate: str, *, enable_and_force: bool) -> None:
    """Replace ``tenant_isolation`` on ``table`` with ``predicate``.

    ``DROP`` then ``CREATE`` rather than an in-place alter because PostgreSQL has
    no "ALTER POLICY ... USING" that also rewrites WITH CHECK atomically in every
    supported version. Both statements run inside the migration's transaction, so
    there is no window in which the table is unprotected.
    """
    if enable_and_force:
        op.execute(sa.text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))
        op.execute(sa.text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY"))
    op.execute(sa.text(f"DROP POLICY IF EXISTS tenant_isolation ON {table}"))
    op.execute(sa.text(f"CREATE POLICY tenant_isolation ON {table} USING ({predicate}) WITH CHECK ({predicate})"))


def _assert_policies_match(tables: Sequence[str], expected_fragment: str) -> None:
    """Re-read pg_policy and raise unless every table really carries the predicate.

    ``expected_fragment`` is matched against the normalised expression PostgreSQL
    stores, not against the SQL we sent, so this cannot be satisfied by a
    statement that parsed but did not take effect.
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


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        logger.info("Skipping %s: row-level security is PostgreSQL-only", revision)
        return

    rewrite = _tables_with_tenant_id(REWRITE_TABLES)
    adopt = _tables_with_tenant_id(ADOPT_TABLES)

    for table in rewrite:
        _write_policy(table, HARDENED_PREDICATE, enable_and_force=False)
    for table in adopt:
        _write_policy(table, HARDENED_PREDICATE, enable_and_force=True)

    # "NULLIF" is the part that distinguishes the hardened predicate from the
    # legacy one, and it survives PostgreSQL's normalisation of the expression.
    _assert_policies_match(rewrite + adopt, "NULLIF")
    logger.info(
        "%s: tenant_isolation hardened on %d tables (%d newly adopted)",
        revision,
        len(rewrite) + len(adopt),
        len(adopt),
    )


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        logger.info("Skipping %s downgrade: row-level security is PostgreSQL-only", revision)
        return

    # Restore the legacy predicate on the tables that had one before this
    # revision. This deliberately reinstates the empty-GUC defect: a downgrade
    # that quietly kept the fix would misrepresent what the older revision was.
    rewrite = _tables_with_tenant_id(REWRITE_TABLES)
    for table in rewrite:
        _write_policy(table, LEGACY_PREDICATE, enable_and_force=False)

    # The adopted tables had no policy and no RLS at this revision's parent.
    for table in _tables_with_tenant_id(ADOPT_TABLES):
        op.execute(sa.text(f"DROP POLICY IF EXISTS tenant_isolation ON {table}"))
        op.execute(sa.text(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY"))
        op.execute(sa.text(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY"))

    _assert_policies_match(rewrite, "current_setting")
    logger.info("%s: reverted to the legacy predicate on %d tables", revision, len(rewrite))
