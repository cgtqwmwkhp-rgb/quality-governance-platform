"""What the 25 tenant_isolation policies actually do once the connection stops
bypassing them (C-27), against real PostgreSQL.

Why this cannot be a unit test
------------------------------
Row-level security does not exist in SQLite, and the entire finding is about a
PostgreSQL role attribute. The application connects as a role holding
``rolbypassrls``, so PostgreSQL never evaluates a single one of these policies for
it. They are correct-looking, deployed, and inert. Nothing that stubs the database
can tell you what they do when they finally run, which is why two defects survived
in them for months:

* the predicate raised ``22P02`` instead of filtering, on any pooled connection
  that had already served one tenant-scoped request, and
* two of the tables the registry claims are protected had no policy at all.

Both are asserted here against a database built by the real alembic chain, read out
of ``pg_policy`` and ``pg_class`` rather than out of the migration source, so a
migration that parsed but did not take effect cannot satisfy these tests.

Why ``SET LOCAL ROLE`` and a rolled-back transaction
----------------------------------------------------
Identity changes with ``SET LOCAL ROLE`` rather than a second login: a superuser
that has ``SET ROLE``d to a non-bypass role *is* subject to RLS, which is exactly
the condition under test, and it needs no password, no ``pg_hba`` cooperation, and
no credential to exist for ``qgp_app`` before the cutover is authorised. The
migration grants ``qgp_app`` to the migration identity precisely so this is
possible.

Rows are seeded inside a transaction that is always rolled back, so this shares the
integration database with every other test in the job without changing what any of
them can see. It also never alters the RLS configuration of ``public`` — it asserts
against whatever the chain actually deployed.

``session_replication_role = replica`` is used while seeding so one row per table
can be inserted without satisfying 25 tables' worth of foreign keys. It was
verified on PostgreSQL 14 that this does **not** relax row-level security, and it
is reset to ``origin`` before any assertion is made, so no result here depends on
it.

CHECK constraints are still enforced under ``replica``, which is deliberate — a row
that violates one is not a row this suite should be reading back. Where a CHECK
spans two columns and the generic row builder cannot satisfy it, the value is
stated explicitly in ``SEED_OVERRIDES`` rather than the table being dropped from
coverage.
"""

from __future__ import annotations

import os
import re
from typing import Any, Optional

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from src.infrastructure.middleware.tenant_context import RLS_TABLES, TENANT_GUC

#: The role the application should connect as after the cutover, created by
#: ``20260903_app_lp_role``.
APP_ROLE = "qgp_app"

#: Two tenant ids far outside anything the rest of the suite seeds.
TENANT_A = 90261
TENANT_B = 90262

#: Privileges the request path needs on every table.
REQUIRED_PRIVILEGES: tuple[str, ...] = ("SELECT", "INSERT", "UPDATE", "DELETE")

#: Privileges an application role must never hold on a tenant-scoped table.
#: TRUNCATE is the dangerous one: PostgreSQL has no per-row TRUNCATE check, so it
#: crosses every tenant boundary at once regardless of tenant_isolation.
FORBIDDEN_PRIVILEGES: tuple[str, ...] = ("TRUNCATE", "REFERENCES", "TRIGGER")

_LITERAL_RE = re.compile(r"'([^']+)'")

#: Column values the generic row builder cannot derive, applied on top of what it
#: produces. Keyed by table, then by column.
#:
#: ``compliance_requirements`` carries
#: ``CHECK (frequency_months IS NOT NULL OR frequency_days IS NOT NULL)``. Both
#: columns are nullable, so ``_insert_row`` — which populates only NOT NULL columns
#: without a default — leaves both NULL and PostgreSQL rejects the row with 23514.
#: Nothing generic can satisfy a constraint spanning two columns: inferring it
#: would turn this builder into a CHECK-expression solver, and a wrong inference
#: would quietly seed a row that proves less than it appears to.
#:
#: An entry that goes stale fails loudly rather than silently: the INSERT names the
#: column, so a renamed or dropped one makes the table unseedable, and
#: ``test_cross_tenant_rows_are_invisible_under_the_app_role`` fails on the
#: ``unseedable`` report rather than quietly narrowing its coverage.
SEED_OVERRIDES: dict[str, dict[str, Any]] = {
    "compliance_requirements": {"frequency_months": 12},
    # Generic int filler uses the same seq for every NOT NULL int column; that
    # would set src_document_id == dst_document_id and trip ck_document_edges_no_self_loop.
    "document_edges": {"src_document_id": 910001, "dst_document_id": 910002},
    # _check_constraint_literals can pick verdict='unique' from
    # ck_alignment_edges_unique_has_no_pair while the generic filler still sets
    # dst_*; force a paired EXACT row so the UNIQUE/no-pair check stays satisfied.
    "alignment_edges": {
        "verdict": "exact",
        "row_verdict": "exact",
        "src_framework": "9001",
        "src_clause_key": "9001-6.1.2",
        "dst_framework": "14001",
        "dst_clause_key": "14001-6.1.2",
        "clause_ref": "6.1.2",
        "title": "run026-alignment",
        "row_key": "run026-row",
    },
}


