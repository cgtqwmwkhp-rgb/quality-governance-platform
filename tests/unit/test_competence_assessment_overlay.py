"""CB-PR4: assessment bind → demonstration overlay. QGP never writes PAMS."""

from __future__ import annotations

import types
from datetime import date, datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException, Response
from sqlalchemy.sql.elements import BooleanClauseList

from src.api.routes import workforce_competence_board as board_routes
from src.api.routes.assessments import complete_assessment
from src.core.config import settings
from src.domain.exceptions import ConflictError
from src.domain.models.assessment import AssessmentStatus, CompetencyVerdict
from src.domain.models.audit import AuditTemplate
from src.domain.models.competence_assessment_bind import CompetenceAssessmentBind
from src.domain.models.competence_change_request import CompetenceChangeRequest
from src.domain.models.competence_demonstration import CompetenceDemonstration
from src.domain.models.engineer import CompetencyLifecycleState, Engineer
from src.domain.models.pams_cache import PamsCompetenceRow
from src.domain.services import competence_demonstration_service as overlay_service
from src.domain.services.atlas_competence_board_service import assemble_atlas_board
from src.domain.services.competence_change_request_service import PLANT_MAILBOX_DEFAULT
from src.domain.services.competence_demonstration_service import (
    CHARACTERISTIC_ALREADY_BOUND,
    TEMPLATE_ALREADY_BOUND,
    create_bind_async,
    delete_bind_async,
    get_bind_for_template_async,
    load_demonstration_overlay_async,
    record_assessment_demonstration_async,
)
from src.domain.services.workforce_spine import DEFAULT_REASSESSMENT_INTERVAL_DAYS

TENANT = 1
ENGINEER_ID = 9
TEMPLATE_ID = 8
CHARACTERISTIC = "Compressor"


class _FakeResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class _FakeScalars:
    def __init__(self, rows):
        self._rows = list(rows)

    def first(self):
        return self._rows[0] if self._rows else None

    def all(self):
        return list(self._rows)


def _predicates(clause):
    if clause is None:
        return []
    if isinstance(clause, BooleanClauseList):
        found = []
        for child in clause.clauses:
            found.extend(_predicates(child))
        return found
    return [clause]


def _matches(row, statement) -> bool:
    """Evaluate the eq / in / is-not-null criteria the CB-PR4 queries use.

    An unsupported operator raises instead of matching everything, so a query
    this double cannot honestly answer fails the test rather than passing it.
    """
    for predicate in _predicates(statement.whereclause):
        column = getattr(predicate, "left", None)
        if column is None or not hasattr(column, "key"):
            raise AssertionError(f"Unsupported predicate for the session double: {predicate}")
        actual = getattr(row, column.key, None)
        operator = getattr(predicate.operator, "__name__", str(predicate.operator))
        expected = getattr(getattr(predicate, "right", None), "value", None)
        if operator == "eq":
            if actual != expected:
                return False
        elif operator == "in_op":
            if actual not in list(expected or []):
                return False
        elif operator == "is_not":
            if actual is None:
                return False
        else:
            raise AssertionError(f"Unsupported operator for the session double: {operator}")
    return True


class _Savepoint:
    def __init__(self, db):
        self._db = db

    async def __aenter__(self):
        self._db.savepoints += 1
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if exc_type is not None:
            self._db.savepoint_rollbacks += 1
        return False


class _FakeDb:
    """Async session double: ``scalars`` dispatches on the selected entity."""

    def __init__(self, *, execute_results=(), rows=None):
        self.execute = AsyncMock(side_effect=[_FakeResult(value) for value in execute_results])
        self._rows: dict[type, list] = {model: list(items) for model, items in (rows or {}).items()}
        self.added: list = []
        self.deleted: list = []
        self.statements: list = []
        self.commits = 0
        self.rollbacks = 0
        self.flushes = 0
        self.savepoints = 0
        self.savepoint_rollbacks = 0
        self._next_id = 100

    def bucket(self, model: type) -> list:
        return self._rows.setdefault(model, [])

    async def scalars(self, statement):
        self.statements.append(statement)
        entity = statement.column_descriptions[0]["entity"]
        return _FakeScalars([row for row in self.bucket(entity) if _matches(row, statement)])

    async def get(self, model, ident):
        for row in self.bucket(model):
            if getattr(row, "id", None) == ident:
                return row
        return None

    def add(self, obj):
        self.added.append(obj)
        self.bucket(type(obj)).append(obj)

    async def delete(self, obj):
        self.deleted.append(obj)
        bucket = self.bucket(type(obj))
        if obj in bucket:
            bucket.remove(obj)

    async def flush(self):
        self.flushes += 1
        for obj in self.added:
            if getattr(obj, "id", None) is None:
                obj.id = self._next_id
                self._next_id += 1

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1

    async def refresh(self, _obj):
        return None

    def begin_nested(self):
        return _Savepoint(self)

    def added_of(self, model: type) -> list:
        return [obj for obj in self.added if isinstance(obj, model)]


