"""Unit tests for notifications list/prefs/clear routes (WCS-A02)."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.api.routes.notifications import (
    NotificationPreferencesUpdate,
    clear_all_notifications,
    get_notification_preferences,
    update_notification_preferences,
)


class _Scalars:
    def __init__(self, items):
        self._items = items

    def all(self):
        return self._items


class _Result:
    def __init__(self, *, scalar=None, scalars=None, rowcount=0):
        self._scalar = scalar
        self._scalars = scalars if scalars is not None else []
        self.rowcount = rowcount

    def scalar(self):
        return self._scalar

    def scalar_one_or_none(self):
        return self._scalar

    def scalars(self):
        return _Scalars(self._scalars)


@pytest.mark.asyncio
async def test_get_preferences_returns_defaults_when_missing():
    db = SimpleNamespace(execute=AsyncMock(return_value=_Result(scalar=None)))
    user = SimpleNamespace(id=7)

    result = await get_notification_preferences(current_user=user, db=db)

    assert result["email_enabled"] is True
    assert result["push_enabled"] is True
    assert result["category_preferences"] == {}


@pytest.mark.asyncio
async def test_update_preferences_persists_category_preferences():
    prefs = SimpleNamespace(
        user_id=7,
        email_enabled=True,
        sms_enabled=False,
        push_enabled=True,
        category_preferences={},
    )
    db = SimpleNamespace(
        execute=AsyncMock(return_value=_Result(scalar=prefs)),
        add=MagicMock(),
        commit=AsyncMock(),
    )
    user = SimpleNamespace(id=7)
    payload = NotificationPreferencesUpdate(
        email_enabled=False,
        category_preferences={
            "high_priority_alerts": {"email": True, "push": True, "in_app": True},
        },
    )

    result = await update_notification_preferences(preferences=payload, current_user=user, db=db)

    assert result["success"] is True
    assert prefs.email_enabled is False
    assert prefs.category_preferences["high_priority_alerts"]["in_app"] is True
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_clear_all_notifications_deletes_for_current_user():
    db = SimpleNamespace(
        execute=AsyncMock(return_value=_Result(rowcount=3)),
        commit=AsyncMock(),
    )
    user = SimpleNamespace(id=42)

    result = await clear_all_notifications(current_user=user, db=db)

    assert result == {"success": True, "count": 3}
    db.commit.assert_awaited_once()
    db.execute.assert_awaited_once()
