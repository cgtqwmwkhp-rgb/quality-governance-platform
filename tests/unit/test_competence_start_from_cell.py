"""CB-UI-3: start a family demonstration from a plant board cell.

The claims under test are the ones a plant cell could get wrong once it becomes
a button, and the two the board would then report dishonestly:

* a **bound** cell starts the mode that is bound, on the bound template, through
  the one create path that leads to a demonstration — not a second execute
  shell, and not a third mode;
* the **assessor gate** holds server-side wherever the run is created: a person
  cannot assess themselves, and cannot assess a characteristic PAMS has not
  issued *them*. Where issuance cannot be proven at all the gate refuses rather
  than assumes;
* an **unbound** cell is startable in no mode, and says the characteristic has
  no family template yet — which is a gap in QGP's mapping, not a failure
  against the person on the row;
* **a pass writes no PAMS**, and a fail still opens the CB-PR4 revoke change
  request rather than a new channel.
"""

from __future__ import annotations

import ast
import types
from datetime import datetime, timezone
from pathlib import Path
from typing import get_args
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from src.api.routes import workforce_competence_board as board_routes
from src.api.routes.assessments import complete_assessment, create_assessment_run
from src.api.schemas.assessment import AssessmentPlantEvidence, AssessmentRunCreate
from src.core.config import settings
from src.domain.error_codes import ErrorCode
from src.domain.exceptions import AuthorizationError, BadRequestError
from src.domain.models.assessment import AssessmentRun, AssessmentStatus, CompetencyVerdict
from src.domain.models.audit import AuditTemplate
from src.domain.models.competence_assessment_bind import BIND_MODES, CompetenceAssessmentBind
from src.domain.models.competence_change_request import CompetenceChangeRequest
from src.domain.models.competence_demonstration import CompetenceDemonstration
from src.domain.models.engineer import CompetencyLifecycleState, Engineer
from src.domain.models.pams_cache import PamsCompetenceRow
from src.domain.services import competence_family_start_service as start_service
from src.domain.services.competence_family_start_service import (
    ASSESSOR_HAS_NO_EMPLOYEE_RECORD,
    ASSESSOR_IS_THE_ENGINEER,
    ASSESSOR_SNAPSHOT_MISSING,
    NO_BIND_FOR_CHARACTERISTIC,
    NO_BIND_FOR_MODE,
    PLANT_EVIDENCE_MAX_LEN,
    bound_modes_by_characteristic,
    check_assessor_gate_async,
    enforce_bound_template_assessor_gate_async,
    normalise_plant_evidence,
    resolve_startable_bind_async,
)

# One session double in the tree: the CB-PR4/CB-UI-2 fake already dispatches
# ``scalars`` on the selected entity and refuses operators it cannot honestly
# evaluate, which is exactly what the gate's queries need.
from tests.unit.test_competence_assessment_overlay import (
    _assert_no_pams_write,
    _FakeDb,
    _forbid_pams_writes,
    _patch_complete_assessment,
    _published_template,
)

TENANT = 1
#: The engineer being assessed.
ENGINEER_ID = 9
#: The assessor's own employee record, and the user account behind it.
ASSESSOR_ENGINEER_ID = 4
ASSESSOR_USER_ID = 42
FIELD_TEMPLATE_ID = 8
INDUCTION_TEMPLATE_ID = 12
CHARACTERISTIC = "COUNTERBALANCE_FLT"
UNBOUND_CHARACTERISTIC = "SCISSOR_LIFT"

NOW = datetime(2026, 9, 3, 10, 0)

REPO_ROOT = Path(__file__).resolve().parents[2]
MIGRATION_PATH = REPO_ROOT / "alembic/versions/20260903_assessment_plant_evidence.py"


# ---------------------------------------------------------------- fixtures


class _StartDb(_FakeDb):
    """``_FakeDb`` plus the column defaults an ``AssessmentRun`` INSERT would fill.

    ``_FakeDb.flush`` stamps an integer id, which is right for every other table
    in this area and wrong for ``assessment_runs`` — its primary key is a uuid
    string and ``AssessmentRunResponse.id`` is typed ``str``. Filling the run's
    server-side defaults here keeps the route test running the *real*
    serializer rather than a patched stand-in, which is the part that would
    quietly stop echoing ``plant_evidence``.
    """

    async def flush(self) -> None:
        for index, obj in enumerate(self.added):
            if isinstance(obj, AssessmentRun) and obj.id is None:
                obj.id = f"asm-run-cb-ui-3-{index}"
                obj.template_version = 1
                obj.created_at = NOW
                obj.updated_at = NOW
        await super().flush()


def _bind(*, characteristic=CHARACTERISTIC, template_id=FIELD_TEMPLATE_ID, mode="field", bind_id=3, tenant_id=TENANT):
    return CompetenceAssessmentBind(
        id=bind_id,
        tenant_id=tenant_id,
        template_id=template_id,
        characteristic_key=characteristic,
        mode=mode,
        interval_days=None,
        created_at=NOW,
    )


def _engineer(*, engineer_id=ENGINEER_ID, user_id=None, tenant_id=TENANT):
    """The engineer being assessed has no linked user account by default.

    That is the realistic shape for a plant technician on the PAMS board, and
    it is the case that makes the self-assessment check compare employee
    records rather than user ids.
    """
    return Engineer(id=engineer_id, tenant_id=tenant_id, user_id=user_id)


