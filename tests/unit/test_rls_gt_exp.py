"""Unit tests for golden-thread RLS expand (evidence_assets + risks_v2)."""

from __future__ import annotations

import ast
from pathlib import Path

from src.infrastructure.middleware.tenant_context import RLS_TABLES

REPO = Path(__file__).resolve().parents[2]
MIGRATION = REPO / "alembic" / "versions" / "20260719_rls_gt_exp.py"


def _migration_body() -> str:
    return MIGRATION.read_text(encoding="utf-8")


def test_migration_file_exists():
    assert MIGRATION.is_file()


def test_revision_chains_from_capa_nm_rta():
    body = _migration_body()
    assert 'revision: str = "20260719_rls_gt_exp"' in body
    assert 'down_revision: Union[str, Sequence[str], None] = "20260718_capa_nm_rta"' in body


def test_expand_adds_golden_thread_tables():
    body = _migration_body()
    assert "EXPAND_RLS_TABLES = [" in body
    for table in ("risks_v2", "evidence_assets"):
        assert f'"{table}"' in body


def test_middleware_rls_tables_include_gt_expansion():
    assert len(RLS_TABLES) == 23
    for table in ("risks_v2", "evidence_assets"):
        assert table in RLS_TABLES


def test_migration_sql_includes_with_check_and_force():
    source = _migration_body()
    assert "WITH CHECK" in source
    assert "FORCE ROW LEVEL SECURITY" in source
    assert "ENABLE ROW LEVEL SECURITY" in source
    tree = ast.parse(source)
    assert any(isinstance(node, ast.FunctionDef) and node.name == "upgrade" for node in tree.body)
