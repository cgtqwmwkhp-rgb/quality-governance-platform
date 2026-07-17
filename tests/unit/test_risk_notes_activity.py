"""Unit tests for RR-W2 risk notes + activity schemas and routes."""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import ValidationError

from src.api.routes.risk_register import create_risk_note, list_risk_activity, list_risk_notes
from src.api.schemas.risk_register import RiskNoteCreate
from src.domain.exceptions import NotFoundError
from src.domain.models.risk_register import RiskActivityEvent, RiskNote
from src.domain.services.risk_service import RISK_EVENT_ASSESSED, RiskService


class TestRiskNoteCreateSchema:
    def test_strips_body(self):
        note = RiskNoteCreate(body="  hello world  ")
        assert note.body == "hello world"

    def test_rejects_blank_body(self):
        with pytest.raises(ValidationError):
            RiskNoteCreate(body="   ")


class TestRiskNoteModel:
    def test_tablename(self):
        assert RiskNote.__tablename__ == "risk_notes"


class TestRiskActivityEventModel:
    def test_tablename(self):
        assert RiskActivityEvent.__tablename__ == "risk_activity_events"


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


@pytest.mark.asyncio
async def test_list_risk_notes_tenant_scoped():
    risk = SimpleNamespace(id=42, tenant_id=1)
    note = SimpleNamespace(
        id=1,
        risk_id=42,
        body="Check supplier SLA",
        created_by_id=9,
        created_at=datetime(2026, 7, 10, 12, 0, 0),
    )
    db = SimpleNamespace(
        execute=AsyncMock(
            side_effect=[
                _FakeResult(one=risk),
                _FakeResult(items=[note]),
                _FakeResult(rows=[SimpleNamespace(id=9, email="user@example.com")]),
            ]
        ),
        scalar=AsyncMock(return_value=1),
    )
    current_user = SimpleNamespace(tenant_id=1)

    result = await list_risk_notes(
        current_user=current_user,  # type: ignore[arg-type]
        risk_id=42,
        db=db,  # type: ignore[arg-type]
        page=1,
        page_size=50,
    )

    assert result.total == 1
    assert len(result.items) == 1
    assert result.items[0].body == "Check supplier SLA"


@pytest.mark.asyncio
async def test_list_risk_notes_not_found():
    db = SimpleNamespace(execute=AsyncMock(return_value=_FakeResult(one=None)))
    with pytest.raises(NotFoundError):
        await list_risk_notes(
            current_user=SimpleNamespace(tenant_id=1),  # type: ignore[arg-type]
            risk_id=99,
            db=db,  # type: ignore[arg-type]
        )


@pytest.mark.asyncio
async def test_list_risk_activity_returns_events():
    risk = SimpleNamespace(id=42, tenant_id=1)
    event = SimpleNamespace(
        id=5,
        risk_id=42,
        event_type=RISK_EVENT_ASSESSED,
        summary="Assessment saved — net score 9 (trend stable)",
        payload={"residual_score": 9, "trend": "stable"},
        actor_id=3,
        created_at=datetime(2026, 7, 10, 12, 0, 0),
    )
    db = SimpleNamespace(
        execute=AsyncMock(
            side_effect=[
                _FakeResult(one=risk),
                _FakeResult(items=[event]),
                _FakeResult(rows=[SimpleNamespace(id=3, email="actor@example.com")]),
            ]
        ),
        scalar=AsyncMock(return_value=1),
    )

    result = await list_risk_activity(
        current_user=SimpleNamespace(tenant_id=1),  # type: ignore[arg-type]
        risk_id=42,
        db=db,  # type: ignore[arg-type]
    )

    assert result.total == 1
    assert result.items[0].event_type == RISK_EVENT_ASSESSED
    assert result.items[0].payload == {"residual_score": 9, "trend": "stable"}


@pytest.mark.asyncio
async def test_create_risk_note_delegates_to_service(monkeypatch):
    risk = SimpleNamespace(id=42, tenant_id=1)
    note = SimpleNamespace(
        id=7,
        risk_id=42,
        body="Escalated to procurement",
        created_by_id=5,
        created_at=datetime(2026, 7, 10, 12, 0, 0),
    )
    db = SimpleNamespace(execute=AsyncMock(return_value=_FakeResult(one=risk)))
    service = MagicMock()
    service.append_risk_note = AsyncMock(return_value=note)

    monkeypatch.setattr("src.api.routes.risk_register.RiskService", lambda _db: service)
    monkeypatch.setattr(
        "src.api.routes.risk_register._resolve_user_email",
        AsyncMock(return_value="owner@example.com"),
    )
    monkeypatch.setattr(
        "src.api.routes.risk_register.invalidate_tenant_cache",
        AsyncMock(),
    )

    result = await create_risk_note(
        current_user=SimpleNamespace(id=5, tenant_id=1),  # type: ignore[arg-type]
        risk_id=42,
        body=RiskNoteCreate(body="Escalated to procurement"),
        db=db,  # type: ignore[arg-type]
    )

    service.append_risk_note.assert_awaited_once()
    assert result.id == 7
    assert result.created_by_email == "owner@example.com"


@pytest.mark.asyncio
async def test_append_risk_note_writes_note_and_activity():
    risk = SimpleNamespace(id=42, tenant_id=1)
    db = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    service = RiskService(db)
    await service.append_risk_note(risk, body="Follow up next week", created_by_id=9)

    assert db.add.call_count == 2
    db.commit.assert_awaited_once()