def _database_url() -> str:
    return os.environ.get("DATABASE_URL", "")


pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skipif(
        not _database_url().startswith("postgresql"),
        reason="Row-level security is PostgreSQL-only; this suite runs against the CI Postgres service.",
    ),
]


@pytest.fixture
async def pg_engine():
    """A dedicated NullPool engine, so nothing here disturbs the app engine's pool.

    Function-scoped because ``pytest.ini`` pins the asyncio loop to function scope;
    a wider scope would bind these fixtures to a loop that is already closed.
    """
    engine = create_async_engine(_database_url(), poolclass=NullPool)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest.fixture
async def deployed_policies(pg_engine) -> dict[str, dict[str, Any]]:
    """The ``tenant_isolation`` policies as actually deployed, keyed by table.

    Read from the catalogue, not from the migration files. If the chain claimed to
    create a policy and did not, that shows up here as an absence.
    """
    async with pg_engine.connect() as conn:
        rows = (await conn.execute(sa.text("""
                    SELECT c.relname AS table_name,
                           c.relrowsecurity AS enabled,
                           c.relforcerowsecurity AS forced,
                           pg_get_expr(p.polqual, p.polrelid) AS using_expr,
                           pg_get_expr(p.polwithcheck, p.polrelid) AS check_expr
                    FROM pg_class AS c
                    JOIN pg_namespace AS n ON n.oid = c.relnamespace
                    JOIN pg_policy AS p ON p.polrelid = c.oid
                    WHERE n.nspname = 'public' AND p.polname = 'tenant_isolation'
                    """))).mappings().all()
    if not rows:
        pytest.skip("No tenant_isolation policies in this database — alembic chain not applied.")
    return {row["table_name"]: dict(row) for row in rows}


@pytest.fixture
async def app_role_present(pg_engine) -> bool:
    async with pg_engine.connect() as conn:
        exists = await conn.scalar(sa.text("SELECT 1 FROM pg_roles WHERE rolname = :r"), {"r": APP_ROLE})
    return bool(exists)


# ---------------------------------------------------------------------------
# Generic row builder: one valid row per policy table, without 23 fixtures
# ---------------------------------------------------------------------------


async def _enum_first_label(conn, udt_name: str) -> Optional[str]:
    return await conn.scalar(
        sa.text(
            "SELECT e.enumlabel FROM pg_enum AS e JOIN pg_type AS t ON t.oid = e.enumtypid "
            "WHERE t.typname = :n ORDER BY e.enumsortorder LIMIT 1"
        ),
        {"n": udt_name},
    )


async def _check_constraint_literals(conn, table: str) -> dict[str, str]:
    """Map column -> a literal some CHECK constraint on this table permits.

    Crude on purpose: it takes the first quoted literal from each constraint and
    associates it with every bare word in that constraint. That is enough to
    satisfy ``status``/``severity``-style allowlists, and a wrong guess only makes
    one INSERT fail loudly rather than producing a silently wrong test.
    """
    definitions = (
        (
            await conn.execute(
                sa.text(
                    "SELECT pg_get_constraintdef(c.oid) FROM pg_constraint AS c "
                    "WHERE c.conrelid = CAST(:t AS regclass) AND c.contype = 'c'"
                ),
                {"t": table},
            )
        )
        .scalars()
        .all()
    )

    allowed: dict[str, str] = {}
    for definition in definitions:
        literals = _LITERAL_RE.findall(definition)
        if not literals:
            continue
        stripped = _LITERAL_RE.sub("", definition).replace("(", " ").replace(")", " ")
        for word in stripped.split():
            allowed.setdefault(word.strip(","), literals[0])
    return allowed


