"""Tests for the case/action ``tenant_id`` NOT NULL convergence migration.

The July 2026 WCS-TEN2 wave tightened ``tenant_id`` *conditionally*: it counted
residual NULLs and only issued ``SET NOT NULL`` when that count was zero. On an
empty database the count is always zero, so CI and fresh developer databases
always matched the ORM; on staging and production, rows created by tenant-less
service accounts survived the backfill and the columns stayed nullable. Drift
that no fresh-database check can see.

These tests cover the two properties that matter and that the wave lacked: the
migration converges the schema when the data permits it, and it **refuses
loudly** when the data does not, rather than skipping quietly.

Two environment constraints shape how they are written.

* The repository contains a top-level ``alembic/`` package directory, which
  shadows the installed ``alembic`` distribution whenever the repository root is
  on ``sys.path`` — as it is under pytest. So no test in this suite can
  ``import alembic.operations``. Existing migration tests work around this by
  asserting on migration source text; the behavioural tests here instead drive
  real Alembic in a subprocess whose ``sys.path`` does not include the
  repository root, loading the migration by file path.
* The migration chain is not SQLite-clean, independently of this change: the
  pre-existing ``20260330_ext_audit_fix`` calls ``ALTER`` on a constraint, which
  SQLite only supports in batch mode. So the behavioural tests build the target
  tables directly rather than running the chain.
"""

from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path

import pytest

from tests.unit._tenant_scope_support import model_metadata_summary

REPO_ROOT = Path(__file__).resolve().parents[2]
MIGRATION_PATH = REPO_ROOT / "alembic/versions/20260901_case_action_tenant_id_not_null.py"
MIGRATION_SOURCE = MIGRATION_PATH.read_text(encoding="utf-8")

# Driven in a subprocess so that real Alembic is importable. Reads a JSON job on
# argv and reports what the migration did, so assertions live in the test rather
# than in this string.
_RUNNER = r"""
import importlib.util, json, sys
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

job = json.loads(sys.argv[1])

spec = importlib.util.spec_from_file_location("_mig", job["migration"])
mig = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mig)

engine = sa.create_engine("sqlite:///" + job["db"])

with engine.begin() as conn:
    for table in job["create_tables"]:
        conn.execute(sa.text(
            "CREATE TABLE %s (id INTEGER PRIMARY KEY, tenant_id INTEGER NULL, "
            "reference_number VARCHAR)" % table
        ))
    for stmt in job["seed"]:
        conn.execute(sa.text(stmt))


def run(step):
    with engine.begin() as conn:
        with Operations.context(MigrationContext.configure(conn)):
            getattr(mig, step)()


result = {"error": None, "error_type": None, "steps_run": []}
try:
    for step in job["steps"]:
        run(step)
        result["steps_run"].append(step)
except Exception as exc:
    result["error"] = str(exc)
    result["error_type"] = type(exc).__name__

inspector = sa.inspect(engine)
present = set(inspector.get_table_names())
result["nullable"] = {
    table: bool(col["nullable"])
    for table in job["create_tables"]
    if table in present
    for col in inspector.get_columns(table)
    if col["name"] == "tenant_id"
}
result["rows"] = {}
for table, query in job.get("row_checks", {}).items():
    with engine.connect() as conn:
        result["rows"][table] = [list(r) for r in conn.execute(sa.text(query)).all()]

print(json.dumps(result))
"""

TARGET_TABLES: tuple[str, ...] = (
    "complaints",
    "incidents",
    "near_misses",
    "road_traffic_collisions",
    "capa_actions",
    "complaint_actions",
    "incident_actions",
    "investigation_actions",
    "rta_actions",
    "compliance_evidence_links",
)


def run_migration(
    tmp_path: Path,
    *,
    steps: list[str],
    create_tables: tuple[str, ...] = TARGET_TABLES,
    seed: list[str] | None = None,
    row_checks: dict[str, str] | None = None,
) -> dict:
    tmp_path.mkdir(parents=True, exist_ok=True)
    job = {
        "migration": str(MIGRATION_PATH),
        "db": str(tmp_path / "drift.db"),
        "create_tables": list(create_tables),
        "seed": seed or [],
        "steps": steps,
        "row_checks": row_checks or {},
    }
    completed = subprocess.run(
        [sys.executable, "-c", _RUNNER, json.dumps(job)],
        # Run outside the repository so the local alembic/ directory does not
        # shadow the installed alembic distribution.
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        timeout=120,
    )
    if completed.returncode != 0:
        pytest.fail(f"migration runner failed:\nstdout={completed.stdout}\nstderr={completed.stderr}")
    return json.loads(completed.stdout)


