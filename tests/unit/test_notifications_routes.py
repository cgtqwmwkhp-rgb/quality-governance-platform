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
async def test_update_preferences_merges_instead_of_clobbering_push_keys():
    """FR-NOTIF-ADMIN-03: this surface cannot wipe keys only the push API writes.

    Both routes write the one ``category_preferences`` JSON column, and the push
    API's flat event flags are invisible to this route's payload — a wholesale
    replace silently deleted them.
    """
    prefs = SimpleNamespace(
        user_id=7,
        email_enabled=True,
        sms_enabled=False,
        push_enabled=True,
        category_preferences={"incident_alerts": False, "mentions": True},
    )
    db = SimpleNamespace(
        execute=AsyncMock(return_value=_Result(scalar=prefs)),
        add=MagicMock(),
        commit=AsyncMock(),
    )
    payload = NotificationPreferencesUpdate(
        category_preferences={
            "high_priority_alerts": {"email": True, "push": True, "in_app": True},
            "document_updates": {"email": False, "push": False, "in_app": True},
        },
    )

    result = await update_notification_preferences(preferences=payload, current_user=SimpleNamespace(id=7), db=db)

    assert prefs.category_preferences["incident_alerts"] is False
    assert prefs.category_preferences["mentions"] is True
    assert prefs.category_preferences["high_priority_alerts"]["push"] is True
    assert prefs.category_preferences["document_updates"]["email"] is False
    # The response reports the merged state, not just what the caller sent.
    assert result["preferences"]["category_preferences"]["mentions"] is True


@pytest.mark.asyncio
async def test_update_preferences_partial_category_payload_keeps_other_channels():
    prefs = SimpleNamespace(
        user_id=7,
        category_preferences={"action_reminders": {"email": True, "push": True, "in_app": True}},
    )
    db = SimpleNamespace(
        execute=AsyncMock(return_value=_Result(scalar=prefs)),
        add=MagicMock(),
        commit=AsyncMock(),
    )
    payload = NotificationPreferencesUpdate(category_preferences={"action_reminders": {"push": False}})

    await update_notification_preferences(preferences=payload, current_user=SimpleNamespace(id=7), db=db)

    assert prefs.category_preferences["action_reminders"] == {
        "email": True,
        "push": False,
        "in_app": True,
    }


@pytest.mark.asyncio
async def test_update_preferences_without_category_payload_leaves_categories_intact():
    stored = {"incident_alerts": False}
    prefs = SimpleNamespace(user_id=7, email_enabled=True, category_preferences=stored)
    db = SimpleNamespace(
        execute=AsyncMock(return_value=_Result(scalar=prefs)),
        add=MagicMock(),
        commit=AsyncMock(),
    )

    await update_notification_preferences(
        preferences=NotificationPreferencesUpdate(email_enabled=False),
        current_user=SimpleNamespace(id=7),
        db=db,
    )

    assert prefs.email_enabled is False
    assert prefs.category_preferences == stored


@pytest.mark.asyncio
async def test_push_preferences_update_keeps_category_channel_maps():
    """The reverse direction: the push API must not drop the UI's nested maps."""
    from src.api.routes.push_notifications import NotificationPreferenceUpdate
    from src.api.routes.push_notifications import update_notification_preferences as update_push_preferences

    prefs = SimpleNamespace(
        user_id=7,
        push_enabled=True,
        email_enabled=True,
        sms_enabled=False,
        email_digest_frequency="daily",
        quiet_hours_start=None,
        quiet_hours_end=None,
        category_preferences={"audit_notifications": {"email": True, "push": False, "in_app": True}},
    )
    db = SimpleNamespace(
        execute=AsyncMock(return_value=_Result(scalar=prefs)),
        add=MagicMock(),
        commit=AsyncMock(),
    )

    await update_push_preferences(
        updates=NotificationPreferenceUpdate(mentions=False, push_enabled=False),
        current_user=SimpleNamespace(id=7),
        db=db,
    )

    assert prefs.push_enabled is False
    assert prefs.category_preferences["mentions"] is False
    assert prefs.category_preferences["audit_notifications"] == {
        "email": True,
        "push": False,
        "in_app": True,
    }


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
