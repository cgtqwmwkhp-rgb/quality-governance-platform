"""Unit tests for Safety lookup approve / discard (PX-196)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.domain.exceptions import ValidationError
from src.domain.services.safety_lookup_approval_service import SafetyLookupApprovalService


def _pending_type(*, entity_id: int = 9, name: str = "SPARE") -> SimpleNamespace:
    return SimpleNamespace(
        id=entity_id,
        name=name,
        is_active=True,
        approval_status="pending",
        updated_by_id=None,
    )


@pytest.mark.asyncio
async def test_reject_discards_unused_pending_lookup_without_target() -> None:
    db = MagicMock()
    pending = _pending_type()

    pending_result = MagicMock()
    pending_result.scalar_one_or_none.return_value = pending
    usage_result = MagicMock()
    usage_result.scalar_one_or_none.return_value = None

    db.execute = AsyncMock(side_effect=[pending_result, usage_result])
    db.commit = AsyncMock()

    service = SafetyLookupApprovalService(db)
    result = await service.reject(
        "asset_type",
        9,
        target_id=None,
        tenant_id=1,
        actor_user_id=42,
    )

    assert result["approval_status"] == "rejected"
    assert result["merged"] is False
    assert pending.approval_status == "rejected"
    assert pending.is_active is False
    db.commit.assert_awaited()


@pytest.mark.asyncio
async def test_reject_blocks_discard_when_assets_still_reference_lookup() -> None:
    db = MagicMock()
    pending = _pending_type()

    pending_result = MagicMock()
    pending_result.scalar_one_or_none.return_value = pending
    usage_result = MagicMock()
    usage_result.scalar_one_or_none.return_value = 101

    db.execute = AsyncMock(side_effect=[pending_result, usage_result])
    db.commit = AsyncMock()

    service = SafetyLookupApprovalService(db)
    with pytest.raises(ValidationError, match="assets still reference"):
        await service.reject(
            "asset_type",
            9,
            target_id=None,
            tenant_id=1,
            actor_user_id=42,
        )
    db.commit.assert_not_awaited()
