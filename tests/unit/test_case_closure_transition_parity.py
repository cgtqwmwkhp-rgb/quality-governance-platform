"""Regression suite: ``…/closure-validation`` must account for transition legality.

B-3 on staging. A complaint sitting in ``received``:

1. ``GET /complaints/{id}/closure-validation`` answered 200 with
   ``can_close=false`` and ``reasons=["MISSING_LESSONS_LEARNT"]``.
2. The operator wrote lessons learnt, exactly as the Close dialog asked.
3. ``PATCH /complaints/{id}`` with ``status=closed`` refused with
   ``INVALID_STATE_TRANSITION`` — because ``received`` has no edge to ``closed``
   at all, so no amount of lessons learnt was ever going to help.

The validation endpoint judged lessons and open work only. It never asked the
register whether the status could move to closed in the first place, so it named
a blocker the operator could clear and stayed silent about the one they could not.

These tests drive the real route functions, and they assert on the *pair* of
outcomes rather than on either path alone: agreement between the read and the
write is the invariant that keeps being broken here.
"""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.api.routes.complaints import get_complaint_closure_validation
from src.api.routes.complaints import update_complaint as update_complaint_route
from src.api.routes.near_miss import get_near_miss_closure_validation
from src.api.routes.near_miss import update_near_miss as update_near_miss_route
from src.api.schemas.complaint import ComplaintUpdate
from src.api.schemas.near_miss import NearMissUpdate
from src.domain.exceptions import StateTransitionError
from src.domain.services.case_closure import (
    _TRANSITION_VALIDATOR_LOADERS,
    CASE_CONFIGS,
    CASE_TYPE_COMPLAINT,
    CASE_TYPE_INCIDENT,
    CASE_TYPE_NEAR_MISS,
    CASE_TYPE_RTA,
    CLOSURE_REASON_INVALID_STATE_TRANSITION,
    CLOSURE_REASON_MISSING_LESSONS_LEARNT,
    CaseActionTally,
    check_close_transition,
)

LESSONS = "Complaint handling script rewritten and the team rebriefed"


def _user(*, tenant_id: int | None = 1, is_superuser: bool = True):
    return SimpleNamespace(id=42, tenant_id=tenant_id, is_superuser=is_superuser)