def _assessor_engineer(*, engineer_id=ASSESSOR_ENGINEER_ID, user_id=ASSESSOR_USER_ID, tenant_id=TENANT):
    return Engineer(id=engineer_id, tenant_id=tenant_id, user_id=user_id)


def _issued_row(*, engineer_id, characteristic):
    return PamsCompetenceRow(snapshot_id=1, engineer_id=engineer_id, characteristic_key=characteristic)


def _snapshot():
    return types.SimpleNamespace(
        id=1,
        status="ready",
        source_name="vw_plantex_engineercompetence",
        row_count=2,
        completed_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )


def _patch_snapshot(monkeypatch, rows, *, snapshot=True):
    """Point the gate at a snapshot without opening a PAMS connection."""
    monkeypatch.setattr(
        start_service,
        "load_current_snapshot_async",
        AsyncMock(return_value=(_snapshot() if snapshot else None, list(rows))),
    )


def _patch_create_collaborators(monkeypatch, *, references=("ASM-2026-0500",)):
    """Everything ``create_assessment_run`` needs that is not the gate.

    The gate itself is deliberately **not** patched: it is the subject.
    """
    reference_iter = iter(references)
    monkeypatch.setattr(
        "src.api.routes.assessments._generate_assessment_reference_number",
        AsyncMock(side_effect=lambda _db: next(reference_iter)),
    )
    monkeypatch.setattr(
        "src.api.routes.assessments.GovernanceService.validate_supervisor",
        AsyncMock(return_value={"valid": True, "reason": None}),
    )
    monkeypatch.setattr(
        "src.api.routes.assessments.GovernanceService.check_template_approval",
        AsyncMock(return_value={"approved": True, "reason": None}),
    )


def _user(user_id=ASSESSOR_USER_ID, tenant_id=TENANT):
    return types.SimpleNamespace(id=user_id, tenant_id=tenant_id, roles=[], is_superuser=False)


def _startable_db(*, modes=("field",), engineer_user_id=None, execute_results=()):
    binds = []
    for index, mode in enumerate(modes):
        template_id = FIELD_TEMPLATE_ID if mode == "field" else INDUCTION_TEMPLATE_ID
        binds.append(_bind(template_id=template_id, mode=mode, bind_id=3 + index))
    return _StartDb(
        execute_results=execute_results,
        rows={
            AuditTemplate: [
                _published_template(template_id=FIELD_TEMPLATE_ID),
                _published_template(template_id=INDUCTION_TEMPLATE_ID),
            ],
            CompetenceAssessmentBind: binds,
            Engineer: [_engineer(user_id=engineer_user_id), _assessor_engineer()],
        },
    )


# ------------------------------------------------- AC-01 bound cell starts


@pytest.mark.asyncio
async def test_bound_cell_starts_the_field_assessment_on_the_bound_template(monkeypatch):
    monkeypatch.setattr(settings, "competence_board_enabled", True)
    _forbid_pams_writes(monkeypatch)
    _patch_create_collaborators(monkeypatch)
    db = _startable_db()
    _patch_snapshot(monkeypatch, [_issued_row(engineer_id=ASSESSOR_ENGINEER_ID, characteristic=CHARACTERISTIC)])

    result = await board_routes.start_competence_assessment(
        payload=board_routes.CompetenceAssessmentStartCreate(
            engineer_id=ENGINEER_ID,
            characteristic_key=CHARACTERISTIC,
            mode="field",
        ),
        db=db,
        current_user=_user(),
    )

    assert result.template_id == FIELD_TEMPLATE_ID
    assert result.characteristic_key == CHARACTERISTIC
    assert result.mode == "field"
    assert result.engineer_id == ENGINEER_ID
    assert result.status == AssessmentStatus.DRAFT.value
    assert result.reference_number == "ASM-2026-0500"

    runs = db.added_of(AssessmentRun)
    assert len(runs) == 1
    # The assessor is the run's supervisor, which is what the demonstration
    # records as ``assessed_by_id`` when the run completes.
    assert runs[0].supervisor_id == ASSESSOR_USER_ID
    assert runs[0].engineer_id == ENGINEER_ID
    assert CHARACTERISTIC in (runs[0].title or "")
    _assert_no_pams_write(db)


@pytest.mark.asyncio
async def test_induction_starts_only_when_that_mode_is_bound(monkeypatch):
    monkeypatch.setattr(settings, "competence_board_enabled", True)
    _patch_create_collaborators(monkeypatch)
    _patch_snapshot(monkeypatch, [_issued_row(engineer_id=ASSESSOR_ENGINEER_ID, characteristic=CHARACTERISTIC)])

    both = _startable_db(modes=("field", "induction"))
    result = await board_routes.start_competence_assessment(
        payload=board_routes.CompetenceAssessmentStartCreate(
            engineer_id=ENGINEER_ID,
            characteristic_key=CHARACTERISTIC,
            mode="induction",
        ),
        db=both,
        current_user=_user(),
    )
    assert result.template_id == INDUCTION_TEMPLATE_ID
    assert result.mode == "induction"

    field_only = _startable_db(modes=("field",))
    with pytest.raises(BadRequestError) as exc_info:
        await board_routes.start_competence_assessment(
            payload=board_routes.CompetenceAssessmentStartCreate(
                engineer_id=ENGINEER_ID,
                characteristic_key=CHARACTERISTIC,
                mode="induction",
            ),
            db=field_only,
            current_user=_user(),
        )
    # The sentence must not claim the characteristic is unmapped: it is mapped,
    # and it is the mode that is missing. It also names the mode that *is*
    # bound, so the reader knows which half of the pair to go and add.
    message = str(exc_info.value)
    assert message == NO_BIND_FOR_MODE.format(characteristic=CHARACTERISTIC, mode="induction", bound="field")
    assert NO_BIND_FOR_CHARACTERISTIC.format(characteristic=CHARACTERISTIC) not in message
    assert field_only.added_of(AssessmentRun) == []


