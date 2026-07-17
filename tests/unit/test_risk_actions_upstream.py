"""Unit tests for RR-W3 CAPA-by-source actions + upstream reverse links."""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.api.routes.risk_register import create_risk_action, list_risk_actions, list_risk_upstream, update_risk_owner
from src.api.schemas.risk_register import RiskActionCreate, RiskOwnerUpdate
from src.domain.exceptions import NotFoundError
from src.domain.services.case_risk_links import case_type_href, parse_linked_risk_ids
from src.domain.services.risk_service import RISK_EVENT_ACTION_CREATED, RISK_EVENT_OWNER_CHANGED, RiskService


class _FakeScalars:
    def __init__(self, items):
        self._items = items

    def all(self):
        return self._items


class _FakeResult:
    def __init__(self, one=None, items=None, rows=None):
        self._one = one
        self._items = items or []
        self._rows = rows or []

    def scalar_one_or_none(self):
        return self._one

    def scalars(self):
        return _FakeScalars(self._items)

    def all(self):
        return self._rows or self._items


def test_case_type_href_deep_links():
    assert case_type_href("incident", 7) == "/incidents/7"
    assert case_type_href("near_miss", 3) == "/near-misses/3"
    assert case_type_href("rta", 2) == "/rtas/2"
    assert case_type_href("complaint", 9) == "/complaints/9"


def test_parse_linked_risk_ids_still_works():
    assert parse_linked_risk_ids("1, 2,2,x") == [1, 2]


@pytest.mark.asyncio
async def test_list_capa_actions_for_risk_filters_source():
    capa = SimpleNamespace(
        id=11,
        reference_number="CAPA-001",
        title="Mitigate supplier risk",
        description="Follow up",
        status=SimpleNamespace(value="open"),
        priority=SimpleNamespace(value="high"),
        source_id=42,
        due_date=None,
        assigned_to_id=7,
        created_at=datetime(2026, 7, 10, 12, 0, 0),
    )
    db = SimpleNamespace(
        scalar=AsyncMock(return_value=1),
        execute=AsyncMock(return_value=_FakeResult(items=[capa])),
    )
    service = RiskService(db)  # type: ignore[arg-type]
    rows, total = await service.list_capa_actions_for_risk(tenant_id=1, risk_id=42)
    assert total == 1
    assert rows[0].reference_number == "CAPA-001"


@pytest.mark.asyncio
async def test_list_risk_actions_route_tenant_scoped(monkeypatch):
    risk = SimpleNamespace(id=42, tenant_id=1)
    capa = SimpleNamespace(
        id=11,
        reference_number="CAPA-001",
        title="Mitigate",
        description="",
        status=SimpleNamespace(value="open"),
        priority=SimpleNamespace(value="medium"),
        source_id=42,
        due_date=None,
        assigned_to_id=None,
        created_at=datetime(2026, 7, 10, 12, 0, 0),
    )
    db = SimpleNamespace(execute=AsyncMock(return_value=_FakeResult(one=risk)))
    service = MagicMock()
    service.list_capa_actions_for_risk = AsyncMock(return_value=([capa], 1))
    import src.api.routes.risk_register as routes

    monkeypatch.setattr(routes, "RiskService", MagicMock(return_value=service))
    result = await list_risk_actions(
        current_user=SimpleNamespace(tenant_id=1),  # type: ignore[arg-type]
        risk_id=42,
        db=db,  # type: ignore[arg-type]
    )
    assert result.total == 1
    assert result.items[0].source_type == "risk"
    assert result.items[0].href == "/actions?sourceType=risk&sourceId=42"


@pytest.mark.asyncio
async def test_list_risk_actions_not_found():
    db = SimpleNamespace(execute=AsyncMock(return_value=_FakeResult(one=None)))
    with pytest.raises(NotFoundError):
        await list_risk_actions(
            current_user=SimpleNamespace(tenant_id=1),  # type: ignore[arg-type]
            risk_id=99,
            db=db,  # type: ignore[arg-type]
        )


