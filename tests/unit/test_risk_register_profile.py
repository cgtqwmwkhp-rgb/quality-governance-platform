"""Unit tests for RR-P0 risk profile schema and route shape."""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from src.api.routes.risk_register import get_risk_profile
from src.api.schemas.risk_register import AssessmentHistoryItem, RiskProfileResponse
from src.domain.exceptions import NotFoundError


class _FakeScalars:
    def __init__(self, items):
        self._items = items

    def all(self):
        return self._items


class _FakeResult:
    def __init__(self, one=None, items=None):
        self._one = one
        self._items = items or []

    def scalar_one_or_none(self):
        return self._one

    def scalars(self):
        return _FakeScalars(self._items)


def _risk(**overrides):
    base = {
        "id": 42,
        "reference": "RSK-00042",
        "title": "Supplier disruption",
        "description": "Key supplier failure impact",
        "category": "operational",
        "status": "active",
        "treatment_strategy": "treat",
        "inherent_score": 16,
        "residual_score": 9,
        "risk_owner_id": 7,
        "risk_owner_name": "Alex Owner",
        "last_review_date": datetime(2026, 6, 1, 12, 0, 0),
        "next_review_date": datetime(2026, 9, 1, 12, 0, 0),
        "updated_at": datetime(2026, 7, 1, 8, 30, 0),
        "created_at": datetime(2026, 1, 15, 9, 0, 0),
        "linked_actions": ["CAPA-1", "CAPA-2"],
        "review_notes": "Monitor Q3.",
    }
    base.update(overrides)
    return SimpleNamespace(**base)


class TestRiskProfileResponseSchema:
    def test_minimal_profile_shape(self):
        profile = RiskProfileResponse(id=1, title="Test risk")
        assert profile.id == 1
        assert profile.title == "Test risk"
        assert profile.assessment_history == []
        assert profile.linked_actions == []
        assert profile.treatment is None

    def test_full_profile_shape(self):
        profile = RiskProfileResponse(
            id=42,
            reference="RSK-00042",
            title="Supplier disruption",
            description="Key supplier failure impact",
            category="operational",
            status="active",
            treatment="treat",
            inherent_score=16,
            inherent_level="high",
            residual_score=9,
            residual_level="medium",
            risk_owner_id=7,
            risk_owner_name="Alex Owner",
            last_review_date="2026-06-01T12:00:00",
            next_review_date="2026-09-01T12:00:00",
            updated_at="2026-07-01T08:30:00",
            created_at="2026-01-15T09:00:00",
            assessment_history=[
                AssessmentHistoryItem(
                    date="2026-06-01T12:00:00",
                    inherent_score=16,
                    residual_score=9,
                    status="active",
                )
            ],
            linked_actions=["CAPA-1"],
            review_notes="Monitor Q3.",
        )
        dumped = profile.model_dump()
        assert dumped["treatment"] == "treat"
        assert dumped["inherent_level"] == "high"
        assert dumped["residual_level"] == "medium"
        assert len(dumped["assessment_history"]) == 1
        assert dumped["linked_actions"] == ["CAPA-1"]

    def test_title_required(self):
        with pytest.raises(ValidationError):
            RiskProfileResponse(id=1)  # type: ignore[call-arg]


@pytest.mark.asyncio
async def test_get_risk_profile_returns_typed_shape():
    risk = _risk()
    history = [
        SimpleNamespace(
            assessment_date=datetime(2026, 6, 1, 12, 0, 0),
            inherent_score=16,
            residual_score=9,
            status="active",
        )
    ]
    db = SimpleNamespace(
        execute=AsyncMock(
            side_effect=[
                _FakeResult(one=risk),
                _FakeResult(items=history),
            ]
        )
    )
    current_user = SimpleNamespace(tenant_id=1)

    result = await get_risk_profile(
        current_user=current_user,  # type: ignore[arg-type]
        risk_id=42,
        db=db,  # type: ignore[arg-type]
        history_limit=10,
    )

    assert isinstance(result, RiskProfileResponse)
    assert result.id == 42
    assert result.reference == "RSK-00042"
    assert result.treatment == "treat"
    assert result.inherent_score == 16
    assert result.inherent_level == "high"
    assert result.residual_score == 9
    assert result.residual_level == "medium"
    assert result.risk_owner_name == "Alex Owner"
    assert result.linked_actions == ["CAPA-1", "CAPA-2"]
    assert result.review_notes == "Monitor Q3."
    assert len(result.assessment_history) == 1
    assert result.assessment_history[0].inherent_score == 16
    assert result.updated_at == "2026-07-01T08:30:00"
    assert result.created_at == "2026-01-15T09:00:00"


@pytest.mark.asyncio
async def test_get_risk_profile_tenant_fail_closed():
    db = SimpleNamespace(execute=AsyncMock(return_value=_FakeResult(one=None)))
    current_user = SimpleNamespace(tenant_id=99)

    with pytest.raises(NotFoundError):
        await get_risk_profile(
            current_user=current_user,  # type: ignore[arg-type]
            risk_id=42,
            db=db,  # type: ignore[arg-type]
            history_limit=10,
        )

    assert db.execute.await_count == 1
    call_stmt = db.execute.await_args.args[0]
    compiled = str(call_stmt.compile(compile_kwargs={"literal_binds": True}))
    assert "tenant_id" in compiled


@pytest.mark.asyncio
async def test_get_risk_profile_null_scores_yield_null_levels():
    risk = _risk(inherent_score=None, residual_score=None, linked_actions=None)
    db = SimpleNamespace(
        execute=AsyncMock(
            side_effect=[
                _FakeResult(one=risk),
                _FakeResult(items=[]),
            ]
        )
    )
    result = await get_risk_profile(
        current_user=SimpleNamespace(tenant_id=1),  # type: ignore[arg-type]
        risk_id=42,
        db=db,  # type: ignore[arg-type]
    )
    assert result.inherent_level is None
    assert result.residual_level is None
    assert result.linked_actions == []
