"""Pure notification builders for Compliance Schedule (hermetic, no DB, no clock)."""

from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.domain.models.notification import NotificationPriority, NotificationType
from src.domain.services import compliance_schedule_notifications as builders
from src.domain.services.compliance_schedule_notifications import (
    ENTITY_TYPE,
    admin_bands_for,
    build_notification_kwargs,
    dedupe_key,
    notification_exists_for_key,
    priority_for_band,
    recipient_user_ids,
)
from src.domain.services.compliance_schedule_policy import classify_due_band

ALL_BANDS = ("overdue", "due_7", "due_30", "due_60")
EVALUATED_AT = datetime(2026, 8, 4, 8, 15, tzinfo=timezone.utc)


# --- dedupe key ------------------------------------------------------------------


def test_dedupe_key_distinguishes_occurrences_of_the_same_requirement():
    """The bug an occurrence-blind key would cause: a recurring reminder sent once, ever."""
    this_year = dedupe_key(11, date(2026, 8, 1), "overdue")
    next_year = dedupe_key(11, date(2027, 8, 1), "overdue")

    assert this_year != next_year


def test_dedupe_key_is_stable_for_the_same_reminder():
    assert dedupe_key(11, date(2026, 8, 1), "due_7") == dedupe_key(11, date(2026, 8, 1), "due_7")


def test_dedupe_key_distinguishes_bands_and_requirements():
    same_occurrence = {dedupe_key(11, date(2026, 8, 1), band) for band in ALL_BANDS}
    assert len(same_occurrence) == len(ALL_BANDS)

    assert dedupe_key(11, date(2026, 8, 1), "due_7") != dedupe_key(12, date(2026, 8, 1), "due_7")


def test_dedupe_key_is_prefixed_with_the_indexed_entity_type():
    """The partial unique index is predicated on entity_type; the key should agree."""
    assert dedupe_key(11, date(2026, 8, 1), "due_7").startswith(f"{ENTITY_TYPE}:")


# --- bands, priority, routing ----------------------------------------------------


@pytest.mark.parametrize("band", ALL_BANDS)
def test_every_band_the_policy_can_return_has_a_priority_and_a_title(band):
    """Drift guard: a new band in the policy must not KeyError here at runtime."""
    assert priority_for_band(band) in tuple(NotificationPriority)
    assert builders.title_for_band(band, title="Fire risk assessment")


def test_no_band_is_ever_critical():
    """CRITICAL is reserved for SOS and RIDDOR; a due date is not one of those."""
    assert all(priority_for_band(band) is not NotificationPriority.CRITICAL for band in ALL_BANDS)


def test_overdue_and_due_7_outrank_the_longer_windows():
    assert priority_for_band("overdue") is NotificationPriority.HIGH
    assert priority_for_band("due_7") is NotificationPriority.HIGH
    assert priority_for_band("due_30") is NotificationPriority.MEDIUM
    assert priority_for_band("due_60") is NotificationPriority.LOW


def test_statutory_requirements_escalate_to_admins_a_week_out():
    assert admin_bands_for(statutory=False) == ("overdue",)
    assert admin_bands_for(statutory=True) == ("overdue", "due_7")


# --- recipients ------------------------------------------------------------------


def test_owner_gets_every_band_and_admins_are_not_copied_routinely():
    for band in ("due_7", "due_30", "due_60"):
        assert recipient_user_ids(
            owner_user_id=7,
            admin_user_ids=[1, 2],
            band=band,
            statutory=False,
        ) == [7]


def test_admins_are_copied_when_a_requirement_goes_overdue():
    assert recipient_user_ids(
        owner_user_id=7,
        admin_user_ids=[1, 2],
        band="overdue",
        statutory=False,
    ) == [7, 1, 2]


def test_statutory_due_7_copies_admins_but_routine_due_7_does_not():
    statutory = recipient_user_ids(owner_user_id=7, admin_user_ids=[1], band="due_7", statutory=True)
    routine = recipient_user_ids(owner_user_id=7, admin_user_ids=[1], band="due_7", statutory=False)

    assert statutory == [7, 1]
    assert routine == [7]


def test_an_unowned_requirement_falls_back_to_admins_for_every_band():
    """Silence is the one unacceptable outcome for an obligation nobody owns."""
    for band in ALL_BANDS:
        assert recipient_user_ids(
            owner_user_id=None,
            admin_user_ids=[1, 2],
            band=band,
            statutory=False,
        ) == [1, 2]