def _placeholder_value(data_type: str, seq: int) -> Any:
    kind = data_type.lower()
    if "int" in kind or kind in {"numeric", "real", "double precision"}:
        return seq
    if "bool" in kind:
        return False
    if "json" in kind:
        return "{}"
    if kind == "array" or "[]" in kind:
        return "{}"
    return f"run026-{seq}"


async def _insert_row(conn, table: str, tenant_id: int) -> None:
    """Insert one row into ``table`` owned by ``tenant_id``.

    Only NOT NULL columns without a default are populated, plus anything named in
    ``SEED_OVERRIDES``; everything else is left to the database. Raises on failure —
    a table that cannot be seeded must not be silently dropped from coverage.
    """
    columns = (
        await conn.execute(
            sa.text(
                "SELECT column_name, data_type, udt_name FROM information_schema.columns "
                "WHERE table_schema = 'public' AND table_name = :t "
                "  AND is_nullable = 'NO' AND column_default IS NULL AND is_generated = 'NEVER' "
                "ORDER BY ordinal_position"
            ),
            {"t": table},
        )
    ).all()
    allowed = await _check_constraint_literals(conn, table)

    names: list[str] = []
    params: dict[str, Any] = {}
    for name, data_type, udt_name in columns:
        names.append(name)
        if name == "tenant_id":
            params[name] = tenant_id
        elif data_type == "USER-DEFINED":
            params[name] = await _enum_first_label(conn, udt_name) or f"run026-{tenant_id}"
        elif name in allowed:
            params[name] = allowed[name]
        else:
            params[name] = _placeholder_value(data_type, tenant_id)

    if "tenant_id" not in params:
        names.append("tenant_id")
        params["tenant_id"] = tenant_id

    # Timestamps need a real value; the generic filler cannot produce one.
    literals: dict[str, str] = {}
    for name, data_type, _udt in columns:
        if "timestamp" in data_type.lower() or data_type.lower() == "date":
            literals[name] = "now()"
            params.pop(name, None)

    # Applied last so an override wins over both the generic filler and the
    # timestamp literals, and so it can name a nullable column the loop above never
    # considered.
    for name, value in SEED_OVERRIDES.get(table, {}).items():
        if name not in names:
            names.append(name)
        literals.pop(name, None)
        params[name] = value

    rendered = ", ".join(literals.get(name, f":{name}") for name in names)
    await conn.execute(sa.text(f"INSERT INTO {table} ({', '.join(names)}) VALUES ({rendered})"), params)


@pytest.fixture
async def seeded_two_tenants(pg_engine, deployed_policies):
    """One row per policy table for each of two tenants, rolled back afterwards.

    Yields ``(connection, seeded_tables)``. The caller runs its assertions inside
    the same transaction, which is why the uncommitted rows are visible to it and
    invisible to everything else.
    """
    async with pg_engine.connect() as conn:
        transaction = await conn.begin()
        try:
            # Transaction-local so it cannot leak, and reset before any assertion.
            # This is a superuser-only GUC on PostgreSQL 14; without it the foreign
            # keys of 25 tables would have to be satisfied, so skip rather than
            # report a pass that proved nothing.
            try:
                await conn.execute(sa.text("SET LOCAL session_replication_role = replica"))
            except Exception as exc:  # noqa: BLE001
                await transaction.rollback()
                pytest.skip(
                    "Cannot set session_replication_role, so one row per policy table cannot be "
                    f"seeded without satisfying every foreign key: {exc}"
                )
            await conn.execute(sa.text(f"SELECT set_config('{TENANT_GUC}', :t, true)"), {"t": str(TENANT_A)})

            seeded: list[str] = []
            unseedable: dict[str, str] = {}
            for table in sorted(deployed_policies):
                savepoint = await conn.begin_nested()
                try:
                    for tenant in (TENANT_A, TENANT_B):
                        await _insert_row(conn, table, tenant)
                    await savepoint.commit()
                    seeded.append(table)
                except Exception as exc:  # noqa: BLE001 - reported, never hidden
                    await savepoint.rollback()
                    unseedable[table] = str(exc).splitlines()[0][:200]

            await conn.execute(sa.text("SET LOCAL session_replication_role = origin"))
            yield conn, seeded, unseedable
        finally:
            await transaction.rollback()


