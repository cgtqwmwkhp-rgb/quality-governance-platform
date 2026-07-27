"""Regression suite: the read/validate paths and the write/close paths must agree.

Two P1 defects reached staging because a register's routes answered "yes" and
"here is what is left to do" while the write path answered something else
entirely for the same record and the same caller:

* An RTA whose ``tenant_id`` was NULL validated as closeable-but-for-lessons,
  then refused the close with ``OPEN_ACTIONS_REMAIN`` — naming work that did not
  exist, because the update route handed the gate the record's (absent) tenant
  while the validation route handed it the caller's.
* A near miss listed, opened and produced a closure checklist, then returned 404
  on PATCH, because the route's read helper exempted superusers from the tenant
  filter and the service's read did not.

These tests drive the real route functions rather than the services alone: both
defects lived in what the route chose to pass, so a test that calls the services
directly would have missed them.
"""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.api.routes.near_miss import get_near_miss as get_near_miss_route
from src.api.routes.near_miss import update_near_miss as update_near_miss_route
from src.api.routes.rtas import get_rta_closure_validation
from src.api.routes.rtas import update_rta as update_rta_route
from src.api.schemas.near_miss import NearMissUpdate
from src.api.schemas.rta import RTAUpdate
from src.domain.exceptions import StateTransitionError
from src.domain.services.case_closure import (
    CLOSURE_REASON_MISSING_LESSONS_LEARNT,
    CLOSURE_REASON_OPEN_ACTIONS_REMAIN,
    CLOSURE_REASON_TENANT_SCOPE_UNRESOLVED,
    CaseActionTally,
    CaseOpenWorkItem,
)

LESSONS = "Driver debriefed and route risk assessment reissued"


def _user(*, tenant_id: int | None = 1, is_superuser: bool = True):
    return SimpleNamespace(id=42, tenant_id=tenant_id, is_superuser=is_superuser)


