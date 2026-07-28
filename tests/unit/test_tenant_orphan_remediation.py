"""Tests for the tenant-orphan remediation scripts (Run025 ops park).

These scripts delete and rewrite rows in an audited register, so the properties
worth testing are the refusals rather than the happy path: that a dependent row
outside the reviewed set stops the operation, that deletion order puts children
first without relying on a cascade, and that the staging assign cannot be pointed
at production or made to guess a tenant.

The end-to-end behaviour against PostgreSQL — including FORCE RLS and real
``ondelete`` rules — is verified by hand against scratch databases and recorded in
the PR body. What is unit-tested here is the decision logic, which is where a
silent mistake would not announce itself.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from scripts.ops.run025 import _models
from scripts.ops.run025._dependencies import InboundRef, deletion_order
from scripts.ops.run025.assign_tenant_orphan_rows import TenantAmbiguous
from scripts.ops.run025.assign_tenant_orphan_rows import main as assign_main
from scripts.ops.run025.assign_tenant_orphan_rows import resolve_tenant
from scripts.ops.run025.backfill_tenant_orphan_rows import (
    PROVENANCE_RULES,
    RowSetDrifted,
    _assert_disjoint,
    _creator_column,
    _debris_signals,
    apply_plan,
    backfill_scope,
)
from scripts.ops.run025.backfill_tenant_orphan_rows import main as backfill_main
from scripts.ops.run025.purge_tenant_orphan_rows import _reference_parts
from scripts.ops.run025.purge_tenant_orphan_rows import main as purge_main
from tests.unit._tenant_scope_support import model_metadata_summary

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = REPO_ROOT / "scripts" / "ops" / "run025"


# --------------------------------------------------------------------------- #
# Deletion order
# --------------------------------------------------------------------------- #


def test_children_are_deleted_before_the_parents_they_reference():
    """The order must not depend on a cascade firing.

    ``incident_actions.incident_id`` is ON DELETE CASCADE, so deleting the incident
    first would work by accident. Deleting the child first means the parent delete
    removes exactly one row, which is what was reviewed.
    """
    candidates = [("incidents", 2), ("incident_actions", 1), ("capa_actions", 2)]
    edges = [(("incident_actions", 1), ("incidents", 2))]

    order = deletion_order(candidates, edges)

    assert order.index(("incident_actions", 1)) < order.index(("incidents", 2))
    assert set(order) == set(candidates)


def test_deletion_order_ignores_edges_pointing_outside_the_candidate_set():
    order = deletion_order([("incidents", 2)], [(("incident_actions", 99), ("incidents", 2))])
    assert order == [("incidents", 2)]


def test_deletion_order_refuses_a_reference_cycle_rather_than_guessing():
    with pytest.raises(RuntimeError, match="circular foreign-key references"):
        deletion_order(
            [("a", 1), ("b", 1)],
            [(("a", 1), ("b", 1)), (("b", 1), ("a", 1))],
        )


def test_deletion_order_of_an_empty_set_is_empty():
    assert deletion_order([], []) == []


# --------------------------------------------------------------------------- #
# Foreign-key classification
# --------------------------------------------------------------------------- #


def _ref(on_delete: str) -> InboundRef:
    return InboundRef(
        constraint="c",
        child_table="incident_actions",
        child_column="incident_id",
        parent_table="incidents",
        on_delete=on_delete,
    )


@pytest.mark.parametrize(
    "on_delete,deletes,mutates,blocks",
    [
        ("CASCADE", True, False, False),
        ("SET NULL", False, True, False),
        ("SET DEFAULT", False, True, False),
        ("NO ACTION", False, False, True),
        ("RESTRICT", False, False, True),
    ],
)
def test_every_ondelete_rule_is_classified(on_delete, deletes, mutates, blocks):
    """Each rule harms the reviewed set differently; none may be treated as benign."""
    ref = _ref(on_delete)
    assert ref.deletes_child is deletes
    assert ref.mutates_child is mutates
    assert ref.blocks_parent is blocks


def test_a_missing_ondelete_clause_is_treated_as_no_action():
    """Absent means NO ACTION in both PostgreSQL and SQLite; it must not read as CASCADE."""
    from scripts.ops.run025._dependencies import _normalise_on_delete

    assert _normalise_on_delete(None) == "NO ACTION"
    assert _normalise_on_delete({}) == "NO ACTION"
    assert _normalise_on_delete({"ondelete": "cascade"}) == "CASCADE"


# --------------------------------------------------------------------------- #
# Reference numbers
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "reference,expected",
    [
        ("INC-2026-0002", ("INC", "2026", 2)),
        ("CAPA-2026-0117", ("CAPA", "2026", 117)),
        ("RTAACT-2026-0001", ("RTAACT", "2026", 1)),
        # Portal hex references are not sequential and must not be parsed as such:
        # int("FFFFFFFF") is not 4294967295 in this context, it is meaningless.
        ("INC-2026-FFFFFFFF", None),
        ("nonsense", None),
        (None, None),
        ("", None),
    ],
)
def test_only_sequential_references_are_parsed(reference, expected):
    assert _reference_parts(reference) == expected


# --------------------------------------------------------------------------- #
# Tenant resolution for the staging assign
# --------------------------------------------------------------------------- #


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def mappings(self):
        return self

    def all(self):
        return self._rows


class _FakeDb:
    def __init__(self, tenants):
        self._tenants = tenants

    async def execute(self, *_args, **_kwargs):
        return _FakeResult(self._tenants)


@pytest.mark.anyio
async def test_a_single_active_tenant_is_resolved_from_the_data():
    db = _FakeDb([{"id": 1, "name": "Default Organisation", "is_active": True}])
    tenant_id, detail = await resolve_tenant(db, None)
    assert tenant_id == 1
    assert detail["resolution"] == "the only active tenant"


@pytest.mark.anyio
async def test_several_active_tenants_refuse_rather_than_pick_one():
    db = _FakeDb(
        [
            {"id": 1, "name": "Default Organisation", "is_active": True},
            {"id": 2, "name": "Second Client", "is_active": True},
        ]
    )
    with pytest.raises(TenantAmbiguous, match="human decision"):
        await resolve_tenant(db, None)


@pytest.mark.anyio
async def test_an_explicit_tenant_id_must_exist_and_be_active():
    db = _FakeDb(
        [
            {"id": 1, "name": "Default Organisation", "is_active": True},
            {"id": 2, "name": "Retired Client", "is_active": False},
        ]
    )
    assert (await resolve_tenant(db, 1))[0] == 1
    with pytest.raises(TenantAmbiguous, match="not active"):
        await resolve_tenant(db, 2)
    with pytest.raises(TenantAmbiguous, match="does not exist"):
        await resolve_tenant(db, 99)


@pytest.mark.anyio
async def test_a_database_with_no_tenants_refuses():
    with pytest.raises(TenantAmbiguous, match="no tenants at all"):
        await resolve_tenant(_FakeDb([]), None)


@pytest.mark.anyio
async def test_no_active_tenant_refuses():
    db = _FakeDb([{"id": 1, "name": "Retired", "is_active": False}])
    with pytest.raises(TenantAmbiguous, match="are active"):
        await resolve_tenant(db, None)


@pytest.mark.anyio
async def test_default_tenant_id_disagreeing_with_the_database_is_the_finding(monkeypatch):
    """Silently preferring either side would hide a real configuration split."""
    monkeypatch.setenv("DEFAULT_TENANT_ID", "7")
    db = _FakeDb([{"id": 1, "name": "Default Organisation", "is_active": True}])
    with pytest.raises(TenantAmbiguous, match="disagree about which tenant is default"):
        await resolve_tenant(db, None)


@pytest.mark.anyio
async def test_a_non_numeric_default_tenant_id_refuses(monkeypatch):
    monkeypatch.setenv("DEFAULT_TENANT_ID", "default")
    db = _FakeDb([{"id": 1, "name": "Default Organisation", "is_active": True}])
    with pytest.raises(TenantAmbiguous, match="not an integer"):
        await resolve_tenant(db, None)


# --------------------------------------------------------------------------- #
# Safety posture
# --------------------------------------------------------------------------- #


def test_assign_refuses_production_even_with_the_prod_acknowledgement(monkeypatch):
    """There is deliberately no flag that permits this on production."""
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://user@localhost/whatever")
    assert assign_main(["--apply", "--i-understand-prod"]) == 2


def test_purge_refuses_apply_on_production_without_the_acknowledgement(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://user@localhost/whatever")
    with pytest.raises(SystemExit) as excinfo:
        purge_main(["--apply"])
    assert excinfo.value.code == 2


def test_purge_apply_requires_a_manifest():
    """An unrecorded delete of audited rows is the thing we are trying to avoid."""
    source = (SCRIPT_DIR / "purge_tenant_orphan_rows.py").read_text(encoding="utf-8")
    assert "--apply requires --manifest" in source


@pytest.mark.parametrize(
    "script",
    ["purge_tenant_orphan_rows.py", "assign_tenant_orphan_rows.py", "backfill_tenant_orphan_rows.py"],
)
def test_mutating_scripts_never_write_outside_an_apply_path(script):
    """Every DELETE/UPDATE must live in a function only reached under --apply.

    ``AsyncFunctionDef`` is a separate node type from ``FunctionDef``, so matching
    only the latter skipped every ``async def`` in these scripts — which is all of
    the database code, including ``apply_plan`` itself. The check now covers both.
    """
    tree = ast.parse((SCRIPT_DIR / script).read_text(encoding="utf-8"))
    offenders = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) or node.name == "apply_plan":
            continue
        for literal in ast.walk(node):
            if isinstance(literal, ast.Constant) and isinstance(literal.value, str):
                upper = literal.value.upper()
                if any(f"{verb} " in upper for verb in ("DELETE FROM", "UPDATE ", "TRUNCATE", "INSERT INTO")):
                    offenders.append(f"{script}:{node.name}")
    assert not offenders, f"write statements outside apply_plan(): {sorted(set(offenders))}"


# --------------------------------------------------------------------------- #
# The remediation and the migration must agree on which tables matter
# --------------------------------------------------------------------------- #


def test_target_tables_are_read_from_the_migration_not_restated():
    """Cleaning nine of ten tables leaves the deploy failing for the same reason."""
    migration = _models.TENANT_NOT_NULL_MIGRATION.read_text(encoding="utf-8")
    declared = None
    for node in ast.walk(ast.parse(migration)):
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.target.id == "TARGET_TABLES" and node.value is not None:
                declared = tuple(ast.literal_eval(node.value))
    assert declared is not None, "the migration no longer declares TARGET_TABLES"
    assert _models.migration_target_tables() == declared
    assert "compliance_evidence_links" in declared


# --------------------------------------------------------------------------- #
# Out-of-scope backfill: scope, provenance, and the single-tenant precondition
# --------------------------------------------------------------------------- #


def test_backfill_can_never_touch_a_case_or_action_table():
    """The two scripts are kept on disjoint tables so neither can do the other's job.

    ``assign`` refuses production because attributing a *case* to a tenant is a
    confidentiality claim. That refusal is only worth anything if the production-
    capable script cannot reach the same tables.

    The real model metadata is fetched from a subprocess: importing it in-process
    would configure the mapper registry and take unrelated tests down with it, for
    the reason set out in ``_tenant_scope_support``.
    """
    tenant_required = set(model_metadata_summary()["tenant_required"])
    in_migration = set(_models.migration_target_tables())
    scope = tenant_required - in_migration
    assert scope, "the backfill has no tables in scope at all, which cannot be right"
    assert not scope.intersection(in_migration)
    for table in ("incidents", "capa_actions", "incident_actions", "road_traffic_collisions"):
        assert table not in scope
    for table in PROVENANCE_RULES:
        assert table in scope, f"{table} has provenance rules but is not a table this script may write to"


def test_backfill_scope_subtracts_the_migration_tables(monkeypatch):
    """The exclusion is a set subtraction, not a hand-maintained list."""
    monkeypatch.setattr(
        "scripts.ops.run025.backfill_tenant_orphan_rows.tenant_required_tables",
        lambda: ["audit_runs", "incidents", "risks_v2"],
    )
    assert backfill_scope() == ("audit_runs", "risks_v2")


def test_the_disjointness_check_actually_fails_when_it_should():
    with pytest.raises(RuntimeError, match="case/action migration scope"):
        _assert_disjoint(("audit_runs", "incidents"))


def test_every_table_with_known_production_orphans_has_declared_provenance():
    """A table with orphans and no rule is refused, so the rules must cover them."""
    measured_in_production = {
        "external_audit_import_drafts",
        "audit_runs",
        "external_audit_import_jobs",
        "audit_findings",
        "risks_v2",
    }
    assert measured_in_production.issubset(PROVENANCE_RULES)


def test_provenance_rules_never_name_a_case_or_action_table():
    in_migration = set(_models.migration_target_tables())
    assert not set(PROVENANCE_RULES).intersection(in_migration)


def test_risks_v2_creator_column_is_created_by_not_created_by_id():
    """Every other table uses created_by_id; a generic sweep would miss this one."""
    assert _creator_column(PROVENANCE_RULES["risks_v2"]) == "created_by"
    assert _creator_column(PROVENANCE_RULES["audit_runs"]) == "created_by_id"


def test_the_strongest_parent_is_declared_first():
    """Rules are tried in order, so the first must be the one that implies ownership."""
    assert PROVENANCE_RULES["audit_findings"][0].parent_table == "audit_runs"
    assert PROVENANCE_RULES["external_audit_import_drafts"][0].parent_table == "external_audit_import_jobs"


def test_debris_signals_separate_synthetic_rows_from_business_records():
    """Attributing test debris into an audited register is the purge decision inverted."""
    rows = [
        {"id": 1, "title": "UAT smoke draft", "created_by_id": 100},
        {"id": 2, "title": "Nonconformance in goods-in", "created_by_id": 101},
        {"id": 3, "title": "Genuine finding", "created_by_id": 102},
    ]
    creators = {
        100: {"email": "alice@plantexpand.com", "is_active": True},
        101: {"email": "smoke-runner@plantexpand.com", "is_active": False},
        102: {"email": "bob@plantexpand.com", "is_active": False},
    }
    signals = _debris_signals(rows, creators, "created_by_id", "id")
    assert signals["rows_matching_test_tokens"] == 1
    assert signals["example_test_token_ids"] == [1]
    assert signals["rows_created_by_ci_smoke_account"] == 1
    assert signals["rows_created_by_deactivated_user"] == 1


def test_backfill_refuses_an_explicitly_named_tenant(monkeypatch):
    """The default is only defensible as a derived fact, never as an operator's claim."""
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://user@localhost/whatever")
    assert backfill_main(["--tenant-id", "1"]) == 2


