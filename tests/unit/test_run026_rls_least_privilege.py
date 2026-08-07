"""Guards for the C-27 least-privilege work that do not need a database.

These cover the four things that can silently rot without PostgreSQL noticing:

* the hardened predicate drifting apart from the copy inside a migration,
* a table joining ``RLS_TABLES`` with no migration hardening it, which is the
  registry claiming a protection nothing supplies,
* a future RLS migration reintroducing the ``EXCEPTION WHEN OTHERS ... RAISE
  NOTICE`` pattern that lost ``controlled_documents`` its policy for three months,
* the role migration quietly acquiring a credential or a dangerous privilege.

The behavioural proof lives in
``tests/integration/test_run026_rls_least_privilege_postgres.py``, because none of
this can be demonstrated without a real PostgreSQL role.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Any

import pytest

from src.infrastructure.middleware.tenant_context import RLS_TABLES, TENANT_GUC, TENANT_ISOLATION_PREDICATE

REPO = Path(__file__).resolve().parents[2]
VERSIONS = REPO / "alembic" / "versions"
GUC_GUARD_MIGRATION = VERSIONS / "20260902_rls_empty_guc_guard.py"
ROLE_MIGRATION = VERSIONS / "20260903_app_least_privilege_role.py"

#: Every migration that puts a table under the hardened ``tenant_isolation``
#: policy, with the module constants naming the tables it covers.
#:
#: ``20260902_rls_guc_guard`` is where the ``NULLIF`` guard was introduced and it
#: names the 23 tables that existed then. It is not extensible, for two
#: independent reasons: it is applied in staging and production, so editing its
#: tuples changes no deployed policy; and its own ``_tables_with_tenant_id``
#: filter skips any name that does not exist at *its* point in the chain, so a
#: table created later would be listed and not protected — the precise failure
#: mode that cost ``controlled_documents`` its policy for three months.
#:
#: A table created after that revision is therefore hardened by the revision that
#: creates it, and registered here. Every entry is held to the same conventions as
#: the original: a ``HARDENED_PREDICATE`` literal identical to
#: ``TENANT_ISOLATION_PREDICATE``, ENABLE + FORCE, USING *and* WITH CHECK, no
#: swallowed failures, and a re-read of ``pg_policy`` that raises. Adding a name
#: to ``RLS_TABLES`` without a migration in this registry fails
#: ``test_migration_covers_every_registered_rls_table``.
HARDENING_MIGRATIONS: tuple[tuple[Path, tuple[str, ...]], ...] = (
    (GUC_GUARD_MIGRATION, ("REWRITE_TABLES", "ADOPT_TABLES")),
    (VERSIONS / "20260913_compliance_schedule_wave0.py", ("ADOPT_TABLES",)),
    (VERSIONS / "20261012_rls_sso_provisioning.py", ("ADOPT_TABLES",)),
    (VERSIONS / "20261013_compliance_schedule_fra_ocr_drafts.py", ("ADOPT_TABLES",)),
    (VERSIONS / "20261015_document_edges.py", ("ADOPT_TABLES",)),
)


def _module_constants(path: Path) -> dict[str, Any]:
    """Module-level literal assignments, read without importing the module.

    A migration cannot be imported from the test process: the repository's own
    ``alembic/`` package shadows the installed ``alembic`` distribution on
    ``sys.path``, so ``from alembic import op`` fails. Reading the literals out of
    the AST compares the real values rather than grepping for substrings, which is
    what the older RLS migration tests had to settle for.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    constants: dict[str, Any] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            targets: list[ast.expr] = list(node.targets)
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
        else:
            continue
        for target in targets:
            if not isinstance(target, ast.Name) or node.value is None:
                continue
            try:
                constants[target.id] = ast.literal_eval(node.value)
            except (ValueError, TypeError):
                # Derived values such as REWRITE_TABLES + ADOPT_TABLES; the tests
                # recompute those from their literal parts instead.
                continue
    return constants