def test_an_owner_who_is_also_an_admin_is_notified_once():
    assert recipient_user_ids(
        owner_user_id=1,
        admin_user_ids=[1, 2],
        band="overdue",
        statutory=False,
    ) == [1, 2]


def test_no_owner_and_no_admins_yields_nobody_rather_than_raising():
    assert recipient_user_ids(owner_user_id=None, admin_user_ids=[], band="overdue", statutory=True) == []


# --- dedupe fast path ------------------------------------------------------------


def _row(*, user_id: int, key: str, entity_type: str = ENTITY_TYPE):
    return SimpleNamespace(user_id=user_id, entity_type=entity_type, extra_data={"dedupe_key": key})


def test_existing_reminder_is_recognised():
    rows = [_row(user_id=7, key=dedupe_key(11, date(2026, 8, 1), "due_7"))]

    assert notification_exists_for_key(rows, user_id=7, requirement_id=11, due_date=date(2026, 8, 1), band="due_7")


def test_a_different_user_band_or_occurrence_is_not_a_match():
    key = dedupe_key(11, date(2026, 8, 1), "due_7")
    rows = [_row(user_id=7, key=key)]

    assert not notification_exists_for_key(rows, user_id=8, requirement_id=11, due_date=date(2026, 8, 1), band="due_7")
    assert not notification_exists_for_key(
        rows, user_id=7, requirement_id=11, due_date=date(2026, 8, 1), band="overdue"
    )
    assert not notification_exists_for_key(rows, user_id=7, requirement_id=11, due_date=date(2027, 8, 1), band="due_7")


def test_another_modules_row_is_never_a_match():
    """Rows outside this entity_type are outside the index's predicate too."""
    rows = [_row(user_id=7, key="safety_asset:11:overdue", entity_type="safety_asset")]

    assert not notification_exists_for_key(
        rows, user_id=7, requirement_id=11, due_date=date(2026, 8, 1), band="overdue"
    )


def test_a_row_with_no_extra_data_does_not_crash_the_check():
    rows = [SimpleNamespace(user_id=7, entity_type=ENTITY_TYPE, extra_data=None)]

    assert not notification_exists_for_key(
        rows, user_id=7, requirement_id=11, due_date=date(2026, 8, 1), band="overdue"
    )


# --- the row itself --------------------------------------------------------------


def test_built_kwargs_carry_everything_the_row_and_the_index_need():
    kwargs = build_notification_kwargs(
        user_id=7,
        tenant_id=3,
        requirement_id=11,
        reference_number="CSR-0011",
        title="Fire risk assessment",
        band="overdue",
        due_date=date(2026, 8, 1),
        statutory=True,
        evaluated_at=EVALUATED_AT,
    )

    assert kwargs["user_id"] == 7
    assert kwargs["tenant_id"] == 3
    assert kwargs["type"] is NotificationType.COMPLIANCE_ALERT
    assert kwargs["priority"] is NotificationPriority.HIGH
    assert kwargs["entity_type"] == ENTITY_TYPE
    assert kwargs["entity_id"] == "11"
    assert kwargs["action_url"] == "/compliance-schedule/11"
    assert kwargs["delivered_channels"] == ["in_app"]

    extra = kwargs["extra_data"]
    assert extra["dedupe_key"] == dedupe_key(11, date(2026, 8, 1), "overdue")
    assert extra["band"] == "overdue"
    assert extra["due_date"] == "2026-08-01"
    assert extra["statutory"] is True
    assert extra["evaluated_at"] == EVALUATED_AT.isoformat()


def test_the_message_states_the_reference_the_date_and_a_next_step():
    kwargs = build_notification_kwargs(
        user_id=7,
        tenant_id=3,
        requirement_id=11,
        reference_number="CSR-0011",
        title="Fire risk assessment",
        band="overdue",
        due_date=date(2026, 8, 1),
        statutory=True,
        evaluated_at=EVALUATED_AT,
    )

    message = kwargs["message"]
    assert "CSR-0011" in message
    assert "2026-08-01" in message
    assert "statutory" in message.lower()
    assert "Fire risk assessment" in message


def test_a_routine_requirement_does_not_claim_to_be_statutory():
    kwargs = build_notification_kwargs(
        user_id=7,
        tenant_id=3,
        requirement_id=11,
        reference_number="CSR-0011",
        title="Gutter clearance",
        band="due_30",
        due_date=date(2026, 9, 1),
        statutory=False,
        evaluated_at=EVALUATED_AT,
    )

    assert "statutory" not in kwargs["message"].lower()


