"""Unit tests for document_access_logs tenant_id fail-safe backfill (WCS-TEN2)."""

from __future__ import annotations

import ast
from pathlib import Path

from src.domain.models.document_control import DocumentAccessLog

REPO_ROOT = Path(__file__).resolve().parents[2]
MIGRATION_PATH = REPO_ROOT / "alembic/versions/20260711_document_access_logs_tenant_not_null.py"


def _load_should_enforce_not_null():
    tree = ast.parse(MIGRATION_PATH.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "should_enforce_not_null":
            module = ast.Module(body=[node], type_ignores=[])
            ast.fix_missing_locations(module)
            namespace: dict = {}
            exec(compile(module, str(MIGRATION_PATH), "exec"), namespace)
            return namespace["should_enforce_not_null"]
    raise AssertionError("should_enforce_not_null not found")


def test_dal_orm_tenant_id_is_required():
    column = DocumentAccessLog.__table__.c.tenant_id
    assert column.nullable is False
    assert column.index is True


def test_migration_enforces_only_when_all_rows_are_attributed():
    fn = _load_should_enforce_not_null()
    assert fn(0) is True
    assert fn(1) is False


def test_migration_chains_from_odr_and_never_invents_tenant():
    body = MIGRATION_PATH.read_text(encoding="utf-8")
    assert 'revision: str = "20260711_dal_tenant_nn"' in body
    assert 'down_revision: Union[str, Sequence[str], None] = "20260711_odr_tenant_nn"' in body
    assert 'TABLE = "document_access_logs"' in body
    assert 'PARENT = "controlled_documents"' in body
    assert "FAIL-SAFE" in body
    assert "tenant_id = 1" not in body
