"""FR-NOTIF-ADMIN-03: category preferences and quiet hours gate real delivery.

Two layers are covered:

* the pure rules in ``notification_preferences`` (category shapes, quiet-hours
  windows, merge semantics);
* the canonical ``NotificationService`` dispatch path, proving a suppressed
  channel is never handed to a delivery method.
"""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.domain.models.notification import NotificationChannel, NotificationPriority, NotificationType
from src.domain.services.notification_preferences import (
    PreferenceSnapshot,
    categories_for,
    filter_channels,
    in_quiet_window,
    is_quiet_hours,
    merge_category_preferences,
    parse_hhmm,
)
from src.domain.services.notification_service import NotificationService

ALL_CHANNELS = [
    NotificationChannel.IN_APP,
    NotificationChannel.EMAIL,
    NotificationChannel.SMS,
    NotificationChannel.PUSH,
]


class _Result:
    def __init__(self, scalar=None):
        self._scalar = scalar

    def scalar_one_or_none(self):
        return self._scalar


def _prefs_row(**overrides):
    """A NotificationPreference-shaped row with everything switched on."""
    row = SimpleNamespace(
        user_id=7,
        email_enabled=True,
        sms_enabled=True,
        push_enabled=True,
        phone_number="+447700900000",
        quiet_hours_enabled=False,
        quiet_hours_start=None,
        quiet_hours_end=None,
        category_preferences={},
    )
    for key, value in overrides.items():
        setattr(row, key, value)
    return row


def _service_with_prefs(row):
    db = SimpleNamespace(
        execute=AsyncMock(return_value=_Result(scalar=row)),
        add=MagicMock(),
        commit=AsyncMock(),
        refresh=AsyncMock(),
    )
    return NotificationService(db=db)


# ============================================================================
# Category mapping
# ============================================================================


class TestCategoryMapping:
    def test_assignment_types_share_the_assignment_category(self):
        for notification_type in (
            NotificationType.ASSIGNMENT,
            NotificationType.REASSIGNMENT,
            NotificationType.ACTION_ASSIGNED,
        ):
            assert categories_for(notification_type, NotificationPriority.MEDIUM) == ("assignment_notifications",)

    def test_overdue_action_is_a_reminder_not_an_assignment(self):
        assert categories_for(NotificationType.ACTION_OVERDUE, NotificationPriority.MEDIUM) == ("action_reminders",)

    def test_high_priority_adds_the_high_priority_category(self):
        assert categories_for(NotificationType.AUDIT_FINDING, NotificationPriority.HIGH) == (
            "audit_notifications",
            "high_priority_alerts",
        )

    def test_uncategorised_type_has_no_governing_category(self):
        assert categories_for(NotificationType.SYSTEM_ANNOUNCEMENT, NotificationPriority.LOW) == ()


# ============================================================================
# Category enforcement (pure)
# ============================================================================


