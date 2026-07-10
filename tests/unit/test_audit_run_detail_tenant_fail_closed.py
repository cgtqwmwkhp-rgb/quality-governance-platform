"""Fail-closed tenant scoping for AuditService get_run_detail / complete_run."""

from __future__ import annotations

import inspect
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.domain.exceptions import NotFoundError
from src.domain.services.audit_service import AuditService


class _FakeResult:
    def __init__(self, entity):
        self._entity = entity

    def scalar_one_or_none(self):
        return self._entity


def _assert_fail_closed_sql(stmt) -> None:
    sql = str(stmt.compile(compile_kwargs={"literal_binds": True})).upper()
    assert "IS NULL" not in sql
    assert " OR " not in sql
    assert "TENANT_ID" in sql


@pytest.mark.asyncio
async def test_get_run_detail_sql_is_exact_tenant_match_only():
    captured: list = []

    async def _execute(stmt):
        captured.append(stmt)
        return _FakeResult(None)

    async def _scalar(_stmt):
        return 0

    service = AuditService(db=SimpleNamespace(execute=_execute, scalar=_scalar))

    with pytest.raises(NotFoundError, match="AuditRun 7 not found"):
        await service.get_run_detail(7, tenant_id=42)

    assert len(captured) == 1
    _assert_fail_closed_sql(captured[0])


@pytest.mark.asyncio
async def test_complete_run_sql_is_exact_tenant_match_only():
    captured: list = []

    async def _execute(stmt):
        captured.append(stmt)
        return _FakeResult(None)

    service = AuditService(db=SimpleNamespace(execute=_execute))

    with pytest.raises(NotFoundError, match="AuditRun 7 not found"):
        await service.complete_run(7, tenant_id=42)

    assert len(captured) == 1
    _assert_fail_closed_sql(captured[0])


def test_get_run_detail_and_complete_run_source_is_fail_closed():
    for method in (AuditService.get_run_detail, AuditService.complete_run):
        source = inspect.getsource(method)
        assert "is_(None)" not in source
        assert "or_(" not in source
        assert "AuditRun.tenant_id == tenant_id" in source
