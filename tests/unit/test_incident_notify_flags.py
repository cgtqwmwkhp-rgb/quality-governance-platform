"""Incident owner-assignment notify flags — default-OFF polarity + gate bite."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from src.domain.services.incident_notify_flags import (
    ASSIGNMENT_NOTIFY_FLAG,
    DEFAULT_OFF_FLAG_KEYS,
    NOTIFY_FLAG_KEYS,
    assignment_notify_enabled,
    ensure_incident_notify_flags,
    is_incident_notify_flag_enabled,
)


def test_notify_flag_keys_are_stable() -> None:
    assert ASSIGNMENT_NOTIFY_FLAG in NOTIFY_FLAG_KEYS
    assert ASSIGNMENT_NOTIFY_FLAG in DEFAULT_OFF_FLAG_KEYS


@pytest.mark.asyncio
async def test_missing_row_defaults_off() -> None:
    """Absent feature_flags row → False (inverse of CS notify polarity)."""
    db = MagicMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=result)

    assert await is_incident_notify_flag_enabled(db, ASSIGNMENT_NOTIFY_FLAG, tenant_id=1) is False
    assert await assignment_notify_enabled(db, tenant_id=1) is False


@pytest.mark.asyncio
async def test_persisted_disabled_row_is_off() -> None:
    db = MagicMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = SimpleNamespace(
        enabled=False,
        tenant_overrides=None,
        rollout_percentage=100,
    )
    db.execute = AsyncMock(return_value=result)

    assert await is_incident_notify_flag_enabled(db, ASSIGNMENT_NOTIFY_FLAG, tenant_id=1) is False


@pytest.mark.asyncio
async def test_persisted_enabled_row_is_on() -> None:
    db = MagicMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = SimpleNamespace(
        enabled=True,
        tenant_overrides=None,
        rollout_percentage=100,
    )
    db.execute = AsyncMock(return_value=result)

    assert await is_incident_notify_flag_enabled(db, ASSIGNMENT_NOTIFY_FLAG, tenant_id=1) is True


@pytest.mark.asyncio
async def test_ensure_seeds_disabled() -> None:
    service = MagicMock()
    service._get_flag = AsyncMock(return_value=None)
    created = SimpleNamespace(key=ASSIGNMENT_NOTIFY_FLAG, enabled=False)
    service.create_flag = AsyncMock(return_value=created)

    with patch(
        "src.domain.services.incident_notify_flags.FeatureFlagService",
        return_value=service,
    ):
        ensured = await ensure_incident_notify_flags(MagicMock())

    assert ensured == [created]
    kwargs = service.create_flag.await_args.kwargs
    assert kwargs["key"] == ASSIGNMENT_NOTIFY_FLAG
    assert kwargs["enabled"] is False
    assert kwargs["rollout_percentage"] == 100


@pytest.mark.asyncio
async def test_incident_notify_skips_when_flag_off() -> None:
    from src.api.routes.incidents import _notify_case_owner_assignment

    db = MagicMock()
    with (
        patch(
            "src.domain.services.incident_notify_flags.assignment_notify_enabled",
            new_callable=AsyncMock,
            return_value=False,
        ),
        patch("src.api.routes.incidents.NotificationService") as svc_cls,
    ):
        await _notify_case_owner_assignment(
            db,
            entity_type="incident",
            entity_id=9,
            assigned_to_user_id=3,
            assigned_by_user_id=1,
            reference="INC-9",
            tenant_id=2,
        )

    svc_cls.assert_not_called()


@pytest.mark.asyncio
async def test_incident_notify_sends_when_flag_on() -> None:
    from src.api.routes.incidents import _notify_case_owner_assignment

    db = MagicMock()
    mock_service = AsyncMock()
    mock_service.create_assignment = AsyncMock()

    with (
        patch(
            "src.domain.services.incident_notify_flags.assignment_notify_enabled",
            new_callable=AsyncMock,
            return_value=True,
        ),
        patch(
            "src.api.routes.incidents.NotificationService",
            return_value=mock_service,
        ),
    ):
        await _notify_case_owner_assignment(
            db,
            entity_type="incident",
            entity_id=9,
            assigned_to_user_id=3,
            assigned_by_user_id=1,
            reference="INC-9",
            tenant_id=2,
        )

    mock_service.create_assignment.assert_awaited_once()
    kwargs = mock_service.create_assignment.await_args.kwargs
    assert kwargs["entity_type"] == "incident"
    assert kwargs["assigned_to_user_id"] == 3


@pytest.mark.asyncio
async def test_get_incident_notify_flag_seeds_missing_row() -> None:
    """GET /feature-flags/{incident-key} must seed so Admin Notification Settings can PATCH."""
    from src.api.routes.feature_flags import get_feature_flag

    seeded = SimpleNamespace(
        id=uuid4(),
        key=ASSIGNMENT_NOTIFY_FLAG,
        name="seeded",
        description="",
        enabled=False,
        rollout_percentage=100,
        tenant_overrides=None,
        metadata_=None,
        created_by="system",
        updated_by=None,
        created_at=None,
        updated_at=None,
    )
    service = MagicMock()
    service._get_flag = AsyncMock(return_value=seeded)

    with (
        patch(
            "src.domain.services.incident_notify_flags.ensure_incident_notify_flags",
            new_callable=AsyncMock,
            return_value=[seeded],
        ) as ensure,
        patch(
            "src.api.routes.feature_flags.FeatureFlagService",
            return_value=service,
        ),
    ):
        response = await get_feature_flag(
            key=ASSIGNMENT_NOTIFY_FLAG,
            db=MagicMock(),
            current_user=SimpleNamespace(id=1, tenant_id=1),
        )

    ensure.assert_awaited_once()
    assert response.key == ASSIGNMENT_NOTIFY_FLAG
    assert response.enabled is False