# ---------------------------------------------------------------------------
# The policies as deployed
# ---------------------------------------------------------------------------


async def test_every_registry_table_has_a_deployed_policy(deployed_policies):
    """``RLS_TABLES`` must describe reality, not intent.

    Fails before 20260902_rls_guc_guard: the registry named 23 tables and only 21
    had a policy. ``20260711_rls_docs_exp`` tried to protect
    ``controlled_documents`` and ``controlled_document_versions`` but runs one
    revision *before* ``20260711_ctl_docs_create``, which is what creates the first
    of them, so its IF EXISTS guard skipped both and its
    ``EXCEPTION WHEN OTHERS ... RAISE NOTICE`` swallowed the miss.
    """
    missing = sorted(set(RLS_TABLES) - set(deployed_policies))
    assert not missing, (
        f"RLS_TABLES claims these tables are protected but no tenant_isolation policy exists: {missing}. "
        f"Every policy on such a table enforces nothing."
    )


async def test_no_policy_exists_outside_the_registry(deployed_policies):
    """A policy nobody registered is a policy nobody maintains."""
    unregistered = sorted(set(deployed_policies) - set(RLS_TABLES))
    assert not unregistered, (
        f"tenant_isolation is deployed on {unregistered}, which RLS_TABLES does not list. "
        f"Add them to the registry so the tenant-context machinery knows about them."
    )


async def test_every_policy_is_enabled_forced_and_constrains_writes(deployed_policies):
    """ENABLE alone exempts the table owner; FORCE is what binds it. WITH CHECK is
    what stops a write landing in another tenant."""
    problems = []
    for table, row in sorted(deployed_policies.items()):
        if not row["enabled"]:
            problems.append(f"{table}: row level security not enabled")
        if not row["forced"]:
            problems.append(f"{table}: not FORCED, so the table owner bypasses the policy")
        if row["check_expr"] is None:
            problems.append(f"{table}: policy has no WITH CHECK, so writes are unconstrained")
    assert not problems, "\n".join(problems)


async def test_every_policy_predicate_guards_the_empty_guc(deployed_policies):
    """The predicate must treat an empty GUC as "no tenant", not cast it to int.

    Fails before 20260902_rls_guc_guard for all 21 policies then deployed. See
    ``test_a_reused_connection_filters_instead_of_erroring`` for why this matters —
    this test is the cheap structural check, that one is the proof.
    """
    unguarded = sorted(
        table
        for table, row in deployed_policies.items()
        if "NULLIF" not in (row["using_expr"] or "") or "NULLIF" not in (row["check_expr"] or "")
    )
    assert not unguarded, (
        f"These policies cast the tenant GUC to int without a NULLIF guard: {unguarded}. "
        f"On a pooled connection whose transaction-local GUC has reverted to the empty string, "
        f"''::int raises 22P02 and aborts the transaction instead of filtering the row."
    )


# ---------------------------------------------------------------------------
# What the app role actually experiences
# ---------------------------------------------------------------------------