def test_there_is_no_third_mode():
    """The wire mode is the bind's mode. CB-UI-3 invents nothing."""
    assert set(get_args(board_routes.BindMode)) == set(BIND_MODES) == {"field", "induction"}
    assert set(get_args(board_routes.CompetenceAssessmentStartCreate.model_fields["mode"].annotation)) == set(
        BIND_MODES
    )


@pytest.mark.asyncio
async def test_start_is_refused_when_the_person_has_no_employee_record(monkeypatch):
    """An unmapped PAMS row has no engineer for a demonstration to attach to."""
    monkeypatch.setattr(settings, "competence_board_enabled", True)
    _patch_create_collaborators(monkeypatch)
    _patch_snapshot(monkeypatch, [_issued_row(engineer_id=ASSESSOR_ENGINEER_ID, characteristic=CHARACTERISTIC)])
    db = _startable_db()

    with pytest.raises(HTTPException) as exc_info:
        await board_routes.start_competence_assessment(
            payload=board_routes.CompetenceAssessmentStartCreate(
                engineer_id=987654,
                characteristic_key=CHARACTERISTIC,
            ),
            db=db,
            current_user=_user(),
        )

    assert exc_info.value.status_code == 400
    assert "no QGP employee record" in exc_info.value.detail
    assert db.added_of(AssessmentRun) == []


# ------------------------------------------------------- AC-02 assessor gate


@pytest.mark.asyncio
async def test_the_assessor_cannot_be_the_engineer_being_assessed(monkeypatch):
    monkeypatch.setattr(settings, "competence_board_enabled", True)
    _patch_create_collaborators(monkeypatch)
    # Issued on the characteristic, so this refusal is about *who*, not *what*.
    _patch_snapshot(monkeypatch, [_issued_row(engineer_id=ASSESSOR_ENGINEER_ID, characteristic=CHARACTERISTIC)])
    db = _startable_db()

    with pytest.raises(AuthorizationError) as exc_info:
        await board_routes.start_competence_assessment(
            payload=board_routes.CompetenceAssessmentStartCreate(
                engineer_id=ASSESSOR_ENGINEER_ID,
                characteristic_key=CHARACTERISTIC,
            ),
            db=db,
            current_user=_user(),
        )

    assert ASSESSOR_IS_THE_ENGINEER in str(exc_info.value)
    assert exc_info.value.http_status == 403
    assert exc_info.value.details["characteristic_key"] == CHARACTERISTIC
    assert db.added_of(AssessmentRun) == []


@pytest.mark.asyncio
async def test_a_gate_refusal_is_coded_so_the_client_can_render_its_sentence(monkeypatch):
    """403 is several failures wearing one status code, and this is one of them.

    The frontend interceptor rewrites an uncoded 403 to "You don't have
    permission to perform this action.", which tells an assessor standing at the
    machine none of the four things the gate actually decided and implies an
    administrator could grant something. The code is what lets the client keep
    the server's sentence, so it is asserted here rather than left to the UI.

    It must not be ``COMPETENCY_GATE_BLOCKED``: that code means the *engineer*
    is not competent for the asset type, and two execution screens already
    branch on it to explain the subject's gap. This refusal is about the viewer.
    """
    monkeypatch.setattr(settings, "competence_board_enabled", True)
    _patch_create_collaborators(monkeypatch)
    _patch_snapshot(monkeypatch, [_issued_row(engineer_id=ASSESSOR_ENGINEER_ID, characteristic=CHARACTERISTIC)])

    with pytest.raises(AuthorizationError) as exc_info:
        await board_routes.start_competence_assessment(
            payload=board_routes.CompetenceAssessmentStartCreate(
                engineer_id=ASSESSOR_ENGINEER_ID,
                characteristic_key=CHARACTERISTIC,
            ),
            db=_startable_db(),
            current_user=_user(),
        )

    assert exc_info.value.code == ErrorCode.ASSESSOR_NOT_ELIGIBLE.value
    assert exc_info.value.code == "ASSESSOR_NOT_ELIGIBLE"
    assert exc_info.value.code != ErrorCode.COMPETENCY_GATE_BLOCKED.value
    # The coded refusal must still carry the prose; a code with a generic
    # message would move the problem rather than fix it.
    assert ASSESSOR_IS_THE_ENGINEER in exc_info.value.message


