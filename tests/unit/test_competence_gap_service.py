"""Unit tests for Assessor competence_gap → Workforce closed loop."""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.domain.models.capa import CAPAAction, CAPAPriority, CAPASource, CAPAStatus, CAPAType
from src.domain.models.competence_gap import (
    CompetenceGapAction,
    CompetenceGapSignalType,
    CompetenceGapSourceType,
    CompetenceGapStatus,
)
from src.domain.models.engineer import CompetencyLifecycleState, CompetencyRecord, CompetencyRequirement
from src.domain.services.competence_gap_service import (
    CompetenceGapService,
    normalize_signal_type,
    should_open_competence_gap,
)


def test_capa_source_has_competence_gap():
    assert CAPASource.COMPETENCE_GAP.value == "competence_gap"


def test_normalize_signal_maps_gap_and_nc():
    assert normalize_signal_type("gap") == CompetenceGapSignalType.COMPETENCE_GAP
    assert normalize_signal_type("competence_gap") == CompetenceGapSignalType.COMPETENCE_GAP
    assert normalize_signal_type("nonconformity") == CompetenceGapSignalType.NONCONFORMITY
    assert normalize_signal_type("evidence") is None


def test_should_open_competence_gap():
    assert should_open_competence_gap("competence_gap")
    assert should_open_competence_gap("nonconformity")
    assert should_open_competence_gap("gap")
    assert not should_open_competence_gap("evidence")
    assert not should_open_competence_gap("opportunity")


@pytest.mark.asyncio
async def test_from_signal_idempotent():
    existing = CompetenceGapAction(
        tenant_id=1,
        source_type=CompetenceGapSourceType.COMPLIANCE_EVIDENCE_LINK.value,
        source_id=9,
        signal_type=CompetenceGapSignalType.COMPETENCE_GAP,
        status=CompetenceGapStatus.OPEN,
        created_by_id=1,
    )
    existing.id = 11

    prior = MagicMock()
    prior.scalar_one_or_none.return_value = existing
    db = SimpleNamespace(execute=AsyncMock(return_value=prior), add=MagicMock(), flush=AsyncMock())

    svc = CompetenceGapService()
    gap = await svc.from_signal(
        db,
        tenant_id=1,
        created_by_id=1,
        source_type="compliance_evidence_link",
        source_id=9,
        signal_type="competence_gap",
        commit=False,
    )
    assert gap.id == 11
    db.add.assert_not_called()


@pytest.mark.asyncio
async def test_from_signal_creates_row():
    prior = MagicMock()
    prior.scalar_one_or_none.return_value = None
    db = SimpleNamespace(
        execute=AsyncMock(return_value=prior),
        add=MagicMock(),
        flush=AsyncMock(),
        commit=AsyncMock(),
        refresh=AsyncMock(),
    )

    async def flush_side_effect():
        for call in db.add.call_args_list:
            obj = call.args[0]
            if isinstance(obj, CompetenceGapAction) and getattr(obj, "id", None) is None:
                obj.id = 77

    db.flush.side_effect = flush_side_effect

    svc = CompetenceGapService()
    with patch(
        "src.domain.services.competence_gap_service.record_audit_event",
        new=AsyncMock(),
    ):
        gap = await svc.from_signal(
            db,
            tenant_id=1,
            created_by_id=3,
            source_type="compliance_evidence_link",
            source_id=42,
            signal_type="nonconformity",
            confidence=0.9,
            commit=True,
        )

    assert gap.id == 77
    assert gap.signal_type == CompetenceGapSignalType.NONCONFORMITY
    assert gap.status == CompetenceGapStatus.OPEN
    assert db.commit.await_count == 1


