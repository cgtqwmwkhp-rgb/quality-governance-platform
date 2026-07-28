"""Tests for the Run025 tenant-scope inventory and model/schema parity scripts.

Both scripts are read-only, and both exist because the repository had no way to
compare the declared models against a database that actually holds data. The
properties worth pinning are the ones that make their output trustworthy:

* they never mutate, and reject ``--apply`` rather than accepting it as a no-op;
* they load exactly the metadata ``alembic/env.py`` compares against, so their
  findings can be reconciled with ``alembic check`` rather than argued with;
* they report row-level-security blindness instead of a false zero.

The RLS-blindness behaviour is the subtle one. Every case table is under FORCE ROW
LEVEL SECURITY with a policy comparing ``tenant_id`` to
``current_setting('app.current_tenant_id')``. A NULL never satisfies it, and FORCE
applies the policy to the table owner too, so a role without ``rolsuper`` or
``rolbypassrls`` sees no rows at all — and a naive inventory would cheerfully
report "0 orphans" for a table full of them.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from scripts.ops.run025 import _models
from scripts.ops.run025.inventory_tenant_id_nulls import dsn_label
from scripts.ops.run025.inventory_tenant_id_nulls import main as inventory_main
from scripts.ops.run025.verify_model_schema_parity import main as parity_main
from tests.unit._tenant_scope_support import model_metadata_summary

REPO_ROOT = Path(__file__).resolve().parents[2]
OPS_DIR = REPO_ROOT / "scripts/ops/run025"


# --------------------------------------------------------------------------- #
# Read-only contract
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("entry", [inventory_main, parity_main])
def test_apply_is_rejected_not_silently_ignored(entry, capsys):
    """An operator who reaches for --apply must be told it does not exist."""
    assert entry(["--apply"]) == 2
    assert "read-only" in capsys.readouterr().err


@pytest.mark.parametrize(
    "script",
    ["inventory_tenant_id_nulls.py", "verify_model_schema_parity.py", "_models.py"],
)
def test_scripts_contain_no_write_statements(script):
    """Inspect string literals only.

    SQL reaches the database as a string, so that is where to look. Scanning the
    whole source instead would trip over ordinary Python identifiers — the shared
    ``truncate`` helper reads as ``TRUNCATE`` once upper-cased.
    """
    tree = ast.parse((OPS_DIR / script).read_text(encoding="utf-8"))
    literals = [
        node.value.upper() for node in ast.walk(tree) if isinstance(node, ast.Constant) and isinstance(node.value, str)
    ]
    docstrings = {
        ast.get_docstring(node, clean=False)
        for node in ast.walk(tree)
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    }
    prose = {doc.upper() for doc in docstrings if doc}

    for literal in literals:
        if literal in prose:
            continue
        for statement in ("UPDATE ", "INSERT INTO", "DELETE FROM", "ALTER TABLE", "DROP TABLE", "TRUNCATE TABLE"):
            assert statement not in literal, f"{script} builds SQL containing {statement!r}: {literal[:120]!r}"


def test_scripts_use_the_shared_apply_safety_contract():
    """Dry-run default and the production acknowledgement flag come from one place."""
    for script in ("inventory_tenant_id_nulls.py", "verify_model_schema_parity.py"):
        source = (OPS_DIR / script).read_text(encoding="utf-8")
        assert "from scripts.ops.run021._common import" in source
        assert "add_safety_args" in source
        assert "enforce_apply_safety" in source


# --------------------------------------------------------------------------- #
# Metadata alignment with alembic/env.py
# --------------------------------------------------------------------------- #


def test_side_effect_module_list_is_read_from_alembic_env():
    """Restating the list here would go stale and silently narrow the check."""
    modules = _models.side_effect_model_modules()
    assert "src.domain.models.kri" in modules
    assert "src.domain.models.near_miss" in modules
    env_source = (REPO_ROOT / "alembic/env.py").read_text(encoding="utf-8")
    for module in modules:
        assert module in env_source


def test_excluded_tables_are_read_from_alembic_env():
    excluded = _models.alembic_check_excluded_tables()
    assert "root_cause_analyses" in excluded
    assert "obsolete_document_records" in excluded


def test_metadata_excludes_the_audit_template_collision_tables():
    """pkgutil-sweeping the models package registers tables no migration creates.

    ``audit_template.py`` declares a second ``AuditTemplate`` on the same Base as
    ``audit.py``. Importing it adds seven tables that do not exist in any
    database, which would show up as bogus "missing table" findings.
    """
    tables = set(model_metadata_summary()["tables"])
    assert "audit_builder_templates" not in tables
    assert "audit_template_versions" not in tables
    assert "road_traffic_collisions" in tables


def test_tenant_required_tables_includes_every_case_and_action_register():
    required = set(model_metadata_summary()["tenant_required"])
    for table in (
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
    ):
        assert table in required, f"{table} should declare tenant_id NOT NULL"


def test_tenant_required_tables_excludes_tables_that_allow_a_null_tenant():
    """NULL tenant is legitimate for some tables; the inventory must not flag them."""
    summary = model_metadata_summary()
    required = set(summary["tenant_required"])
    nullable = set(summary["tenant_nullable"])
    # Superuser service accounts legitimately have no tenant.
    assert "users" not in required
    assert "users" in nullable
    # RTA running-sheet entries declare tenant_id nullable in the ORM.
    assert "rta_running_sheet_entries" not in required
    assert "rta_running_sheet_entries" in nullable


# --------------------------------------------------------------------------- #
# DSN reporting
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "dsn,expected",
    [
        ("postgresql+asyncpg://user:secret@db.example.net:5432/qgp", "postgresql://db.example.net:5432/qgp"),
        ("postgresql://postgres@localhost:5432/quality_governance", "postgresql://localhost:5432/quality_governance"),
        ("sqlite+aiosqlite:////tmp/x.db", "sqlite://(local socket)//tmp/x.db"),
    ],
)
def test_dsn_label_names_the_deployment_without_leaking_the_password(dsn, expected):
    label = dsn_label(dsn)
    assert label == expected
    assert "secret" not in label


def test_dsn_label_does_not_raise_on_a_malformed_dsn():
    assert dsn_label("not a dsn at all") == "<unparseable dsn>"
