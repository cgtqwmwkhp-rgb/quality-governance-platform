"""Compliance schedule list SQL statutory filter (register views R3)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.domain.services.compliance_schedule_list_filters import CLIENT_ONLY_LIST_PARAMS, SERVER_FILTERABLE_PARAMS
from src.domain.services.compliance_schedule_service import ComplianceScheduleService


def test_clause_and_register_are_not_server_filterable() -> None:
    assert "statutory" in SERVER_FILTERABLE_PARAMS
    assert "status" in SERVER_FILTERABLE_PARAMS
    assert "clause" not in SERVER_FILTERABLE_PARAMS
    assert "framework" not in SERVER_FILTERABLE_PARAMS
    assert "register" not in SERVER_FILTERABLE_PARAMS
    assert "clause" in CLIENT_ONLY_LIST_PARAMS
    assert "register" in CLIENT_ONLY_LIST_PARAMS
    assert SERVER_FILTERABLE_PARAMS.isdisjoint(CLIENT_ONLY_LIST_PARAMS)


def _execute_capturing(captured: list) -> AsyncMock:
    async def execute(query, *args, **kwargs):
        captured.append(query)
        result = MagicMock()
        result.scalar.return_value = 0
        scalars = MagicMock()
        scalars.all.return_value = []
        result.scalars.return_value = scalars
        return result

    return execute


def _where_sql(query) -> str:
    compiled = str(query.compile(compile_kwargs={"literal_binds": True}))
    _, _, where = compiled.partition("WHERE")
    return where.upper()


@pytest.mark.asyncio
async def test_list_requirements_applies_statutory_in_sql() -> None:
    captured: list = []
    db = AsyncMock()
    db.execute = _execute_capturing(captured)
    svc = ComplianceScheduleService(db)

    rows, total = await svc.list_requirements(tenant_id=1, statutory=True)

    assert total == 0
    assert rows == []
    assert len(captured) >= 2
    where = _where_sql(captured[0])
    assert "STATUTORY" in where
    assert "TRUE" in where or "1" in where or "STATUTORY IS TRUE" in where


@pytest.mark.asyncio
async def test_list_requirements_omits_statutory_from_where_when_unset() -> None:
    captured: list = []
    db = AsyncMock()
    db.execute = _execute_capturing(captured)
    svc = ComplianceScheduleService(db)

    await svc.list_requirements(tenant_id=1)

    where = _where_sql(captured[0])
    assert "STATUTORY" not in where