def _bind(*, characteristic=CHARACTERISTIC, template_id=TEMPLATE_ID, tenant_id=TENANT, bind_id=3):
    return CompetenceAssessmentBind(
        id=bind_id,
        tenant_id=tenant_id,
        template_id=template_id,
        characteristic_key=characteristic,
        created_at=datetime(2026, 9, 1, 9, 0),
    )


def _engineer(*, engineer_id=ENGINEER_ID, tenant_id=TENANT):
    return Engineer(id=engineer_id, tenant_id=tenant_id, user_id=77)


def _run(*, run_id="asm-run-cb4", asset_type_id=None, outcome=None):
    response = types.SimpleNamespace(question_id=101, verdict=CompetencyVerdict.COMPETENT, feedback="done")
    return types.SimpleNamespace(
        id=run_id,
        reference_number="ASM-2026-0009",
        supervisor_id=42,
        engineer_id=ENGINEER_ID,
        template_id=TEMPLATE_ID,
        template_version=1,
        asset_type_id=asset_type_id,
        asset_id=None,
        title="Assessment",
        location=None,
        notes=None,
        status=AssessmentStatus.IN_PROGRESS,
        scheduled_date=None,
        started_at=None,
        completed_at=None,
        outcome=outcome,
        overall_notes=None,
        debrief_notes=None,
        debrief_signature=None,
        debrief_signed_at=None,
        tenant_id=TENANT,
        responses=[response],
        created_at=None,
        updated_at=None,
    )


def _template():
    question = types.SimpleNamespace(
        id=101,
        is_active=True,
        criticality="essential",
        question_text="Isolation procedure",
    )
    return types.SimpleNamespace(questions=[question])


def _patch_complete_assessment(monkeypatch, *, outcome: str, capa=None):
    monkeypatch.setattr("src.api.routes.assessments._assert_assessment_access", AsyncMock())
    monkeypatch.setattr(
        "src.api.routes.assessments.CompetencyScoringService.score_assessment",
        lambda responses, questions: types.SimpleNamespace(outcome=outcome, scorable_items=1),
    )
    monkeypatch.setattr(
        "src.api.routes.assessments._to_assessment_run_response",
        lambda run_obj, **_extra: run_obj,
    )
    monkeypatch.setattr(
        "src.api.routes.assessments.NotificationService.notify_assessment_complete",
        AsyncMock(),
    )
    monkeypatch.setattr(
        "src.api.routes.assessments.CAPAAutoService.create_from_assessment",
        capa or AsyncMock(return_value=[]),
    )


def _forbid_pams_writes(monkeypatch):
    """Any attempt to reach the PAMS database from this path must fail loudly."""

    def _explode(*_args, **_kwargs):
        raise AssertionError("QGP must never open a PAMS connection from an assessment")

    monkeypatch.setattr("src.domain.services.pams_competence_snapshot_service._build_pams_engine", _explode)
    monkeypatch.setattr("src.domain.services.pams_competence_snapshot_service.fetch_pams_competence_rows", _explode)


def _assert_no_pams_write(db: _FakeDb):
    assert db.added_of(PamsCompetenceRow) == []
    assert db.deleted == []


# ---------------------------------------------------------------- AC-01 flag


@pytest.mark.asyncio
async def test_assessment_binds_and_board_404_when_flag_off(monkeypatch):
    monkeypatch.setattr(settings, "competence_board_enabled", False)
    with pytest.raises(HTTPException) as exc_info:
        await board_routes.require_competence_board_enabled()
    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == board_routes.DISABLED_DETAIL


