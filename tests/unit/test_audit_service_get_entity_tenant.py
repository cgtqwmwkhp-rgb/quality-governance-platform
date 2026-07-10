"""Fail-closed tenant scoping for AuditService._get_entity."""

from __future__ import annotations

import inspect
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.domain.exceptions import NotFoundError
from src.domain.models.audit import AuditTemplate
from src.domain.services.audit_service import AuditService


class _FakeResult:
    def __init__(self, entity):
        self._entity = entity

    def scalar_one_or_none(self):
        return self._entity


@pytest.mark.asyncio
async def test_get_entity_sql_is_exact_tenant_match_only():
    """Scoped _get_entity must not use OR IS NULL (NULL rows excluded)."""
    captured: list = []

    async def _execute(stmt):
        captured.append(stmt)
        return _FakeResult(SimpleNamespace(id=9, tenant_id=42))

    service = AuditService(db=SimpleNamespace(execute=_execute))
    entity = await service._get_entity(AuditTemplate, 9, tenant_id=42)

    assert entity.id == 9
    assert len(captured) == 1
    sql = str(captured[0].compile(compile_kwargs={"literal_binds": True})).upper()
    assert "IS NULL" not in sql
    assert " OR " not in sql
    assert "TENANT_ID" in sql
    assert "= 42" in sql or "42" in sql


@pytest.mark.asyncio
async def test_get_entity_does_not_return_null_tenant_row_when_scoped():
    """When no exact-tenant row exists (NULL tenant filtered out), raise NotFoundError."""
    service = AuditService(db=SimpleNamespace(execute=AsyncMock(return_value=_FakeResult(None))))

    with pytest.raises(NotFoundError, match="AuditTemplate 9 not found"):
        await service._get_entity(AuditTemplate, 9, tenant_id=42)

    # Confirm the executed statement excluded NULL tenants.
    stmt = service.db.execute.await_args.args[0]
    sql = str(stmt.compile(compile_kwargs={"literal_binds": True})).upper()
    assert "IS NULL" not in sql
    assert " OR " not in sql
    assert "TENANT_ID" in sql


@pytest.mark.asyncio
async def test_get_entity_returns_exact_tenant_match():
    matched = SimpleNamespace(id=9, tenant_id=42)
    service = AuditService(db=SimpleNamespace(execute=AsyncMock(return_value=_FakeResult(matched))))

    entity = await service._get_entity(AuditTemplate, 9, tenant_id=42)
    assert entity is matched


@pytest.mark.asyncio
async def test_get_entity_without_tenant_scope_skips_tenant_predicate():
    captured: list = []

    async def _execute(stmt):
        captured.append(stmt)
        return _FakeResult(SimpleNamespace(id=9, tenant_id=None))

    service = AuditService(db=SimpleNamespace(execute=_execute))
    entity = await service._get_entity(AuditTemplate, 9, tenant_id=None)

    assert entity.tenant_id is None
    sql = str(captured[0].compile(compile_kwargs={"literal_binds": True})).upper()
    # Unscoped PK lookup must not inject a tenant predicate beyond the model columns list.
    # The WHERE clause should only constrain id.
    where_sql = sql.split("WHERE", 1)[-1]
    assert "TENANT_ID" not in where_sql


def test_get_entity_source_is_fail_closed():
    """Guard against regressions that reintroduce NULL-inclusive OR in _get_entity."""
    source = inspect.getsource(AuditService._get_entity)
    assert "is_(None)" not in source
    assert "or_(" not in source
    assert "model_any.tenant_id == tenant_id" in source
