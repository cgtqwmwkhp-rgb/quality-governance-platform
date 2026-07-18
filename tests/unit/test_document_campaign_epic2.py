"""Unit tests for document campaign EPIC-2 (reminders, compliance, inbox)."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.domain.models.document_campaign import DEFAULT_REMINDER_OFFSETS_HOURS
from src.domain.services.document_campaign_service import (
    DocumentCampaignService,
    _reminder_defaults_setting_key,
)


def _scalar_one_result(item):
    result = MagicMock()
    result.scalar_one_or_none.return_value = item
    return result


class TestReminderDefaults:
    @pytest.mark.asyncio
    async def test_get_reminder_defaults_returns_system_setting(self):
        setting = SimpleNamespace(value="[48, 168]")
        db = SimpleNamespace(execute=AsyncMock(return_value=_scalar_one_result(setting)))
        service = DocumentCampaignService(db)

        hours = await service.get_reminder_defaults(tenant_id=1)

        assert hours == [48, 168]

    @pytest.mark.asyncio
    async def test_get_reminder_defaults_falls_back_when_missing(self):
        db = SimpleNamespace(execute=AsyncMock(return_value=_scalar_one_result(None)))
        service = DocumentCampaignService(db)

        hours = await service.get_reminder_defaults(tenant_id=1)

        assert hours == list(DEFAULT_REMINDER_OFFSETS_HOURS)

    @pytest.mark.asyncio
    async def test_set_reminder_defaults_creates_setting(self):
        db = SimpleNamespace(
            execute=AsyncMock(return_value=_scalar_one_result(None)),
            add=MagicMock(),
            commit=AsyncMock(),
        )
        service = DocumentCampaignService(db)

        hours = await service.set_reminder_defaults(tenant_id=1, hours=[720, 24, 168], user_id=5)

        assert hours == [24, 168, 720]
        added = db.add.call_args[0][0]
        assert added.key == _reminder_defaults_setting_key(1)
        assert added.value_type == "json"
        db.commit.assert_awaited_once()


def test_process_campaign_reminders_import():
    from src.infrastructure.tasks.document_campaign_tasks import process_campaign_reminders

    assert process_campaign_reminders.name.endswith("process_campaign_reminders")