def _iter_api_routes(router):
    """Flatten ``include_router`` mounts.

    FastAPI >=0.140 (the lockfile pin) wraps included routers as
    ``_IncludedRouter`` with no ``.path``. Child routes live on
    ``original_router``. Older FastAPI flattens APIRoutes onto the parent.
    """
    for route in getattr(router, "routes", []) or []:
        nested_router = getattr(route, "original_router", None)
        if nested_router is not None:
            yield from _iter_api_routes(nested_router)
            continue
        nested = getattr(route, "routes", None)
        if nested is not None:
            yield from _iter_api_routes(route)
            continue
        yield route


def test_iter_api_routes_flattens_included_router_without_path():
    """CI FastAPI 0.140 wraps include_router; the wrapper has no ``path``."""

    class _Child:
        path = "/assessment-binds"
        methods = {"POST"}

    class _Included:
        original_router = types.SimpleNamespace(routes=[_Child()])
        routes = []

    parent = types.SimpleNamespace(routes=[_Included()])
    assert [route.path for route in _iter_api_routes(parent)] == ["/assessment-binds"]


def test_bind_routes_are_registered_behind_the_flag_dependency():
    """POST/GET/DELETE assessment-binds live on the flagged router.

    FastAPI 0.140 (lockfile) wraps ``include_router`` as ``_IncludedRouter``
    with no ``.path``, so walking ``board_routes.router.routes`` and reading
    ``route.path`` raises. The flag is the router-level dependency on
    ``_enabled_router``; bind endpoints are declared there, not on the
    unguarded parent.
    """
    assert any(
        getattr(dependency, "dependency", None) is board_routes.require_competence_board_enabled
        for dependency in board_routes._enabled_router.dependencies
    )
    guarded = [
        route
        for route in _iter_api_routes(board_routes._enabled_router)
        if "assessment-binds" in getattr(route, "path", "")
    ]
    assert {tuple(sorted(route.methods)) for route in guarded} == {("POST",), ("GET",), ("DELETE",)}


def test_flag_default_stays_false():
    assert settings.competence_board_enabled is False


# ------------------------------------------------- AC-02 explicit bind only


@pytest.mark.asyncio
async def test_bind_is_explicit_and_created_once():
    db = _FakeDb(rows={AuditTemplate: [AuditTemplate(id=TEMPLATE_ID, tenant_id=TENANT)]})

    row, created = await create_bind_async(
        db, tenant_id=TENANT, template_id=TEMPLATE_ID, characteristic_key=CHARACTERISTIC
    )
    assert created is True
    assert row.characteristic_key == CHARACTERISTIC
    assert row.template_id == TEMPLATE_ID

    same, created_again = await create_bind_async(
        db, tenant_id=TENANT, template_id=TEMPLATE_ID, characteristic_key=CHARACTERISTIC
    )
    assert created_again is False
    assert same is row
    assert len(db.added_of(CompetenceAssessmentBind)) == 1


@pytest.mark.asyncio
async def test_matching_asset_type_name_does_not_auto_bind():
    """A QGP asset type called "Compressor" is not the PAMS characteristic."""
    db = _FakeDb(
        rows={
            CompetenceAssessmentBind: [],
            PamsCompetenceRow: [
                PamsCompetenceRow(engineer_id=ENGINEER_ID, characteristic_key=CHARACTERISTIC, snapshot_id=1)
            ],
        }
    )

    assert await get_bind_for_template_async(db, tenant_id=TENANT, template_id=TEMPLATE_ID) is None
    result = await record_assessment_demonstration_async(
        db,
        tenant_id=TENANT,
        engineer_id=ENGINEER_ID,
        template_id=TEMPLATE_ID,
        source_run_id="asm-run-unbound",
        outcome="pass",
    )
    assert result is None
    assert db.added_of(CompetenceDemonstration) == []

    bind_sql = str(db.statements[0]).lower()
    assert "competence_assessment_binds.template_id" in bind_sql
    assert "competence_assessment_binds.tenant_id" in bind_sql
    assert "asset_type" not in bind_sql
    assert "name" not in bind_sql