class TestCategorySuppression:
    def test_no_stored_preferences_suppresses_nothing(self):
        decision = filter_channels(
            ALL_CHANNELS,
            snapshot=PreferenceSnapshot(),
            notification_type=NotificationType.ASSIGNMENT,
            priority=NotificationPriority.MEDIUM,
        )

        assert decision.allowed == ALL_CHANNELS
        assert decision.suppressed == {}

    def test_nested_entry_suppresses_only_the_disabled_channels(self):
        snapshot = PreferenceSnapshot(
            category_preferences={
                "assignment_notifications": {"email": False, "push": True, "in_app": True},
            }
        )

        decision = filter_channels(
            ALL_CHANNELS,
            snapshot=snapshot,
            notification_type=NotificationType.ASSIGNMENT,
            priority=NotificationPriority.MEDIUM,
        )

        assert NotificationChannel.EMAIL not in decision.allowed
        assert NotificationChannel.PUSH in decision.allowed
        assert NotificationChannel.IN_APP in decision.allowed
        # No SMS toggle exists in the UI, so the entry expresses no SMS opinion.
        assert NotificationChannel.SMS in decision.allowed
        assert decision.suppressed == {"email": "category:assignment_notifications"}

    def test_camel_case_in_app_key_is_honoured(self):
        snapshot = PreferenceSnapshot(category_preferences={"mentions": {"inApp": False}})

        decision = filter_channels(
            [NotificationChannel.IN_APP],
            snapshot=snapshot,
            notification_type=NotificationType.MENTION,
            priority=NotificationPriority.MEDIUM,
        )

        assert decision.allowed == []
        assert decision.suppressed == {"in_app": "category:mentions"}

    def test_flat_false_flag_suppresses_push_only(self):
        """The push API's bare booleans govern push; they claim nothing else."""
        snapshot = PreferenceSnapshot(category_preferences={"incident_alerts": False})

        decision = filter_channels(
            ALL_CHANNELS,
            snapshot=snapshot,
            notification_type=NotificationType.INCIDENT_UPDATE,
            priority=NotificationPriority.MEDIUM,
        )

        assert decision.allowed == [
            NotificationChannel.IN_APP,
            NotificationChannel.EMAIL,
            NotificationChannel.SMS,
        ]
        assert decision.suppressed == {"push": "category:incident_alerts"}

    def test_flat_true_flag_suppresses_nothing(self):
        snapshot = PreferenceSnapshot(category_preferences={"incident_alerts": True})

        decision = filter_channels(
            ALL_CHANNELS,
            snapshot=snapshot,
            notification_type=NotificationType.INCIDENT_UPDATE,
            priority=NotificationPriority.MEDIUM,
        )

        assert decision.suppressed == {}

    def test_high_priority_category_can_suppress_a_typed_notification(self):
        snapshot = PreferenceSnapshot(
            category_preferences={"high_priority_alerts": {"email": False, "push": False, "in_app": True}}
        )

        decision = filter_channels(
            ALL_CHANNELS,
            snapshot=snapshot,
            notification_type=NotificationType.AUDIT_FINDING,
            priority=NotificationPriority.HIGH,
        )

        assert decision.allowed == [NotificationChannel.IN_APP, NotificationChannel.SMS]
        assert decision.suppressed == {
            "email": "category:high_priority_alerts",
            "push": "category:high_priority_alerts",
        }

    def test_critical_priority_bypasses_category_preferences(self):
        """A preference toggle must never mute a life-safety alert."""
        snapshot = PreferenceSnapshot(
            category_preferences={"incident_alerts": {"email": False, "push": False, "in_app": False}}
        )

        decision = filter_channels(
            ALL_CHANNELS,
            snapshot=snapshot,
            notification_type=NotificationType.SOS_ALERT,
            priority=NotificationPriority.CRITICAL,
        )

        assert decision.allowed == ALL_CHANNELS
        assert decision.suppressed == {}

    def test_unrelated_category_does_not_gate(self):
        snapshot = PreferenceSnapshot(
            category_preferences={"audit_notifications": {"email": False, "push": False, "in_app": False}}
        )

        decision = filter_channels(
            ALL_CHANNELS,
            snapshot=snapshot,
            notification_type=NotificationType.ASSIGNMENT,
            priority=NotificationPriority.MEDIUM,
        )

        assert decision.suppressed == {}

    def test_malformed_entry_is_treated_as_no_opinion(self):
        snapshot = PreferenceSnapshot(
            category_preferences={
                "assignment_notifications": "yes please",
                "action_reminders": {"email": "true"},
            }
        )

        assert (
            filter_channels(
                ALL_CHANNELS,
                snapshot=snapshot,
                notification_type=NotificationType.ASSIGNMENT,
                priority=NotificationPriority.MEDIUM,
            ).suppressed
            == {}
        )
        assert (
            filter_channels(
                ALL_CHANNELS,
                snapshot=snapshot,
                notification_type=NotificationType.ACTION_OVERDUE,
                priority=NotificationPriority.MEDIUM,
            ).suppressed
            == {}
        )


# ============================================================================
# Quiet hours (pure)
# ============================================================================


