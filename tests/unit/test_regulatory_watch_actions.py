"""Unit tests for regulatory watch → Actions closed-loop (GKB WL2)."""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.domain.models.capa import CAPAAction, CAPAPriority, CAPASource, CAPAStatus, CAPAType
from src.domain.models.governed_knowledge import RegulatoryImpactStatus, RegulatoryWatchImpact
from src.domain.services.regulatory_watch_actions import (
    HIGH_CONFIDENCE_DUE_DAYS,
    RegulatoryWatchActionsService,
    _due_and_priority,
)


def test_due_and_priority_high_confidence():
    due, priority = _due_and_priority(0.9)
    assert priority == CAPAPriority.HIGH
    assert due > datetime.now(timezone.utc).replace(tzinfo=None)


def test_due_and_priority_standard():
    due, priority = _due_and_priority(0.6)
    assert priority == CAPAPriority.MEDIUM
    assert due > datetime.now(timezone.utc).replace(tzinfo=None)


def test_capa_source_has_regulatory_watch():
    assert CAPASource.REGULATORY_WATCH.value == "regulatory_watch"


def test_impact_status_resolved_exists():
    assert RegulatoryImpactStatus.RESOLVED.value == "resolved"


@pytest.mark.asyncio
async def test_create_action_for_impact_sets_owner_due_and_status():
    impact = RegulatoryWatchImpact(
        id=42,
        tenant_id=1,
        update_id="9",
        document_id=7,
        confidence=0.9,
        rationale="Matched coshh",
        status=RegulatoryImpactStatus.NEW,
    )
    # Simulate ORM identity
    impact.id = 42

    prior_result = MagicMock()
    prior_result.scalar_one_or_none.return_value = None

    db = SimpleNamespace(
        execute=AsyncMock(return_value=prior_result),
        get=AsyncMock(return_value=None),
        add=MagicMock(),
        flush=AsyncMock(),
        commit=AsyncMock(),
        refresh=AsyncMock(),
    )

    async def flush_side_effect():
        for call in db.add.call_args_list:
            obj = call.args[0]
            if isinstance(obj, CAPAAction) and getattr(obj, "id", None) is None:
                obj.id = 501

    db.flush.side_effect = flush_side_effect

    async def refresh_side_effect(obj):
        if isinstance(obj, CAPAAction) and getattr(obj, "id", None) is None:
            obj.id = 501

    db.refresh.side_effect = refresh_side_effect

    svc = RegulatoryWatchActionsService()
    with (
        patch.object(svc, "_context_titles", new=AsyncMock(return_value=("HSE update", "COSHH Policy"))),
        patch(
            "src.domain.services.regulatory_watch_actions.ReferenceNumberService.generate",
            new=AsyncMock(return_value="CAPA-2026-0099"),
        ),
    ):
        capa = await svc.create_action_for_impact(
            db,
            impact=impact,
            created_by_id=3,
            tenant_id=1,
            owner_id=3,
            auto_applied=True,
            commit=True,
        )

    assert isinstance(capa, CAPAAction)
    assert capa.source_type == CAPASource.REGULATORY_WATCH
    assert capa.source_id == 42
    assert capa.assigned_to_id == 3
    assert capa.due_date is not None
    assert capa.priority == CAPAPriority.HIGH
    assert capa.capa_type == CAPAType.PREVENTIVE
    assert impact.status == RegulatoryImpactStatus.TASK_CREATED
    assert impact.action_id == 501
    assert impact.owner_id == 3
    assert impact.due_date is not None
    # High confidence → 7-day SLA window
    delta = impact.due_date - datetime.now(timezone.utc).replace(tzinfo=None)
    assert abs(delta.days - HIGH_CONFIDENCE_DUE_DAYS) <= 1


