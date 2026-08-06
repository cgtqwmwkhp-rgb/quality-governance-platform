"""A failed compliance check has to leave a corrective action behind (W18).

Two halves: ``CAPAAutoService.create_from_compliance_record`` in isolation, and
the completion path that calls it. The tenancy assertions are the point of the
first half — ``capa_actions`` is under ``tenant_isolation`` with FORCE, so a CAPA
minted against the wrong tenant is not a mislabelled row, it is a write the
policy refuses mid-transaction and a completion the operator loses.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.domain.models.capa import CAPAAction, CAPAPriority, CAPASource, CAPAStatus, CAPAType
from src.domain.models.compliance_schedule import (
    ComplianceRecord,
    ComplianceRecordOutcome,
    ComplianceRequirement,
    ComplianceScheduleAnchor,
)
from src.domain.services.capa_auto_service import (
    CAPAAutoService,
    compliance_requirement_source_reference,
)
from src.domain.services.compliance_schedule_service import ComplianceScheduleService

NOW = datetime(2026, 6, 1, 9, 0, tzinfo=timezone.utc)


def _result(scalar=None, scalars_all=None):
    result = MagicMock()
    result.scalar_one_or_none.return_value = scalar
    result.scalar.return_value = scalar
    scalars = MagicMock()
    scalars.all.return_value = scalars_all if scalars_all is not None else ([] if scalar is None else [scalar])
    result.scalars.return_value = scalars
    return result


@pytest.fixture
def db():
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    return session


def _requirement(**overrides) -> ComplianceRequirement:
    kwargs = dict(
        id=10,
        tenant_id=1,
        reference_number="CSR-2026-0001",
        title="Fire risk assessment — Wickford",
        taxonomy_id="HS",
        frequency_months=12,
        frequency_days=None,
        anchor=ComplianceScheduleAnchor.SCHEDULE,
        statutory=True,
        next_due_date=date(2026, 3, 1),
        is_active=True,
        external_id="req-ext",
        owner_id=7,
    )
    kwargs.update(overrides)
    return ComplianceRequirement(**kwargs)


def _record(**overrides) -> ComplianceRecord:
    kwargs = dict(
        id=55,
        tenant_id=1,
        reference_number="CRC-2026-0001",
        requirement_id=10,
        due_date=date(2026, 3, 1),
        outcome=ComplianceRecordOutcome.COMPLETED,
        completed_at=NOW,
        check_passed=False,
        notes="Two fire doors failed inspection.",
        external_id="rec-ext",
    )
    kwargs.update(overrides)
    return ComplianceRecord(**kwargs)


# ---------------------------------------------------------------------------
# CAPAAutoService.create_from_compliance_record
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_creates_capa_linked_to_record_and_requirement(db):
    db.execute = AsyncMock(return_value=_result(None))
    requirement = _requirement()
    record = _record()

    with patch(
        "src.domain.services.capa_auto_service.ReferenceNumberService.generate",
        new=AsyncMock(return_value="CAPA-2026-0009"),
    ):
        capa = await CAPAAutoService.create_from_compliance_record(
            db,
            record=record,
            requirement=requirement,
            created_by_id=9,
            now=NOW,
        )

    assert capa.source_type == CAPASource.COMPLIANCE_RECORD
    # The occurrence identifies the failure; the obligation is what a reader opens.
    assert capa.source_id == 55
    assert capa.source_reference == "compliance_requirement:10"
    assert capa.tenant_id == 1
    assert capa.status == CAPAStatus.OPEN
    assert capa.capa_type == CAPAType.CORRECTIVE
    assert capa.created_by_id == 9
    assert capa.assigned_to_id == 7
    assert requirement.reference_number in capa.description
    assert record.reference_number in capa.description
    assert "Wickford" in capa.title
    db.add.assert_called_once_with(capa)


@pytest.mark.asyncio
async def test_statutory_obligation_gets_the_shorter_fuse(db):
    db.execute = AsyncMock(return_value=_result(None))
    with patch(
        "src.domain.services.capa_auto_service.ReferenceNumberService.generate",
        new=AsyncMock(return_value="CAPA-2026-0010"),
    ):
        statutory = await CAPAAutoService.create_from_compliance_record(
            db,
            record=_record(),
            requirement=_requirement(statutory=True),
            created_by_id=9,
            now=NOW,
        )
        discretionary = await CAPAAutoService.create_from_compliance_record(
            db,
            record=_record(id=56, reference_number="CRC-2026-0002"),
            requirement=_requirement(statutory=False),
            created_by_id=9,
            now=NOW,
        )

    assert statutory.priority == CAPAPriority.CRITICAL
    assert statutory.due_date == NOW + timedelta(days=7)
    assert discretionary.priority == CAPAPriority.HIGH
    assert discretionary.due_date == NOW + timedelta(days=30)


@pytest.mark.asyncio
async def test_second_call_for_the_same_occurrence_returns_the_first_capa(db):
    existing = CAPAAction(id=3, reference_number="CAPA-2026-0001")
    db.execute = AsyncMock(return_value=_result(existing))

    capa = await CAPAAutoService.create_from_compliance_record(
        db,
        record=_record(),
        requirement=_requirement(),
        created_by_id=9,
        now=NOW,
    )

    assert capa is existing
    db.add.assert_not_called()


@pytest.mark.asyncio
async def test_dedupe_is_scoped_to_the_records_tenant(db):
    """The lookup must carry the tenant, not just the ids.

    Record ids are unique platform-wide today, so tenant on the dedupe read looks
    redundant — until a restore or an import renumbers, at which point an
    unscoped read is how one customer's CAPA gets handed to another.
    """
    captured: dict = {}

    async def _spy(_db, **kwargs):
        captured.update(kwargs)
        return None

    with patch.object(CAPAAutoService, "_existing_action", new=AsyncMock(side_effect=_spy)):
        with patch(
            "src.domain.services.capa_auto_service.ReferenceNumberService.generate",
            new=AsyncMock(return_value="CAPA-2026-0011"),
        ):
            await CAPAAutoService.create_from_compliance_record(
                db,
                record=_record(tenant_id=4),
                requirement=_requirement(tenant_id=4),
                created_by_id=9,
                now=NOW,
            )

    assert captured["tenant_id"] == 4
    assert captured["source_type"] == CAPASource.COMPLIANCE_RECORD
    assert captured["source_id"] == 55
    assert captured["source_reference"] == "compliance_requirement:10"


@pytest.mark.asyncio
async def test_refuses_a_requirement_from_another_tenant(db):
    db.execute = AsyncMock(return_value=_result(None))
    with pytest.raises(ValueError, match="tenant"):
        await CAPAAutoService.create_from_compliance_record(
            db,
            record=_record(tenant_id=1),
            requirement=_requirement(tenant_id=2),
            created_by_id=9,
            now=NOW,
        )
    db.add.assert_not_called()


@pytest.mark.asyncio
async def test_refuses_a_requirement_the_record_does_not_belong_to(db):
    db.execute = AsyncMock(return_value=_result(None))
    with pytest.raises(ValueError, match="requirement"):
        await CAPAAutoService.create_from_compliance_record(
            db,
            record=_record(requirement_id=99),
            requirement=_requirement(id=10),
            created_by_id=9,
            now=NOW,
        )
    db.add.assert_not_called()


@pytest.mark.asyncio
async def test_refuses_an_untenanted_record(db):
    db.execute = AsyncMock(return_value=_result(None))
    with pytest.raises(ValueError, match="tenant"):
        await CAPAAutoService.create_from_compliance_record(
            db,
            record=_record(tenant_id=None),
            requirement=_requirement(tenant_id=None),
            created_by_id=9,
            now=NOW,
        )
    db.add.assert_not_called()


@pytest.mark.asyncio
async def test_refuses_a_record_that_has_not_been_flushed(db):
    db.execute = AsyncMock(return_value=_result(None))
    with pytest.raises(ValueError, match="flushed"):
        await CAPAAutoService.create_from_compliance_record(
            db,
            record=_record(id=None),
            requirement=_requirement(),
            created_by_id=9,
            now=NOW,
        )
    db.add.assert_not_called()


@pytest.mark.asyncio
async def test_unowned_obligation_leaves_the_capa_unassigned(db):
    db.execute = AsyncMock(return_value=_result(None))
    with patch(
        "src.domain.services.capa_auto_service.ReferenceNumberService.generate",
        new=AsyncMock(return_value="CAPA-2026-0012"),
    ):
        capa = await CAPAAutoService.create_from_compliance_record(
            db,
            record=_record(),
            requirement=_requirement(owner_id=None),
            created_by_id=9,
            now=NOW,
        )
    assert capa.assigned_to_id is None


def test_source_reference_matches_the_shape_the_ui_parses():
    assert compliance_requirement_source_reference(10) == "compliance_requirement:10"


# ---------------------------------------------------------------------------
# ComplianceScheduleService.complete_requirement
# ---------------------------------------------------------------------------


def _flush_assigns_ids(session, start: int = 100) -> None:
    """Give flushed rows a primary key, as a real session would.

    ``create_from_compliance_record`` refuses an unflushed record, so a mock
    session that never assigns ids would make the completion path untestable for
    the wrong reason.
    """
    counter = {"next": start}

    async def _flush():
        for call in session.add.call_args_list:
            row = call.args[0]
            if getattr(row, "id", None) is None:
                row.id = counter["next"]
                counter["next"] += 1

    session.flush = AsyncMock(side_effect=_flush)


@pytest.mark.asyncio
async def test_failed_check_raises_a_capa_in_the_same_transaction(db):
    requirement = _requirement()
    db.execute = AsyncMock(
        side_effect=[
            _result(requirement),  # get_requirement
            _result(None),  # duplicate occurrence check
        ]
    )
    service = ComplianceScheduleService(db)
    auto = AsyncMock(return_value=CAPAAction(reference_number="CAPA-2026-0020"))

    with (
        patch(
            "src.domain.services.compliance_schedule_service.ReferenceNumberService.generate",
            new=AsyncMock(return_value="CRC-2026-0001"),
        ),
        patch(
            "src.domain.services.compliance_schedule_service.record_audit_event",
            new=AsyncMock(),
        ) as audit,
        patch.object(CAPAAutoService, "create_from_compliance_record", new=auto),
    ):
        record = await service.complete_requirement(
            10,
            tenant_id=1,
            user_id=9,
            completed_at=NOW,
            check_passed=False,
            notes="Two fire doors failed inspection.",
        )

    auto.assert_awaited_once()
    kwargs = auto.await_args.kwargs
    assert kwargs["record"] is record
    assert kwargs["requirement"] is requirement
    assert kwargs["created_by_id"] == 9
    # One commit, after the CAPA: the corrective action and the record it answers
    # land together or not at all.
    db.commit.assert_awaited_once()
    assert audit.await_args.kwargs["payload"]["capa_reference"] == "CAPA-2026-0020"


@pytest.mark.asyncio
@pytest.mark.parametrize("check_passed", [True, None])
async def test_no_capa_when_the_check_passed_or_did_not_apply(db, check_passed):
    """None is "no pass/fail dimension", not "failed"; neither owes a CAPA."""
    db.execute = AsyncMock(side_effect=[_result(_requirement()), _result(None)])
    service = ComplianceScheduleService(db)
    auto = AsyncMock()

    with (
        patch(
            "src.domain.services.compliance_schedule_service.ReferenceNumberService.generate",
            new=AsyncMock(return_value="CRC-2026-0001"),
        ),
        patch(
            "src.domain.services.compliance_schedule_service.record_audit_event",
            new=AsyncMock(),
        ) as audit,
        patch.object(CAPAAutoService, "create_from_compliance_record", new=auto),
    ):
        await service.complete_requirement(
            10,
            tenant_id=1,
            user_id=9,
            completed_at=NOW,
            check_passed=check_passed,
        )

    auto.assert_not_awaited()
    assert audit.await_args.kwargs["payload"]["capa_reference"] is None


@pytest.mark.asyncio
async def test_a_capa_that_cannot_be_raised_takes_the_completion_with_it(db):
    """Matches ``complete_assessment``: the CAPA is not wrapped in a swallow.

    A record stating the check failed, with no corrective action anywhere, is
    the exact gap the register exists to close — and it would be written
    silently. Failing the request leaves the operator able to retry.
    """
    requirement = _requirement()
    db.execute = AsyncMock(side_effect=[_result(requirement), _result(None)])
    service = ComplianceScheduleService(db)

    with (
        patch(
            "src.domain.services.compliance_schedule_service.ReferenceNumberService.generate",
            new=AsyncMock(return_value="CRC-2026-0001"),
        ),
        patch(
            "src.domain.services.compliance_schedule_service.record_audit_event",
            new=AsyncMock(),
        ),
        patch.object(
            CAPAAutoService,
            "create_from_compliance_record",
            new=AsyncMock(side_effect=RuntimeError("capa refused")),
        ),
    ):
        with pytest.raises(RuntimeError, match="capa refused"):
            await service.complete_requirement(
                10,
                tenant_id=1,
                user_id=9,
                completed_at=NOW,
                check_passed=False,
            )

    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_capa_is_raised_against_the_completing_tenant(db):
    """No tenant argument reaches the auto service — it reads the record."""
    requirement = _requirement(tenant_id=3, owner_id=None)
    db.execute = AsyncMock(side_effect=[_result(requirement), _result(None)])
    _flush_assigns_ids(db)
    service = ComplianceScheduleService(db)

    with (
        patch(
            "src.domain.services.compliance_schedule_service.ReferenceNumberService.generate",
            new=AsyncMock(return_value="CRC-2026-0001"),
        ),
        patch(
            "src.domain.services.compliance_schedule_service.record_audit_event",
            new=AsyncMock(),
        ),
        patch(
            "src.domain.services.capa_auto_service.ReferenceNumberService.generate",
            new=AsyncMock(return_value="CAPA-2026-0021"),
        ),
        patch.object(CAPAAutoService, "_existing_action", new=AsyncMock(return_value=None)),
    ):
        record = await service.complete_requirement(
            10,
            tenant_id=3,
            user_id=9,
            completed_at=NOW,
            check_passed=False,
        )

    added = [call.args[0] for call in db.add.call_args_list]
    capas = [row for row in added if isinstance(row, CAPAAction)]
    assert len(capas) == 1
    assert capas[0].tenant_id == 3
    assert capas[0].source_id == record.id
    assert capas[0].source_reference == "compliance_requirement:10"


# ---------------------------------------------------------------------------
# Unified Actions register
# ---------------------------------------------------------------------------


def test_unified_actions_recognises_the_compliance_record_source():
    """Without this the Actions filter would answer an empty register."""
    from src.api.routes._action_unified import (
        CAPA_ONLY_API_SOURCE_TYPES,
        capa_api_source_type,
        capa_enum_from_api_filter,
    )

    assert "compliance_record" in CAPA_ONLY_API_SOURCE_TYPES
    assert capa_enum_from_api_filter("compliance_record") == CAPASource.COMPLIANCE_RECORD
    assert capa_api_source_type(CAPASource.COMPLIANCE_RECORD) == "compliance_record"
