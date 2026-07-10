"""Unit tests for audit_findings tenant_id NOT NULL (WCS-TEN2 Phase 2)."""

from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.domain.models.audit import AuditFinding, AuditRun
from src.domain.services.audit_service import AuditService

REPO_ROOT = Path(__file__).resolve().parents[2]
MIGRATION_PATH = REPO_ROOT / "alembic/versions/20260710_audit_findings_tenant_not_null.py"


def _load_should_enforce_not_null():
    """Extract the pure helper without importing the migration (local alembic/ package shadows)."""
    source = MIGRATION_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "should_enforce_not_null":
            module = ast.Module(body=[node], type_ignores=[])
            ast.fix_missing_locations(module)
            ns: dict = {}
            exec(compile(module, str(MIGRATION_PATH), "exec"), ns)
            return ns["should_enforce_not_null"]
    raise AssertionError("should_enforce_not_null not found in migration")


def test_audit_finding_orm_tenant_id_is_required():
    column = AuditFinding.__table__.c.tenant_id
    assert column.nullable is False
    assert column.index is True


def test_audit_run_orm_tenant_id_remains_nullable():
    """Phase 2 is findings-only; do not mass-NOT-NULL audit_runs."""
    assert AuditRun.__table__.c.tenant_id.nullable is True


def test_migration_fail_safe_helper_only_enforces_when_zero_nulls():
    should_enforce_not_null = _load_should_enforce_not_null()
    assert should_enforce_not_null(0) is True
    assert should_enforce_not_null(1) is False
    assert should_enforce_not_null(42) is False


def test_migration_revision_chains_from_doc_ctl_tenant():
    assert MIGRATION_PATH.is_file()
    tree = ast.parse(MIGRATION_PATH.read_text(encoding="utf-8"))
    revision = None
    down_revision = None
    for node in tree.body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.target.id == "revision" and isinstance(node.value, ast.Constant):
                revision = node.value.value
            if node.target.id == "down_revision" and isinstance(node.value, ast.Constant):
                down_revision = node.value.value
    assert revision == "20260710_af_tenant_nn"
    assert down_revision == "20260710_doc_ctl_tenant"
    body = MIGRATION_PATH.read_text(encoding="utf-8")
    assert "should_enforce_not_null" in body
    assert "FAIL-SAFE" in body
    # No silent default-tenant invention in SQL/backfill
    assert "tenant_id = 1" not in body
    assert "SET tenant_id = 1" not in body.upper()
    followup = REPO_ROOT / "docs/data/audit-findings-tenant-backfill.md"
    assert followup.is_file()
    assert "fail-safe" in followup.read_text(encoding="utf-8").lower()


def _sql(statement) -> str:
    return str(statement.compile(compile_kwargs={"literal_binds": True})).lower()


@pytest.mark.asyncio
async def test_list_findings_query_is_exact_tenant_only():
    service = AuditService(db=SimpleNamespace())
    captured: list = []

    async def _paginate(query, page, page_size):
        captured.append(query)
        return SimpleNamespace(items=[], total=0, page=page, page_size=page_size)

    service._paginate = _paginate  # type: ignore[method-assign]
    await service.list_findings(17, page=1, page_size=20)

    assert len(captured) == 1
    sql = _sql(captured[0])
    assert "tenant_id = 17" in sql
    where_sql = sql.split("where", 1)[-1]
    assert "is null" not in where_sql
    assert " or " not in where_sql


@pytest.mark.asyncio
async def test_create_finding_stamps_tenant_from_scoped_call(monkeypatch: pytest.MonkeyPatch):
    run = SimpleNamespace(id=9, tenant_id=31)
    added: list = []

    db = SimpleNamespace(
        add=added.append,
        flush=AsyncMock(),
        refresh=AsyncMock(),
    )
    service = AuditService(db=db)
    service._get_entity = AsyncMock(return_value=run)  # type: ignore[method-assign]
    service._ensure_action_for_finding = AsyncMock(return_value=None)  # type: ignore[method-assign]
    service._ensure_risk_for_finding = AsyncMock(return_value=None)  # type: ignore[method-assign]

    async def _generate(*_a, **_k):
        return "FND-TEST-1"

    monkeypatch.setattr(
        "src.domain.services.audit_service.ReferenceNumberService.generate",
        _generate,
    )
    monkeypatch.setattr(
        "src.domain.services.audit_service.invalidate_tenant_cache",
        AsyncMock(),
    )
    monkeypatch.setattr(
        "src.domain.services.audit_service.track_metric",
        lambda *_a, **_k: None,
    )

    finding = await service.create_finding(
        9,
        {"title": "Gap", "description": "Missing control", "severity": "medium"},
        user_id=1,
        tenant_id=31,
    )

    assert isinstance(finding, AuditFinding)
    assert finding.tenant_id == 31
    assert finding.tenant_id == run.tenant_id
    assert finding.run_id == 9
    assert added and added[0] is finding
    service._get_entity.assert_awaited()