# --------------------------------------------------------------------------- #
# Revision wiring and scope
# --------------------------------------------------------------------------- #


def _executable_source() -> str:
    """Migration source with docstrings removed.

    The migration's docstring necessarily quotes the pattern it replaces
    (``should_enforce_not_null``, ``FAIL-SAFE``) to explain the history, so tests
    that assert those are gone must look at the code, not the prose.
    """
    tree = ast.parse(MIGRATION_SOURCE)
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        body = node.body
        if body and isinstance(body[0], ast.Expr) and isinstance(getattr(body[0].value, "value", None), str):
            body.pop(0)
            if not body:
                body.append(ast.Pass())
    return ast.unparse(tree)


def _module_constant(name: str):
    tree = ast.parse(MIGRATION_SOURCE)
    for node in tree.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Name) and target.id == name:
                    return ast.literal_eval(node.value)
    raise AssertionError(f"{name} not found in {MIGRATION_PATH.name}")


def test_migration_chains_from_the_current_head():
    assert _module_constant("revision") == "20260901_case_tenant_nn"
    assert _module_constant("down_revision") == "20260831_lookup_enum_align"


def test_targets_are_the_case_and_action_registers_plus_the_swept_table():
    assert _module_constant("TARGET_TABLES") == TARGET_TABLES


def test_every_target_declares_tenant_id_not_null_in_the_orm():
    """The migration must not tighten a column the models say may be NULL.

    This is the invariant that makes it safe to run at all: it only ever asserts
    in the database what the ORM already asserts in Python.
    """
    summary = model_metadata_summary()
    for table_name in TARGET_TABLES:
        assert table_name in summary["tables"], f"{table_name} is not a mapped table"
        assert table_name in summary["tenant_required"], f"{table_name}.tenant_id is nullable in the ORM"


def test_target_list_covers_every_orm_table_whose_tenant_id_drifts_conditionally():
    """Guard against a target being quietly dropped from the list later.

    Every table the WCS-TEN2 wave tried to tighten with a data-conditional
    migration is at risk of the same drift. These are the case and action
    registers among them; if a new one appears, this list must grow with it.
    """
    conditional = set()
    for path in sorted((REPO_ROOT / "alembic/versions").glob("*.py")):
        source = path.read_text(encoding="utf-8")
        if "should_enforce_not_null" not in source:
            continue
        tree = ast.parse(source)
        for node in tree.body:
            if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id in {"TABLE", "TABLES"} for t in node.targets
            ):
                value = ast.literal_eval(node.value)
                conditional.update([value] if isinstance(value, str) else value)

    case_and_action = {
        t
        for t in conditional
        if t.endswith("_actions")
        or t
        in {
            "complaints",
            "incidents",
            "near_misses",
            "road_traffic_collisions",
        }
    }
    missing = case_and_action - set(TARGET_TABLES)
    assert not missing, f"conditionally-tightened case/action tables not covered: {sorted(missing)}"


def test_migration_never_writes_a_tenant_id():
    """No backfill, no invented tenant, no row movement of any kind.

    Deciding which client owns an orphaned road traffic collision is a human
    judgement backed by evidence. A migration that guesses can attribute one
    client's case to another, which is worse than an unusable row.
    """
    code = _executable_source()
    statements = code.upper()
    assert "UPDATE " not in statements
    assert "SET TENANT_ID" not in statements
    assert "INSERT INTO" not in statements
    assert "DELETE FROM" not in statements
    assert "tenant_id = 1" not in code


def test_migration_does_not_reintroduce_the_conditional_skip():
    """The wave's defect was silence, not conditionality.

    A migration may refuse, but it must not decide to leave the column nullable
    and carry on.
    """
    code = _executable_source()
    assert "should_enforce_not_null" not in code
    assert "FAIL-SAFE" not in code
    assert "TenantOrphanRowsError" in code


# --------------------------------------------------------------------------- #
# Convergence
# --------------------------------------------------------------------------- #


def test_upgrade_tightens_every_nullable_target_when_nothing_is_orphaned(tmp_path):
    result = run_migration(tmp_path, steps=["upgrade"], seed=["INSERT INTO complaints (id, tenant_id) VALUES (1, 7)"])

    assert result["error"] is None
    assert result["nullable"] == {table: False for table in TARGET_TABLES}


