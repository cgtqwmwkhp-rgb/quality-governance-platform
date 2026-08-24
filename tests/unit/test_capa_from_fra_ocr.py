"""Unit tests for CAPAAutoService.create_from_fra_ocr_actions (slice 5)."""

from __future__ import annotations

from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.domain.models.capa import CAPAPriority, CAPASource
from src.domain.services.capa_auto_service import CAPAAutoService, fra_ocr_draft_source_reference


def test_fra_ocr_source_value_and_reference() -> None:
    assert CAPASource.FRA_OCR.value == "fra_ocr"
    assert fra_ocr_draft_source_reference(7) == "fra_ocr_draft:7"


@pytest.mark.asyncio
async def test_create_from_fra_ocr_actions_empty_returns_empty() -> None:
    db = AsyncMock()
    requirement = SimpleNamespace(id=10, tenant_id=1, reference_number="CSR-1", title="FRA", owner_id=3)
    created = await CAPAAutoService.create_from_fra_ocr_actions(
        db,
        draft_id=7,
        requirement=requirement,
        actions=[],
        created_by_id=42,
    )
    assert created == []
    db.add.assert_not_called()


@pytest.mark.asyncio
async def test_create_from_fra_ocr_actions_creates_checked_rows_only() -> None:
    db = MagicMock()
    requirement = SimpleNamespace(
        id=10,
        tenant_id=1,
        reference_number="CSR-1",
        title="Fire risk assessment",
        owner_id=3,
    )
    actions = [
        {"index": 0, "text": "Replace seals", "priority_normalised": "high", "target_date": date(2026, 7, 1)},
        {"index": -1, "text": "ignored"},
        {"index": 2, "text": "   "},
        {"index": 1, "text": "Update signage", "priority_normalised": "low"},
    ]

    with (
        patch.object(CAPAAutoService, "_existing_action", new=AsyncMock(return_value=None)),
        patch(
            "src.domain.services.capa_auto_service.ReferenceNumberService.generate",
            new=AsyncMock(side_effect=["CAPA-A", "CAPA-B"]),
        ),
    ):
        created = await CAPAAutoService.create_from_fra_ocr_actions(
            db,
            draft_id=7,
            requirement=requirement,
            actions=actions,
            created_by_id=42,
            now=datetime(2026, 6, 1, tzinfo=timezone.utc),
        )

    assert len(created) == 2
    assert db.add.call_count == 2
    assert created[0].source_type == CAPASource.FRA_OCR
    assert created[0].source_id == 0
    assert created[0].source_reference == "fra_ocr_draft:7"
    assert created[0].priority == CAPAPriority.HIGH
    assert created[0].assigned_to_id == 3
    assert created[1].source_id == 1
    assert created[1].priority == CAPAPriority.LOW


@pytest.mark.asyncio
async def test_create_from_fra_ocr_actions_idempotent_per_index() -> None:
    db = AsyncMock()
    requirement = SimpleNamespace(
        id=10,
        tenant_id=1,
        reference_number="CSR-1",
        title="FRA",
        owner_id=None,
    )
    existing = SimpleNamespace(id=99, reference_number="CAPA-EXISTING")

    with patch.object(CAPAAutoService, "_existing_action", new=AsyncMock(return_value=existing)):
        created = await CAPAAutoService.create_from_fra_ocr_actions(
            db,
            draft_id=7,
            requirement=requirement,
            actions=[{"index": 0, "text": "Already raised"}],
            created_by_id=42,
        )

    assert created == [existing]
    db.add.assert_not_called()


def test_unified_actions_recognises_fra_ocr_source() -> None:
    """Without this the Actions filter would hide FRA OCR CAPAs."""
    from src.api.routes._action_unified import (
        CAPA_ONLY_API_SOURCE_TYPES,
        capa_api_source_type,
        capa_enum_from_api_filter,
    )

    assert "fra_ocr" in CAPA_ONLY_API_SOURCE_TYPES
    assert capa_enum_from_api_filter("fra_ocr") == CAPASource.FRA_OCR
    assert capa_api_source_type(CAPASource.FRA_OCR) == "fra_ocr"
