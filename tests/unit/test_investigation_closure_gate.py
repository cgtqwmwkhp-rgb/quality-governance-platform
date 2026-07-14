"""Unit tests for investigation closure gate (D-W1-10)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.domain.exceptions import StateTransitionError
from src.domain.models.investigation import InvestigationActionStatus
from src.domain.services.investigation_closure_helpers import (
    CLOSURE_REASON_OPEN_ACTIONS_REMAIN,
    assert_investigation_can_close,
    fetch_open_work_for_investigation,
    open_work_to_payload,
)


def _fake_action(**overrides):
    defaults = {
        "id": 12,
        "reference_number": "INV-ACT-2026-0012",
        "title": "Replace guard",
        "status": InvestigationActionStatus.OPEN,
        "investigation_id": 7,
        "tenant_id": 1,
    }
    defaults.update(overrides)
    obj = MagicMock()
    for key, value in defaults.items():
        setattr(obj, key, value)
    return obj


class TestFetchOpenWorkForInvestigation:
    @pytest.mark.asyncio
    async def test_returns_open_investigation_actions(self):
        db = AsyncMock()
        open_action = _fake_action()
        result = MagicMock()
        result.scalars.return_value.all.return_value = [open_action]
        db.execute.return_value = result

        items = await fetch_open_work_for_investigation(db, investigation_id=7, tenant_id=1)

        assert len(items) == 1
        assert items[0].reference_number == "INV-ACT-2026-0012"
        assert items[0].action_key == "investigation_action:12"
        assert items[0].status == "open"

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_open_actions(self):
        db = AsyncMock()
        result = MagicMock()
        result.scalars.return_value.all.return_value = []
        db.execute.return_value = result

        items = await fetch_open_work_for_investigation(db, investigation_id=7, tenant_id=1)

        assert items == []


class TestAssertInvestigationCanClose:
    @pytest.mark.asyncio
    async def test_passes_when_no_open_work(self):
        db = AsyncMock()
        result = MagicMock()
        result.scalars.return_value.all.return_value = []
        db.execute.return_value = result

        open_work = await assert_investigation_can_close(db, investigation_id=7, tenant_id=1)

        assert open_work == []

    @pytest.mark.asyncio
    async def test_raises_when_open_work_remains(self):
        db = AsyncMock()
        result = MagicMock()
        result.scalars.return_value.all.return_value = [_fake_action()]
        db.execute.return_value = result

        with pytest.raises(StateTransitionError) as exc_info:
            await assert_investigation_can_close(db, investigation_id=7, tenant_id=1)

        err = exc_info.value
        assert err.code == CLOSURE_REASON_OPEN_ACTIONS_REMAIN
        assert err.details["open_work_count"] == 1
        assert err.details["open_work"][0]["reference_number"] == "INV-ACT-2026-0012"


class TestOpenWorkPayload:
    def test_serializes_unblock_hint(self):
        from src.domain.services.investigation_closure_helpers import OpenWorkItem

        payload = open_work_to_payload(
            [
                OpenWorkItem(
                    kind="investigation_action",
                    id=3,
                    reference_number="INV-ACT-3",
                    title="Train staff",
                    status="in_progress",
                    action_key="investigation_action:3",
                )
            ]
        )

        assert payload[0]["unblock_hint"].startswith("Complete or cancel")


class TestClosureReasonCodeStability:
    def test_open_actions_remain_reason_is_stable(self):
        from src.api.routes.investigations import ClosureReasonCode

        assert ClosureReasonCode.OPEN_ACTIONS_REMAIN == "OPEN_ACTIONS_REMAIN"