@pytest.mark.asyncio
async def test_the_gate_refuses_self_assessment_without_help_from_validate_supervisor(monkeypatch):
    """The rule is self-contained, and it compares employee records.

    ``GovernanceService.validate_supervisor`` already refuses self-assessment,
    by comparing ``engineer.user_id`` to the supervisor's user id. This asserts
    the family gate reaches the same answer on its own rather than inheriting
    it, so relaxing or reordering that check cannot quietly make a plant cell
    self-assessable — and it compares the *employee records*, which is the
    identity a PAMS snapshot row and a demonstration are both keyed on.
    """
    monkeypatch.setattr(settings, "competence_board_enabled", True)
    _patch_snapshot(monkeypatch, [_issued_row(engineer_id=ASSESSOR_ENGINEER_ID, characteristic=CHARACTERISTIC)])
    db = _StartDb(rows={CompetenceAssessmentBind: [_bind()], Engineer: [_assessor_engineer()]})

    gate = await check_assessor_gate_async(
        db,
        tenant_id=TENANT,
        assessor_user_id=ASSESSOR_USER_ID,
        engineer_id=ASSESSOR_ENGINEER_ID,
        characteristic_key=CHARACTERISTIC,
    )

    assert gate.allowed is False
    assert gate.reason == ASSESSOR_IS_THE_ENGINEER
    assert gate.assessor_engineer_id == ASSESSOR_ENGINEER_ID


@pytest.mark.asyncio
async def test_an_assessor_pams_has_not_issued_is_refused(monkeypatch):
    monkeypatch.setattr(settings, "competence_board_enabled", True)
    _patch_create_collaborators(monkeypatch)
    # The snapshot holds the assessor — on a *different* characteristic.
    _patch_snapshot(
        monkeypatch,
        [
            _issued_row(engineer_id=ASSESSOR_ENGINEER_ID, characteristic="TELEHANDLER"),
            _issued_row(engineer_id=ENGINEER_ID, characteristic=CHARACTERISTIC),
        ],
    )
    db = _startable_db()

    with pytest.raises(AuthorizationError) as exc_info:
        await board_routes.start_competence_assessment(
            payload=board_routes.CompetenceAssessmentStartCreate(
                engineer_id=ENGINEER_ID,
                characteristic_key=CHARACTERISTIC,
            ),
            db=db,
            current_user=_user(),
        )

    message = str(exc_info.value)
    assert CHARACTERISTIC in message
    assert "PAMS has not issued you" in message
    # The engineer being assessed *is* issued; that is not the assessor's claim.
    assert db.added_of(AssessmentRun) == []
    _assert_no_pams_write(db)


@pytest.mark.asyncio
async def test_the_gate_fails_closed_when_issuance_cannot_be_proven(monkeypatch):
    """No employee record and no snapshot are refusals, not empty results."""
    monkeypatch.setattr(settings, "competence_board_enabled", True)

    no_record = _StartDb(rows={CompetenceAssessmentBind: [_bind()], Engineer: [_engineer()]})
    _patch_snapshot(monkeypatch, [_issued_row(engineer_id=ASSESSOR_ENGINEER_ID, characteristic=CHARACTERISTIC)])
    gate = await check_assessor_gate_async(
        db=no_record,
        tenant_id=TENANT,
        assessor_user_id=ASSESSOR_USER_ID,
        engineer_id=ENGINEER_ID,
        characteristic_key=CHARACTERISTIC,
    )
    assert gate.allowed is False
    assert gate.reason == ASSESSOR_HAS_NO_EMPLOYEE_RECORD
    assert gate.assessor_engineer_id is None

    no_snapshot = _StartDb(rows={CompetenceAssessmentBind: [_bind()], Engineer: [_assessor_engineer()]})
    _patch_snapshot(monkeypatch, [], snapshot=False)
    gate = await check_assessor_gate_async(
        db=no_snapshot,
        tenant_id=TENANT,
        assessor_user_id=ASSESSOR_USER_ID,
        engineer_id=ENGINEER_ID,
        characteristic_key=CHARACTERISTIC,
    )
    assert gate.allowed is False
    assert gate.reason == ASSESSOR_SNAPSHOT_MISSING

    # A snapshot that exists but holds nothing for them is a different fact and
    # still a refusal — never "issued because we found no contradiction".
    _patch_snapshot(monkeypatch, [])
    empty = _StartDb(rows={CompetenceAssessmentBind: [_bind()], Engineer: [_assessor_engineer()]})
    gate = await check_assessor_gate_async(
        db=empty,
        tenant_id=TENANT,
        assessor_user_id=ASSESSOR_USER_ID,
        engineer_id=ENGINEER_ID,
        characteristic_key=CHARACTERISTIC,
    )
    assert gate.allowed is False
    assert "PAMS has not issued you" in (gate.reason or "")


@pytest.mark.asyncio
async def test_the_gate_is_tenant_scoped(monkeypatch):
    """An assessor whose employee record belongs to another tenant is not one here."""
    monkeypatch.setattr(settings, "competence_board_enabled", True)
    _patch_snapshot(monkeypatch, [_issued_row(engineer_id=ASSESSOR_ENGINEER_ID, characteristic=CHARACTERISTIC)])
    db = _StartDb(rows={Engineer: [_assessor_engineer(tenant_id=2)]})

    gate = await check_assessor_gate_async(
        db,
        tenant_id=TENANT,
        assessor_user_id=ASSESSOR_USER_ID,
        engineer_id=ENGINEER_ID,
        characteristic_key=CHARACTERISTIC,
    )
    assert gate.allowed is False
    assert gate.reason == ASSESSOR_HAS_NO_EMPLOYEE_RECORD


