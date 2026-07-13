"""Unit tests for standards-assessment proposed-link notifications."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.domain.services.standards_assessment_notifications import (
    case_standards_deep_link,
    exceptions_deep_link,
    notify_proposed_standards_links,
    resolve_case_notify_user_ids,
)


def test_exceptions_deep_link() -> None:
    assert exceptions_deep_link("incident") == "/knowledge-exceptions?entity_type=incident"


def test_case_standards_deep_link_known() -> None:
    assert case_standards_deep_link("near_miss", "42") == "/near-misses/42?tab=standards"


def test_case_standards_deep_link_fallback() -> None:
    assert case_standards_deep_link("audit_finding", "9") == "/knowledge-exceptions?entity_type=audit_finding"


@pytest.mark.asyncio
async def test_resolve_near_miss_owner_and_creator() -> None:
    db = AsyncMock()
    near_miss = MagicMock(assigned_to_id=7, created_by_id=3)
    result = MagicMock()
    result.scalar_one_or_none.return_value = near_miss
    db.execute = AsyncMock(return_value=result)

    ids = await resolve_case_notify_user_ids(
        db, entity_type="near_miss", entity_id="11", tenant_id=1
    )
    assert ids == [7, 3]


@pytest.mark.asyncio
async def test_notify_skips_sender_and_zero_links() -> None:
    db = AsyncMock()
    assert await notify_proposed_standards_links(
        db,
        entity_type="incident",
        entity_id="1",
        tenant_id=1,
        links_created=0,
        sender_id=5,
    ) == []

    with patch(
        "src.domain.services.standards_assessment_notifications.resolve_case_notify_user_ids",
        new=AsyncMock(return_value=[5, 9]),
    ):
        created = await notify_proposed_standards_links(
            db,
            entity_type="incident",
            entity_id="1",
            tenant_id=1,
            links_created=2,
            sender_id=5,
        )
    assert len(created) == 1
    assert created[0].user_id == 9
    assert created[0].action_url == "/knowledge-exceptions?entity_type=incident"
    assert created[0].extra_data["standards_url"] == "/incidents/1?tab=standards"
    db.add.assert_called_once()
