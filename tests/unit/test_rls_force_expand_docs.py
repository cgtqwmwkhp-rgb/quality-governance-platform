"""Unit tests for FORCE RLS expand to TEN2-complete document tables."""

from __future__ import annotations

import ast
from pathlib import Path

from src.infrastructure.middleware.tenant_context import RLS_TABLES

REPO = Path(__file__).resolve().parents[2]
MIGRATION = REPO / "alembic" / "versions" / "20260711_rls_force_expand_docs.py"


def _migration_body() -> str:
    return MIGRATION.read_text(encoding="utf-8")


def test_migration_file_exists():
    assert MIGRATION.is_file()


def test_revision_chains_from_actions_expand_head():
    body = _migration_body()
    assert 'revision: str = "20260711_rls_docs_exp"' in body
    assert 'down_revision: Union[str, Sequence[str], None] = "20260711_rls_act_exp"' in body


def test_expand_adds_three_ten2_document_tables():
    body = _migration_body()
    assert "EXPAND_RLS_TABLES = [" in body
    for table in (
        "document_versions",
        "controlled_documents",
        "controlled_document_versions",
    ):
        assert f'"{table}"' in body


def test_middleware_rls_tables_include_docs_expansion():
    assert len(RLS_TABLES) == 21
    for table in (
        "document_versions",
        "controlled_documents",
        "controlled_document_versions",
    ):
        assert table in RLS_TABLES
    for table in ("documents", "incident_actions", "rta_actions"):
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