# ------------------------- AC-03 the gate cannot be walked around


@pytest.mark.asyncio
async def test_posting_the_bound_template_directly_hits_the_same_gate(monkeypatch):
    """The generic create route is not a way in.

    Gating only the board's start endpoint would leave ``POST /api/v1/assessments/``
    accepting a bound ``template_id`` from anyone who could read one, and its
    completion writes the demonstration all the same.
    """
    monkeypatch.setattr(settings, "competence_board_enabled", True)
    _patch_create_collaborators(monkeypatch)
    _patch_snapshot(monkeypatch, [_issued_row(engineer_id=ASSESSOR_ENGINEER_ID, characteristic="TELEHANDLER")])
    db = _startable_db()

    with pytest.raises(AuthorizationError):
        await create_assessment_run(
            AssessmentRunCreate(template_id=FIELD_TEMPLATE_ID, engineer_id=ENGINEER_ID),
            db,
            _user(),
        )

    assert db.added_of(AssessmentRun) == []


@pytest.mark.asyncio
async def test_an_unbound_template_is_not_gated(monkeypatch):
    """A run that will never write a demonstration gets no new rules."""
    monkeypatch.setattr(settings, "competence_board_enabled", True)
    db = _StartDb(rows={CompetenceAssessmentBind: []})

    def _explode(*_args, **_kwargs):
        raise AssertionError("an unbound template must not consult the PAMS snapshot")

    monkeypatch.setattr(start_service, "load_current_snapshot_async", _explode)

    assert (
        await enforce_bound_template_assessor_gate_async(
            db,
            tenant_id=TENANT,
            assessor_user_id=ASSESSOR_USER_ID,
            engineer_id=ENGINEER_ID,
            template_id=FIELD_TEMPLATE_ID,
        )
        is None
    )


@pytest.mark.asyncio
async def test_the_gate_is_inert_while_the_board_flag_is_off(monkeypatch):
    """Flag off is exactly the pre-CB-UI-3 behaviour, binds or no binds."""
    monkeypatch.setattr(settings, "competence_board_enabled", False)
    db = _StartDb(rows={CompetenceAssessmentBind: [_bind()], Engineer: [_engineer()]})

    assert (
        await enforce_bound_template_assessor_gate_async(
            db,
            tenant_id=TENANT,
            assessor_user_id=ASSESSOR_USER_ID,
            engineer_id=ENGINEER_ID,
            template_id=FIELD_TEMPLATE_ID,
        )
        is None
    )
    # Not even the bind lookup runs, so the flag is a real kill and not a
    # filter over work already done.
    assert db.statements == []


def test_the_start_route_lives_behind_the_board_flag_dependency():
    from tests.unit.test_competence_assessment_overlay import _iter_api_routes

    guarded = [
        route
        for route in _iter_api_routes(board_routes._enabled_router)
        if getattr(route, "path", "") == "/assessments"
    ]
    assert {tuple(sorted(route.methods)) for route in guarded} == {("POST",)}


# ------------------------------------------------------- AC-04 unbound cells


@pytest.mark.asyncio
async def test_an_unbound_characteristic_is_startable_in_no_mode(monkeypatch):
    monkeypatch.setattr(settings, "competence_board_enabled", True)
    db = _startable_db()

    for mode in BIND_MODES:
        with pytest.raises(BadRequestError) as exc_info:
            await resolve_startable_bind_async(
                db,
                tenant_id=TENANT,
                characteristic_key=UNBOUND_CHARACTERISTIC,
                mode=mode,
            )
        message = str(exc_info.value)
        assert message == NO_BIND_FOR_CHARACTERISTIC.format(characteristic=UNBOUND_CHARACTERISTIC)
        # The copy sends the reader to the CB-UI-2 mapping screen and never
        # describes the person on the row.
        assert "IT-Admin" in message
        assert "Competence binds" in message
        for forbidden in ("fail", "failed", "not competent", "grey"):
            assert forbidden not in message.lower()


def test_the_board_marks_unbound_columns_as_unbound_rather_than_hiding_them():
    """Empty ``bound_modes`` is the unbound signal; the column still renders."""
    modes = bound_modes_by_characteristic(
        [
            _bind(characteristic=CHARACTERISTIC, mode="field"),
            _bind(characteristic=CHARACTERISTIC, mode="induction", template_id=INDUCTION_TEMPLATE_ID, bind_id=4),
            _bind(characteristic="TELEHANDLER", mode="induction", template_id=77, bind_id=5),
        ]
    )

    assert modes[CHARACTERISTIC] == ["field", "induction"]
    assert modes["TELEHANDLER"] == ["induction"]
    assert UNBOUND_CHARACTERISTIC not in modes

    column = board_routes.CompetenceBoardColumn(key=UNBOUND_CHARACTERISTIC, label=UNBOUND_CHARACTERISTIC)
    assert column.bound_modes == []


def test_bound_modes_order_does_not_depend_on_row_order():
    """The picker must not reshuffle between two loads of the same data."""
    forward = bound_modes_by_characteristic(
        [
            _bind(mode="field", bind_id=9),
            _bind(mode="induction", template_id=INDUCTION_TEMPLATE_ID, bind_id=1),
        ]
    )
    reverse = bound_modes_by_characteristic(
        [
            _bind(mode="induction", template_id=INDUCTION_TEMPLATE_ID, bind_id=1),
            _bind(mode="field", bind_id=9),
        ]
    )
    assert forward == reverse == {CHARACTERISTIC: ["field", "induction"]}


