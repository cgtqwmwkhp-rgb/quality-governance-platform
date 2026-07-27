"""Unit tests for the shared case closure gate (incident/complaint/near miss/RTA)."""

from __future__ import annotations

import inspect
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.domain.exceptions import StateTransitionError
from src.domain.services.case_closure import (
    CASE_TYPE_INCIDENT,
    CASE_TYPE_NEAR_MISS,
    CASE_TYPE_RTA,
    CLOSURE_REASON_MISSING_LESSONS_LEARNT,
    CLOSURE_REASON_OPEN_ACTIONS_REMAIN,
    CLOSURE_REASON_TENANT_SCOPE_UNRESOLVED,
    apply_close_stamps,
    assert_case_can_close,
    clear_close_stamps,
    evaluate_case_closure,
    is_closed_status,
    reopen_status_for,
    resolve_case_tenant_id,
    validation_to_payload,
)


def _row(**overrides):
    obj = MagicMock()
    for key, value in overrides.items():
        setattr(obj, key, value)
    return obj


def _native_action(**overrides):
    defaults = {
        "id": 12,
        "reference_number": "INC-ACT-12",
        "title": "Replace guard",
        "status": "in_progress",
        "tenant_id": 1,
        "created_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
    }
    defaults.update(overrides)
    return _row(**defaults)


def _capa(**overrides):
    defaults = {
        "id": 44,
        "reference_number": "CAPA-44",
        "title": "Retrain crew",
        "status": "in_progress",
        "tenant_id": 1,
    }
    defaults.update(overrides)
    return _row(**defaults)


def _db_with_queries(*row_lists):
    """AsyncMock db where each execute() returns the next list of scalar rows."""
    db = AsyncMock()
    results = []
    for rows in row_lists:
        result = MagicMock()
        result.scalars.return_value.all.return_value = rows
        result.scalars.return_value.first.return_value = rows[0] if rows else None
        results.append(result)
    db.execute = AsyncMock(side_effect=results)
    return db


