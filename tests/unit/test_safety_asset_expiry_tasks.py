"""AM-NOTIFY: band selection + dedupe for safety asset expiry notifications."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from src.infrastructure.tasks.safety_asset_expiry_tasks import (
    action_url_for_asset,
    build_notification_kwargs,
    classify_expiry_band,
    dedupe_key,
    effective_due_date,
    notification_exists_for_band,
    recipient_user_ids,
)

NOW = datetime(2026, 7, 14, 12, 0, tzinfo=timezone.utc)


def test_effective_due_date_prefers_earlier_of_expiry_and_service():
    expiry = NOW + timedelta(days=60)
    service = NOW + timedelta(days=20)
    assert effective_due_date(expiry, service) == service
    assert effective_due_date(expiry, service, include_service_due=False) == expiry
    assert effective_due_date(None, service) == service
    assert effective_due_date(None, None) is None


@pytest.mark.parametrize(
    ("days", "expected"),
    [
        (-1, "overdue"),
        (-30, "overdue"),
        (0, "due_30"),
        (15, "due_30"),
        (30, "due_30"),
        (31, "due_60"),
        (45, "due_60"),
        (60, "due_60"),
        (61, "due_90"),
        (90, "due_90"),
        (91, None),
        (120, None),
    ],
)
def test_classify_expiry_band_exclusive_windows(days: int, expected: str | None):
    due = NOW + timedelta(days=days)
    assert classify_expiry_band(due, now=NOW) == expected


def test_classify_expiry_band_none_when_missing():
    assert classify_expiry_band(None, now=NOW) is None


def test_action_url_and_dedupe_key():
    assert action_url_for_asset(42) == "/safety-assets/42"
    assert dedupe_key(42, "due_30") == "safety_asset:42:due_30"


def test_recipient_user_ids_owner_plus_admins_deduped():
    assert recipient_user_ids(owner_user_id=7, admin_user_ids=[7, 9, 9, 11]) == [7, 9, 11]
    assert recipient_user_ids(owner_user_id=None, admin_user_ids=[3]) == [3]
    assert recipient_user_ids(owner_user_id=None, admin_user_ids=[]) == []


def test_notification_exists_for_band_matches_band_or_dedupe_key():
    rows = [
        SimpleNamespace(
            user_id=1,
            entity_type="safety_asset",
            entity_id="42",
            extra_data={"band": "due_30", "dedupe_key": "safety_asset:42:due_30"},
        ),
        SimpleNamespace(
            user_id=2,
            entity_type="safety_asset",
            entity_id="42",
            extra_data={"band": "due_60"},
        ),
    ]
    assert notification_exists_for_band(rows, user_id=1, asset_id=42, band="due_30") is True
    assert notification_exists_for_band(rows, user_id=1, asset_id=42, band="due_60") is False
    assert notification_exists_for_band(rows, user_id=2, asset_id=42, band="due_60") is True
    assert notification_exists_for_band(rows, user_id=9, asset_id=42, band="due_30") is False


def test_notification_exists_for_band_ignores_other_assets():
    rows = [
        SimpleNamespace(
            user_id=1,
            entity_type="safety_asset",
            entity_id="99",
            extra_data={"band": "due_30"},
        )
    ]
    assert notification_exists_for_band(rows, user_id=1, asset_id=42, band="due_30") is False


def test_build_notification_kwargs_deep_link_and_category():
    due = NOW + timedelta(days=20)
    kwargs = build_notification_kwargs(
        user_id=5,
        asset_id=42,
        asset_number="SA-001",
        asset_name="CO2 Extinguisher",
        band="due_30",
        due_at=due,
        tenant_id=1,
    )
    assert kwargs["user_id"] == 5
    assert kwargs["entity_type"] == "safety_asset"
    assert kwargs["entity_id"] == "42"
    assert kwargs["action_url"] == "/safety-assets/42"
    assert kwargs["delivered_channels"] == ["in_app"]
    assert kwargs["extra_data"]["band"] == "due_30"
    assert kwargs["extra_data"]["notification_category"] == "safety_asset_expiry"
    assert kwargs["extra_data"]["dedupe_key"] == "safety_asset:42:due_30"
    assert "CO2 Extinguisher" in kwargs["title"]
    assert "SA-001" in kwargs["message"]


def test_build_notification_kwargs_overdue_uses_expired_type():
    from src.domain.models.notification import NotificationPriority, NotificationType

    due = NOW - timedelta(days=3)
    kwargs = build_notification_kwargs(
        user_id=1,
        asset_id=7,
        asset_number="SA-7",
        asset_name="First Aid Kit",
        band="overdue",
        due_at=due,
    )
    assert kwargs["type"] is NotificationType.CERTIFICATE_EXPIRED
    assert kwargs["priority"] is NotificationPriority.HIGH


def test_check_safety_asset_expiry_registered_on_celery_app():
    from src.infrastructure.tasks.celery_app import CELERY_TASK_MODULES, celery_app

    assert "src.infrastructure.tasks.safety_asset_expiry_tasks" in CELERY_TASK_MODULES
    celery_app.loader.import_default_modules()
    assert "src.infrastructure.tasks.safety_asset_expiry_tasks.check_safety_asset_expiry" in celery_app.tasks
    assert "check-safety-asset-expiry" in celery_app.conf.beat_schedule