class TestQuietHoursWindow:
    @pytest.mark.parametrize(
        "value,expected_hour",
        [("22:00", 22), ("07:30", 7), ("00:00", 0), (" 23:59 ", 23)],
    )
    def test_parses_valid_bounds(self, value, expected_hour):
        parsed = parse_hhmm(value)
        assert parsed is not None
        assert parsed.hour == expected_hour

    @pytest.mark.parametrize("value", ["", "2200", "24:00", "22:60", "-1:00", "22:00:00", None, 2200, "ab:cd"])
    def test_rejects_unusable_bounds(self, value):
        assert parse_hhmm(value) is None

    def test_window_across_midnight_covers_both_sides(self):
        start, end = parse_hhmm("22:00"), parse_hhmm("07:00")

        assert in_quiet_window(parse_hhmm("23:30"), start, end) is True
        assert in_quiet_window(parse_hhmm("02:00"), start, end) is True
        assert in_quiet_window(parse_hhmm("22:00"), start, end) is True
        assert in_quiet_window(parse_hhmm("07:00"), start, end) is False
        assert in_quiet_window(parse_hhmm("12:00"), start, end) is False

    def test_same_day_window(self):
        start, end = parse_hhmm("09:00"), parse_hhmm("17:00")

        assert in_quiet_window(parse_hhmm("12:00"), start, end) is True
        assert in_quiet_window(parse_hhmm("08:59"), start, end) is False
        assert in_quiet_window(parse_hhmm("17:00"), start, end) is False

    def test_equal_bounds_are_not_an_all_day_window(self):
        """A mis-saved 22:00/22:00 must not mute a user around the clock."""
        start = parse_hhmm("22:00")

        assert in_quiet_window(parse_hhmm("22:00"), start, start) is False
        assert in_quiet_window(parse_hhmm("03:00"), start, start) is False


class TestQuietHoursEvaluation:
    def _snapshot(self, **overrides):
        base = dict(quiet_hours_enabled=True, quiet_hours_start="22:00", quiet_hours_end="07:00")
        base.update(overrides)
        return PreferenceSnapshot(**base)

    def test_disabled_quiet_hours_never_gate(self):
        snapshot = self._snapshot(quiet_hours_enabled=False)
        night = datetime(2026, 1, 15, 23, 30, tzinfo=timezone.utc)

        assert is_quiet_hours(snapshot, now=night, tz_name="Europe/London") is False

    def test_inside_window_is_quiet(self):
        night = datetime(2026, 1, 15, 23, 30, tzinfo=timezone.utc)

        assert is_quiet_hours(self._snapshot(), now=night, tz_name="Europe/London") is True

    def test_outside_window_is_not_quiet(self):
        midday = datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc)

        assert is_quiet_hours(self._snapshot(), now=midday, tz_name="Europe/London") is False

    def test_bounds_are_interpreted_in_the_configured_timezone(self):
        """23:30 UTC in July is 00:30 in London — inside a 22:00-07:00 window."""
        summer_night = datetime(2026, 7, 15, 23, 30, tzinfo=timezone.utc)

        assert is_quiet_hours(self._snapshot(), now=summer_night, tz_name="Europe/London") is True

        # 21:30 UTC in July is 22:30 London: quiet there, but not in UTC.
        summer_evening = datetime(2026, 7, 15, 21, 30, tzinfo=timezone.utc)
        assert is_quiet_hours(self._snapshot(), now=summer_evening, tz_name="Europe/London") is True
        assert is_quiet_hours(self._snapshot(), now=summer_evening, tz_name="UTC") is False

    def test_unknown_timezone_falls_back_to_utc(self):
        night = datetime(2026, 1, 15, 23, 30, tzinfo=timezone.utc)

        assert is_quiet_hours(self._snapshot(), now=night, tz_name="Mars/Olympus_Mons") is True

    @pytest.mark.parametrize(
        "start,end",
        [(None, "07:00"), ("22:00", None), ("nonsense", "07:00"), ("22:00", "")],
    )
    def test_unusable_bounds_do_not_gate(self, start, end):
        snapshot = self._snapshot(quiet_hours_start=start, quiet_hours_end=end)
        night = datetime(2026, 1, 15, 23, 30, tzinfo=timezone.utc)

        assert is_quiet_hours(snapshot, now=night, tz_name="Europe/London") is False