def _complaint(**overrides):
    defaults = {
        "id": 1,
        "tenant_id": 1,
        "reference_number": "CMP-2026-0001",
        "title": "Repeated missed collections",
        "status": "received",
        "lessons_learnt": None,
        "owner_id": None,
        "closed_at": None,
        "closed_by_id": None,
        "updated_at": None,
        "updated_by_id": None,
        "first_response_at": None,
        "response_due_at": None,
        "response_sla_hours": None,
        "received_date": datetime(2026, 1, 4, tzinfo=timezone.utc),
        "created_at": datetime(2026, 1, 4, tzinfo=timezone.utc),
        "complainant_email": "resident@example.com",
        "priority": "medium",
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _near_miss(**overrides):
    defaults = {
        "id": 1,
        "tenant_id": 1,
        "reference_number": "NM-2026-0001",
        "description": "Load swung close to a pedestrian route",
        "status": "AWAITING_TRIAGE",
        "lessons_learnt": LESSONS,
        "closed_at": None,
        "closed_by_id": None,
        "assigned_at": None,
        "assigned_to_id": None,
        "updated_at": None,
        "updated_by_id": None,
        "contract": "C-1",
        "contract_id": None,
        "created_at": datetime(2026, 1, 6, tzinfo=timezone.utc),
        "event_date": datetime(2026, 1, 6, tzinfo=timezone.utc),
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _db_returning(row):
    """Session whose every query yields ``row`` (or nothing when ``row`` is None)."""
    result = MagicMock()
    result.scalar_one_or_none.return_value = row
    result.scalar_one.return_value = row
    result.scalars.return_value.all.return_value = []
    result.scalars.return_value.first.return_value = None

    db = AsyncMock()
    db.execute = AsyncMock(return_value=result)
    return db


def _no_open_work():
    """Isolate the transition question from the open-work question."""
    return patch(
        "src.domain.services.case_closure.fetch_open_work_for_case",
        AsyncMock(return_value=([], CaseActionTally(total=0, complete=0, incomplete=0))),
    )


def _quiet_complaint_side_effects():
    return (
        patch("src.domain.services.complaint_service.record_audit_event", AsyncMock()),
        patch("src.domain.services.complaint_service.invalidate_tenant_cache", AsyncMock()),
        patch("src.api.routes.complaints._trigger_operational_standards_assess", AsyncMock()),
    )


def _quiet_near_miss_side_effects():
    return (
        patch("src.domain.services.near_miss_service.record_audit_event", AsyncMock()),
        patch("src.domain.services.near_miss_service.invalidate_tenant_cache", AsyncMock()),
        patch("src.api.routes.near_miss._trigger_operational_standards_assess", AsyncMock()),
    )


async def _complaint_validation(complaint, user):
    """``GET /complaints/{id}/closure-validation`` as a comparable outcome."""
    try:
        payload = await get_complaint_closure_validation(complaint.id, _db_returning(complaint), user)
    except StateTransitionError as exc:
        return ("refused", exc.code)
    return ("ok", tuple(payload["reasons"]))


async def _complaint_close(complaint, user, *, lessons):
    """``PATCH /complaints/{id}`` with a closing payload, as a comparable outcome."""
    try:
        await update_complaint_route(
            complaint.id,
            ComplaintUpdate(status="closed", lessons_learnt=lessons),
            _db_returning(complaint),
            user,
            request_id="req-transition",
        )
    except StateTransitionError as exc:
        return ("refused", exc.code)
    return ("closed", ())


class TestValidationAndCloseAgreeOnTransitionLegality:
    """B-3: the dialog's readiness read must answer "will closing succeed?"."""

    @pytest.mark.asyncio
    async def test_illegal_transition_is_reported_and_enforced_under_one_code(self):
        """The staging case: CMP-2026-0001 in `received`, lessons already supplied.

        Validation used to report no blocker at all once lessons were present,
        and the close then refused with INVALID_STATE_TRANSITION.
        """
        user = _user()
        stored = {"status": "received", "lessons_learnt": LESSONS}
        patches = _quiet_complaint_side_effects()

        with _no_open_work(), patches[0], patches[1], patches[2]:
            validation = await _complaint_validation(_complaint(**stored), user)
            close = await _complaint_close(_complaint(**stored), user, lessons=LESSONS)

        assert validation == ("ok", (CLOSURE_REASON_INVALID_STATE_TRANSITION,))
        assert close == ("refused", CLOSURE_REASON_INVALID_STATE_TRANSITION)

    @pytest.mark.asyncio
    async def test_supplying_lessons_learnt_does_not_unblock_an_illegal_transition(self):
        """The operator did as instructed and was no better off. Both paths must say so."""
        user = _user()
        patches = _quiet_complaint_side_effects()

        with _no_open_work(), patches[0], patches[1], patches[2]:
            before = await _complaint_validation(_complaint(lessons_learnt=None), user)
            after = await _complaint_validation(_complaint(lessons_learnt=LESSONS), user)
            close = await _complaint_close(_complaint(lessons_learnt=None), user, lessons=LESSONS)

        assert CLOSURE_REASON_INVALID_STATE_TRANSITION in before[1]
        assert CLOSURE_REASON_MISSING_LESSONS_LEARNT in before[1]
        # Lessons clear one reason and leave the one that actually blocks the close.
        assert after == ("ok", (CLOSURE_REASON_INVALID_STATE_TRANSITION,))
        assert close == ("refused", CLOSURE_REASON_INVALID_STATE_TRANSITION)

    @pytest.mark.asyncio
    async def test_validation_names_the_next_legal_step_instead_of_a_bare_failure(self):
        """ "Not yet closable, and here is the step that moves you on."""
        user = _user()

        with _no_open_work():
            payload = await get_complaint_closure_validation(
                1,
                _db_returning(_complaint(lessons_learnt=LESSONS)),
                user,
            )

        assert payload["can_close"] is False
        assert payload["transition_allowed"] is False
        assert payload["allowed_next_statuses"] == ["acknowledged", "escalated"]

    @pytest.mark.asyncio
    async def test_a_legal_transition_is_reported_clean_and_permitted(self):
        """Agreement must not be bought by refusing every close."""
        user = _user()
        closeable = _complaint(status="resolved", lessons_learnt=LESSONS)
        patches = _quiet_complaint_side_effects()

        with _no_open_work(), patches[0], patches[1], patches[2]:
            validation = await _complaint_validation(closeable, user)
            payload = await get_complaint_closure_validation(1, _db_returning(closeable), user)
            close = await _complaint_close(_complaint(status="resolved"), user, lessons=LESSONS)

        assert validation == ("ok", ())
        assert payload["transition_allowed"] is True
        assert payload["allowed_next_statuses"] == []
        assert close == ("closed", ())

    @pytest.mark.asyncio
    async def test_near_miss_dead_end_status_is_refused_by_both_paths(self):
        """A status with no edges at all is honest about having no next step."""
        user = _user()
        patches = _quiet_near_miss_side_effects()

        with _no_open_work():
            payload = await get_near_miss_closure_validation(1, _db_returning(_near_miss()), user)

            with patches[0], patches[1], patches[2]:
                with pytest.raises(StateTransitionError) as exc_info:
                    await update_near_miss_route(
                        1,
                        NearMissUpdate(status="CLOSED", lessons_learnt=LESSONS),
                        _db_returning(_near_miss()),
                        user,
                        request_id="req-dead-end",
                    )

        assert payload["can_close"] is False
        assert payload["reasons"] == [CLOSURE_REASON_INVALID_STATE_TRANSITION]
        assert payload["allowed_next_statuses"] == []
        assert exc_info.value.code == CLOSURE_REASON_INVALID_STATE_TRANSITION


class TestTransitionVerdictComesFromTheRegister:
    """The gate must not hold a second copy of any register's lifecycle map."""

    @pytest.mark.parametrize(
        "case_type, statuses",
        [
            (
                CASE_TYPE_INCIDENT,
                [
                    "reported",
                    "under_investigation",
                    "pending_actions",
                    "actions_in_progress",
                    "pending_review",
                    "closed",
                ],
            ),
            (
                CASE_TYPE_COMPLAINT,
                [
                    "received",
                    "acknowledged",
                    "under_investigation",
                    "pending_response",
                    "awaiting_customer",
                    "resolved",
                    "escalated",
                    "closed",
                ],
            ),
            (
                CASE_TYPE_NEAR_MISS,
                ["REPORTED", "UNDER_REVIEW", "ACTION_REQUIRED", "IN_PROGRESS", "CLOSED", "AWAITING_TRIAGE"],
            ),
            (
                CASE_TYPE_RTA,
                ["reported", "under_investigation", "pending_insurance", "pending_actions", "closed"],
            ),
        ],
    )
    def test_every_status_matches_the_registers_own_validator(self, case_type, statuses):
        """Whatever the write path would do with status → closed, the gate agrees."""
        validator = _TRANSITION_VALIDATOR_LOADERS[case_type]()
        closed_status = CASE_CONFIGS[case_type].closed_status

        for status in statuses:
            try:
                validator(status, closed_status)
            except StateTransitionError:
                write_path_allows = False
            else:
                write_path_allows = True

            assert (
                check_close_transition(case_type, status).allowed is write_path_allows
            ), f"{case_type} '{status}': gate and write path disagree on the move to {closed_status}"

    def test_actions_in_progress_incident_cannot_close_and_says_where_to_go(self):
        """A register where the illegal edge is not the initial state either."""
        check = check_close_transition(CASE_TYPE_INCIDENT, "actions_in_progress")

        assert check.allowed is False
        assert check.allowed_next_statuses == ["pending_actions", "pending_review"]

    def test_an_already_closed_case_follows_its_own_registers_same_status_rule(self):
        """Three registers treat status → same status as a no-op; complaints do not.

        That asymmetry is the write path's, not the gate's: ``PATCH`` a closed
        complaint with ``status=closed`` and ``validate_complaint_transition``
        refuses it before the gate is ever consulted. Mirroring it here is the
        whole point — the gate must report what the close will actually do, not
        a tidier rule of its own invention.
        """
        assert check_close_transition(CASE_TYPE_INCIDENT, "closed").allowed is True
        assert check_close_transition(CASE_TYPE_RTA, "closed").allowed is True
        assert check_close_transition(CASE_TYPE_NEAR_MISS, "CLOSED").allowed is True

        closed_complaint = check_close_transition(CASE_TYPE_COMPLAINT, "closed")
        assert closed_complaint.allowed is False
        assert closed_complaint.allowed_next_statuses == ["under_investigation"]