@pytest.mark.asyncio
async def test_create_capa_sets_source_and_owner():
    gap = CompetenceGapAction(
        tenant_id=1,
        source_type=CompetenceGapSourceType.COMPLIANCE_EVIDENCE_LINK.value,
        source_id=5,
        signal_type=CompetenceGapSignalType.COMPETENCE_GAP,
        status=CompetenceGapStatus.OPEN,
        created_by_id=1,
        confidence=0.9,
    )
    gap.id = 5

    prior = MagicMock()
    prior.scalar_one_or_none.return_value = None
    db = SimpleNamespace(
        get=AsyncMock(return_value=None),
        execute=AsyncMock(return_value=prior),
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

    svc = CompetenceGapService()
    with (
        patch(
            "src.domain.services.competence_gap_service.ReferenceNumberService.generate",
            new=AsyncMock(return_value="CAPA-2026-0100"),
        ),
        patch(
            "src.domain.services.competence_gap_service.record_audit_event",
            new=AsyncMock(),
        ),
    ):
        capa = await svc.create_capa(
            db,
            gap=gap,
            tenant_id=1,
            created_by_id=3,
            owner_id=3,
        )

    assert capa.source_type == CAPASource.COMPETENCE_GAP
    assert capa.source_id == 5
    assert capa.assigned_to_id == 3
    assert capa.priority == CAPAPriority.HIGH
    assert capa.capa_type == CAPAType.CORRECTIVE
    assert gap.status == CompetenceGapStatus.CAPA_CREATED
    assert gap.capa_action_id == 501


@pytest.mark.asyncio
async def test_resolve_requires_active_competency_record():
    gap = CompetenceGapAction(
        tenant_id=1,
        source_type=CompetenceGapSourceType.COMPLIANCE_EVIDENCE_LINK.value,
        source_id=1,
        signal_type=CompetenceGapSignalType.COMPETENCE_GAP,
        status=CompetenceGapStatus.LINKED,
        created_by_id=1,
        engineer_id=9,
        requirement_id=4,
    )
    gap.id = 1

    req = CompetencyRequirement(
        id=4,
        asset_type_id=20,
        template_id=1,
        name="Gas Safe",
        tenant_id=1,
    )
    empty = MagicMock()
    empty.scalars.return_value.first.return_value = None

    db = SimpleNamespace(
        get=AsyncMock(return_value=req),
        execute=AsyncMock(return_value=empty),
        add=MagicMock(),
        commit=AsyncMock(),
        refresh=AsyncMock(),
    )

    svc = CompetenceGapService()
    with pytest.raises(ValueError, match="active CompetencyRecord"):
        await svc.resolve(db, gap=gap, tenant_id=1, resolved_by_id=2)


@pytest.mark.asyncio
async def test_resolve_with_active_record():
    gap = CompetenceGapAction(
        tenant_id=1,
        source_type=CompetenceGapSourceType.COMPLIANCE_EVIDENCE_LINK.value,
        source_id=1,
        signal_type=CompetenceGapSignalType.COMPETENCE_GAP,
        status=CompetenceGapStatus.LINKED,
        created_by_id=1,
        engineer_id=9,
        requirement_id=4,
    )
    gap.id = 1

    req = CompetencyRequirement(
        id=4,
        asset_type_id=20,
        template_id=1,
        name="Gas Safe",
        tenant_id=1,
    )
    record = CompetencyRecord(
        engineer_id=9,
        asset_type_id=20,
        template_id=1,
        source_type="assessment",
        source_run_id="abc",
        state=CompetencyLifecycleState.ACTIVE,
        tenant_id=1,
    )
    found = MagicMock()
    found.scalars.return_value.first.return_value = record

    db = SimpleNamespace(
        get=AsyncMock(return_value=req),
        execute=AsyncMock(return_value=found),
        add=MagicMock(),
        commit=AsyncMock(),
        refresh=AsyncMock(),
    )

    svc = CompetenceGapService()
    with patch(
        "src.domain.services.competence_gap_service.record_audit_event",
        new=AsyncMock(),
    ):
        resolved = await svc.resolve(db, gap=gap, tenant_id=1, resolved_by_id=2, notes="OJT passed")

    assert resolved.status == CompetenceGapStatus.RESOLVED
    assert resolved.resolved_by_id == 2
    assert resolved.resolved_at is not None


@pytest.mark.asyncio
async def test_golden_thread_returns_ordered_events():
    gap = CompetenceGapAction(
        tenant_id=1,
        source_type=CompetenceGapSourceType.COMPLIANCE_EVIDENCE_LINK.value,
        source_id=3,
        signal_type=CompetenceGapSignalType.NONCONFORMITY,
        status=CompetenceGapStatus.CAPA_CREATED,
        created_by_id=1,
        engineer_id=2,
        requirement_id=8,
        capa_action_id=99,
        confidence=0.8,
        rationale="Missing IPAF",
    )
    gap.id = 12
    gap.created_at = datetime(2026, 7, 13, 12, 0, tzinfo=timezone.utc)
    gap.updated_at = datetime(2026, 7, 13, 13, 0, tzinfo=timezone.utc)

    capa = CAPAAction(
        reference_number="CAPA-1",
        title="t",
        description="d",
        capa_type=CAPAType.CORRECTIVE,
        status=CAPAStatus.OPEN,
        priority=CAPAPriority.MEDIUM,
        source_type=CAPASource.COMPETENCE_GAP,
        source_id=12,
        created_by_id=1,
        tenant_id=1,
        assigned_to_id=4,
    )
    capa.id = 99
    capa.created_at = datetime(2026, 7, 13, 13, 30, tzinfo=timezone.utc)

    logs = MagicMock()
    logs.scalars.return_value.all.return_value = []

    db = SimpleNamespace(
        get=AsyncMock(return_value=capa),
        execute=AsyncMock(return_value=logs),
    )

    svc = CompetenceGapService()
    pack = await svc.golden_thread(db, gap=gap, tenant_id=1)
    assert pack["gap"]["id"] == 12
    events = [e["event"] for e in pack["events"]]
    assert events[0] == "competence_gap.detected"
    assert "competence_gap.linked" in events
    assert "competence_gap.capa_created" in events