@pytest.mark.asyncio
async def test_the_board_reports_what_the_viewer_is_issued_on(monkeypatch):
    monkeypatch.setattr(settings, "competence_board_enabled", True)
    rows = [
        types.SimpleNamespace(
            engineer_id=engineer_id,
            pams_technician_id=None,
            engineer_name="Pat",
            email=None,
            depot="SS11",
            characteristic_key=characteristic,
            thorough_exam=None,
        )
        for engineer_id, characteristic in (
            (ENGINEER_ID, CHARACTERISTIC),
            (ENGINEER_ID, UNBOUND_CHARACTERISTIC),
            (ASSESSOR_ENGINEER_ID, CHARACTERISTIC),
        )
    ]
    monkeypatch.setattr(
        "src.api.routes.workforce_competence_board.load_current_snapshot_async",
        AsyncMock(return_value=(_snapshot(), rows)),
    )
    db = _StartDb(
        rows={
            CompetenceAssessmentBind: [_bind()],
            Engineer: [_engineer(), _assessor_engineer()],
        }
    )

    response = await board_routes.get_competence_board(db=db, current_user=_user(), family="pams")

    assert response.assessor.engineer_id == ASSESSOR_ENGINEER_ID
    assert response.assessor.issued_characteristic_keys == [CHARACTERISTIC]
    assert response.assessor.blocked_reason is None
    by_key = {column.key: column for column in response.columns}
    assert by_key[CHARACTERISTIC].bound_modes == ["field"]
    # Listed, and honestly unbound rather than dropped or greyed.
    assert by_key[UNBOUND_CHARACTERISTIC].bound_modes == []


@pytest.mark.asyncio
async def test_a_viewer_with_no_employee_record_is_told_so_not_shown_a_start(monkeypatch):
    monkeypatch.setattr(settings, "competence_board_enabled", True)
    monkeypatch.setattr(
        "src.api.routes.workforce_competence_board.load_current_snapshot_async",
        AsyncMock(
            return_value=(
                _snapshot(),
                [
                    types.SimpleNamespace(
                        engineer_id=ENGINEER_ID,
                        pams_technician_id=None,
                        engineer_name="Pat",
                        email=None,
                        depot=None,
                        characteristic_key=CHARACTERISTIC,
                        thorough_exam=None,
                    )
                ],
            )
        ),
    )
    db = _StartDb(rows={CompetenceAssessmentBind: [_bind()], Engineer: [_engineer()]})

    response = await board_routes.get_competence_board(db=db, current_user=_user(), family="pams")

    assert response.assessor.engineer_id is None
    assert response.assessor.blocked_reason == ASSESSOR_HAS_NO_EMPLOYEE_RECORD
    assert response.assessor.issued_characteristic_keys == []


# ---------------------------------------------------------- AC-05 evidence


def test_plant_evidence_keeps_only_what_was_filled_in():
    assert normalise_plant_evidence(None) is None
    assert normalise_plant_evidence({}) is None
    # An all-blank form stores nothing, so "no evidence" and "tabbed through the
    # boxes" are the same row rather than one holding empty strings.
    assert normalise_plant_evidence({"make": "  ", "model": "", "serial": None}) is None
    assert normalise_plant_evidence({"make": " Hyster ", "serial": "H2-9981"}) == {
        "make": "Hyster",
        "serial": "H2-9981",
    }
    # Unknown keys are dropped here as well as refused by the schema, because
    # this is also the normaliser for anything already on a row.
    assert normalise_plant_evidence({"make": "Hyster", "oem_certificate": "yes"}) == {"make": "Hyster"}
    assert normalise_plant_evidence({"serial": "x" * 400}) == {"serial": "x" * PLANT_EVIDENCE_MAX_LEN}


def test_plant_evidence_schema_refuses_an_unknown_field():
    with pytest.raises(ValidationError):
        board_routes.CompetencePlantEvidenceIn(make="Hyster", oem_model_code="H2")
    with pytest.raises(ValidationError):
        AssessmentPlantEvidence(asset_type_id=4)


@pytest.mark.asyncio
async def test_evidence_lands_on_the_run_and_is_readable_back(monkeypatch):
    monkeypatch.setattr(settings, "competence_board_enabled", True)
    _patch_create_collaborators(monkeypatch)
    _patch_snapshot(monkeypatch, [_issued_row(engineer_id=ASSESSOR_ENGINEER_ID, characteristic=CHARACTERISTIC)])
    db = _startable_db()

    result = await board_routes.start_competence_assessment(
        payload=board_routes.CompetenceAssessmentStartCreate(
            engineer_id=ENGINEER_ID,
            characteristic_key=CHARACTERISTIC,
            plant_evidence=board_routes.CompetencePlantEvidenceIn(
                make="Hyster",
                model="H2.5FT",
                serial="H2-9981",
                pams_plant_id="PLT-4471",
            ),
        ),
        db=db,
        current_user=_user(),
    )

    expected = {"make": "Hyster", "model": "H2.5FT", "serial": "H2-9981", "pams_plant_id": "PLT-4471"}
    assert result.plant_evidence == expected
    assert db.added_of(AssessmentRun)[0].plant_evidence == expected