@pytest.mark.asyncio
async def test_second_template_cannot_take_a_bound_characteristic():
    db = _FakeDb(
        rows={
            AuditTemplate: [AuditTemplate(id=TEMPLATE_ID, tenant_id=TENANT), AuditTemplate(id=99, tenant_id=TENANT)],
            CompetenceAssessmentBind: [_bind()],
        }
    )

    with pytest.raises(ConflictError) as exc_info:
        await create_bind_async(db, tenant_id=TENANT, template_id=99, characteristic_key=CHARACTERISTIC)
    assert CHARACTERISTIC_ALREADY_BOUND in str(exc_info.value)

    with pytest.raises(ConflictError) as other:
        await create_bind_async(db, tenant_id=TENANT, template_id=TEMPLATE_ID, characteristic_key="Trailer")
    assert TEMPLATE_ALREADY_BOUND in str(other.value)


@pytest.mark.asyncio
async def test_bind_lookup_is_tenant_scoped():
    db = _FakeDb(rows={CompetenceAssessmentBind: [_bind(tenant_id=2)]})
    assert await get_bind_for_template_async(db, tenant_id=TENANT, template_id=TEMPLATE_ID) is None


@pytest.mark.asyncio
async def test_delete_bind_keeps_demonstration_history():
    bind = _bind()
    demonstration = CompetenceDemonstration(
        id=5,
        tenant_id=TENANT,
        engineer_id=ENGINEER_ID,
        characteristic_key=CHARACTERISTIC,
        template_id=TEMPLATE_ID,
        source_run_id="asm-run-old",
        outcome="pass",
        state=CompetencyLifecycleState.ACTIVE.value,
        assessed_at=datetime(2026, 8, 1, 10, 0),
    )
    db = _FakeDb(rows={CompetenceAssessmentBind: [bind], CompetenceDemonstration: [demonstration]})

    await delete_bind_async(db, tenant_id=TENANT, bind_id=bind.id)

    assert db.bucket(CompetenceAssessmentBind) == []
    assert db.bucket(CompetenceDemonstration) == [demonstration]


# --------------------------------------------------------- AC-03 pass overlay


@pytest.mark.asyncio
async def test_complete_pass_writes_demonstration_and_never_writes_pams(monkeypatch):
    _forbid_pams_writes(monkeypatch)
    _patch_complete_assessment(monkeypatch, outcome="pass")
    run = _run()
    db = _FakeDb(
        execute_results=[run, _template(), _engineer()],
        rows={CompetenceAssessmentBind: [_bind()], Engineer: [_engineer()]},
    )

    result = await complete_assessment(run.id, db, types.SimpleNamespace(id=42, tenant_id=TENANT, roles=[]))

    assert result is run
    assert run.status == AssessmentStatus.COMPLETED
    demonstrations = db.added_of(CompetenceDemonstration)
    assert len(demonstrations) == 1
    written = demonstrations[0]
    assert written.characteristic_key == CHARACTERISTIC
    assert written.engineer_id == ENGINEER_ID
    assert written.tenant_id == TENANT
    assert written.source_run_id == run.id
    assert written.outcome == "pass"
    assert written.state == CompetencyLifecycleState.ACTIVE.value
    assert written.assessed_by_id == 42
    expected_expiry = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(
        days=DEFAULT_REASSESSMENT_INTERVAL_DAYS
    )
    assert abs((written.expires_at - expected_expiry).total_seconds()) < 60
    assert db.added_of(CompetenceChangeRequest) == []
    assert db.savepoints == 1
    _assert_no_pams_write(db)


# --------------------------------------------------------- AC-04 fail overlay


