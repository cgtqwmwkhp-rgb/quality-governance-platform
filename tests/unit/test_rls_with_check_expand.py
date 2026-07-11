"""Unit tests for RLS WITH CHECK rewrite + FORCE expand migration."""

from __future__ import annotations

import ast
from pathlib import Path

from src.infrastructure.middleware.tenant_context import RLS_TABLES

REPO = Path(__file__).resolve().parents[2]
MIGRATION = REPO / "alembic" / "versions" / "20260711_rls_with_check_expand.py"


def _migration_body() -> str:
    return MIGRATION.read_text(encoding="utf-8")


def test_migration_file_exists():
    assert MIGRATION.is_file()


def test_revision_chains_from_document_annotations_head():
    body = _migration_body()
    assert 'revision: str = "20260711_rls_wc_exp"' in body
    assert 'down_revision: Union[str, Sequence[str], None] = "20260711_dann_tenant_nn"' in body


def test_existing_tables_get_with_check_rewrite():
    body = _migration_body()
    assert "EXISTING_RLS_TABLES" in body
    for table in (
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
    ):
        assert f'"{table}"' in body


def test_expand_adds_three_ten2_owned_tables():
    body = _migration_body()
    assert "EXPAND_RLS_TABLES = [" in body
    assert '"policies"' in body
    assert '"audit_findings"' in body
    assert '"investigation_actions"' in body


def test_middleware_rls_tables_include_expansion():
    assert len(RLS_TABLES) == 15
    for table in ("policies", "audit_findings", "investigation_actions"):
        assert table in RLS_TABLES
    for table in ("incidents", "users", "audit_log_entries"):
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