def test_upgrade_is_idempotent(tmp_path):
    result = run_migration(tmp_path, steps=["upgrade", "upgrade"])

    assert result["error"] is None
    assert result["steps_run"] == ["upgrade", "upgrade"]
    assert not any(result["nullable"].values())


def test_downgrade_restores_nullability_and_upgrade_reapplies(tmp_path):
    result = run_migration(tmp_path, steps=["upgrade", "downgrade"])
    assert result["error"] is None
    assert all(result["nullable"].values()), "downgrade must restore nullable=True"

    again = run_migration(tmp_path / "second", steps=["upgrade", "downgrade", "upgrade"])
    assert again["error"] is None
    assert not any(again["nullable"].values())


def test_downgrade_preserves_rows(tmp_path):
    """SQLite alters nullability by rebuilding the table; rows must survive."""
    result = run_migration(
        tmp_path,
        steps=["upgrade", "downgrade"],
        seed=["INSERT INTO complaints (id, tenant_id, reference_number) VALUES (1, 7, 'CMP-1')"],
        row_checks={"complaints": "SELECT id, tenant_id, reference_number FROM complaints"},
    )

    assert result["error"] is None
    assert result["rows"]["complaints"] == [[1, 7, "CMP-1"]]


def test_absent_tables_are_skipped_not_fatal(tmp_path):
    """Not every deployment has every table; a missing one must not abort."""
    result = run_migration(tmp_path, steps=["upgrade"], create_tables=("complaints", "rta_actions"))

    assert result["error"] is None
    assert result["nullable"] == {"complaints": False, "rta_actions": False}


def test_upgrade_with_no_target_tables_present_is_a_no_op(tmp_path):
    result = run_migration(tmp_path, steps=["upgrade", "downgrade"], create_tables=())

    assert result["error"] is None
    assert result["steps_run"] == ["upgrade", "downgrade"]


# --------------------------------------------------------------------------- #
# Refusal — the property the July wave lacked
# --------------------------------------------------------------------------- #


def test_upgrade_refuses_when_any_row_has_no_tenant(tmp_path):
    result = run_migration(
        tmp_path,
        steps=["upgrade"],
        seed=["INSERT INTO road_traffic_collisions (id, tenant_id, reference_number) VALUES (1, NULL, 'RTA-1')"],
    )

    assert result["error_type"] == "TenantOrphanRowsError"
    assert "road_traffic_collisions: 1 row(s)" in result["error"]
    assert "inventory_tenant_id_nulls" in result["error"]


def test_refusal_reports_every_affected_table_not_just_the_first(tmp_path):
    """An operator needs the whole repair list in one pass, not one table per run."""
    result = run_migration(
        tmp_path,
        steps=["upgrade"],
        seed=[f"INSERT INTO {t} (id, tenant_id) VALUES (1, NULL)" for t in ("complaints", "incidents", "rta_actions")],
    )

    assert result["error_type"] == "TenantOrphanRowsError"
    for table in ("complaints", "incidents", "rta_actions"):
        assert f"{table}: 1 row(s)" in result["error"]


def test_refusal_leaves_the_schema_untouched(tmp_path):
    """No half-application: a refused upgrade must tighten nothing."""
    result = run_migration(
        tmp_path,
        steps=["upgrade"],
        seed=["INSERT INTO near_misses (id, tenant_id) VALUES (1, NULL)"],
    )

    assert result["error_type"] == "TenantOrphanRowsError"
    assert all(result["nullable"].values())


def test_upgrade_succeeds_once_the_orphan_is_attributed(tmp_path):
    """The remediation loop must actually close."""
    blocked = run_migration(
        tmp_path,
        steps=["upgrade"],
        seed=["INSERT INTO complaints (id, tenant_id) VALUES (1, NULL)"],
    )
    assert blocked["error_type"] == "TenantOrphanRowsError"

    repaired = run_migration(
        tmp_path / "repaired",
        steps=["upgrade"],
        seed=[
            "INSERT INTO complaints (id, tenant_id) VALUES (1, NULL)",
            "UPDATE complaints SET tenant_id = 7 WHERE tenant_id IS NULL",
        ],
    )
    assert repaired["error"] is None
    assert not any(repaired["nullable"].values())