class TestQuietHoursChannelGating:
    def _snapshot(self):
        return PreferenceSnapshot(
            quiet_hours_enabled=True,
            quiet_hours_start="22:00",
            quiet_hours_end="07:00",
        )

    def test_quiet_hours_hold_back_push_and_sms_only(self):
        night = datetime(2026, 1, 15, 23, 30, tzinfo=timezone.utc)

        decision = filter_channels(
            ALL_CHANNELS,
            snapshot=self._snapshot(),
            notification_type=NotificationType.ASSIGNMENT,
            priority=NotificationPriority.MEDIUM,
            now=night,
            tz_name="Europe/London",
        )

        assert decision.allowed == [NotificationChannel.IN_APP, NotificationChannel.EMAIL]
        assert decision.suppressed == {"sms": "quiet_hours", "push": "quiet_hours"}

    def test_critical_alerts_ignore_quiet_hours(self):
        night = datetime(2026, 1, 15, 23, 30, tzinfo=timezone.utc)

        decision = filter_channels(
            ALL_CHANNELS,
            snapshot=self._snapshot(),
            notification_type=NotificationType.RIDDOR_INCIDENT,
            priority=NotificationPriority.CRITICAL,
            now=night,
            tz_name="Europe/London",
        )

        assert decision.allowed == ALL_CHANNELS
        assert decision.suppressed == {}

    def test_category_reason_wins_over_quiet_hours_reason(self):
        snapshot = PreferenceSnapshot(
            category_preferences={"assignment_notifications": {"push": False}},
            quiet_hours_enabled=True,
            quiet_hours_start="22:00",
            quiet_hours_end="07:00",
        )
        night = datetime(2026, 1, 15, 23, 30, tzinfo=timezone.utc)

        decision = filter_channels(
            [NotificationChannel.PUSH],
            snapshot=snapshot,
            notification_type=NotificationType.ASSIGNMENT,
            priority=NotificationPriority.MEDIUM,
            now=night,
            tz_name="Europe/London",
        )

        assert decision.suppressed == {"push": "category:assignment_notifications"}


# ============================================================================
# Dispatcher enforcement
# ============================================================================


class TestDispatcherRespectsPreferences:
    @pytest.mark.asyncio
    async def test_category_opt_out_stops_email_delivery(self):
        row = _prefs_row(
            category_preferences={"assignment_notifications": {"email": False, "push": True, "in_app": True}}
        )
        service = _service_with_prefs(row)

        with (
            patch.object(service, "_deliver_in_app", new_callable=AsyncMock) as in_app,
            patch.object(service, "_deliver_email", new_callable=AsyncMock) as email,
            patch.object(service, "_deliver_push", new_callable=AsyncMock) as push,
        ):
            notification = await service.create_notification(
                user_id=7,
                notification_type=NotificationType.ASSIGNMENT,
                title="Action assigned",
                message="CAPA-42 is yours",
                priority=NotificationPriority.MEDIUM,
            )

        email.assert_not_awaited()
        in_app.assert_awaited_once()
        push.assert_awaited_once()
        assert notification.extra_data["suppressed_channels"] == {"email": "category:assignment_notifications"}
        assert "email" not in (notification.delivered_channels or [])

    @pytest.mark.asyncio
    async def test_explicitly_requested_channels_are_still_gated(self):
        """Callers pass channels to say what suits the message, not to bypass consent."""
        row = _prefs_row(category_preferences={"audit_notifications": {"email": False, "in_app": True}})
        service = _service_with_prefs(row)

        with (
            patch.object(service, "_deliver_in_app", new_callable=AsyncMock) as in_app,
            patch.object(service, "_deliver_email", new_callable=AsyncMock) as email,
        ):
            await service.create_notification(
                user_id=7,
                notification_type=NotificationType.AUDIT_COMPLETED,
                title="Audit complete",
                message="Audit 9 closed",
                priority=NotificationPriority.MEDIUM,
                channels=[NotificationChannel.IN_APP, NotificationChannel.EMAIL],
            )

        email.assert_not_awaited()
        in_app.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_quiet_hours_stop_push_and_sms_but_keep_the_in_app_record(self):
        row = _prefs_row(quiet_hours_enabled=True, quiet_hours_start="22:00", quiet_hours_end="07:00")
        service = _service_with_prefs(row)
        night = datetime(2026, 1, 15, 23, 30, tzinfo=timezone.utc)

        with (
            patch("src.domain.services.notification_preferences._now_utc", return_value=night),
            patch.object(service, "_deliver_in_app", new_callable=AsyncMock) as in_app,
            patch.object(service, "_deliver_email", new_callable=AsyncMock) as email,
            patch.object(service, "_deliver_sms", new_callable=AsyncMock) as sms,
            patch.object(service, "_deliver_push", new_callable=AsyncMock) as push,
        ):
            notification = await service.create_notification(
                user_id=7,
                notification_type=NotificationType.ACTION_OVERDUE,
                title="Action overdue",
                message="CAPA-42 is overdue",
                priority=NotificationPriority.HIGH,
            )

        push.assert_not_awaited()
        sms.assert_not_awaited()
        in_app.assert_awaited_once()
        email.assert_awaited_once()
        assert notification.extra_data["suppressed_channels"] == {
            "sms": "quiet_hours",
            "push": "quiet_hours",
        }

    @pytest.mark.asyncio
    async def test_critical_alert_delivers_during_quiet_hours(self):
        row = _prefs_row(
            quiet_hours_enabled=True,
            quiet_hours_start="22:00",
            quiet_hours_end="07:00",
            category_preferences={"incident_alerts": False},
        )
        service = _service_with_prefs(row)
        night = datetime(2026, 1, 15, 23, 30, tzinfo=timezone.utc)

        with (
            patch("src.domain.services.notification_preferences._now_utc", return_value=night),
            patch.object(service, "_deliver_in_app", new_callable=AsyncMock),
            patch.object(service, "_deliver_email", new_callable=AsyncMock),
            patch.object(service, "_deliver_sms", new_callable=AsyncMock) as sms,
            patch.object(service, "_deliver_push", new_callable=AsyncMock) as push,
        ):
            notification = await service.create_notification(
                user_id=7,
                notification_type=NotificationType.SOS_ALERT,
                title="SOS",
                message="Lone worker alert",
                priority=NotificationPriority.CRITICAL,
            )

        push.assert_awaited_once()
        sms.assert_awaited_once()
        assert "suppressed_channels" not in notification.extra_data

    @pytest.mark.asyncio
    async def test_user_without_stored_preferences_keeps_previous_behaviour(self):
        """Regression guard: enforcement must not silently mute untouched users."""
        service = _service_with_prefs(None)

        with (
            patch.object(service, "_deliver_in_app", new_callable=AsyncMock) as in_app,
            patch.object(service, "_deliver_email", new_callable=AsyncMock) as email,
        ):
            notification = await service.create_notification(
                user_id=7,
                notification_type=NotificationType.ASSIGNMENT,
                title="Action assigned",
                message="CAPA-42 is yours",
                priority=NotificationPriority.MEDIUM,
                channels=[NotificationChannel.IN_APP, NotificationChannel.EMAIL],
            )

        in_app.assert_awaited_once()
        email.assert_awaited_once()
        assert "suppressed_channels" not in notification.extra_data


