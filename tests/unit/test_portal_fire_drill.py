"""Unit tests for portal fire-drill list + complete (Wave 3)."""

from __future__ import annotations

from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.domain.exceptions import NotFoundError, ValidationError
from src.domain.services.portal_fire_drill_service import (
    ALLOWED_TEMPLATE_KEY,
    EVIDENCE_CAPTURE_SUPPORTED,
    PortalFireDrillService,
)


class _AllResult:
    def __init__(self, rows: list[object]) -> None:
        self._rows = rows

    def all(self) -> list[object]:
        return self._rows


class _OneResult:
    def __init__(self, row: object | None) -> None:
        self._row = row

    def one_or_none(self) -> object | None:
        return self._row


def _requirement(
    *,
    req_id: int = 10,
    owner_id: int = 7,
    title: str = "Site fire drill",
    next_due: date = date(2026, 8, 1),
) -> SimpleNamespace:
    return SimpleNamespace(
        id=req_id,
        title=title,
        reference_number=f"CSR-2026-{req_id:04d}",
        next_due_date=next_due,
        location_id=3,
        owner_id=owner_id,
        last_completed_at=None,
        is_active=True,
    )


@pytest.mark.asyncio
async def test_list_returns_owned_fire_drills_only() -> None:
    req = _requirement()
    db = SimpleNamespace(execute=AsyncMock(return_value=_AllResult([(req, "Wickford")])))
    service = PortalFireDrillService(db)

    payload = await service.list_my_fire_drills(
        user_id=7,
        tenant_id=1,
        now=datetime(2026, 7, 15, tzinfo=timezone.utc),
    )

    assert payload["total"] == 1
    assert payload["evidence_capture_supported"] is EVIDENCE_CAPTURE_SUPPORTED
    item = payload["items"][0]
    assert item["id"] == 10
    assert item["location_name"] == "Wickford"
    assert item["status"] == "due_soon"
    assert ALLOWED_TEMPLATE_KEY == "fire_drill_evacuation"


@pytest.mark.asyncio
async def test_list_empty_when_none_owned() -> None:
    db = SimpleNamespace(execute=AsyncMock(return_value=_AllResult([])))
    service = PortalFireDrillService(db)

    payload = await service.list_my_fire_drills(user_id=7, tenant_id=1)

    assert payload == {
        "items": [],
        "total": 0,
        "evidence_capture_supported": EVIDENCE_CAPTURE_SUPPORTED,
    }


@pytest.mark.asyncio
async def test_complete_delegates_to_schedule_service_for_owner() -> None:
    req = _requirement()
    record = SimpleNamespace(
        id=99,
        reference_number="CR-2026-0001",
        requirement_id=10,
        due_date=date(2026, 8, 1),
        completed_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
        check_passed=True,
        notes="All clear",
    )
    db = SimpleNamespace(
        execute=AsyncMock(return_value=_OneResult((req, ALLOWED_TEMPLATE_KEY))),
    )
    service = PortalFireDrillService(db)
    service._schedule.complete_requirement = AsyncMock(return_value=record)  # type: ignore[method-assign]

    out = await service.complete_my_fire_drill(
        10,
        user_id=7,
        tenant_id=1,
        notes="All clear",
        check_passed=True,
    )

    assert out is record
    service._schedule.complete_requirement.assert_awaited_once_with(
        10,
        tenant_id=1,
        user_id=7,
        completed_at=None,
        check_passed=True,
        notes="All clear",
        evidence_asset_ids=None,
        due_date_override=None,
    )


@pytest.mark.asyncio
async def test_complete_rejects_non_owner() -> None:
    req = _requirement(owner_id=99)
    db = SimpleNamespace(
        execute=AsyncMock(return_value=_OneResult((req, ALLOWED_TEMPLATE_KEY))),
    )
    service = PortalFireDrillService(db)
    service._schedule.complete_requirement = AsyncMock()  # type: ignore[method-assign]

    with pytest.raises(NotFoundError):
        await service.complete_my_fire_drill(10, user_id=7, tenant_id=1)

    service._schedule.complete_requirement.assert_not_awaited()


@pytest.mark.asyncio
async def test_complete_rejects_non_allowlisted_template() -> None:
    req = _requirement()
    db = SimpleNamespace(
        execute=AsyncMock(return_value=_OneResult((req, "fire_risk_assessment"))),
    )
    service = PortalFireDrillService(db)
    service._schedule.complete_requirement = AsyncMock()  # type: ignore[method-assign]

    with pytest.raises(NotFoundError):
        await service.complete_my_fire_drill(10, user_id=7, tenant_id=1)

    service._schedule.complete_requirement.assert_not_awaited()


@pytest.mark.asyncio
async def test_complete_rejects_missing_requirement() -> None:
    db = SimpleNamespace(execute=AsyncMock(return_value=_OneResult(None)))
    service = PortalFireDrillService(db)

    with pytest.raises(NotFoundError):
        await service.complete_my_fire_drill(404, user_id=7, tenant_id=1)


@pytest.mark.asyncio
async def test_complete_rejects_evidence_when_unsupported() -> None:
    assert EVIDENCE_CAPTURE_SUPPORTED is False
    db = SimpleNamespace(execute=AsyncMock())
    service = PortalFireDrillService(db)
    service._schedule.complete_requirement = AsyncMock()  # type: ignore[method-assign]

    with pytest.raises(ValidationError, match="evidence"):
        await service.complete_my_fire_drill(
            10,
            user_id=7,
            tenant_id=1,
            evidence_asset_ids=[1],
        )

    service._schedule.complete_requirement.assert_not_awaited()


@pytest.mark.asyncio
async def test_route_kill_switch_returns_404_when_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    from fastapi import HTTPException

    from src.api.routes import portal_fire_drill as routes

    async def _closed() -> bool:
        return False

    monkeypatch.setattr(routes, "compliance_schedule_is_open", _closed)

    with pytest.raises(HTTPException) as excinfo:
        await routes.require_compliance_schedule_enabled()

    assert excinfo.value.status_code == 404


@pytest.mark.asyncio
async def test_route_kill_switch_passes_when_open(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.api.routes import portal_fire_drill as routes

    async def _open() -> bool:
        return True

    monkeypatch.setattr(routes, "compliance_schedule_is_open", _open)
    await routes.require_compliance_schedule_enabled()