def test_backfill_refuses_apply_on_production_without_the_acknowledgement(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://user@localhost/whatever")
    with pytest.raises(SystemExit) as excinfo:
        backfill_main(["--apply"])
    assert excinfo.value.code == 2


def test_backfill_apply_requires_a_manifest():
    source = (SCRIPT_DIR / "backfill_tenant_orphan_rows.py").read_text(encoding="utf-8")
    assert "--apply requires --manifest" in source


class _DriftingDb:
    """A database where one planned row stopped being NULL since the plan was built."""

    def __init__(self, visible):
        self._visible = visible
        self.rolled_back = False
        self.committed = False
        self.updates = 0

    async def run_sync(self, fn):
        return "sqlite"

    async def execute(self, statement, params=None):
        text = str(statement).upper()
        if text.startswith("UPDATE"):
            self.updates += 1
            return _FakeResult([])
        return _ScalarResult(self._visible)

    async def rollback(self):
        self.rolled_back = True

    async def commit(self):
        self.committed = True


class _ScalarResult:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return self

    def all(self):
        return self._rows


@pytest.mark.anyio
async def test_apply_rolls_back_when_a_planned_row_is_no_longer_orphaned(monkeypatch):
    """The manifest is the change record; writing a different set would invalidate it."""
    db = _DriftingDb(visible=[1])
    monkeypatch.setattr(
        "scripts.ops.run025.backfill_tenant_orphan_rows.open_session",
        _session_factory(db),
    )
    with pytest.raises(RowSetDrifted, match="no longer NULL-tenant"):
        await apply_plan({"audit_runs": [{"pk": 1, "tenant_id": 1}, {"pk": 2, "tenant_id": 1}]}, {"audit_runs": "id"})
    assert db.rolled_back is True
    assert db.updates == 0, "nothing may be written once drift is detected"
    assert db.committed is False


def _session_factory(db):
    class _Ctx:
        async def __aenter__(self):
            return db

        async def __aexit__(self, *_exc):
            return False

    async def _open_session():
        return _Ctx()

    return _open_session
