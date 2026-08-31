"""AUD-DEV-3: list_runs catalogue filters keep exact tenant match."""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest

from src.domain.services.audit_service import AuditService
from tests.unit.test_route_authz_tenant_scope import _assert_exact_tenant_sql, _FakeResult, _sql


@pytest.mark.asyncio
async def test_list_runs_progress_open_sql_excludes_completed_and_stays_tenant_exact():
    captured: list = []

    async def _execute(stmt):
        captured.append(stmt)
        return _FakeResult(0)

    service = AuditService(db=SimpleNamespace(execute=_execute))
    await service.list_runs(42, page=1, page_size=20, progress="open")

    assert captured
    joined = " ".join(_sql(stmt) for stmt in captured)
    assert "COMPLETED" in joined
    assert "CANCELLED" in joined
    for stmt in captured:
        _assert_exact_tenant_sql(_sql(stmt), 42)


@pytest.mark.asyncio
async def test_list_runs_employee_and_type_and_dates_keep_tenant_exact():
    captured: list = []

    async def _execute(stmt):
        captured.append(stmt)
        return _FakeResult(0)

    service = AuditService(db=SimpleNamespace(execute=_execute))
    await service.list_runs(
        42,
        page=1,
        page_size=20,
        progress="completed",
        audit_type="inspection",
        employee="Alex",
        date_from=date(2026, 8, 1),
        date_to=date(2026, 8, 31),
    )

    joined = " ".join(_sql(stmt) for stmt in captured)
    assert "INSPECTION" in joined
    assert "ALEX" in joined or "%Alex%" in joined or "ALEX" in joined.upper()
    for stmt in captured:
        _assert_exact_tenant_sql(_sql(stmt), 42)
