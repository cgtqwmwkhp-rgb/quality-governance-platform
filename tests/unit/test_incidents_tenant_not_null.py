"""Unit tests for incidents tenant_id fail-safe backfill (WCS-TEN2)."""

from __future__ import annotations

import ast
from pathlib import Path

from src.domain.models.incident import Incident

REPO_ROOT = Path(__file__).resolve().parents[2]
MIGRATION_PATH = REPO_ROOT / "alembic/versions/20260710_incidents_tenant_not_null.py"


def _load_should_enforce_not_null():
    """Extract the pure helper without importing Alembic migration modules."""
    tree = ast.parse(MIGRATION_PATH.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "should_enforce_not_null":
            module = ast.Module(body=[node], type_ignores=[])
            ast.fix_missing_locations(module)
            namespace: dict = {}
            exec(compile(module, str(MIGRATION_PATH), "exec"), namespace)
            return namespace["should_enforce_not_null"]
    raise AssertionError("should_enforce_not_null not found in migration")


def test_incident_orm_tenant_id_is_required():
    column = Incident.__table__.c.tenant_id
    assert column.nullable is False
    assert column.index is True


def test_migration_enforces_only_when_all_incidents_are_attributed():
    should_enforce_not_null = _load_should_enforce_not_null()
    assert should_enforce_not_null(0) is True
    assert should_enforce_not_null(1) is False


def test_migration_chains_from_ext_drafts_and_never_invents_tenant():
    body = MIGRATION_PATH.read_text(encoding="utf-8")
    assert 'revision: str = "20260710_inc_tenant_nn"' in body
    assert 'down_revision: Union[str, Sequence[str], None] = "20260710_ext_draft_nn"' in body
    assert 'TABLE = "incidents"' in body
    assert 'PARENT = "users"' in body
    assert 'PARENT_KEY = "created_by_id"' in body
    assert "FAIL-SAFE" in body
    assert "tenant_id = 1" not in body
    assert "SET tenant_id = 1" not in body.upper()
    assert (REPO_ROOT / "docs/data/incidents-tenant-backfill.md").is_file()


def test_create_path_stamps_incident_tenant_from_caller():
    body = (REPO_ROOT / "src/domain/services/incident_service.py").read_text(encoding="utf-8")
    assert "Incident(" in body
    assert "tenant_id=tenant_id," in body
    assert "created_by_id=user_id," in body