@pytest.mark.parametrize("band", ALL_BANDS)
def test_every_band_builds_a_complete_row(band):
    kwargs = build_notification_kwargs(
        user_id=7,
        tenant_id=3,
        requirement_id=11,
        reference_number="CSR-0011",
        title="Fire risk assessment",
        band=band,
        due_date=date(2026, 8, 1),
        statutory=False,
        evaluated_at=EVALUATED_AT,
    )

    assert kwargs["title"]
    assert kwargs["message"]
    assert kwargs["extra_data"]["band"] == band


# --- drift guards ----------------------------------------------------------------


def test_bands_under_test_match_what_the_policy_can_actually_return():
    """If the policy gains a band, this test fails before the sweep KeyErrors in production."""
    observed = {
        classify_due_band(date(2026, 8, 1), now=date(2026, 8, 2)),  # overdue
        classify_due_band(date(2026, 8, 5), now=date(2026, 8, 1)),  # due_7
        classify_due_band(date(2026, 8, 25), now=date(2026, 8, 1)),  # due_30
        classify_due_band(date(2026, 9, 25), now=date(2026, 8, 1)),  # due_60
    }

    assert observed == set(ALL_BANDS)


def test_module_never_mentions_expired():
    """Same honest-language rule the policy module is held to."""
    source = Path(builders.__file__).read_text(encoding="utf-8")
    assert "expired" not in source.lower()


def test_sweep_and_assignment_paths_import_the_builders():
    """Builders stay the single source of due/assignment copy and keys."""
    from src.domain.services import compliance_schedule_assignment_notify as assign
    from src.infrastructure.tasks import compliance_schedule_notification_tasks as sweep

    assert "compliance_schedule_notifications" in Path(sweep.__file__).read_text(encoding="utf-8")
    assert "compliance_schedule_notifications" in Path(assign.__file__).read_text(encoding="utf-8")


# --- owner assignment ------------------------------------------------------------


def test_should_notify_owner_change_only_when_new_person_gains_ownership():
    from src.domain.services.compliance_schedule_notifications import should_notify_owner_change

    assert should_notify_owner_change(previous_owner_id=None, new_owner_id=7) is True
    assert should_notify_owner_change(previous_owner_id=3, new_owner_id=7) is True
    assert should_notify_owner_change(previous_owner_id=7, new_owner_id=7) is False
    assert should_notify_owner_change(previous_owner_id=7, new_owner_id=None) is False
    assert should_notify_owner_change(previous_owner_id=None, new_owner_id=None) is False


def test_build_assignment_notification_kwargs_for_new_owner():
    from src.domain.services.compliance_schedule_notifications import (
        ASSIGNMENT_NOTIFICATION_CATEGORY,
        build_assignment_notification_kwargs,
    )

    kwargs = build_assignment_notification_kwargs(
        user_id=7,
        tenant_id=3,
        requirement_id=11,
        reference_number="CSR-0011",
        title="Fire risk assessment",
        assigned_by_user_id=2,
        previous_owner_id=None,
        next_due_date=date(2026, 9, 1),
    )

    assert kwargs["type"] is NotificationType.ASSIGNMENT
    assert kwargs["user_id"] == 7
    assert kwargs["tenant_id"] == 3
    assert kwargs["entity_type"] == ENTITY_TYPE
    assert kwargs["entity_id"] == "11"
    assert kwargs["action_url"] == "/compliance-schedule/11"
    assert kwargs["sender_id"] == 2
    assert "CSR-0011" in kwargs["message"]
    assert "2026-09-01" in kwargs["message"]
    assert kwargs["extra_data"]["notification_category"] == ASSIGNMENT_NOTIFICATION_CATEGORY
    assert kwargs["extra_data"]["previous_owner_id"] is None


def test_build_assignment_notification_kwargs_reassignment_type():
    from src.domain.services.compliance_schedule_notifications import build_assignment_notification_kwargs

    kwargs = build_assignment_notification_kwargs(
        user_id=7,
        tenant_id=3,
        requirement_id=11,
        reference_number="CSR-0011",
        title="Fire risk assessment",
        assigned_by_user_id=2,
        previous_owner_id=4,
        next_due_date=None,
    )

    assert kwargs["type"] is NotificationType.REASSIGNMENT
    assert kwargs["extra_data"]["previous_owner_id"] == 4
    assert "reassigned" in kwargs["title"].lower() or "reassigned" in kwargs["message"].lower()
