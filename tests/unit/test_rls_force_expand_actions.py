"""Unit tests for FORCE RLS expand to TEN2-complete action tables."""

from __future__ import annotations

import ast
from pathlib import Path

from src.infrastructure.middleware.tenant_context import RLS_TABLES

REPO = Path(__file__).resolve().parents[2]
MIGRATION = REPO / "alembic" / "versions" / "20260711_rls_force_expand_actions.py"


def _migration_body() -> str:
    return MIGRATION.read_text(encoding="utf-8")


def test_migration_file_exists():
    assert MIGRATION.is_file()


def test_revision_chains_from_with_check_expand_head():
    body = _migration_body()
    assert 'revision: str = "20260711_rls_act_exp"' in body
    assert 'down_revision: Union[str, Sequence[str], None] = "20260711_rls_wc_exp"' in body


def test_expand_adds_three_ten2_action_tables():
    body = _migration_body()
    assert "EXPAND_RLS_TABLES = [" in body
    for table in ("incident_actions", "complaint_actions", "rta_actions"):
        assert f'"{table}"' in body


def test_middleware_rls_tables_include_action_expansion():
    assert len(RLS_TABLES) == 18
    for table in ("incident_actions", "complaint_actions", "rta_actions"):
        assert table in RLS_TABLES
    for table in ("policies", "audit_findings", "investigation_actions", "incidents"):
        assert table in RLS_TABLES


def test_migration_sql_includes_with_check_and_force():
    source = _migration_body()
    assert "WITH CHECK" in source
    assert "FORCE ROW LEVEL SECURITY" in source
    assert "ENABLE ROW LEVEL SECURITY" in source
    assert "tenant_id = 1" not in source
    tree = ast.parse(source)
    assert any(isinstance(node, ast.FunctionDef) and node.name == "upgrade" for node in tree.body)
    assert any(isinstance(node, ast.FunctionDef) and node.name == "downgrade" for node in tree.body)
