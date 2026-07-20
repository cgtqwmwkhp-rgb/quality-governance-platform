"""Friday Atlas upload reminder helpers."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from src.infrastructure.tasks.training_matrix_upload_reminder_tasks import (
    ACTION_URL,
    build_notification_kwargs,
    dedupe_key_for_week,
    format_last_upload_label,
    notification_exists_for_week,
    week_key,
)


def test_week_key_iso_format():
    now = datetime(2026, 7, 17, 8, 0, tzinfo=timezone.utc)  # Friday
    assert week_key(now) == "2026-W29"


def test_dedupe_and_exists_for_week():
    week = "2026-W29"
    assert dedupe_key_for_week(week) == "training_matrix_upload:2026-W29"
    rows = [
        SimpleNamespace(
            user_id=1,
            entity_type="training_matrix_upload",
            entity_id=week,
            extra_data={"week_key": week, "dedupe_key": dedupe_key_for_week(week)},
        )
    ]
    assert notification_exists_for_week(rows, user_id=1, week=week) is True
    assert notification_exists_for_week(rows, user_id=2, week=week) is False
    assert notification_exists_for_week(rows, user_id=1, week="2026-W30") is False


def test_build_notification_kwargs_includes_last_upload():
    kwargs = build_notification_kwargs(
        user_id=9,
        week="2026-W29",
        tenant_id=1,
        last_upload_label="17 Jul 2026 08:00 UTC by Ada Lovelace (matrix.csv)",
    )
    assert kwargs["user_id"] == 9
    assert kwargs["entity_type"] == "training_matrix_upload"
    assert kwargs["entity_id"] == "2026-W29"
    assert kwargs["action_url"] == ACTION_URL
    assert "Ada Lovelace" in kwargs["message"]
    assert kwargs["extra_data"]["dedupe_key"] == "training_matrix_upload:2026-W29"
    assert "in_app" in kwargs["delivered_channels"]


def test_format_last_upload_label():
    created = datetime(2026, 7, 17, 8, 0, tzinfo=timezone.utc)
    label = format_last_upload_label(
        created_at=created,
        uploaded_by_name="Ada Lovelace",
        filename="atlas.csv",
    )
    assert label is not None
    assert "Ada Lovelace" in label
    assert "atlas.csv" in label
    assert format_last_upload_label(created_at=None, uploaded_by_name=None, filename=None) is None
