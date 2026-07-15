"""Unit coverage for the read-only LOLER inspection-history scaffold."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.domain.models.loler import LOLERExaminationType
from src.domain.services.loler_inspection_service import LOLERInspectionService, inspection_status

NOW = datetime(2026, 7, 15, 12, tzinfo=timezone.utc)


@pytest.mark.parametrize(
    ("due_delta", "safe_to_operate", "expected"),
    [
        (None, True, "review_required"),
        (-1, True, "overdue"),
        (0, True, "due_soon"),
        (30, True, "due_soon"),
        (31, True, "compliant"),
        (90, False, "unsafe"),
    ],
)
def test_inspection_status_derives_asset_date_state(
    due_delta: int | None,
    safe_to_operate: bool,
    expected: str,
) -> None:
    due = NOW + timedelta(days=due_delta) if due_delta is not None else None

    assert inspection_status(next_due_date=due, safe_to_operate=safe_to_operate, now=NOW) == expected


@pytest.mark.asyncio
async def test_get_asset_history_returns_latest_status_and_certificates() -> None:
    latest_due = NOW + timedelta(days=14)
    latest = SimpleNamespace(
        id=22,
        reference_number="LOLER-2026-0022",
        examination_type=LOLERExaminationType.THOROUGH_EXAMINATION,
        examination_date=NOW,
        next_examination_due=latest_due,
        safe_to_operate=True,
        competent_person_name="A. Examiner",
    )
    earlier = SimpleNamespace(
        id=12,
        reference_number="LOLER-2025-0012",
        examination_type=LOLERExaminationType.INSPECTION,
        examination_date=NOW - timedelta(days=180),
        next_examination_due=NOW - timedelta(days=1),
        safe_to_operate=True,
        competent_person_name="B. Examiner",
    )
    result = MagicMock()
    result.scalars.return_value.all.return_value = [latest, earlier]
    db = MagicMock()
    db.execute = AsyncMock(return_value=result)

    history = await LOLERInspectionService(db).get_asset_history(asset_id=7, tenant_id=3)

    assert history.asset_id == 7
    assert history.next_due_date == latest_due
    assert history.status == "due_soon"
    assert [item.id for item in history.items] == [22, 12]
    assert history.items[1].status == "overdue"
    db.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_asset_history_reports_absent_certificate_without_database_writes() -> None:
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    db = MagicMock()
    db.execute = AsyncMock(return_value=result)

    history = await LOLERInspectionService(db).get_asset_history(asset_id=9, tenant_id=3)

    assert history.status == "not_recorded"
    assert history.next_due_date is None
    assert history.items == []
    db.add.assert_not_called()
    db.commit.assert_not_called()
