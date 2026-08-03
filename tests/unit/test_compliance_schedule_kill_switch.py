"""Kill-switch TTL behaviour for Compliance Schedule (hermetic, no DB)."""

from __future__ import annotations

import pytest

from src.domain.services import compliance_schedule_kill_switch as kill_switch_module
from src.domain.services.compliance_schedule_kill_switch import (
    compliance_schedule_kill_switch_engaged,
    compliance_schedule_kill_switch_last_known,
    reset_compliance_schedule_kill_switch_cache,
)


class _FakeSessionFactory:
    def __init__(self, *, enabled: bool | None = False, error: Exception | None = None) -> None:
        self._enabled = enabled
        self._error = error
        self.reads = 0

    def __call__(self) -> "_FakeSessionFactory":
        return self

    async def __aenter__(self) -> "_FakeSessionFactory":
        return self

    async def __aexit__(self, *_exc_info: object) -> bool:
        return False

    async def execute(self, _statement: object) -> "_FakeSessionFactory":
        self.reads += 1
        if self._error is not None:
            raise self._error
        return self

    def scalar_one_or_none(self) -> bool | None:
        return self._enabled


@pytest.fixture(autouse=True)
def clean_kill_switch_cache():
    reset_compliance_schedule_kill_switch_cache()
    yield
    reset_compliance_schedule_kill_switch_cache()


async def test_absent_row_reads_as_not_engaged():
    assert await compliance_schedule_kill_switch_engaged(_FakeSessionFactory(enabled=None)) is False


async def test_a_verdict_is_reused_within_its_ttl():
    factory = _FakeSessionFactory(enabled=True)

    assert await compliance_schedule_kill_switch_engaged(factory) is True
    assert await compliance_schedule_kill_switch_engaged(factory) is True
    assert factory.reads == 1


async def test_an_expired_verdict_is_re_read(monkeypatch):
    monkeypatch.setattr(kill_switch_module, "SUCCESS_TTL_SECONDS", 0.0)
    factory = _FakeSessionFactory(enabled=False)

    await compliance_schedule_kill_switch_engaged(factory)
    await compliance_schedule_kill_switch_engaged(factory)

    assert factory.reads == 2


async def test_engaging_after_false_is_observed_after_ttl(monkeypatch):
    """Direct-SQL style flip: process that already read False sees True after TTL."""
    monkeypatch.setattr(kill_switch_module, "SUCCESS_TTL_SECONDS", 0.0)

    assert await compliance_schedule_kill_switch_engaged(_FakeSessionFactory(enabled=False)) is False
    assert await compliance_schedule_kill_switch_engaged(_FakeSessionFactory(enabled=True)) is True


async def test_unreadable_switch_cannot_reopen_an_observed_kill(monkeypatch):
    monkeypatch.setattr(kill_switch_module, "SUCCESS_TTL_SECONDS", 0.0)
    monkeypatch.setattr(kill_switch_module, "ERROR_RETRY_SECONDS", 0.0)

    assert await compliance_schedule_kill_switch_engaged(_FakeSessionFactory(enabled=True)) is True
    broken = _FakeSessionFactory(error=ConnectionRefusedError("database is gone"))
    assert await compliance_schedule_kill_switch_engaged(broken) is True


async def test_last_known_is_false_before_any_read():
    assert compliance_schedule_kill_switch_last_known() is False
