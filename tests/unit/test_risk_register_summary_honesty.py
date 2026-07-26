"""Unit tests for risk-register summary never-reviewed honesty (PX-157)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.api.routes.risk_register import get_risk_summary


class _FakeResult:
    def __init__(self, scalar=None, rows=None):
        self._scalar = scalar
        self._rows = rows or []

    def scalar_one(self):
        return self._scalar

    def all(self):
        return self._rows


@pytest.mark.asyncio
async def test_get_risk_summary_includes_never_reviewed_count():
    """Summary returns never_reviewed so UI can refuse Outside Appetite reassurance."""
    db = AsyncMock()
    # Order of executes in get_risk_summary:
    # total, critical, high, medium, low, outside_appetite, overdue, never_reviewed, escalated, categories
    db.execute = AsyncMock(
        side_effect=[
            _FakeResult(scalar=129),
            _FakeResult(scalar=0),
            _FakeResult(scalar=1),
            _FakeResult(scalar=1),
            _FakeResult(scalar=1),
            _FakeResult(scalar=0),
            _FakeResult(scalar=125),
            _FakeResult(scalar=126),
            _FakeResult(scalar=0),
            _FakeResult(rows=[("compliance", 50)]),
        ]
    )
    user = SimpleNamespace(tenant_id=1)

    result = await get_risk_summary(current_user=user, db=db)

    assert result["total_risks"] == 129
    assert result["never_reviewed"] == 126
    assert result["outside_appetite"] == 0
    assert result["overdue_review"] == 125
    assert result["by_level"]["high"] == 1