async def test_a_reused_connection_filters_instead_of_erroring(pg_engine, deployed_policies, app_role_present):
    """The defect that made every policy dangerous rather than merely inert.

    ``apply_tenant_guc`` binds the tenant with ``set_config(name, value, true)``,
    which is transaction-local. When that transaction ends PostgreSQL restores the
    *session* value — which, for a custom GUC only ever set transaction-locally, is
    the empty string and not "unset". Verified on PostgreSQL 14 for COMMIT, ROLLBACK
    and ``DISCARD ALL``; SQLAlchemy's pool returns connections with ROLLBACK, so
    this is the ordinary path.

    So the second request on a pooled connection, by a caller with no tenant, did
    not fail closed — it raised 22P02 and poisoned the transaction, turning every
    following statement in that session into an error too.

    This reproduces the exact sequence on one physical connection: bind a tenant,
    end the transaction, then query with nothing bound. Fails before
    20260902_rls_guc_guard on every policy table.
    """
    if not app_role_present:
        pytest.skip(f"{APP_ROLE} does not exist; 20260903_app_lp_role has not been applied here.")

    errors: dict[str, str] = {}
    leaked: dict[str, int] = {}

    async with pg_engine.connect() as conn:
        # Request 1: a tenant-scoped transaction, exactly as get_db does it.
        transaction = await conn.begin()
        await conn.execute(sa.text(f"SET LOCAL ROLE {APP_ROLE}"))
        await conn.execute(sa.text(f"SELECT set_config('{TENANT_GUC}', :t, true)"), {"t": str(TENANT_A)})
        await transaction.rollback()

        # The GUC has now reverted to '' rather than to unset. This is the state
        # every recycled connection in the pool is in. Reading it autobegins a
        # transaction, so close that before opening the next one explicitly.
        reverted = await conn.scalar(sa.text(f"SELECT current_setting('{TENANT_GUC}', true)"))
        await conn.rollback()
        assert reverted == "", (
            f"Expected the transaction-local GUC to revert to the empty string, got {reverted!r}. "
            f"If PostgreSQL has changed this behaviour, the reasoning behind the NULLIF guard needs revisiting."
        )

        # Request 2: no tenant bound, as on login or any unauthenticated path.
        for table in sorted(deployed_policies):
            transaction = await conn.begin()
            try:
                await conn.execute(sa.text(f"SET LOCAL ROLE {APP_ROLE}"))
                count = await conn.scalar(sa.text(f"SELECT count(*) FROM {table}"))
                if count:
                    leaked[table] = int(count)
            except Exception as exc:  # noqa: BLE001 - the exception *is* the finding
                errors[table] = f"{type(exc).__name__}: {str(exc).splitlines()[0][:160]}"
            finally:
                await transaction.rollback()

    assert not errors, (
        "With no tenant bound on a reused connection these tables raised instead of returning "
        "nothing, which is an HTTP 500 rather than an empty list:\n  "
        + "\n  ".join(f"{table}: {message}" for table, message in sorted(errors.items()))
    )
    assert not leaked, f"Tables returned rows with no tenant bound, which is a tenancy leak: {leaked}"


async def test_a_never_bound_guc_returns_no_rows(pg_engine, deployed_policies, app_role_present):
    """The one case the existing docstrings describe correctly: a fresh connection
    that has never bound the GUC reads NULL and fails closed."""
    if not app_role_present:
        pytest.skip(f"{APP_ROLE} does not exist; 20260903_app_lp_role has not been applied here.")

    leaked: dict[str, int] = {}
    async with pg_engine.connect() as conn:
        transaction = await conn.begin()
        try:
            await conn.execute(sa.text(f"SET LOCAL ROLE {APP_ROLE}"))
            assert await conn.scalar(sa.text(f"SELECT current_setting('{TENANT_GUC}', true)")) is None
            for table in sorted(deployed_policies):
                count = await conn.scalar(sa.text(f"SELECT count(*) FROM {table}"))
                if count:
                    leaked[table] = int(count)
        finally:
            await transaction.rollback()

    assert not leaked, f"Rows were visible with no tenant GUC ever bound: {leaked}"