# ============================================================================
# Merge semantics (pure)
# ============================================================================


class TestMergeCategoryPreferences:
    def test_incoming_keys_do_not_drop_stored_keys(self):
        merged = merge_category_preferences(
            {"incident_alerts": False, "mentions": True},
            {"audit_notifications": {"email": True, "push": False, "in_app": True}},
        )

        assert merged["incident_alerts"] is False
        assert merged["mentions"] is True
        assert merged["audit_notifications"]["push"] is False

    def test_shared_key_is_replaced(self):
        merged = merge_category_preferences(
            {"action_reminders": {"email": True, "push": True, "in_app": True}},
            {"action_reminders": {"email": False, "push": False, "in_app": True}},
        )

        assert merged["action_reminders"] == {"email": False, "push": False, "in_app": True}

    def test_partial_channel_map_does_not_drop_untouched_channels(self):
        merged = merge_category_preferences(
            {"action_reminders": {"email": True, "push": True, "in_app": True}},
            {"action_reminders": {"push": False}},
        )

        assert merged["action_reminders"] == {"email": True, "push": False, "in_app": True}

    def test_shape_change_on_one_key_takes_the_explicit_write(self):
        merged = merge_category_preferences(
            {"mentions": {"email": True, "push": True, "in_app": True}},
            {"mentions": False},
        )

        assert merged["mentions"] is False

    @pytest.mark.parametrize("incoming", [None, "wipe", 0, []])
    def test_non_mapping_update_changes_nothing(self, incoming):
        existing = {"mentions": True}

        assert merge_category_preferences(existing, incoming) == existing

    def test_missing_storage_starts_from_the_update(self):
        assert merge_category_preferences(None, {"mentions": False}) == {"mentions": False}

    def test_result_does_not_alias_stored_dicts(self):
        """Returning a fresh dict is what makes SQLAlchemy notice the change."""
        existing = {"action_reminders": {"email": True}}

        merged = merge_category_preferences(existing, {"action_reminders": {"push": False}})
        merged["action_reminders"]["email"] = False

        assert existing["action_reminders"]["email"] is True