def _executable_source(path: Path) -> str:
    """The module's code with every docstring stripped.

    These migrations explain the defects they fix, so prose describing
    ``EXCEPTION WHEN OTHERS`` or a password would otherwise satisfy — or wrongly
    fail — a check that is about the code. ``ast.unparse`` also drops comments.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        body = getattr(node, "body", [])
        if (
            body
            and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)
        ):
            body.pop(0)
    return ast.unparse(tree)


def _hardening_coverage() -> dict[str, str]:
    """Table -> the migration that hardens it, across the whole registry.

    Raises rather than asserts on an overlap: two migrations naming one table is a
    registry defect, not a property of ``RLS_TABLES``, and every test here would
    otherwise report it as something else.
    """
    covered: dict[str, str] = {}
    for path, constant_names in HARDENING_MIGRATIONS:
        constants = _module_constants(path)
        for constant_name in constant_names:
            assert constant_name in constants, f"{path.name} has no module-level {constant_name}"
            for table in constants[constant_name]:
                if table in covered and covered[table] != path.name:
                    raise AssertionError(
                        f"{table!r} is hardened by both {covered[table]} and {path.name}. "
                        "One revision owns a table's policy; listing it twice means one of "
                        "them is describing a database state it does not produce."
                    )
                covered[table] = path.name
    return covered


@pytest.fixture(scope="module")
def guc_guard() -> dict[str, Any]:
    return _module_constants(GUC_GUARD_MIGRATION)


@pytest.fixture(params=[path for path, _ in HARDENING_MIGRATIONS], ids=lambda path: path.stem)
def hardening_migration(request) -> Path:
    return request.param


@pytest.fixture(scope="module")
def role_migration() -> dict[str, Any]:
    return _module_constants(ROLE_MIGRATION)


# ---------------------------------------------------------------------------
# The predicate
# ---------------------------------------------------------------------------


def test_canonical_predicate_guards_the_empty_guc():
    """``NULLIF`` is what stops ``''::int`` raising 22P02 on a recycled connection."""
    assert "NULLIF" in TENANT_ISOLATION_PREDICATE
    assert f"current_setting('{TENANT_GUC}', true)" in TENANT_ISOLATION_PREDICATE
    assert TENANT_ISOLATION_PREDICATE.startswith("tenant_id = ")


def test_migration_predicate_matches_the_canonical_one(hardening_migration):
    """Every hardening migration deliberately keeps its own copy of the predicate so
    it cannot change meaning when application code is edited. This test is what
    makes that duplication safe, and it applies to all of them: a later migration
    that installs a policy with the *unguarded* predicate would reintroduce the
    22P02 defect on the tables it creates while every structural check still
    reported 25 policies."""
    constants = _module_constants(hardening_migration)
    assert constants.get("HARDENED_PREDICATE") == TENANT_ISOLATION_PREDICATE, (
        f"The predicate inside {hardening_migration.name} has drifted from "
        "TENANT_ISOLATION_PREDICATE. Whichever is wrong, they must agree, or the "
        "readiness check will compare deployed policies against the wrong expectation."
    )


def test_legacy_predicate_is_the_unguarded_form(guc_guard):
    """The downgrade target must be the predicate as it really was, defect included."""
    assert "NULLIF" not in guc_guard["LEGACY_PREDICATE"]
    assert guc_guard["LEGACY_PREDICATE"] == f"tenant_id = current_setting('{TENANT_GUC}', true)::int"


def test_migration_covers_every_registered_rls_table():
    """A table in the registry that no hardening migration touches has no policy at
    all, or keeps the broken predicate — and either way ``RLS_TABLES`` is claiming
    protection nothing supplies."""
    covered = _hardening_coverage()
    missing = sorted(set(RLS_TABLES) - set(covered))
    assert not missing, (
        f"RLS_TABLES entries no hardening migration touches: {missing}. Harden them in the "
        "revision that creates them and add that revision to HARDENING_MIGRATIONS."
    )
    extra = sorted(set(covered) - set(RLS_TABLES))
    assert not extra, f"Migrations harden tables absent from RLS_TABLES: {extra}"


def test_the_two_previously_unprotected_tables_are_adopted(guc_guard):
    """``20260711_rls_docs_exp`` ran one revision before the table it was protecting
    existed, so both of these had no policy at all until now."""
    assert set(guc_guard["ADOPT_TABLES"]) == {"controlled_documents", "controlled_document_versions"}
    assert not set(guc_guard["ADOPT_TABLES"]) & set(guc_guard["REWRITE_TABLES"])


def test_hardening_migration_does_not_swallow_failures(hardening_migration):
    """The mistake that cost two tables their policy must not be reintroduced.

    ``EXCEPTION WHEN OTHERS THEN RAISE NOTICE`` around a conditional DDL block turns
    "this did not happen" into a log line nobody reads. Every hardening migration
    verifies its own outcome against pg_policy and raises instead.

    Checked against the docstring-stripped source, so the explanation of the original
    defect in a migration's own docstring cannot mask a reintroduction of it.
    """
    code = _executable_source(hardening_migration)
    assert "EXCEPTION WHEN OTHERS" not in code.upper(), (
        f"{hardening_migration.name} must not swallow errors: silently skipping a table is exactly "
        "how controlled_documents ended up with no policy."
    )
    assert "_assert_policies_match" in code, (
        f"{hardening_migration.name} must verify what it claims to have done, by re-reading "
        "pg_policy rather than trusting that its DDL took effect."
    )
    assert "RuntimeError" in code


def test_hardening_migration_forces_rls_and_constrains_writes(hardening_migration):
    """A policy is only worth what its weakest clause allows.

    ENABLE without FORCE exempts the table owner, which is every identity the
    migrations and the current application connect as. USING without WITH CHECK
    filters reads and leaves writes free to land in any tenant. Both were real
    defects in earlier revisions of this family, so both are checked structurally
    here as well as behaviourally in the PostgreSQL suite.
    """
    code = _executable_source(hardening_migration).upper()
    for clause in ("ENABLE ROW LEVEL SECURITY", "FORCE ROW LEVEL SECURITY", "WITH CHECK"):
        assert clause in code, f"{hardening_migration.name} never issues {clause}."


# ---------------------------------------------------------------------------
# The role
# ---------------------------------------------------------------------------


def _create_role_clause() -> str:
    """The ``CREATE ROLE`` statement's attribute list, up to its terminating ``;``.

    Scoped this tightly on purpose: the surrounding ``RAISE NOTICE`` text mentions
    both ``CREATEROLE`` and "no password" while explaining itself, and a check that
    reads the whole module would be satisfied or broken by prose rather than by the
    statement it is meant to police.
    """
    code = _executable_source(ROLE_MIGRATION)
    match = re.search(r"CREATE ROLE\s+\{APP_ROLE\}(?P<attributes>[^;]*);", code)
    assert match is not None, "Could not find the CREATE ROLE statement in the role migration."
    return match.group("attributes").upper()


def test_role_is_created_without_a_credential():
    """A migration in version control is the wrong place for a password, and a role
    that cannot log in yet cannot be used by accident before the cutover."""
    attributes = _create_role_clause()
    assert "NOLOGIN" in attributes
    assert "PASSWORD" not in attributes, "No PASSWORD clause belongs in CREATE ROLE."

    # Nor should any SQL anywhere in the migration set one.
    code = _executable_source(ROLE_MIGRATION).upper()
    assert "PASSWORD '" not in code, "No password literal belongs in a migration."
    assert "ALTER ROLE" not in code, "Granting LOGIN is a runbook step, not a migration step."


def test_role_is_created_without_rls_bypass_or_escalation():
    """Every negative attribute is stated explicitly so the intent is reviewable
    rather than dependent on CREATE ROLE defaults."""
    attributes = _create_role_clause()
    for attribute in ("NOBYPASSRLS", "NOSUPERUSER", "NOCREATEDB", "NOCREATEROLE", "NOREPLICATION"):
        assert attribute in attributes, f"CREATE ROLE must state {attribute} explicitly."

    # Strip the negative forms, then look for a bare positive one left behind.
    residue = attributes
    for attribute in ("NOBYPASSRLS", "NOSUPERUSER", "NOCREATEDB", "NOCREATEROLE", "NOREPLICATION", "NOLOGIN"):
        residue = residue.replace(attribute, "")
    for escalation in ("SUPERUSER", "BYPASSRLS", "CREATEROLE", "CREATEDB", "REPLICATION"):
        assert escalation not in residue, f"CREATE ROLE must never grant {escalation}."


def test_role_grants_are_limited_to_dml(role_migration):
    """SELECT/INSERT/UPDATE/DELETE and nothing else. TRUNCATE has no per-row RLS
    check, so it would cross every tenant boundary at once."""
    assert set(role_migration["REQUIRED_TABLE_PRIVILEGES"]) == {"SELECT", "INSERT", "UPDATE", "DELETE"}
    assert "TRUNCATE" in role_migration["FORBIDDEN_TABLE_PRIVILEGES"]
    code = _executable_source(ROLE_MIGRATION).upper()
    assert "GRANT TRUNCATE" not in code
    assert "GRANT ALL" not in code


def test_role_migration_verifies_its_own_result():
    """A half-granted role that reports success is how a cutover turns into an outage."""
    code = _executable_source(ROLE_MIGRATION)
    assert "_assert_role_is_least_privilege" in code
    assert "RuntimeError" in code


def test_role_downgrade_revokes_default_privileges():
    """Default privileges survive a plain REVOKE and would silently re-grant on the
    next CREATE TABLE, so the downgrade must undo them with the same FOR ROLE clause."""
    code = _executable_source(ROLE_MIGRATION)
    assert code.count("ALTER DEFAULT PRIVILEGES") >= 4, (
        "Expected ALTER DEFAULT PRIVILEGES to be both granted in upgrade and revoked in downgrade, "
        "for tables and for sequences."
    )
    assert "REVOKE USAGE, SELECT ON SEQUENCES" in code


# ---------------------------------------------------------------------------
# The readiness script
# ---------------------------------------------------------------------------


def test_readiness_script_has_no_apply_path():
    """Changing the application's database role is a human cutover with an ordering
    requirement, not something a script should be able to do."""
    from scripts.ops.run026 import rls_role_readiness

    assert not hasattr(rls_role_readiness, "apply_plan")
    body = (REPO / "scripts" / "ops" / "run026" / "rls_role_readiness.py").read_text(encoding="utf-8")
    assert "read-only by design" in body
    for statement in ("UPDATE ", "DELETE FROM", "INSERT INTO", "DROP ", "ALTER ROLE", "CREATE ROLE"):
        assert f'sa.text(f"{statement}' not in body, f"Readiness script must not issue {statement.strip()}"


def test_readiness_script_checks_all_three_failure_modes():
    """Predicate safety, grant completeness and the auth bootstrap are independent;
    any one of them alone is enough to break the cutover."""
    from scripts.ops.run026 import rls_role_readiness

    assert rls_role_readiness.EMPTY_GUC_GUARD_MARKER == "NULLIF"
    assert "TRUNCATE" not in rls_role_readiness.REQUIRED_TABLE_PRIVILEGES
    for attribute in ("rolsuper", "rolbypassrls"):
        assert attribute in rls_role_readiness.DISQUALIFYING_ATTRIBUTES


def test_readiness_verdict_blocks_on_the_auth_bootstrap():
    """The verdict must refuse on an auth bootstrap failure even when everything else
    is green, because that failure mode locks every user out at once."""
    from scripts.ops.run026.rls_role_readiness import _verdict

    healthy = {
        "policies": {
            "policies_without_empty_guc_guard": [],
            "policies_not_enabled_and_forced": [],
            "policies_without_with_check": [],
            "in_registry_but_no_policy": [],
            "has_policy_but_not_in_registry": [],
        },
        "candidate_role": {
            "role": "qgp_app",
            "exists": True,
            "can_login": True,
            "disqualifying_attributes": [],
            "tables_missing_required_grants": [],
            "sequences_missing_usage": [],
        },
        "auth_bootstrap": {"auth_would_work": False},
        "null_tenant_rows": {"trusted": True, "total_rows_that_would_become_invisible": 0},
    }
    verdict = _verdict(healthy)
    assert verdict["ready_for_role_change"] is False
    assert any("authentication would break" in blocker for blocker in verdict["blockers"])

    healthy["auth_bootstrap"] = {"auth_would_work": True}
    assert _verdict(healthy)["ready_for_role_change"] is True


def test_readiness_verdict_blocks_on_untrusted_null_counts():
    """A NULL count taken through the policies being assessed is always zero, and
    acting on it would be worse than having no number at all."""
    from scripts.ops.run026.rls_role_readiness import _verdict

    report = {
        "policies": {
            "policies_without_empty_guc_guard": [],
            "policies_not_enabled_and_forced": [],
            "policies_without_with_check": [],
            "in_registry_but_no_policy": [],
            "has_policy_but_not_in_registry": [],
        },
        "candidate_role": {
            "role": "qgp_app",
            "exists": True,
            "can_login": True,
            "disqualifying_attributes": [],
            "tables_missing_required_grants": [],
            "sequences_missing_usage": [],
        },
        "auth_bootstrap": {"auth_would_work": True},
        "null_tenant_rows": {"trusted": False},
    }
    verdict = _verdict(report)
    assert verdict["ready_for_role_change"] is False
    assert any("could not be measured" in blocker for blocker in verdict["blockers"])