def _case(**overrides):
    defaults = {
        "id": 5,
        "tenant_id": 1,
        "reference_number": "INC-5",
        "title": "Struck by",
        "status": "under_investigation",
        "lessons_learnt": "Toolbox talk delivered",
        "closed_at": None,
        "closed_by_id": None,
        "created_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


class TestEvaluateCaseClosure:
    @pytest.mark.asyncio
    async def test_clean_case_can_close(self):
        # native actions, CAPAs, linked investigation
        db = _db_with_queries([], [], [])

        validation = await evaluate_case_closure(db, case_type=CASE_TYPE_INCIDENT, case=_case(), tenant_id=1)

        assert validation.can_close is True
        assert validation.reasons == []
        assert validation.summary["actions_total"] == 0

    @pytest.mark.asyncio
    async def test_blank_lessons_block_closure(self):
        db = _db_with_queries([], [], [])

        validation = await evaluate_case_closure(
            db, case_type=CASE_TYPE_INCIDENT, case=_case(lessons_learnt="   "), tenant_id=1
        )

        assert validation.can_close is False
        assert validation.reasons == [CLOSURE_REASON_MISSING_LESSONS_LEARNT]

    @pytest.mark.asyncio
    async def test_incoming_lessons_override_the_stored_value(self):
        """A close request that supplies lessons passes even if the row is blank."""
        db = _db_with_queries([], [], [])

        validation = await evaluate_case_closure(
            db,
            case_type=CASE_TYPE_INCIDENT,
            case=_case(lessons_learnt=None),
            tenant_id=1,
            lessons_learnt="Learned something",
        )

        assert validation.can_close is True

    @pytest.mark.asyncio
    async def test_clearing_lessons_in_the_same_request_blocks_closure(self):
        db = _db_with_queries([], [], [])

        validation = await evaluate_case_closure(
            db,
            case_type=CASE_TYPE_INCIDENT,
            case=_case(lessons_learnt="Stored lessons"),
            tenant_id=1,
            lessons_learnt=None,
        )

        assert validation.can_close is False
        assert CLOSURE_REASON_MISSING_LESSONS_LEARNT in validation.reasons

    @pytest.mark.asyncio
    async def test_incomplete_native_action_blocks_closure(self):
        db = _db_with_queries([_native_action()], [], [])

        validation = await evaluate_case_closure(db, case_type=CASE_TYPE_INCIDENT, case=_case(), tenant_id=1)

        assert validation.can_close is False
        assert validation.reasons == [CLOSURE_REASON_OPEN_ACTIONS_REMAIN]
        assert validation.open_work[0].action_key == "incident_action:12"
        assert validation.summary["actions_incomplete"] == 1

    @pytest.mark.asyncio
    @pytest.mark.parametrize("done_status", ["completed", "cancelled", "verified", "COMPLETED"])
    async def test_done_native_statuses_do_not_block(self, done_status):
        db = _db_with_queries([_native_action(status=done_status)], [], [])

        validation = await evaluate_case_closure(db, case_type=CASE_TYPE_INCIDENT, case=_case(), tenant_id=1)

        assert validation.can_close is True
        assert validation.summary["actions_complete"] == 1

    @pytest.mark.asyncio
    async def test_unknown_native_status_fails_closed(self):
        """An unmapped status is live work: the gate must not wave it through."""
        db = _db_with_queries([_native_action(status="awaiting_parts")], [], [])

        validation = await evaluate_case_closure(db, case_type=CASE_TYPE_INCIDENT, case=_case(), tenant_id=1)

        assert validation.can_close is False

    @pytest.mark.asyncio
    async def test_open_capa_blocks_near_miss_closure(self):
        # Near misses have no native action table: CAPA probe, then investigation.
        db = _db_with_queries([_capa()], [])

        validation = await evaluate_case_closure(
            db,
            case_type=CASE_TYPE_NEAR_MISS,
            case=_case(status="UNDER_REVIEW"),
            tenant_id=1,
        )

        assert validation.can_close is False
        assert validation.open_work[0].action_key == "capa:44"

    @pytest.mark.asyncio
    async def test_closed_capa_does_not_block(self):
        db = _db_with_queries([_capa(status="closed")], [])

        validation = await evaluate_case_closure(
            db,
            case_type=CASE_TYPE_NEAR_MISS,
            case=_case(status="UNDER_REVIEW"),
            tenant_id=1,
        )

        assert validation.can_close is True

    @pytest.mark.asyncio
    async def test_single_probe_failure_still_reports_the_other_probe(self):
        """One broken probe must not silently report a clean close."""
        db = AsyncMock()
        capa_result = MagicMock()
        capa_result.scalars.return_value.all.return_value = [_capa()]
        investigation_result = MagicMock()
        investigation_result.scalars.return_value.first.return_value = None
        db.execute = AsyncMock(side_effect=[RuntimeError("actions table missing"), capa_result, investigation_result])

        validation = await evaluate_case_closure(
            db, case_type=CASE_TYPE_RTA, case=_case(status="under_investigation"), tenant_id=1
        )

        assert validation.can_close is False
        assert validation.open_work[0].kind == "capa_action"

    @pytest.mark.asyncio
    async def test_all_probes_failing_raises_rather_than_passing(self):
        db = AsyncMock()
        db.execute = AsyncMock(side_effect=RuntimeError("database down"))

        with pytest.raises(RuntimeError):
            await evaluate_case_closure(
                db, case_type=CASE_TYPE_RTA, case=_case(status="under_investigation"), tenant_id=1
            )


class TestAssertCaseCanClose:
    @pytest.mark.asyncio
    async def test_missing_lessons_raises_with_reason_code(self):
        db = _db_with_queries([], [], [])

        with pytest.raises(StateTransitionError) as exc_info:
            await assert_case_can_close(db, case_type=CASE_TYPE_INCIDENT, case=_case(lessons_learnt=""), tenant_id=1)

        err = exc_info.value
        assert err.code == CLOSURE_REASON_MISSING_LESSONS_LEARNT
        assert err.details["reasons"] == [CLOSURE_REASON_MISSING_LESSONS_LEARNT]

    @pytest.mark.asyncio
    async def test_open_actions_raise_with_open_work_payload(self):
        db = _db_with_queries([_native_action()], [], [])

        with pytest.raises(StateTransitionError) as exc_info:
            await assert_case_can_close(db, case_type=CASE_TYPE_INCIDENT, case=_case(), tenant_id=1)

        err = exc_info.value
        assert err.code == CLOSURE_REASON_OPEN_ACTIONS_REMAIN
        assert err.details["open_work_count"] == 1
        assert err.details["open_work"][0]["unblock_hint"].startswith("Complete or cancel")

    @pytest.mark.asyncio
    async def test_both_reasons_are_reported_together(self):
        db = _db_with_queries([_native_action()], [], [])

        with pytest.raises(StateTransitionError) as exc_info:
            await assert_case_can_close(db, case_type=CASE_TYPE_INCIDENT, case=_case(lessons_learnt=None), tenant_id=1)

        assert set(exc_info.value.details["reasons"]) == {
            CLOSURE_REASON_MISSING_LESSONS_LEARNT,
            CLOSURE_REASON_OPEN_ACTIONS_REMAIN,
        }


class TestTenantResolution:
    def test_scope_is_the_cases_own_tenant(self):
        assert resolve_case_tenant_id(_case(tenant_id=9)) == 9

    def test_signature_admits_no_caller_tenant(self):
        """Validation and enforcement cannot disagree on scope if neither can supply one."""
        assert list(inspect.signature(resolve_case_tenant_id).parameters) == ["case"]

    def test_refuses_to_probe_a_case_with_no_tenant(self):
        with pytest.raises(StateTransitionError) as exc_info:
            resolve_case_tenant_id(_case(tenant_id=None))

        err = exc_info.value
        assert err.code == CLOSURE_REASON_TENANT_SCOPE_UNRESOLVED
        assert err.details["reasons"] == [CLOSURE_REASON_TENANT_SCOPE_UNRESOLVED]

    def test_missing_tenant_is_not_reported_as_open_work(self):
        """The operator must be able to tell "no tenant" from "actions remain":
        the second is fixable from the Actions tab, the first is a corrupt row."""
        with pytest.raises(StateTransitionError) as exc_info:
            resolve_case_tenant_id(_case(tenant_id=None))

        assert exc_info.value.code != CLOSURE_REASON_OPEN_ACTIONS_REMAIN
        assert CLOSURE_REASON_OPEN_ACTIONS_REMAIN not in exc_info.value.details["reasons"]


class TestCloseStamps:
    def test_apply_sets_closed_at_and_closed_by(self):
        case = _case()

        changed = apply_close_stamps(case, user_id=3)

        assert case.closed_at is not None
        assert case.closed_by_id == 3
        assert set(changed) == {"closed_at", "closed_by_id"}

    def test_apply_preserves_an_existing_closed_at(self):
        original = datetime(2026, 2, 2, tzinfo=timezone.utc)
        case = _case(closed_at=original, closed_by_id=7)

        apply_close_stamps(case, user_id=3)

        assert case.closed_at == original
        assert case.closed_by_id == 7

    def test_clear_removes_both_stamps(self):
        case = _case(closed_at=datetime.now(timezone.utc), closed_by_id=3)

        changed = clear_close_stamps(case)

        assert case.closed_at is None
        assert case.closed_by_id is None
        assert set(changed) == {"closed_at", "closed_by_id"}


class TestStatusHelpers:
    def test_near_miss_closed_status_is_case_insensitive(self):
        assert is_closed_status(CASE_TYPE_NEAR_MISS, "CLOSED") is True
        assert is_closed_status(CASE_TYPE_NEAR_MISS, "closed") is True
        assert is_closed_status(CASE_TYPE_NEAR_MISS, "UNDER_REVIEW") is False

    def test_reopen_targets_match_the_locked_decisions(self):
        assert reopen_status_for(CASE_TYPE_INCIDENT) == "pending_review"
        assert reopen_status_for("complaint") == "under_investigation"
        assert reopen_status_for(CASE_TYPE_NEAR_MISS) == "UNDER_REVIEW"
        assert reopen_status_for(CASE_TYPE_RTA) == "under_investigation"


class TestValidationPayload:
    @pytest.mark.asyncio
    async def test_payload_shape_matches_the_response_schema(self):
        from src.api.schemas.case_closure import CaseClosureValidationResponse

        db = _db_with_queries([_native_action()], [], [])
        validation = await evaluate_case_closure(db, case_type=CASE_TYPE_INCIDENT, case=_case(), tenant_id=1)

        payload = validation_to_payload(validation)
        parsed = CaseClosureValidationResponse(**payload)

        assert parsed.can_close is False
        assert parsed.open_work_count == 1
        assert parsed.summary.target_status == "closed"