@pytest.mark.asyncio
async def test_complete_fail_opens_revoke_change_request_and_leaves_issuance(monkeypatch):
    _forbid_pams_writes(monkeypatch)
    capa = AsyncMock(return_value=[])
    _patch_complete_assessment(monkeypatch, outcome="fail", capa=capa)
    sent: list = []
    monkeypatch.setattr(
        "src.api.routes.assessments.try_send_change_request_email",
        lambda row: sent.append(row),
    )
    run = _run(run_id="asm-run-fail")
    run.responses[0].verdict = CompetencyVerdict.NOT_COMPETENT
    issued = PamsCompetenceRow(
        id=11,
        snapshot_id=1,
        engineer_id=ENGINEER_ID,
        characteristic_key=CHARACTERISTIC,
        thorough_exam=True,
    )
    db = _FakeDb(
        execute_results=[run, _template(), _engineer()],
        rows={CompetenceAssessmentBind: [_bind()], Engineer: [_engineer()], PamsCompetenceRow: [issued]},
    )

    await complete_assessment(run.id, db, types.SimpleNamespace(id=42, tenant_id=TENANT, roles=[]))

    written = db.added_of(CompetenceDemonstration)[0]
    assert written.state == CompetencyLifecycleState.FAILED.value
    assert written.outcome == "fail"
    assert written.expires_at is None

    requests = db.added_of(CompetenceChangeRequest)
    assert len(requests) == 1
    request = requests[0]
    assert request.family == "pams"
    assert request.action == "revoke"
    assert request.characteristic_key == CHARACTERISTIC
    assert request.routed_to_email == PLANT_MAILBOX_DEFAULT
    assert request.status == "open"
    assert run.id in (request.notes or "")
    assert sent == [request]

    # Issuance is PAMS state: the snapshot row is neither edited nor deleted.
    assert issued.characteristic_key == CHARACTERISTIC
    assert issued.thorough_exam is True
    assert db.bucket(PamsCompetenceRow) == [issued]
    _assert_no_pams_write(db)
    capa.assert_awaited_once()


@pytest.mark.asyncio
async def test_conditional_outcome_is_recorded_as_failed_with_revoke():
    db = _FakeDb(rows={CompetenceAssessmentBind: [_bind()], Engineer: [_engineer()]})

    result = await record_assessment_demonstration_async(
        db,
        tenant_id=TENANT,
        engineer_id=ENGINEER_ID,
        template_id=TEMPLATE_ID,
        source_run_id="asm-run-conditional",
        outcome="conditional",
    )

    assert result is not None
    assert result.demonstration.outcome == "conditional"
    assert result.demonstration.state == CompetencyLifecycleState.FAILED.value
    assert result.change_request_created is True
    assert result.change_request.action == "revoke"


@pytest.mark.asyncio
async def test_open_issue_request_blocks_the_revoke_without_failing_the_run():
    """One-open-per-cell wins; the demonstration is still recorded, not a 409."""
    open_issue = CompetenceChangeRequest(
        id=4,
        tenant_id=TENANT,
        family="pams",
        engineer_id=ENGINEER_ID,
        characteristic_key=CHARACTERISTIC,
        action="issue",
        status="open",
        routed_to_email=PLANT_MAILBOX_DEFAULT,
        created_at=datetime(2026, 8, 30, 8, 0),
    )
    db = _FakeDb(
        rows={
            CompetenceAssessmentBind: [_bind()],
            Engineer: [_engineer()],
            CompetenceChangeRequest: [open_issue],
        }
    )

    result = await record_assessment_demonstration_async(
        db,
        tenant_id=TENANT,
        engineer_id=ENGINEER_ID,
        template_id=TEMPLATE_ID,
        source_run_id="asm-run-blocked",
        outcome="fail",
    )

    assert result is not None
    assert result.demonstration.state == CompetencyLifecycleState.FAILED.value
    assert result.change_request is None
    assert result.change_request_created is False
    assert db.added_of(CompetenceChangeRequest) == []


@pytest.mark.asyncio
async def test_bind_endpoints_create_list_and_revert(monkeypatch):
    monkeypatch.setattr(settings, "competence_board_enabled", True)
    db = _FakeDb(rows={AuditTemplate: [AuditTemplate(id=TEMPLATE_ID, tenant_id=TENANT)]})
    user = types.SimpleNamespace(id=42, tenant_id=TENANT)
    payload = board_routes.CompetenceAssessmentBindCreate(
        template_id=TEMPLATE_ID,
        characteristic_key=CHARACTERISTIC,
    )
    response = Response()

    created = await board_routes.create_competence_assessment_bind(
        payload=payload, db=db, current_user=user, response=response
    )
    assert response.status_code == 201
    assert created.characteristic_key == CHARACTERISTIC
    assert db.commits == 1

    again = await board_routes.create_competence_assessment_bind(
        payload=payload, db=db, current_user=user, response=response
    )
    assert response.status_code == 200
    assert again.id == created.id
    assert len(db.added_of(CompetenceAssessmentBind)) == 1

    listed = await board_routes.list_competence_assessment_binds(db=db, current_user=user)
    assert [item.id for item in listed.items] == [created.id]

    await board_routes.delete_competence_assessment_bind(bind_id=created.id, db=db, current_user=user)
    assert db.bucket(CompetenceAssessmentBind) == []


