"""Unit tests for controlled_document_versions tenant_id fail-safe backfill (WCS-TEN2)."""

from __future__ import annotations

import ast
from pathlib import Path

from src.domain.models.document_control import ControlledDocumentVersion

REPO_ROOT = Path(__file__).resolve().parents[2]
MIGRATION_PATH = REPO_ROOT / "alembic/versions/20260711_controlled_document_versions_tenant_not_null.py"


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


def test_cdv_orm_tenant_id_is_required():
    column = ControlledDocumentVersion.__table__.c.tenant_id
    assert column.nullable is False
    assert column.index is True


def test_migration_enforces_only_when_all_rows_are_attributed():
    should_enforce_not_null = _load_should_enforce_not_null()
    assert should_enforce_not_null(0) is True
    assert should_enforce_not_null(1) is False


def test_migration_chains_from_pv_and_never_invents_tenant():
    body = MIGRATION_PATH.read_text(encoding="utf-8")
    assert 'revision: str = "20260711_cdv_tenant_nn"' in body
    assert 'down_revision: Union[str, Sequence[str], None] = "20260711_pv_tenant_nn"' in body
    assert 'TABLE = "controlled_document_versions"' in body
    assert 'PARENT = "controlled_documents"' in body
    assert 'PARENT_KEY = "document_id"' in body
    assert "FAIL-SAFE" in body
    assert "tenant_id = 1" not in body
    assert (REPO_ROOT / "docs/data/controlled-document-versions-tenant-backfill.md").is_file()


def test_create_path_stamps_tenant_id():
    route = (REPO_ROOT / "src/api/routes/document_control.py").read_text(encoding="utf-8")
    service = (REPO_ROOT / "src/domain/services/document_version_service.py").read_text(
        encoding="utf-8"
    )
    assert "build_initial_controlled_version(" in route
    assert "ControlledDocumentVersion(" in service
    assert "tenant_id=tenant_id" in service