@pytest.mark.asyncio
async def test_create_risk_action_delegates_and_returns_item(monkeypatch):
    risk = SimpleNamespace(id=42, tenant_id=1)
    action = SimpleNamespace(
        id=5,
        reference_number="CAPA-9",
        title="New action",
        description="Desc",
        status=SimpleNamespace(value="open"),
        priority=SimpleNamespace(value="medium"),
        due_date=None,
        assigned_to_id=None,
        created_at=datetime(2026, 7, 11, 9, 0, 0),
    )
    db = SimpleNamespace(execute=AsyncMock(return_value=_FakeResult(one=risk)))
    service = MagicMock()
    service.create_capa_action_for_risk = AsyncMock(return_value=action)
    import src.api.routes.risk_register as routes

    monkeypatch.setattr(routes, "RiskService", MagicMock(return_value=service))
    monkeypatch.setattr(routes, "invalidate_tenant_cache", AsyncMock())
    result = await create_risk_action(
        current_user=SimpleNamespace(id=3, tenant_id=1),  # type: ignore[arg-type]
        risk_id=42,
        body=RiskActionCreate(title="New action", description="Desc"),
        db=db,  # type: ignore[arg-type]
    )
    assert result.id == 5
    assert result.reference_number == "CAPA-9"


@pytest.mark.asyncio
async def test_list_upstream_for_risk_builds_hrefs():
    link = SimpleNamespace(case_type="incident", case_id=7, created_at=datetime(2026, 7, 1), id=1)
    incident = SimpleNamespace(id=7, title="Spill", reference_number="INC-7")
    finding = SimpleNamespace(id=501, title="Missing control", reference_number="AF-501", run_id=41)
    db = SimpleNamespace(execute=AsyncMock())
    db.execute.side_effect = [
        _FakeResult(items=[link]),
        _FakeResult(items=[incident]),
        _FakeResult(items=[finding]),
    ]
    service = RiskService(db)  # type: ignore[arg-type]
    items = await service.list_upstream_for_risk(tenant_id=1, risk_id=42)
    assert len(items) == 2
    assert items[0]["href"] == "/incidents/7"
    assert items[1]["href"] == "/audits/41/execute"


@pytest.mark.asyncio
async def test_list_risk_upstream_route(monkeypatch):
    risk = SimpleNamespace(id=42, tenant_id=1)
    db = SimpleNamespace(execute=AsyncMock(return_value=_FakeResult(one=risk)))
    service = MagicMock()
    service.list_upstream_for_risk = AsyncMock(
        return_value=[
            {
                "source_type": "incident",
                "source_id": 7,
                "title": "Spill",
                "reference": "INC-7",
                "href": "/incidents/7",
            }
        ]
    )
    import src.api.routes.risk_register as routes

    monkeypatch.setattr(routes, "RiskService", MagicMock(return_value=service))
    result = await list_risk_upstream(
        current_user=SimpleNamespace(tenant_id=1),  # type: ignore[arg-type]
        risk_id=42,
        db=db,  # type: ignore[arg-type]
    )
    assert result.total == 1
    assert result.items[0].href == "/incidents/7"


@pytest.mark.asyncio
async def test_update_risk_owner_emits_activity():
    risk = SimpleNamespace(id=42, tenant_id=1, risk_owner_id=None, risk_owner_name=None, updated_at=None)
    owner = SimpleNamespace(id=7, full_name="Alex Owner", email="alex@example.com", tenant_id=1)
    db = SimpleNamespace(
        execute=AsyncMock(return_value=_FakeResult(one=owner)),
        add=MagicMock(),
        commit=AsyncMock(),
        refresh=AsyncMock(),
    )
    service = RiskService(db)  # type: ignore[arg-type]
    updated = await service.update_risk_owner(risk, risk_owner_id=7, risk_owner_name=None, actor_id=3)
    assert updated.risk_owner_id == 7
    assert updated.risk_owner_name == "Alex Owner"
    event = db.add.call_args[0][0]
    assert event.event_type == RISK_EVENT_OWNER_CHANGED


@pytest.mark.asyncio
async def test_update_risk_owner_route(monkeypatch):
    risk = SimpleNamespace(id=42, tenant_id=1, risk_owner_id=None, risk_owner_name=None)
    db = SimpleNamespace(execute=AsyncMock(return_value=_FakeResult(one=risk)))
    service = MagicMock()
    service.update_risk_owner = AsyncMock(
        return_value=SimpleNamespace(id=42, risk_owner_id=7, risk_owner_name="Alex Owner")
    )
    import src.api.routes.risk_register as routes

    monkeypatch.setattr(routes, "RiskService", MagicMock(return_value=service))
    monkeypatch.setattr(routes, "invalidate_tenant_cache", AsyncMock())
    result = await update_risk_owner(
        current_user=SimpleNamespace(id=3, tenant_id=1),  # type: ignore[arg-type]
        risk_id=42,
        body=RiskOwnerUpdate(risk_owner_id=7),
        db=db,  # type: ignore[arg-type]
    )
    assert result.risk_owner_id == 7


def test_action_created_event_constant():
    assert RISK_EVENT_ACTION_CREATED == "action_created"
    assert RISK_EVENT_OWNER_CHANGED == "owner_changed"
