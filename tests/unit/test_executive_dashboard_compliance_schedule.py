"""Compliance Schedule tile gating on the executive dashboard payload."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from src.api.schemas.executive_dashboard import ExecutiveDashboardResponse
from src.domain.services.executive_dashboard import ExecutiveDashboardService


class _PermUser:
    def __init__(self, *, perms: set[str] | None = None, is_superuser: bool = False):
        self._perms = {p.lower() for p in (perms or set())}
        self.is_superuser = is_superuser

    def has_permission(self, permission: str) -> bool:
        if self.is_superuser:
            return True
        return permission.strip().lower() in self._perms


class _QuietSession:
    """Session that fails every execute so aggregates fall back to empties."""

    async def execute(self, *_args: Any, **_kwargs: Any) -> Any:
        raise RuntimeError("simulated empty dashboard DB")

    async def rollback(self) -> None:
        return None


@pytest.mark.asyncio
async def test_compliance_schedule_absent_when_flag_off(monkeypatch):
    from src.core.config import settings

    monkeypatch.setattr(settings, "compliance_schedule_enabled", False)
    service = ExecutiveDashboardService(_QuietSession(), tenant_id=7)
    user = _PermUser(perms={"compliance_schedule:read"})
    payload = await service.get_full_dashboard(30, user=user)
    assert payload["compliance_schedule"] is None
    ExecutiveDashboardResponse.model_validate(payload)


@pytest.mark.asyncio
async def test_compliance_schedule_absent_without_read_permission(monkeypatch):
    from src.core.config import settings

    monkeypatch.setattr(settings, "compliance_schedule_enabled", True)
    with patch(
        "src.domain.services.compliance_schedule_kill_switch.compliance_schedule_kill_switch_last_known",
        return_value=False,
    ):
        service = ExecutiveDashboardService(_QuietSession(), tenant_id=7)
        user = _PermUser(perms=set())
        payload = await service.get_full_dashboard(30, user=user)
    assert payload["compliance_schedule"] is None


@pytest.mark.asyncio
async def test_compliance_schedule_absent_when_user_omitted(monkeypatch):
    from src.core.config import settings

    monkeypatch.setattr(settings, "compliance_schedule_enabled", True)
    with patch(
        "src.domain.services.compliance_schedule_kill_switch.compliance_schedule_kill_switch_last_known",
        return_value=False,
    ):
        service = ExecutiveDashboardService(_QuietSession(), tenant_id=7)
        payload = await service.get_full_dashboard(30)
    assert payload["compliance_schedule"] is None


@pytest.mark.asyncio
async def test_compliance_schedule_present_with_stats_when_open(monkeypatch):
    from src.core.config import settings

    monkeypatch.setattr(settings, "compliance_schedule_enabled", True)
    stats = {"total_active": 12, "current": 7, "due_soon": 3, "overdue": 2}

    with (
        patch(
            "src.domain.services.compliance_schedule_kill_switch.compliance_schedule_kill_switch_last_known",
            return_value=False,
        ),
        patch(
            "src.domain.services.compliance_schedule_service.ComplianceScheduleService.get_stats",
            new=AsyncMock(return_value=stats),
        ),
    ):
        service = ExecutiveDashboardService(_QuietSession(), tenant_id=7)
        user = _PermUser(perms={"compliance_schedule:read"})
        payload = await service.get_full_dashboard(30, user=user)

    cs = payload["compliance_schedule"]
    assert cs is not None
    assert cs["available"] is True
    assert cs["total_active"] == 12
    assert cs["current"] == 7
    assert cs["due_soon"] == 3
    assert cs["overdue"] == 2
    assert cs["href"] == "/compliance-schedule"
    validated = ExecutiveDashboardResponse.model_validate(payload)
    assert validated.compliance_schedule is not None
    assert validated.compliance_schedule.total_active == 12


@pytest.mark.asyncio
async def test_compliance_schedule_unavailable_when_stats_fail(monkeypatch):
    from src.core.config import settings

    monkeypatch.setattr(settings, "compliance_schedule_enabled", True)

    async def _boom(*_a: Any, **_k: Any) -> dict[str, int]:
        raise RuntimeError("stats query failed")

    with (
        patch(
            "src.domain.services.compliance_schedule_kill_switch.compliance_schedule_kill_switch_last_known",
            return_value=False,
        ),
        patch(
            "src.domain.services.compliance_schedule_service.ComplianceScheduleService.get_stats",
            new=_boom,
        ),
    ):
        service = ExecutiveDashboardService(_QuietSession(), tenant_id=7)
        user = _PermUser(is_superuser=True)
        payload = await service.get_full_dashboard(30, user=user)

    cs = payload["compliance_schedule"]
    assert cs is not None
    assert cs["available"] is False
    assert cs["total_active"] is None
    assert "compliance_schedule" in payload["unavailable"]


def test_open_to_helper_requires_permission_and_flag(monkeypatch):
    from src.core.config import settings

    monkeypatch.setattr(settings, "compliance_schedule_enabled", True)
    with patch(
        "src.domain.services.compliance_schedule_kill_switch.compliance_schedule_kill_switch_last_known",
        return_value=False,
    ):
        assert ExecutiveDashboardService._compliance_schedule_open_to(
            _PermUser(perms={"compliance_schedule:read"})
        )
        assert not ExecutiveDashboardService._compliance_schedule_open_to(_PermUser(perms=set()))
        assert not ExecutiveDashboardService._compliance_schedule_open_to(None)
        assert not ExecutiveDashboardService._compliance_schedule_open_to(SimpleNamespace())