@pytest.mark.asyncio
async def test_evidence_is_optional_and_absent_means_absent(monkeypatch):
    monkeypatch.setattr(settings, "competence_board_enabled", True)
    _patch_create_collaborators(monkeypatch)
    _patch_snapshot(monkeypatch, [_issued_row(engineer_id=ASSESSOR_ENGINEER_ID, characteristic=CHARACTERISTIC)])
    db = _startable_db()

    result = await board_routes.start_competence_assessment(
        payload=board_routes.CompetenceAssessmentStartCreate(
            engineer_id=ENGINEER_ID,
            characteristic_key=CHARACTERISTIC,
        ),
        db=db,
        current_user=_user(),
    )

    assert result.plant_evidence is None
    assert db.added_of(AssessmentRun)[0].plant_evidence is None


def test_evidence_is_not_a_board_column_and_not_an_oem_layer():
    """No make/model square, and no catalogue behind the free text.

    CB-OEM owns make and model as *data*. Here they are four optional strings
    on one run, so the board keeps one square per characteristic and nothing
    validates a make against a registry that does not exist yet.
    """
    cell_fields = set(board_routes.CompetenceBoardCell.model_fields)
    column_fields = set(board_routes.CompetenceBoardColumn.model_fields)
    for field in ("make", "model", "serial", "pams_plant_id", "plant_evidence"):
        assert field not in cell_fields
        assert field not in column_fields

    evidence_fields = board_routes.CompetencePlantEvidenceIn.model_fields
    assert set(evidence_fields) == set(start_service.PLANT_EVIDENCE_FIELDS)
    # Free text, not an enum or a foreign key: no catalogue is being implied.
    for field in evidence_fields.values():
        assert field.annotation is not None
        assert "str" in str(field.annotation)
    assert normalise_plant_evidence({"make": "a make nobody has heard of"}) == {"make": "a make nobody has heard of"}


# --------------------------------------- CUJ pass path never writes PAMS


def _run_row(run: AssessmentRun):
    """The started run, shaped for ``complete_assessment``'s own reads."""
    return types.SimpleNamespace(
        id=run.id,
        reference_number=run.reference_number,
        supervisor_id=run.supervisor_id,
        engineer_id=run.engineer_id,
        template_id=run.template_id,
        template_version=1,
        asset_type_id=None,
        asset_id=None,
        title=run.title,
        location=None,
        notes=None,
        plant_evidence=run.plant_evidence,
        status=AssessmentStatus.IN_PROGRESS,
        scheduled_date=None,
        started_at=NOW,
        completed_at=None,
        outcome=None,
        overall_notes=None,
        debrief_notes=None,
        debrief_signature=None,
        debrief_signed_at=None,
        tenant_id=TENANT,
        responses=[types.SimpleNamespace(question_id=101, verdict=CompetencyVerdict.COMPETENT, feedback="ok")],
        created_at=NOW,
        updated_at=NOW,
    )


def _template_row():
    return types.SimpleNamespace(
        questions=[types.SimpleNamespace(id=101, is_active=True, criticality="essential", question_text="Isolation")]
    )


async def _start_then_complete(monkeypatch, *, outcome: str):
    monkeypatch.setattr(settings, "competence_board_enabled", True)
    _forbid_pams_writes(monkeypatch)
    _patch_create_collaborators(monkeypatch)
    issued = _issued_row(engineer_id=ASSESSOR_ENGINEER_ID, characteristic=CHARACTERISTIC)
    engineer_issued = _issued_row(engineer_id=ENGINEER_ID, characteristic=CHARACTERISTIC)
    _patch_snapshot(monkeypatch, [issued, engineer_issued])

    db = _startable_db()
    db.bucket(PamsCompetenceRow).extend([issued, engineer_issued])

    started = await board_routes.start_competence_assessment(
        payload=board_routes.CompetenceAssessmentStartCreate(
            engineer_id=ENGINEER_ID,
            characteristic_key=CHARACTERISTIC,
            plant_evidence=board_routes.CompetencePlantEvidenceIn(serial="H2-9981"),
        ),
        db=db,
        current_user=_user(),
    )

    run_row = _run_row(db.added_of(AssessmentRun)[0])
    _patch_complete_assessment(monkeypatch, outcome=outcome)
    monkeypatch.setattr("src.api.routes.assessments.try_send_change_request_email", lambda _row: None)
    db.execute = AsyncMock(
        side_effect=[
            types.SimpleNamespace(scalar_one_or_none=lambda: run_row),
            types.SimpleNamespace(scalar_one_or_none=lambda: _template_row()),
            types.SimpleNamespace(scalar_one_or_none=lambda: _engineer()),
        ]
    )
    await complete_assessment(run_row.id, db, _user())
    return db, started, run_row, (issued, engineer_issued)


