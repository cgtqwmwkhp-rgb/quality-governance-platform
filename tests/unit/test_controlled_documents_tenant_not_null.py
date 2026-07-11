"""Unit tests for controlled_documents tenant_id fail-safe backfill (WCS-TEN2)."""

from __future__ import annotations

import ast
from pathlib import Path

from src.domain.models.document_control import ControlledDocument

REPO_ROOT = Path(__file__).resolve().parents[2]
MIGRATION_PATH = REPO_ROOT / "alembic/versions/20260711_controlled_documents_tenant_not_null.py"


def _load_should_enforce_not_null():
    tree = ast.parse(MIGRATION_PATH.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "should_enforce_not_null":
            module = ast.Module(body=[node], type_ignores=[])
            ast.fix_missing_locations(module)
            namespace: dict = {}
            exec(compile(module, str(MIGRATION_PATH), "exec"), namespace)
            return namespace["should_enforce_not_null"]
    raise AssertionError("should_enforce_not_null not found in migration")


def test_cd_orm_tenant_id_is_required():
    column = ControlledDocument.__table__.c.tenant_id
    assert column.nullable is False
    assert column.index is True


def test_migration_enforces_only_when_all_rows_are_attributed():
    should_enforce_not_null = _load_should_enforce_not_null()
    assert should_enforce_not_null(0) is True
    assert should_enforce_not_null(1) is False


def test_migration_chains_from_cdv_and_never_invents_tenant():
    body = MIGRATION_PATH.read_text(encoding="utf-8")
    assert 'revision: str = "20260711_cd_tenant_nn"' in body
    assert 'down_revision: Union[str, Sequence[str], None] = "20260711_cdv_tenant_nn"' in body
    assert 'TABLE = "controlled_documents"' in body
    assert 'PARENT = "users"' in body
    assert 'PARENT_KEY = "author_id"' in body
    assert "owner_id" in body
    assert "FAIL-SAFE" in body
    assert "tenant_id = 1" not in body
    assert (REPO_ROOT / "docs/data/controlled-documents-tenant-backfill.md").is_file()


def test_create_path_stamps_tenant_id():
    body = (REPO_ROOT / "src/api/routes/document_control.py").read_text(encoding="utf-8")
    assert "ControlledDocument(" in body
    assert "tenant_id=tenant_id" in body