async def test_cross_tenant_rows_are_invisible_under_the_app_role(seeded_two_tenants, app_role_present):
    """The isolation each of these policies has never once been asked to perform.

    Two rows per table, one per tenant, then read as ``qgp_app`` with tenant A
    bound. Seeing tenant B's row is a cross-tenant data leak; seeing neither means
    the policy is filtering something other than what it claims to.
    """
    if not app_role_present:
        pytest.skip(f"{APP_ROLE} does not exist; 20260903_app_lp_role has not been applied here.")

    conn, seeded, unseedable = seeded_two_tenants
    assert seeded, f"No policy table could be seeded, so nothing was proven. Failures: {unseedable}"

    savepoint = await conn.begin_nested()
    problems: list[str] = []
    try:
        await conn.execute(sa.text(f"SET LOCAL ROLE {APP_ROLE}"))
        await conn.execute(sa.text(f"SELECT set_config('{TENANT_GUC}', :t, true)"), {"t": str(TENANT_A)})
        for table in seeded:
            mine = await conn.scalar(sa.text(f"SELECT count(*) FROM {table} WHERE tenant_id = :t"), {"t": TENANT_A})
            theirs = await conn.scalar(sa.text(f"SELECT count(*) FROM {table} WHERE tenant_id = :t"), {"t": TENANT_B})
            if theirs:
                problems.append(f"{table}: tenant {TENANT_B}'s row is visible to tenant {TENANT_A} ({theirs} row(s))")
            if not mine:
                problems.append(f"{table}: tenant {TENANT_A} cannot see its own row, so the policy over-filters")
    finally:
        await savepoint.rollback()

    assert not problems, "\n".join(problems)
    # Recorded so the count of genuinely-exercised policies is visible in the run,
    # rather than inferred from the number of tests that passed.
    assert not unseedable, (
        f"{len(seeded)} policy tables were proven by real cross-tenant reads, but these could not be "
        f"seeded and are therefore unproven: {unseedable}"
    )


async def test_cross_tenant_writes_are_rejected(seeded_two_tenants, app_role_present):
    """WITH CHECK must stop the app writing a row into a tenant it is not serving."""
    if not app_role_present:
        pytest.skip(f"{APP_ROLE} does not exist; 20260903_app_lp_role has not been applied here.")

    conn, seeded, _unseedable = seeded_two_tenants
    accepted: list[str] = []

    for table in seeded:
        savepoint = await conn.begin_nested()
        try:
            await conn.execute(sa.text(f"SET LOCAL ROLE {APP_ROLE}"))
            await conn.execute(sa.text(f"SELECT set_config('{TENANT_GUC}', :t, true)"), {"t": str(TENANT_A)})
            await conn.execute(
                sa.text(f"UPDATE {table} SET tenant_id = :other WHERE tenant_id = :mine"),
                {"other": TENANT_B, "mine": TENANT_A},
            )
        except Exception:  # noqa: BLE001 - rejection is the expected outcome
            pass
        else:
            accepted.append(table)
        finally:
            await savepoint.rollback()

    assert not accepted, (
        f"These tables let the app move a row into another tenant while serving tenant {TENANT_A}, "
        f"so their WITH CHECK is not enforcing: {accepted}"
    )


# ---------------------------------------------------------------------------
# The role itself
# ---------------------------------------------------------------------------


async def test_app_role_exists_and_cannot_escalate(pg_engine):
    """Fails before 20260903_app_lp_role: the role did not exist."""
    async with pg_engine.connect() as conn:
        attributes = (
            (
                await conn.execute(
                    sa.text(
                        "SELECT rolsuper, rolbypassrls, rolcreatedb, rolcreaterole, rolreplication "
                        "FROM pg_roles WHERE rolname = :r"
                    ),
                    {"r": APP_ROLE},
                )
            )
            .mappings()
            .first()
        )

    assert attributes is not None, (
        f"Role {APP_ROLE} does not exist. Until it does, the application has no identity to move to "
        f"and every tenant_isolation policy stays inert."
    )
    held = sorted(name for name, value in attributes.items() if value)
    assert not held, (
        f"{APP_ROLE} holds {held}. rolsuper and rolbypassrls both skip row-level security entirely, "
        f"which would reproduce the exact defect this work exists to fix."
    )