def _rta(**overrides):
    defaults = {
        "id": 1,
        "tenant_id": 1,
        "reference_number": "RTA-2026-0001",
        "title": "Rear-end collision",
        "status": "under_investigation",
        "lessons_learnt": None,
        "closed_at": None,
        "closed_by_id": None,
        "updated_at": None,
        "updated_by_id": None,
        "created_at": datetime(2026, 1, 5, tzinfo=timezone.utc),
        "collision_date": datetime(2026, 1, 5, tzinfo=timezone.utc),
        "severity": "minor",
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _near_miss(**overrides):
    defaults = {
        "id": 1,
        "tenant_id": 1,
        "reference_number": "NM-2026-0001",
        "description": "Load swung close to a pedestrian route",
        "status": "UNDER_REVIEW",
        "lessons_learnt": None,
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
    return patch(
        "src.domain.services.case_closure.fetch_open_work_for_case",
        AsyncMock(return_value=([], CaseActionTally(total=0, complete=0, incomplete=0))),
    )


def _one_open_action():
    item = CaseOpenWorkItem(
        kind="rta_action",
        id=3,
        reference_number="RTA-ACT-3",
        title="Recover vehicle",
        status="in_progress",
        action_key="rta_action:3",
    )
    return patch(
        "src.domain.services.case_closure.fetch_open_work_for_case",
        AsyncMock(return_value=([item], CaseActionTally(total=1, complete=0, incomplete=1))),
    )


def _quiet_rta_side_effects():
    """Silence audit/cache/standards so assertions stay on the closure decision."""
    return (
        patch("src.domain.services.rta_service.record_audit_event", AsyncMock()),
        patch("src.domain.services.rta_service.invalidate_tenant_cache", AsyncMock()),
        patch("src.api.routes.rtas._trigger_operational_standards_assess", AsyncMock()),
    )


def _quiet_near_miss_side_effects():
    return (
        patch("src.domain.services.near_miss_service.record_audit_event", AsyncMock()),
        patch("src.domain.services.near_miss_service.invalidate_tenant_cache", AsyncMock()),
        patch("src.api.routes.near_miss._trigger_operational_standards_assess", AsyncMock()),
    )


async def _validation_outcome(rta, user, db):
    """``GET /rtas/{id}/closure-validation`` as an outcome we can compare."""
    try:
        payload = await get_rta_closure_validation(rta.id, db, user)
    except StateTransitionError as exc:
        return ("refused", exc.code)
    return ("ok", tuple(payload["reasons"]))


async def _close_outcome(rta, user, db, *, lessons):
    """``PATCH /rtas/{id}`` with a closing payload, as a comparable outcome."""
    try:
        await update_rta_route(
            rta.id,
            RTAUpdate(status="closed", lessons_learnt=lessons),
            db,
            user,
            request_id="req-agreement",
        )
    except StateTransitionError as exc:
        return ("refused", exc.code)
    return ("closed", ())


class TestValidationAndCloseAgree:
    """B-1: `…/closure-validation` and the close itself must not disagree."""

    @pytest.mark.asyncio
    async def test_tenantless_case_is_refused_identically_by_both_paths(self):
        """The staging case: RTA-2026-0001 with tenant_id NULL, superuser in tenant 1.

        Validation used to report only MISSING_LESSONS_LEARNT with zero open work,
        and the close then failed with OPEN_ACTIONS_REMAIN once lessons were given.
        """
        user = _user(tenant_id=1, is_superuser=True)
        patches = _quiet_rta_side_effects()

        with _no_open_work(), patches[0], patches[1], patches[2]:
            validation = await _validation_outcome(_rta(tenant_id=None), user, _db_returning(_rta(tenant_id=None)))
            close = await _close_outcome(
                _rta(tenant_id=None),
                user,
                _db_returning(_rta(tenant_id=None)),
                lessons=LESSONS,
            )

        assert validation == close
        assert validation == ("refused", CLOSURE_REASON_TENANT_SCOPE_UNRESOLVED)

    @pytest.mark.asyncio
    async def test_tenantless_case_never_blames_open_actions(self):
        """Telling an operator to finish actions that do not exist is unactionable."""
        user = _user(tenant_id=1, is_superuser=True)
        patches = _quiet_rta_side_effects()

        with _no_open_work(), patches[0], patches[1], patches[2]:
            _status, code = await _close_outcome(
                _rta(tenant_id=None),
                user,
                _db_returning(_rta(tenant_id=None)),
                lessons=LESSONS,
            )

        assert code != CLOSURE_REASON_OPEN_ACTIONS_REMAIN

    @pytest.mark.asyncio
    async def test_missing_lessons_is_reported_and_enforced_consistently(self):
        """Validation says lessons are the only blocker; the close agrees."""
        user = _user(tenant_id=1, is_superuser=True)
        patches = _quiet_rta_side_effects()

        with _no_open_work(), patches[0], patches[1], patches[2]:
            validation = await _validation_outcome(_rta(), user, _db_returning(_rta()))
            refused = await _close_outcome(_rta(), user, _db_returning(_rta()), lessons=None)
            accepted = await _close_outcome(_rta(), user, _db_returning(_rta()), lessons=LESSONS)

        assert validation == ("ok", (CLOSURE_REASON_MISSING_LESSONS_LEARNT,))
        assert refused == ("refused", CLOSURE_REASON_MISSING_LESSONS_LEARNT)
        assert accepted == ("closed", ())

    @pytest.mark.asyncio
    async def test_open_work_is_reported_and_enforced_consistently(self):
        """Lessons are already on the row, so open work is the only variable."""
        user = _user(tenant_id=1, is_superuser=True)
        stored = {"lessons_learnt": LESSONS}
        patches = _quiet_rta_side_effects()

        with _one_open_action(), patches[0], patches[1], patches[2]:
            validation = await _validation_outcome(_rta(**stored), user, _db_returning(_rta(**stored)))
            close = await _close_outcome(_rta(**stored), user, _db_returning(_rta(**stored)), lessons=LESSONS)

        assert validation == ("ok", (CLOSURE_REASON_OPEN_ACTIONS_REMAIN,))
        assert close == ("refused", CLOSURE_REASON_OPEN_ACTIONS_REMAIN)

    @pytest.mark.asyncio
    async def test_both_paths_probe_the_cases_tenant_not_the_callers(self):
        """A superuser closing another tenant's case must see that case's work."""
        user = _user(tenant_id=1, is_superuser=True)
        patches = _quiet_rta_side_effects()

        with _no_open_work() as probe, patches[0], patches[1], patches[2]:
            await _validation_outcome(_rta(tenant_id=7), user, _db_returning(_rta(tenant_id=7)))
            await _close_outcome(_rta(tenant_id=7), user, _db_returning(_rta(tenant_id=7)), lessons=LESSONS)

            probed_tenants = {call.kwargs["tenant_id"] for call in probe.call_args_list}

        assert probed_tenants == {7}

    @pytest.mark.asyncio
    async def test_cross_tenant_close_evicts_the_records_register_not_the_callers(self):
        """The stale list would otherwise be the one the record actually appears in."""
        user = _user(tenant_id=1, is_superuser=True)

        with (
            _no_open_work(),
            patch("src.domain.services.rta_service.record_audit_event", AsyncMock()),
            patch("src.domain.services.rta_service.invalidate_tenant_cache", AsyncMock()) as evict,
            patch("src.api.routes.rtas._trigger_operational_standards_assess", AsyncMock()),
        ):
            await _close_outcome(_rta(tenant_id=7), user, _db_returning(_rta(tenant_id=7)), lessons=LESSONS)

        assert evict.await_args.args[0] == 7


class TestNearMissReadWriteAgree:
    """B-2: whatever the register can open, the register must be able to save."""

    @pytest.mark.asyncio
    async def test_superuser_can_write_the_cross_tenant_record_it_can_read(self):
        """Read said 200 and write said 404 for the same id and the same caller."""
        user = _user(tenant_id=1, is_superuser=True)
        patches = _quiet_near_miss_side_effects()

        read = await get_near_miss_route(1, _db_returning(_near_miss(tenant_id=7)), user)

        with patches[0], patches[1], patches[2]:
            written = await update_near_miss_route(
                1,
                NearMissUpdate(description="Updated by a platform administrator"),
                _db_returning(_near_miss(tenant_id=7)),
                user,
                request_id="req-read-write",
            )

        assert read.reference_number == "NM-2026-0001"
        assert written.description == "Updated by a platform administrator"

    @pytest.mark.asyncio
    async def test_non_superuser_is_refused_by_both_paths(self):
        """Agreement must not be bought by dropping the tenant filter for everyone."""
        from fastapi import HTTPException

        user = _user(tenant_id=1, is_superuser=False)

        with pytest.raises(HTTPException) as read_exc:
            await get_near_miss_route(1, _db_returning(None), user)

        with pytest.raises(HTTPException) as write_exc:
            await update_near_miss_route(
                1,
                NearMissUpdate(description="should-not-apply"),
                _db_returning(None),
                user,
                request_id="req-denied",
            )

        assert read_exc.value.status_code == 404
        assert write_exc.value.status_code == 404

    @pytest.mark.asyncio
    async def test_close_reaches_the_gate_instead_of_returning_not_found(self):
        """The Close dialog's checklist is worthless if the close 404s."""
        user = _user(tenant_id=1, is_superuser=True)
        patches = _quiet_near_miss_side_effects()

        with _no_open_work(), patches[0], patches[1], patches[2]:
            with pytest.raises(StateTransitionError) as exc_info:
                await update_near_miss_route(
                    1,
                    NearMissUpdate(status="CLOSED"),
                    _db_returning(_near_miss(tenant_id=7, lessons_learnt=None)),
                    user,
                    request_id="req-close",
                )

        assert exc_info.value.code == CLOSURE_REASON_MISSING_LESSONS_LEARNT

    @pytest.mark.asyncio
    async def test_close_with_lessons_succeeds_for_a_readable_record(self):
        user = _user(tenant_id=1, is_superuser=True)
        near_miss = _near_miss(tenant_id=7)
        patches = _quiet_near_miss_side_effects()

        with _no_open_work(), patches[0], patches[1], patches[2]:
            await update_near_miss_route(
                1,
                NearMissUpdate(status="CLOSED", lessons_learnt=LESSONS),
                _db_returning(near_miss),
                user,
                request_id="req-close-ok",
            )

        assert near_miss.status == "CLOSED"
        assert near_miss.closed_at is not None