# ------------------------------------------------------------ AC-05 pams board


def _snapshot():
    return types.SimpleNamespace(
        id=7,
        status="ready",
        source_name="vw_plantex_engineercompetence",
        row_count=2,
        completed_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )


def _snapshot_row(*, engineer_id, characteristic, technician_id=158, name="Cameron"):
    return types.SimpleNamespace(
        engineer_id=engineer_id,
        pams_technician_id=technician_id,
        engineer_name=name,
        email=None,
        depot="SS11",
        characteristic_key=characteristic,
        thorough_exam=True,
    )


@pytest.mark.asyncio
async def test_board_attaches_demonstration_only_where_a_run_exists(monkeypatch):
    monkeypatch.setattr(settings, "competence_board_enabled", True)
    snapshot = _snapshot()
    rows = [
        _snapshot_row(engineer_id=ENGINEER_ID, characteristic=CHARACTERISTIC),
        _snapshot_row(engineer_id=ENGINEER_ID, characteristic="Trailer"),
        _snapshot_row(engineer_id=None, characteristic=CHARACTERISTIC, technician_id=222, name="Unmapped Pat"),
    ]
    monkeypatch.setattr(
        "src.api.routes.workforce_competence_board.load_current_snapshot_async",
        AsyncMock(return_value=(snapshot, rows)),
    )
    older = CompetenceDemonstration(
        id=1,
        tenant_id=TENANT,
        engineer_id=ENGINEER_ID,
        characteristic_key=CHARACTERISTIC,
        template_id=TEMPLATE_ID,
        source_run_id="asm-run-older",
        outcome="fail",
        state=CompetencyLifecycleState.FAILED.value,
        assessed_at=datetime(2026, 7, 1, 9, 0),
    )
    latest = CompetenceDemonstration(
        id=2,
        tenant_id=TENANT,
        engineer_id=ENGINEER_ID,
        characteristic_key=CHARACTERISTIC,
        template_id=TEMPLATE_ID,
        source_run_id="asm-run-latest",
        outcome="pass",
        state=CompetencyLifecycleState.ACTIVE.value,
        assessed_at=datetime(2026, 8, 20, 9, 0),
        expires_at=datetime(2027, 8, 20, 9, 0),
    )
    unmapped_person_demo = CompetenceDemonstration(
        id=3,
        tenant_id=TENANT,
        engineer_id=555,
        characteristic_key=CHARACTERISTIC,
        template_id=TEMPLATE_ID,
        source_run_id="asm-run-other",
        outcome="pass",
        state=CompetencyLifecycleState.ACTIVE.value,
        assessed_at=datetime(2026, 8, 25, 9, 0),
    )
    db = _FakeDb(
        rows={
            Engineer: [_engineer()],
            CompetenceDemonstration: [older, latest, unmapped_person_demo],
        }
    )

    response = await board_routes.get_competence_board(
        db=db,
        current_user=types.SimpleNamespace(tenant_id=TENANT),
        family="pams",
    )

    mapped = next(person for person in response.people if person.engineer_id == ENGINEER_ID)
    demonstrated = mapped.cells[CHARACTERISTIC]
    assert demonstrated.issued is True
    assert demonstrated.demonstrated == "pass"
    assert demonstrated.assessed_at == datetime(2026, 8, 20, 9, 0)
    assert demonstrated.demonstrated_expires_on == date(2027, 8, 20)

    without_run = mapped.cells["Trailer"]
    assert without_run.issued is True
    assert without_run.demonstrated is None
    assert without_run.assessed_at is None
    assert without_run.demonstrated_expires_on is None

    unmapped = next(person for person in response.people if person.engineer_id is None)
    assert unmapped.mapped is False
    assert unmapped.cells[CHARACTERISTIC].demonstrated is None


