"""B-11: create_requirement must persist re-ack and active fields, not silently drop them.

The create route used to enumerate kwargs by hand and omit
``re_acknowledge_period_months``, ``re_acknowledge_on_update`` and ``is_active``.
Defaults made the last two invisible to the echo probe; the period was caught
and allowlisted. Persisting all three closes the silent-drop class.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.domain.services.policy_acknowledgment import PolicyAcknowledgmentService


@pytest.mark.asyncio
async def test_create_requirement_persists_reack_and_active_fields():
    captured: dict = {}

    def add(obj):
        captured["requirement"] = obj

    db = SimpleNamespace(add=add, commit=AsyncMock(), refresh=AsyncMock())
    svc = PolicyAcknowledgmentService(db)

    await svc.create_requirement(
        policy_id=41,
        re_acknowledge_period_months=6,
        re_acknowledge_on_update=False,
        is_active=False,
    )

    requirement = captured["requirement"]
    assert requirement.policy_id == 41
    assert requirement.re_acknowledge_period_months == 6
    assert requirement.re_acknowledge_on_update is False
    assert requirement.is_active is False