@pytest.mark.asyncio
async def test_cuj_a_pass_records_a_demonstration_and_writes_no_pams(monkeypatch):
    db, started, run_row, snapshot_rows = await _start_then_complete(monkeypatch, outcome="pass")

    demonstrations = db.added_of(CompetenceDemonstration)
    assert len(demonstrations) == 1
    written = demonstrations[0]
    assert written.characteristic_key == CHARACTERISTIC
    assert written.engineer_id == ENGINEER_ID
    assert written.source_run_id == started.run_id == run_row.id
    assert written.outcome == "pass"
    assert written.state == CompetencyLifecycleState.ACTIVE.value
    assert written.assessed_by_id == ASSESSOR_USER_ID

    # A pass opens no change request and touches no issuance.
    assert db.added_of(CompetenceChangeRequest) == []
    assert db.bucket(PamsCompetenceRow) == list(snapshot_rows)
    _assert_no_pams_write(db)


@pytest.mark.asyncio
async def test_cuj_a_family_fail_opens_the_existing_it_admin_revoke_request(monkeypatch):
    db, _started, _run_row, snapshot_rows = await _start_then_complete(monkeypatch, outcome="fail")

    written = db.added_of(CompetenceDemonstration)[0]
    assert written.state == CompetencyLifecycleState.FAILED.value
    assert written.expires_at is None

    requests = db.added_of(CompetenceChangeRequest)
    assert len(requests) == 1
    request = requests[0]
    assert request.family == "pams"
    assert request.action == "revoke"
    assert request.characteristic_key == CHARACTERISTIC
    assert request.status == "open"
    assert "field" in (request.notes or "")

    # Nothing is un-issued: the snapshot rows are the same objects, unedited.
    assert db.bucket(PamsCompetenceRow) == list(snapshot_rows)
    assert [row.characteristic_key for row in snapshot_rows] == [CHARACTERISTIC, CHARACTERISTIC]
    _assert_no_pams_write(db)


def test_the_start_path_opens_no_pams_write_and_no_second_revoke_channel():
    """The change a later edit would most plausibly make, caught cheaply.

    Reaching for a PAMS client from the start path, or adding a revoke route
    beside CB-PR2's change request rather than letting completion use the
    CB-PR4 overlay it already goes through.
    """
    from tests.unit.test_competence_assessment_overlay import _iter_api_routes

    service = Path(start_service.__file__).read_text(encoding="utf-8")
    for forbidden in ("fetch_pams_competence_rows", "_build_pams_engine", "sync_pams_competence_snapshot"):
        assert forbidden not in service
    assert "create_change_request_async" not in service

    paths = {getattr(route, "path", "") for route in _iter_api_routes(board_routes._enabled_router)}
    assert "/assessments" in paths
    assert not [path for path in paths if "revoke" in path]


def test_the_start_route_demands_assessment_create_and_not_only_a_board_permission():
    """Calling a handler as a function runs its body, not its ``Depends``.

    ``start_competence_assessment`` reaches ``create_assessment_run`` directly,
    so ``require_permission("assessment:create")`` on the assessment router is
    never evaluated for this request. Without declaring it here, a role holding
    the board's ``engineer:update`` would gain an assessment-create path it was
    never granted. Asserted on the registered route rather than on the source
    text, so deleting the dependency fails this test.
    """
    from src.domain.authz.extraction import REQUIRED_PERMISSION_ATTR
    from tests.unit.test_competence_assessment_overlay import _iter_api_routes

    route = next(
        route
        for route in _iter_api_routes(board_routes._enabled_router)
        if getattr(route, "path", "") == "/assessments" and "POST" in (getattr(route, "methods", None) or set())
    )
    tokens = {
        token
        for dependency in route.dependant.dependencies
        if isinstance(token := getattr(dependency.call, REQUIRED_PERMISSION_ATTR, None), str)
    }
    assert "assessment:create" in tokens, "the run-creating route must demand the run-creating permission"
    assert "engineer:update" in tokens, "and still demand the board permission it is reached through"


# ------------------------------------------------------------- migration


def _migration_tree() -> ast.Module:
    return ast.parse(MIGRATION_PATH.read_text(encoding="utf-8"))


def _module_constant(name: str):
    for node in _migration_tree().body:
        if isinstance(node, ast.AnnAssign) and getattr(node.target, "id", None) == name:
            return ast.literal_eval(node.value)
        if isinstance(node, ast.Assign) and any(getattr(t, "id", None) == name for t in node.targets):
            return ast.literal_eval(node.value)
    raise AssertionError(f"{name} not found in {MIGRATION_PATH.name}")


def test_the_migration_chains_off_the_real_alembic_parent():
    """The filename that sorts last is not the head in this tree."""
    assert _module_constant("revision") == "20260903_asm_plant_evid"
    assert _module_constant("down_revision") == "20260903_cb_bind_mode"


def test_the_migration_adds_one_nullable_column_and_no_table():
    source = MIGRATION_PATH.read_text(encoding="utf-8")
    assert "create_table" not in source
    assert "add_column" in source
    assert "nullable=True" in source
    # No server_default, because the model declares none and leaving one is drift.
    assert "server_default" not in source
    # Re-runnable: both directions check the column before touching it.
    assert source.count("_columns(TABLE)") == 2


def test_the_model_and_the_migration_agree_on_the_column():
    assert "plant_evidence" in AssessmentRun.__table__.columns
    column = AssessmentRun.__table__.columns["plant_evidence"]
    assert column.nullable is True
    assert column.server_default is None
    assert _module_constant("COLUMN") == "plant_evidence"
    assert _module_constant("TABLE") == AssessmentRun.__tablename__