@pytest.mark.asyncio
async def test_empty_overlay_leaves_every_cell_absent(monkeypatch):
    monkeypatch.setattr(settings, "competence_board_enabled", True)
    monkeypatch.setattr(
        "src.api.routes.workforce_competence_board.load_current_snapshot_async",
        AsyncMock(return_value=(_snapshot(), [_snapshot_row(engineer_id=ENGINEER_ID, characteristic=CHARACTERISTIC)])),
    )
    db = _FakeDb(rows={Engineer: [_engineer()], CompetenceDemonstration: []})

    response = await board_routes.get_competence_board(
        db=db,
        current_user=types.SimpleNamespace(tenant_id=TENANT),
        family="pams",
    )

    cell = response.people[0].cells[CHARACTERISTIC]
    assert cell.demonstrated is None
    assert cell.assessed_at is None


@pytest.mark.asyncio
async def test_overlay_query_is_tenant_scoped():
    other_tenant = CompetenceDemonstration(
        id=8,
        tenant_id=2,
        engineer_id=ENGINEER_ID,
        characteristic_key=CHARACTERISTIC,
        template_id=TEMPLATE_ID,
        source_run_id="asm-run-other-tenant",
        outcome="pass",
        state=CompetencyLifecycleState.ACTIVE.value,
        assessed_at=datetime(2026, 8, 1, 9, 0),
    )
    db = _FakeDb(rows={CompetenceDemonstration: [other_tenant]})

    overlay = await load_demonstration_overlay_async(db, tenant_id=TENANT, engineer_ids={ENGINEER_ID})

    assert overlay == {}


@pytest.mark.asyncio
async def test_overlay_is_not_queried_without_mapped_engineers():
    db = _FakeDb()
    assert await load_demonstration_overlay_async(db, tenant_id=TENANT, engineer_ids=set()) == {}
    assert db.statements == []


# ----------------------------------------------------------- AC-06 atlas family


@pytest.mark.asyncio
async def test_atlas_board_has_no_demonstration_overlay(monkeypatch):
    monkeypatch.setattr(settings, "competence_board_enabled", True)

    def _explode(*_args, **_kwargs):
        raise AssertionError("Atlas cells must not consult the PAMS demonstration overlay")

    monkeypatch.setattr("src.api.routes.workforce_competence_board.load_demonstration_overlay_async", _explode)
    view = assemble_atlas_board(
        import_row=types.SimpleNamespace(id=9, status="completed", filename="atlas.xlsx", created_at=None),
        people=[types.SimpleNamespace(id=1, atlas_name="Pat", engineer_id=ENGINEER_ID, department="Engineer")],
        courses=[types.SimpleNamespace(id=1, course_key="first-aid", display_name="First Aid")],
        cells=[
            types.SimpleNamespace(
                person_id=1,
                course_id=1,
                passed_on=date(2026, 1, 10),
                expires_on=date(2029, 1, 10),
            )
        ],
        engineers={ENGINEER_ID: types.SimpleNamespace(id=ENGINEER_ID, display_name="Pat")},
    )
    monkeypatch.setattr(
        "src.api.routes.workforce_competence_board.build_atlas_board_async",
        AsyncMock(return_value=view),
    )

    response = await board_routes.get_competence_board(
        db=_FakeDb(),
        current_user=types.SimpleNamespace(tenant_id=TENANT),
        family="atlas",
    )

    cell = response.people[0].cells["first-aid"]
    assert cell.issued is True
    assert cell.demonstrated is None
    assert cell.assessed_at is None
    assert cell.demonstrated_expires_on is None


# --------------------------------------------- AC-07 asset-type path untouched


