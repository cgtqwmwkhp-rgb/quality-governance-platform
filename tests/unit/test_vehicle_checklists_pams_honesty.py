"""PAMS vehicle checklist honesty metadata tests."""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from typing import Any

import pytest

from src.api.routes import vehicle_checklists
from src.domain.error_codes import ErrorCode
from src.domain.exceptions import DomainError
from src.domain.models.pams_cache import PAMSVanChecklistCache


class _ExecuteResult:
    def __init__(self, *, scalar_value: int | None = None, rows: list[Any] | None = None) -> None:
        self._scalar_value = scalar_value
        self._rows = rows or []

    def scalar(self) -> int | None:
        return self._scalar_value

    def scalars(self) -> "_ExecuteResult":
        return self

    def all(self) -> list[Any]:
        return self._rows


class _FakeDb:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows
        self.execute_calls = 0

    async def execute(self, _query: Any) -> _ExecuteResult:
        self.execute_calls += 1
        if self.execute_calls == 1:
            return _ExecuteResult(scalar_value=len(self._rows))
        return _ExecuteResult(rows=self._rows)


@pytest.mark.asyncio
async def test_list_from_cache_sets_source_and_cache_as_of() -> None:
    rows = [
        SimpleNamespace(
            raw_data={"vanReg": "AB12CDE", "brakes": "pass"},
            pams_id=101,
            synced_at=datetime(2026, 1, 2, 8, 15, 0),
        ),
        SimpleNamespace(
            raw_data={"vanReg": "EF34GHI", "brakes": "fail"},
            pams_id=102,
            synced_at=datetime(2026, 1, 3, 12, 30, 0),
        ),
    ]

    response = await vehicle_checklists._list_from_cache(
        _FakeDb(rows),  # type: ignore[arg-type]
        PAMSVanChecklistCache,
        page=1,
        page_size=25,
        search=None,
    )

    assert response.source == "cache"
    assert response.cache_as_of == "2026-01-03T12:30:00"
    assert response.items[0]["_synced_at"] == "2026-01-02T08:15:00"
    assert response.items[1]["_pams_id"] == 102


@pytest.mark.asyncio
async def test_live_pams_failure_uses_external_service_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(vehicle_checklists, "is_pams_available", lambda: True)
    monkeypatch.setattr(vehicle_checklists, "get_pams_table", lambda _table_name: object())

    async def failing_pams_db() -> Any:
        raise RuntimeError("PAMS unavailable")
        yield None

    monkeypatch.setattr(vehicle_checklists, "get_pams_db", failing_pams_db)

    with pytest.raises(DomainError) as exc_info:
        await vehicle_checklists._list_from_live_pams("vanchecklist", page=1, page_size=25)

    assert exc_info.value.http_status == 503
    assert exc_info.value.code == ErrorCode.EXTERNAL_SERVICE_ERROR
