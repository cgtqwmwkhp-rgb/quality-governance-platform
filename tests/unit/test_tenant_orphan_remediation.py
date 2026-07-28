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
from scripts.ops.run025.purge_tenant_orphan_rows import _reference_parts
from scripts.ops.run025.purge_tenant_orphan_rows import main as purge_main

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


@pytest.mark.parametrize("script", ["purge_tenant_orphan_rows.py", "assign_tenant_orphan_rows.py"])
def test_mutating_scripts_never_write_outside_an_apply_path(script):
    """Every DELETE/UPDATE must live in a function only reached under --apply."""
    tree = ast.parse((SCRIPT_DIR / script).read_text(encoding="utf-8"))
    offenders = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef) or node.name == "apply_plan":
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
