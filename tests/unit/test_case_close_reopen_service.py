"""Service-level close/reopen wiring for the case registers.

`test_case_closure_gate` covers the gate itself; this suite proves each service
actually calls it, stamps `closed_at`/`closed_by_id`, clears them on reopen, and
records the lifecycle audit event under the right name.
"""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from src.api.schemas.incident import IncidentUpdate
from src.api.schemas.rta import RTAUpdate
from src.domain.exceptions import StateTransitionError
from src.domain.services.incident_service import IncidentService
from src.domain.services.rta_service import RTAService


def _incident(**overrides):
    defaults = {
        "id": 5,
        "tenant_id": 1,
        "reference_number": "INC-5",
        "status": "pending_review",
        "lessons_learnt": "Guard refitted and briefed",
        "closed_at": None,
        "closed_by_id": None,
        "updated_by_id": None,
        "updated_at": None,
        "contract_id": None,
        "medical_assistance": None,
        "emergency_services": None,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _rta(**overrides):
    defaults = {
        "id": 9,
        "tenant_id": 1,
        "reference_number": "RTA-9",
        "status": "under_investigation",
        "lessons_learnt": "Route brief updated",
        "closed_at": None,
        "closed_by_id": None,
        "updated_by_id": None,
        "updated_at": None,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


@pytest.fixture
def db():
    session = AsyncMock()
    session.flush = AsyncMock()
    return session


def _no_open_work():
    """Patch the shared probe so these tests exercise wiring, not SQL."""
    from src.domain.services.case_closure import CaseActionTally

    return patch(
        "src.domain.services.case_closure.fetch_open_work_for_case",
        AsyncMock(return_value=([], CaseActionTally(total=0, complete=0, incomplete=0))),
    )


def _one_open_action():
    from src.domain.services.case_closure import CaseActionTally, CaseOpenWorkItem

    item = CaseOpenWorkItem(
        kind="incident_action",
        id=3,
        reference_number="INC-ACT-3",
        title="Fit guard",
        status="in_progress",
        action_key="incident_action:3",
    )
    return patch(
        "src.domain.services.case_closure.fetch_open_work_for_case",
        AsyncMock(return_value=([item], CaseActionTally(total=1, complete=0, incomplete=1))),
    )


def _quiet_side_effects():
    """Silence audit/cache/telemetry so the assertions stay on the close path."""
    return [
        patch("src.domain.services.incident_service.record_audit_event", AsyncMock()),
        patch("src.domain.services.incident_service.invalidate_tenant_cache", AsyncMock()),
    ]


class TestIncidentClose:
    @pytest.mark.asyncio
    async def test_close_stamps_closed_at_and_closed_by(self, db):
        incident = _incident()
        service = IncidentService(db)
        service.get_incident = AsyncMock(return_value=incident)

        with (
            _no_open_work(),
            patch("src.domain.services.incident_service.record_audit_event", AsyncMock()) as audit,
            patch("src.domain.services.incident_service.invalidate_tenant_cache", AsyncMock()),
        ):
            await service.update_incident(5, IncidentUpdate(status="closed"), user_id=7, tenant_id=1)

        assert incident.status == "closed"
        assert incident.closed_at is not None
        assert incident.closed_by_id == 7
        assert audit.await_args.kwargs["event_type"] == "incident.closed"

    @pytest.mark.asyncio
    async def test_close_without_lessons_is_refused_before_mutation(self, db):
        incident = _incident(lessons_learnt="   ")
        service = IncidentService(db)
        service.get_incident = AsyncMock(return_value=incident)

        with _no_open_work():
            with pytest.raises(StateTransitionError) as exc_info:
                await service.update_incident(5, IncidentUpdate(status="closed"), user_id=7, tenant_id=1)

        assert exc_info.value.code == "MISSING_LESSONS_LEARNT"
        # The refused close must leave the row untouched.
        assert incident.status == "pending_review"
        assert incident.closed_at is None
        db.flush.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_close_with_open_action_is_refused(self, db):
        incident = _incident()
        service = IncidentService(db)
        service.get_incident = AsyncMock(return_value=incident)

        with _one_open_action():
            with pytest.raises(StateTransitionError) as exc_info:
                await service.update_incident(5, IncidentUpdate(status="closed"), user_id=7, tenant_id=1)

        assert exc_info.value.code == "OPEN_ACTIONS_REMAIN"
        assert exc_info.value.details["open_work"][0]["reference_number"] == "INC-ACT-3"
        assert incident.status == "pending_review"

    @pytest.mark.asyncio
    async def test_lessons_supplied_in_the_same_request_satisfy_the_gate(self, db):
        incident = _incident(lessons_learnt=None)
        service = IncidentService(db)
        service.get_incident = AsyncMock(return_value=incident)

        with (
            _no_open_work(),
            patch("src.domain.services.incident_service.record_audit_event", AsyncMock()),
            patch("src.domain.services.incident_service.invalidate_tenant_cache", AsyncMock()),
        ):
            await service.update_incident(
                5,
                IncidentUpdate(status="closed", lessons_learnt="Briefed the crew"),
                user_id=7,
                tenant_id=1,
            )

        assert incident.status == "closed"
        assert incident.lessons_learnt == "Briefed the crew"

    @pytest.mark.asyncio
    async def test_clearing_lessons_while_closing_is_refused(self, db):
        incident = _incident(lessons_learnt="Existing lessons")
        service = IncidentService(db)
        service.get_incident = AsyncMock(return_value=incident)

        with _no_open_work():
            with pytest.raises(StateTransitionError) as exc_info:
                await service.update_incident(
                    5,
                    IncidentUpdate(status="closed", lessons_learnt=""),
                    user_id=7,
                    tenant_id=1,
                )

        assert exc_info.value.code == "MISSING_LESSONS_LEARNT"


class TestIncidentReopen:
    @pytest.mark.asyncio
    async def test_reopen_clears_stamps_and_audits_as_reopened(self, db):
        incident = _incident(
            status="closed",
            closed_at=datetime(2026, 3, 3, tzinfo=timezone.utc),
            closed_by_id=7,
        )
        service = IncidentService(db)
        service.get_incident = AsyncMock(return_value=incident)

        with (
            patch("src.domain.services.incident_service.record_audit_event", AsyncMock()) as audit,
            patch("src.domain.services.incident_service.invalidate_tenant_cache", AsyncMock()),
        ):
            await service.update_incident(5, IncidentUpdate(status="pending_review"), user_id=8, tenant_id=1)

        assert incident.status == "pending_review"
        assert incident.closed_at is None
        assert incident.closed_by_id is None
        assert audit.await_args.kwargs["event_type"] == "incident.reopened"

    @pytest.mark.asyncio
    async def test_closed_cannot_jump_straight_back_to_reported(self, db):
        incident = _incident(status="closed")
        service = IncidentService(db)
        service.get_incident = AsyncMock(return_value=incident)

        with pytest.raises(StateTransitionError):
            await service.update_incident(5, IncidentUpdate(status="reported"), user_id=8, tenant_id=1)


class TestRtaTransitions:
    @pytest.mark.asyncio
    async def test_rta_status_changes_are_no_longer_free(self, db):
        """PATCH used to accept any status; closed now only reopens one way."""
        rta = _rta(status="closed")
        service = RTAService(db)
        service.get_rta = AsyncMock(return_value=rta)

        with pytest.raises(StateTransitionError) as exc_info:
            await service.update_rta(9, RTAUpdate(status="pending_insurance"), user_id=2, tenant_id=1)

        assert exc_info.value.details["allowed"] == ["under_investigation"]
        assert rta.status == "closed"

    @pytest.mark.asyncio
    async def test_rta_close_gate_and_stamps(self, db):
        rta = _rta()
        service = RTAService(db)
        service.get_rta = AsyncMock(return_value=rta)

        with (
            _no_open_work(),
            patch("src.domain.services.rta_service.record_audit_event", AsyncMock()) as audit,
            patch("src.domain.services.rta_service.invalidate_tenant_cache", AsyncMock()),
        ):
            await service.update_rta(9, RTAUpdate(status="closed"), user_id=2, tenant_id=1)

        assert rta.status == "closed"
        assert rta.closed_at is not None
        assert audit.await_args.kwargs["event_type"] == "rta.closed"

    @pytest.mark.asyncio
    async def test_rta_reopen_returns_to_under_investigation(self, db):
        rta = _rta(status="closed", closed_at=datetime(2026, 3, 3, tzinfo=timezone.utc), closed_by_id=2)
        service = RTAService(db)
        service.get_rta = AsyncMock(return_value=rta)

        with (
            patch("src.domain.services.rta_service.record_audit_event", AsyncMock()) as audit,
            patch("src.domain.services.rta_service.invalidate_tenant_cache", AsyncMock()),
        ):
            await service.update_rta(9, RTAUpdate(status="under_investigation"), user_id=2, tenant_id=1)

        assert rta.closed_at is None
        assert rta.closed_by_id is None
        assert audit.await_args.kwargs["event_type"] == "rta.reopened"
