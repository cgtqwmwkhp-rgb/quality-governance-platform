"""DLQ /readyz probe honesty — unavailable vs error."""

from __future__ import annotations

import pytest

from src.infrastructure.tasks.dlq_status import dlq_depth_from_exception, dlq_depth_ok, is_missing_failed_tasks_relation


class _FakeUndefinedTable(Exception):
    pgcode = "42P01"


def test_dlq_depth_ok_shape() -> None:
    payload = dlq_depth_ok(3)
    assert payload == {
        "status": "ok",
        "depth": 3,
        "warn_threshold": 10,
        "critical_threshold": 50,
    }


def test_missing_table_message_is_unavailable() -> None:
    exc = Exception('relation "failed_tasks" does not exist')
    assert is_missing_failed_tasks_relation(exc) is True
    payload = dlq_depth_from_exception(exc)
    assert payload["status"] == "unavailable"
    assert payload["depth"] is None
    assert payload["error_class"] == "Exception"
    assert "failed_tasks" in payload["note"]


def test_missing_table_pgcode_is_unavailable() -> None:
    payload = dlq_depth_from_exception(_FakeUndefinedTable("boom"))
    assert payload["status"] == "unavailable"
    assert payload["error_class"] == "_FakeUndefinedTable"


def test_generic_exception_is_error() -> None:
    payload = dlq_depth_from_exception(RuntimeError("connection reset"))
    assert payload["status"] == "error"
    assert payload["depth"] is None
    assert payload["error_class"] == "RuntimeError"
    assert "note" not in payload


@pytest.mark.asyncio
async def test_health_probe_maps_missing_table(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.api.routes import health

    class _BoomConn:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def execute(self, *_args, **_kwargs):
            raise Exception('relation "failed_tasks" does not exist')

    class _BoomEngine:
        def connect(self):
            return _BoomConn()

    monkeypatch.setattr(health, "engine", _BoomEngine())
    payload = await health._probe_dlq_depth()
    assert payload["status"] == "unavailable"
    assert payload["depth"] is None
