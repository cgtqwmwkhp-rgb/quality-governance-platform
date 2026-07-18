"""Unit tests for RR-W5 list DTO fields (trend + updated_at)."""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.api.routes.risk_register import list_risks
from src.domain.services.risk_service import write_score_trend_to_tags


class _FakeScalars:
    def __init__(self, items):
        self._items = items

    def all(self):
        return self._items


class _FakeResult:
    def __init__(self, *, scalar=None, items=None):
        self._scalar = scalar
        self._items = items or []

    def scalar_one(self):
        return self._scalar

    def scalars(self):
        return _FakeScalars(self._items)


def _risk(**overrides):
    base = {
        "id": 7,
        "reference": "RSK-00007",
        "title": "Board-visible risk",
        "category": "strategic",
        "department": "Ops",
        "inherent_score": 20,
        "inherent_likelihood": 4,
        "inherent_impact": 5,
        "residual_score": 16,
        "residual_likelihood": 4,
        "residual_impact": 4,
        "treatment_strategy": "treat",
        "status": "active",
        "is_within_appetite": False,
        "is_escalated": False,
        "escalation_reason": None,
        "risk_owner_name": "SLT Owner",
        "next_review_date": datetime(2026, 1, 1, 0, 0, 0),
        "updated_at": datetime(2026, 7, 10, 9, 15, 0),
        "tags": write_score_trend_to_tags(None, "increasing"),
        "linked_audits": [],
        "linked_actions": [],
        "linked_incidents": [],
        "suggestion_triage_status": None,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


@pytest.mark.asyncio
async def test_list_risks_includes_trend_and_updated_at():
    risk = _risk()
    db = AsyncMock()
    db.execute = AsyncMock(
        side_effect=[
            _FakeResult(scalar=1),
            _FakeResult(items=[risk]),
        ]
    )
    user = SimpleNamespace(tenant_id=1)

    result = await list_risks(current_user=user, db=db, search=None, skip=0, limit=50)

    assert result["total"] == 1
    item = result["items"][0]
    assert item["trend"] == "increasing"
    assert item["updated_at"] == "2026-07-10T09:15:00"
    assert item["next_review_date"] == "2026-01-01T00:00:00"
    assert item["residual_score"] == 16


@pytest.mark.asyncio
async def test_list_risks_trend_null_when_not_persisted():
    risk = _risk(tags=None, updated_at=None)
    db = AsyncMock()
    db.execute = AsyncMock(
        side_effect=[
            _FakeResult(scalar=1),
            _FakeResult(items=[risk]),
        ]
    )
    user = SimpleNamespace(tenant_id=1)

    result = await list_risks(current_user=user, db=db, search=None, skip=0, limit=50)
    item = result["items"][0]
    assert item["trend"] is None
    assert item["updated_at"] is None