@pytest.mark.asyncio
async def test_create_action_idempotent_when_action_already_linked():
    existing = CAPAAction(
        reference_number="CAPA-2026-0001",
        title="Existing",
        description="d",
        capa_type=CAPAType.PREVENTIVE,
        status=CAPAStatus.OPEN,
        priority=CAPAPriority.MEDIUM,
        source_type=CAPASource.REGULATORY_WATCH,
        source_id=5,
        created_by_id=1,
        tenant_id=1,
    )
    existing.id = 88

    impact = RegulatoryWatchImpact(
        tenant_id=1,
        update_id="1",
        document_id=2,
        confidence=0.7,
        status=RegulatoryImpactStatus.TASK_CREATED,
        action_id=88,
    )
    impact.id = 5

    db = SimpleNamespace(
        get=AsyncMock(return_value=existing),
        execute=AsyncMock(),
        add=MagicMock(),
        commit=AsyncMock(),
        refresh=AsyncMock(),
    )

    svc = RegulatoryWatchActionsService()
    capa = await svc.create_action_for_impact(
        db,
        impact=impact,
        created_by_id=1,
        tenant_id=1,
        commit=True,
    )
    assert capa.id == 88
    db.execute.assert_not_called()


@pytest.mark.asyncio
async def test_resolve_impact_closes_linked_capa():
    capa = CAPAAction(
        reference_number="CAPA-2026-0002",
        title="t",
        description="d",
        capa_type=CAPAType.PREVENTIVE,
        status=CAPAStatus.OPEN,
        priority=CAPAPriority.MEDIUM,
        source_type=CAPASource.REGULATORY_WATCH,
        source_id=11,
        created_by_id=1,
        tenant_id=1,
    )
    capa.id = 200

    impact = RegulatoryWatchImpact(
        tenant_id=1,
        update_id="3",
        document_id=4,
        confidence=0.8,
        status=RegulatoryImpactStatus.TASK_CREATED,
        action_id=200,
        owner_id=1,
    )
    impact.id = 11

    db = SimpleNamespace(
        get=AsyncMock(return_value=capa),
        add=MagicMock(),
        commit=AsyncMock(),
        refresh=AsyncMock(),
    )

    svc = RegulatoryWatchActionsService()
    resolved = await svc.resolve_impact(
        db,
        impact=impact,
        resolved_by_id=9,
        tenant_id=1,
        notes="Document rematched and re-acked",
        dismiss=False,
        close_action=True,
    )

    assert resolved.status == RegulatoryImpactStatus.RESOLVED
    assert resolved.resolved_by_id == 9
    assert resolved.resolution_notes == "Document rematched and re-acked"
    assert capa.status == CAPAStatus.CLOSED
    assert capa.verified_by_id == 9


@pytest.mark.asyncio
async def test_dismiss_impact_does_not_require_action():
    impact = RegulatoryWatchImpact(
        tenant_id=1,
        update_id="3",
        document_id=None,
        confidence=0.5,
        status=RegulatoryImpactStatus.NEW,
    )
    impact.id = 12

    db = SimpleNamespace(
        get=AsyncMock(),
        add=MagicMock(),
        commit=AsyncMock(),
        refresh=AsyncMock(),
    )

    svc = RegulatoryWatchActionsService()
    dismissed = await svc.resolve_impact(
        db,
        impact=impact,
        resolved_by_id=2,
        tenant_id=1,
        dismiss=True,
        notes="Not applicable",
    )
    assert dismissed.status == RegulatoryImpactStatus.DISMISSED
    db.get.assert_not_called()


def test_serialize_action_includes_action_key():
    capa = CAPAAction(
        reference_number="CAPA-2026-0003",
        title="Review COSHH",
        description="d",
        capa_type=CAPAType.PREVENTIVE,
        status=CAPAStatus.OPEN,
        priority=CAPAPriority.HIGH,
        source_type=CAPASource.REGULATORY_WATCH,
        source_id=15,
        created_by_id=1,
        tenant_id=1,
        assigned_to_id=4,
    )
    capa.id = 77
    payload = RegulatoryWatchActionsService().serialize_action(capa)
    assert payload["action_key"] == "capa:77"
    assert payload["source_type"] == "regulatory_watch"
    assert payload["reference_number"] == "CAPA-2026-0003"


def test_unified_actions_recognises_regulatory_watch_source():
    from src.api.routes._action_unified import CAPA_ONLY_API_SOURCE_TYPES, capa_enum_from_api_filter

    assert "regulatory_watch" in CAPA_ONLY_API_SOURCE_TYPES
    assert capa_enum_from_api_filter("regulatory_watch") == CAPASource.REGULATORY_WATCH