async def test_app_role_can_reach_every_table_and_sequence(pg_engine, app_role_present):
    """A missing grant is the most likely way the cutover fails: the policies work
    perfectly and the app 500s with ``permission denied`` on first touch."""
    if not app_role_present:
        pytest.skip(f"{APP_ROLE} does not exist; 20260903_app_lp_role has not been applied here.")

    async with pg_engine.connect() as conn:
        missing_tables = (
            (
                await conn.execute(
                    sa.text("""
                    SELECT t.table_name
                    FROM information_schema.tables AS t
                    WHERE t.table_schema = 'public'
                      AND t.table_type = 'BASE TABLE'
                      AND EXISTS (
                            SELECT 1 FROM unnest(CAST(:required AS text[])) AS need(priv)
                            WHERE NOT EXISTS (
                                SELECT 1 FROM information_schema.role_table_grants AS g
                                WHERE g.table_schema = 'public'
                                  AND g.table_name = t.table_name
                                  AND g.grantee = :role
                                  AND g.privilege_type = need.priv
                            )
                      )
                    ORDER BY t.table_name
                    """),
                    {"required": list(REQUIRED_PRIVILEGES), "role": APP_ROLE},
                )
            )
            .scalars()
            .all()
        )

        missing_sequences = (
            (
                await conn.execute(
                    sa.text(
                        "SELECT s.sequence_name FROM information_schema.sequences AS s "
                        "WHERE s.sequence_schema = 'public' "
                        "  AND NOT has_sequence_privilege(:role, quote_ident(s.sequence_name), 'USAGE') "
                        "ORDER BY s.sequence_name"
                    ),
                    {"role": APP_ROLE},
                )
            )
            .scalars()
            .all()
        )

    assert not missing_tables, (
        f"{APP_ROLE} is missing at least one of {REQUIRED_PRIVILEGES} on {len(missing_tables)} table(s): "
        f"{list(missing_tables)[:15]}"
    )
    assert not missing_sequences, (
        f"{APP_ROLE} lacks USAGE on {len(missing_sequences)} sequence(s), so inserts into those tables "
        f"will fail with permission denied: {list(missing_sequences)[:15]}"
    )


async def test_app_role_cannot_truncate(pg_engine, app_role_present):
    """TRUNCATE has no per-row RLS check, so it ignores tenant_isolation entirely."""
    if not app_role_present:
        pytest.skip(f"{APP_ROLE} does not exist; 20260903_app_lp_role has not been applied here.")

    async with pg_engine.connect() as conn:
        overreach = (
            (
                await conn.execute(
                    sa.text(
                        "SELECT DISTINCT privilege_type FROM information_schema.role_table_grants "
                        "WHERE table_schema = 'public' AND grantee = :role "
                        "  AND privilege_type = ANY(CAST(:forbidden AS text[]))"
                    ),
                    {"role": APP_ROLE, "forbidden": list(FORBIDDEN_PRIVILEGES)},
                )
            )
            .scalars()
            .all()
        )

    assert not overreach, (
        f"{APP_ROLE} holds {sorted(overreach)} on tables in public. TRUNCATE in particular is not "
        f"RLS-aware and would empty a tenant-scoped table across every tenant."
    )


# ---------------------------------------------------------------------------
# The gate that is deliberately still shut
# ---------------------------------------------------------------------------


async def test_authentication_is_still_the_blocking_gate(pg_engine, app_role_present):
    """Authentication cannot survive the cutover yet, and this records why.

    ``get_current_user`` selects a user by id and login selects one by email, both
    *before* the tenant is known — the tenant is a column on the row being fetched.
    ``users`` is under FORCE RLS, so with nothing bound there is nothing that can
    match, and the lookup returns nothing. No backfill fixes this; it is the shape
    of the code.

    **This assertion is expected to fail once CUT-2 of
    docs/governance/rls-least-privilege-rollout.md is done, and that failure is the
    signal to invert it.** It is here so the cutover cannot be attempted while the
    blocker is still present without a test going red.
    """
    if not app_role_present:
        pytest.skip(f"{APP_ROLE} does not exist; 20260903_app_lp_role has not been applied here.")

    async with pg_engine.connect() as conn:
        transaction = await conn.begin()
        try:
            # Seeded by the shared integration fixtures, and visible to the owner.
            total = await conn.scalar(sa.text("SELECT count(*) FROM users"))
            if not total:
                pytest.skip("No users in this database, so the auth bootstrap cannot be demonstrated.")

            await conn.execute(sa.text(f"SET LOCAL ROLE {APP_ROLE}"))
            visible = await conn.scalar(sa.text("SELECT count(*) FROM users"))
        finally:
            await transaction.rollback()

    assert visible == 0, (
        f"{APP_ROLE} can now see {visible} of {total} users with no tenant bound. If the auth bootstrap "
        f"has been fixed (CUT-2), invert this test: it exists to keep the cutover blocked while the "
        f"login path still cannot resolve a tenant."
    )