@pytest.mark.asyncio
async def test_asset_type_competency_record_still_written_alongside_overlay(monkeypatch):
    _forbid_pams_writes(monkeypatch)
    _patch_complete_assessment(monkeypatch, outcome="pass")
    monkeypatch.setattr(
        "src.api.routes.assessments.resolve_reassessment_interval_days",
        AsyncMock(return_value=180),
    )
    monkeypatch.setattr(overlay_service, "resolve_reassessment_interval_days", AsyncMock(return_value=180))
    run = _run(run_id="asm-run-both", asset_type_id=5)
    db = _FakeDb(
        execute_results=[run, _template(), _engineer(), None],
        rows={CompetenceAssessmentBind: [_bind()], Engineer: [_engineer()]},
    )

    await complete_assessment(run.id, db, types.SimpleNamespace(id=42, tenant_id=TENANT, roles=[]))

    from src.domain.models.engineer import CompetencyRecord

    records = db.added_of(CompetencyRecord)
    assert len(records) == 1
    assert records[0].asset_type_id == 5
    assert records[0].state == CompetencyLifecycleState.ACTIVE
    assert records[0].source_run_id == run.id

    demonstrations = db.added_of(CompetenceDemonstration)
    assert len(demonstrations) == 1
    assert demonstrations[0].characteristic_key == CHARACTERISTIC
    assert not hasattr(demonstrations[0], "asset_type_id")


@pytest.mark.asyncio
async def test_unbound_template_writes_no_demonstration(monkeypatch):
    _patch_complete_assessment(monkeypatch, outcome="pass")
    run = _run(run_id="asm-run-unbound-complete")
    db = _FakeDb(
        execute_results=[run, _template(), _engineer()],
        rows={CompetenceAssessmentBind: [], Engineer: [_engineer()]},
    )

    await complete_assessment(run.id, db, types.SimpleNamespace(id=42, tenant_id=TENANT, roles=[]))

    assert db.added_of(CompetenceDemonstration) == []
    assert db.added_of(CompetenceChangeRequest) == []


# ------------------------------------------------------------------ CUJ


@pytest.mark.asyncio
async def test_cuj_same_run_recorded_twice_stays_one_demonstration():
    db = _FakeDb(rows={CompetenceAssessmentBind: [_bind()], Engineer: [_engineer()]})

    first = await record_assessment_demonstration_async(
        db,
        tenant_id=TENANT,
        engineer_id=ENGINEER_ID,
        template_id=TEMPLATE_ID,
        source_run_id="asm-run-repeat",
        outcome="pass",
    )
    second = await record_assessment_demonstration_async(
        db,
        tenant_id=TENANT,
        engineer_id=ENGINEER_ID,
        template_id=TEMPLATE_ID,
        source_run_id="asm-run-repeat",
        outcome="pass",
    )

    assert first is not None and second is not None
    assert second.demonstration is first.demonstration
    assert len(db.added_of(CompetenceDemonstration)) == 1


@pytest.mark.asyncio
async def test_cuj_second_fail_does_not_duplicate_the_open_change_request():
    db = _FakeDb(rows={CompetenceAssessmentBind: [_bind()], Engineer: [_engineer()]})

    first = await record_assessment_demonstration_async(
        db,
        tenant_id=TENANT,
        engineer_id=ENGINEER_ID,
        template_id=TEMPLATE_ID,
        source_run_id="asm-run-fail-1",
        outcome="fail",
    )
    second = await record_assessment_demonstration_async(
        db,
        tenant_id=TENANT,
        engineer_id=ENGINEER_ID,
        template_id=TEMPLATE_ID,
        source_run_id="asm-run-fail-2",
        outcome="fail",
    )

    assert first is not None and second is not None
    assert first.change_request_created is True
    assert second.change_request_created is False
    assert second.change_request is first.change_request
    assert len(db.added_of(CompetenceChangeRequest)) == 1
    assert len(db.added_of(CompetenceDemonstration)) == 2


@pytest.mark.asyncio
async def test_overlay_failure_does_not_fail_the_completed_assessment(monkeypatch):
    _patch_complete_assessment(monkeypatch, outcome="pass")
    monkeypatch.setattr(
        overlay_service,
        "get_bind_for_template_async",
        AsyncMock(side_effect=RuntimeError("relation does not exist")),
    )
    run = _run(run_id="asm-run-overlay-down")
    db = _FakeDb(execute_results=[run, _template(), _engineer()], rows={Engineer: [_engineer()]})

    result = await complete_assessment(run.id, db, types.SimpleNamespace(id=42, tenant_id=TENANT, roles=[]))

    assert result is run
    assert run.status == AssessmentStatus.COMPLETED
    assert db.commits >= 1
    assert db.savepoint_rollbacks == 1
    assert db.added_of(CompetenceDemonstration) == []
