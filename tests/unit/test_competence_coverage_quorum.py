"""CB-PR5: compliance-schedule coverage quorum (n of m) — a location duty.

ADR-0020 stays: nothing here adds a per-person compliance-schedule row, and a
coverage gap never rewrites ``next_due_date``. QGP never writes PAMS.
"""

from __future__ import annotations

import types
from datetime import date, datetime, timezone

import pytest
from fastapi import HTTPException, Response
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy.sql.elements import BooleanClauseList

from src.api.routes import compliance_schedule as schedule_routes
from src.api.routes import workforce_competence_board as board_routes
from src.core.config import settings
from src.domain.data.compliance_schedule_catalogue import (
    EXPECTED_TEMPLATE_COUNT_MAX,
    EXPECTED_TEMPLATE_COUNT_MIN,
    catalogue_template_keys,
)
from src.domain.exceptions import NotFoundError, ValidationError
from src.domain.models.competence_coverage_quota import COVERAGE_ROLE_KEYS, CompetenceCoverageQuota
from src.domain.models.compliance_schedule import ComplianceRequirement, ComplianceRequirementTemplate
from src.domain.models.location import Location, LocationKind
from src.domain.models.training_matrix import (
    TrainingMatrixCell,
    TrainingMatrixCourse,
    TrainingMatrixImport,
    TrainingMatrixPerson,
)
from src.domain.services.atlas_competence_board_service import NO_IMPORT_BANNER
from src.domain.services.competence_coverage_service import (
    UNKNOWN_DEPARTMENT_BANNER,
    AtlasCoverageSnapshot,
    assemble_coverage,
    build_coverage_view_async,
    coverage_banner,
    coverage_targets,
    create_quota_async,
    delete_quota_async,
    list_quotas_async,
    load_coverage_overlay_async,
    role_for_course_key,
)

TENANT = 1
OTHER_TENANT = 2
LOCATION_ID = 5
TEMPLATE_KEY = "first_aider_coverage_quorum"
FIRE_TEMPLATE_KEY = "fire_marshal_coverage_quorum"
DEPARTMENT = "Workshop"
TODAY = date(2026, 9, 2)


# --------------------------------------------------------------- session double


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
    """Evaluate the eq / in criteria the CB-PR5 queries use.

    An unsupported operator raises rather than matching everything, so a query
    this double cannot honestly answer fails the test instead of passing it.
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
        else:
            raise AssertionError(f"Unsupported operator for the session double: {operator}")
    return True


class _FakeDb:
    """Async session double: ``scalars`` dispatches on the selected entity."""

    def __init__(self, rows=None):
        self._rows: dict[type, list] = {model: list(items) for model, items in (rows or {}).items()}
        self.added: list = []
        self.deleted: list = []
        self.statements: list = []
        self.commits = 0
        self.flushes = 0
        self._next_id = 100

    def bucket(self, model: type) -> list:
        return self._rows.setdefault(model, [])

    async def scalars(self, statement):
        self.statements.append(statement)
        entity = statement.column_descriptions[0]["entity"]
        found = [row for row in self.bucket(entity) if _matches(row, statement)]
        # ``load_atlas_snapshot_async`` takes the newest import via ORDER BY id
        # DESC LIMIT 1; the double honours that rather than returning insertion
        # order, which would silently read a stale import.
        if entity is TrainingMatrixImport:
            found.sort(key=lambda row: row.id, reverse=True)
            found = found[:1]
        return _FakeScalars(found)

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

    async def refresh(self, _obj):
        return None

    def added_of(self, model: type) -> list:
        return [obj for obj in self.added if isinstance(obj, model)]


# ------------------------------------------------------------------- factories


def _quota(
    *,
    quota_id=1,
    tenant_id=TENANT,
    location_id=LOCATION_ID,
    role_key="first_aider",
    required_n=2,
    template_key=TEMPLATE_KEY,
    match_department=DEPARTMENT,
):
    return CompetenceCoverageQuota(
        id=quota_id,
        tenant_id=tenant_id,
        location_id=location_id,
        role_key=role_key,
        required_n=required_n,
        template_key=template_key,
        match_department=match_department,
        created_at=datetime(2026, 9, 1, 9, 0),
        updated_at=datetime(2026, 9, 1, 9, 0),
    )


def _person(*, pid, name, department=DEPARTMENT, engineer_id=None):
    return TrainingMatrixPerson(
        id=pid,
        tenant_id=TENANT,
        atlas_name=name,
        department=department,
        engineer_id=engineer_id,
        last_seen_import_id=1,
    )


def _course(*, cid, key):
    return TrainingMatrixCourse(id=cid, tenant_id=TENANT, course_key=key, display_name=key)


def _cell(*, person_id, course_id, passed_on=date(2026, 1, 10), expires_on=None):
    return TrainingMatrixCell(
        id=person_id * 100 + course_id,
        tenant_id=TENANT,
        import_id=1,
        person_id=person_id,
        course_id=course_id,
        passed_on=passed_on,
        expires_on=expires_on,
    )


def _snapshot(*, people=(), courses=(), cells=(), has_import=True):
    return AtlasCoverageSnapshot(has_import=has_import, people=list(people), courses=list(courses), cells=list(cells))


def _location(*, location_id=LOCATION_ID, tenant_id=TENANT, name=DEPARTMENT):
    return Location(id=location_id, tenant_id=tenant_id, name=name, kind=LocationKind.SITE)


def _template(*, template_key=TEMPLATE_KEY, template_id=70):
    return ComplianceRequirementTemplate(
        id=template_id,
        tenant_id=None,
        template_key=template_key,
        title="First-aider Coverage (n of m)",
        taxonomy_id="02.09",
        frequency_months=12,
    )


def _user(tenant_id=TENANT):
    return types.SimpleNamespace(id=42, tenant_id=tenant_id)


# ------------------------------------------------------------------ AC-01 flag


@pytest.mark.asyncio
async def test_coverage_routes_are_404_while_the_flag_is_closed(monkeypatch):
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


def test_coverage_routes_are_registered_behind_the_flag_dependency():
    assert any(
        getattr(dependency, "dependency", None) is board_routes.require_competence_board_enabled
        for dependency in board_routes._enabled_router.dependencies
    )
    guarded = {
        (route.path, tuple(sorted(route.methods)))
        for route in _iter_api_routes(board_routes._enabled_router)
        if "coverage" in getattr(route, "path", "")
    }
    assert guarded == {
        ("/coverage", ("GET",)),
        ("/coverage-quotas", ("GET",)),
        ("/coverage-quotas", ("POST",)),
        ("/coverage-quotas/{quota_id}", ("DELETE",)),
    }


def test_flag_default_stays_false():
    assert settings.competence_board_enabled is False


# ------------------------------------------------- AC-02 currency of a cell


def test_unexpired_pass_in_the_matching_department_counts():
    snapshot = _snapshot(
        people=[_person(pid=1, name="Pat")],
        courses=[_course(cid=1, key="first_aid")],
        cells=[_cell(person_id=1, course_id=1, expires_on=date(2027, 1, 10))],
    )
    [state] = assemble_coverage(quotas=[_quota(required_n=1)], snapshot=snapshot, today=TODAY)
    assert state.current_m == 1
    assert state.met is True
    assert state.gap is False
    assert state.unknown is False


def test_expired_cell_does_not_count():
    snapshot = _snapshot(
        people=[_person(pid=1, name="Pat")],
        courses=[_course(cid=1, key="first_aid")],
        cells=[_cell(person_id=1, course_id=1, expires_on=date(2026, 8, 31))],
    )
    [state] = assemble_coverage(quotas=[_quota(required_n=1)], snapshot=snapshot, today=TODAY)
    assert state.current_m == 0
    assert state.met is False
    assert state.gap is True


def test_cell_expiring_today_still_counts():
    """``expires_on >= today`` is the rule; the last day is still cover."""
    snapshot = _snapshot(
        people=[_person(pid=1, name="Pat")],
        courses=[_course(cid=1, key="first_aid")],
        cells=[_cell(person_id=1, course_id=1, expires_on=TODAY)],
    )
    [state] = assemble_coverage(quotas=[_quota(required_n=1)], snapshot=snapshot, today=TODAY)
    assert state.current_m == 1


def test_cell_with_no_passed_on_does_not_count():
    snapshot = _snapshot(
        people=[_person(pid=1, name="Pat")],
        courses=[_course(cid=1, key="first_aid")],
        cells=[_cell(person_id=1, course_id=1, passed_on=None, expires_on=date(2027, 1, 10))],
    )
    [state] = assemble_coverage(quotas=[_quota(required_n=1)], snapshot=snapshot, today=TODAY)
    assert state.current_m == 0
    assert state.gap is True


def test_two_matching_courses_on_one_person_count_as_one():
    snapshot = _snapshot(
        people=[_person(pid=1, name="Pat")],
        courses=[_course(cid=1, key="first_aid"), _course(cid=2, key="cpr_awareness_first_aid")],
        cells=[_cell(person_id=1, course_id=1), _cell(person_id=1, course_id=2)],
    )
    [state] = assemble_coverage(quotas=[_quota(required_n=2)], snapshot=snapshot, today=TODAY)
    assert state.current_m == 1
    assert state.gap is True


def test_unmapped_atlas_person_counts_toward_coverage():
    """No engineer_id is still an appointed person. QGP creates no User."""
    snapshot = _snapshot(
        people=[_person(pid=1, name="Pat", engineer_id=None)],
        courses=[_course(cid=1, key="first_aid")],
        cells=[_cell(person_id=1, course_id=1)],
    )
    [state] = assemble_coverage(quotas=[_quota(required_n=1)], snapshot=snapshot, today=TODAY)
    assert state.current_m == 1
    assert state.met is True


def test_display_name_twins_are_two_people():
    """Name is not a join key — two Atlas rows called Sam are two humans."""
    snapshot = _snapshot(
        people=[_person(pid=1, name="Sam"), _person(pid=2, name="Sam")],
        courses=[_course(cid=1, key="first_aid")],
        cells=[_cell(person_id=1, course_id=1), _cell(person_id=2, course_id=1)],
    )
    [state] = assemble_coverage(quotas=[_quota(required_n=2)], snapshot=snapshot, today=TODAY)
    assert state.current_m == 2
    assert state.met is True


def test_course_allowlist_is_explicit_not_substring():
    assert role_for_course_key("first_aid") == "first_aider"
    assert role_for_course_key("First Aid") == "first_aider"
    assert role_for_course_key("first-aid") == "first_aider"
    assert role_for_course_key("fire_marshall") == "fire_marshal"
    assert role_for_course_key("mental_health_first_aid") == "mhfa"
    # Not on any allowlist, despite containing "first aid".
    assert role_for_course_key("first_aid_appointed_person_refresher") is None
    assert role_for_course_key("fire_extinguisher_awareness") is None
    assert role_for_course_key(None) is None


def test_a_course_for_another_role_does_not_count():
    snapshot = _snapshot(
        people=[_person(pid=1, name="Pat")],
        courses=[_course(cid=1, key="fire_marshal")],
        cells=[_cell(person_id=1, course_id=1)],
    )
    [first_aid, fire] = assemble_coverage(
        quotas=[
            _quota(quota_id=1, role_key="first_aider", required_n=1),
            _quota(quota_id=2, role_key="fire_marshal", required_n=1, template_key=FIRE_TEMPLATE_KEY),
        ],
        snapshot=snapshot,
        today=TODAY,
    )
    assert first_aid.current_m == 0
    assert fire.current_m == 1


# --------------------------------------------- AC-03 unknown is not a failure


def test_null_match_department_is_unknown_not_guessed_from_location_name():
    snapshot = _snapshot(
        people=[_person(pid=1, name="Pat", department=DEPARTMENT)],
        courses=[_course(cid=1, key="first_aid")],
        cells=[_cell(person_id=1, course_id=1)],
    )
    [state] = assemble_coverage(
        quotas=[_quota(required_n=1, match_department=None)],
        snapshot=snapshot,
        today=TODAY,
    )
    assert state.unknown is True
    assert state.met is None
    assert state.gap is False
    assert state.current_m == 0


def test_department_matching_the_location_name_does_not_count_without_the_bind():
    """Location "Workshop" is not the Atlas department "Workshop" by luck."""
    snapshot = _snapshot(
        people=[_person(pid=1, name="Pat", department="Workshop")],
        courses=[_course(cid=1, key="first_aid")],
        cells=[_cell(person_id=1, course_id=1)],
    )
    [state] = assemble_coverage(
        quotas=[_quota(required_n=1, match_department="Engineer")],
        snapshot=snapshot,
        today=TODAY,
    )
    assert state.current_m == 0
    assert state.gap is True
    assert state.unknown is False


def test_department_comparison_is_exact_and_case_sensitive():
    snapshot = _snapshot(
        people=[_person(pid=1, name="Pat", department="workshop")],
        courses=[_course(cid=1, key="first_aid")],
        cells=[_cell(person_id=1, course_id=1)],
    )
    [state] = assemble_coverage(
        quotas=[_quota(required_n=1, match_department="Workshop")],
        snapshot=snapshot,
        today=TODAY,
    )
    assert state.current_m == 0


def test_missing_import_is_unknown_with_a_banner_not_an_error():
    quotas = [_quota(required_n=2)]
    snapshot = _snapshot(has_import=False)
    [state] = assemble_coverage(quotas=quotas, snapshot=snapshot, today=TODAY)
    assert state.unknown is True
    assert state.met is None
    assert state.gap is False
    assert state.current_m == 0
    assert coverage_banner(quotas=quotas, snapshot=snapshot) == NO_IMPORT_BANNER


def test_unset_department_raises_the_unknown_banner():
    quotas = [_quota(match_department=None)]
    snapshot = _snapshot(people=[_person(pid=1, name="Pat")])
    assert coverage_banner(quotas=quotas, snapshot=snapshot) == UNKNOWN_DEPARTMENT_BANNER


# -------------------------------------------------------- AC-04 quota writes


@pytest.mark.asyncio
async def test_create_quota_is_idempotent_for_the_same_tuple():
    db = _FakeDb(rows={Location: [_location()], ComplianceRequirementTemplate: [_template()]})

    row, created = await create_quota_async(
        db,
        tenant_id=TENANT,
        location_id=LOCATION_ID,
        role_key="first_aider",
        required_n=2,
        template_key=TEMPLATE_KEY,
        match_department=DEPARTMENT,
    )
    assert created is True

    same, created_again = await create_quota_async(
        db,
        tenant_id=TENANT,
        location_id=LOCATION_ID,
        role_key="first_aider",
        required_n=3,
        template_key=TEMPLATE_KEY,
        match_department=DEPARTMENT,
    )
    assert created_again is False
    assert same is row
    assert same.required_n == 3
    assert len(db.added_of(CompetenceCoverageQuota)) == 1


@pytest.mark.asyncio
async def test_quota_for_a_location_in_another_tenant_is_not_found():
    db = _FakeDb(
        rows={
            Location: [_location(tenant_id=OTHER_TENANT)],
            ComplianceRequirementTemplate: [_template()],
        }
    )

    with pytest.raises(NotFoundError) as exc_info:
        await create_quota_async(
            db,
            tenant_id=TENANT,
            location_id=LOCATION_ID,
            role_key="first_aider",
            required_n=1,
            template_key=TEMPLATE_KEY,
        )
    # Fail closed: the message must not confirm the location exists elsewhere.
    assert "not found" in str(exc_info.value)
    assert str(OTHER_TENANT) not in str(exc_info.value)
    assert db.added_of(CompetenceCoverageQuota) == []


@pytest.mark.asyncio
async def test_quota_pointing_at_a_missing_catalogue_key_is_refused():
    db = _FakeDb(rows={Location: [_location()], ComplianceRequirementTemplate: [_template()]})

    with pytest.raises(NotFoundError):
        await create_quota_async(
            db,
            tenant_id=TENANT,
            location_id=LOCATION_ID,
            role_key="first_aider",
            required_n=1,
            template_key="not_a_catalogue_key",
        )
    assert db.added_of(CompetenceCoverageQuota) == []


@pytest.mark.asyncio
async def test_service_refuses_an_unknown_role_and_a_zero_quorum():
    db = _FakeDb(rows={Location: [_location()], ComplianceRequirementTemplate: [_template()]})

    with pytest.raises(ValidationError):
        await create_quota_async(
            db,
            tenant_id=TENANT,
            location_id=LOCATION_ID,
            role_key="site_warden",
            required_n=1,
            template_key=TEMPLATE_KEY,
        )
    with pytest.raises(ValidationError):
        await create_quota_async(
            db,
            tenant_id=TENANT,
            location_id=LOCATION_ID,
            role_key="first_aider",
            required_n=0,
            template_key=TEMPLATE_KEY,
        )
    assert db.added_of(CompetenceCoverageQuota) == []


@pytest.mark.asyncio
async def test_delete_quota_is_tenant_scoped_and_keeps_requirements():
    quota = _quota(tenant_id=OTHER_TENANT)
    requirement = ComplianceRequirement(id=31, tenant_id=TENANT, location_id=LOCATION_ID)
    db = _FakeDb(rows={CompetenceCoverageQuota: [quota], ComplianceRequirement: [requirement]})

    with pytest.raises(NotFoundError):
        await delete_quota_async(db, tenant_id=TENANT, quota_id=quota.id)
    assert db.bucket(CompetenceCoverageQuota) == [quota]

    await delete_quota_async(db, tenant_id=OTHER_TENANT, quota_id=quota.id)
    assert db.bucket(CompetenceCoverageQuota) == []
    assert db.bucket(ComplianceRequirement) == [requirement]


@pytest.mark.asyncio
async def test_list_quotas_is_tenant_scoped():
    db = _FakeDb(rows={CompetenceCoverageQuota: [_quota(quota_id=1), _quota(quota_id=2, tenant_id=OTHER_TENANT)]})
    rows = await list_quotas_async(db, tenant_id=TENANT)
    assert [row.id for row in rows] == [1]


# ---------------------------------------------------------------- AC-05 API


@pytest.mark.asyncio
async def test_coverage_endpoint_reports_counts_and_no_named_people(monkeypatch):
    monkeypatch.setattr(settings, "competence_board_enabled", True)
    db = _FakeDb(
        rows={
            CompetenceCoverageQuota: [_quota(required_n=2)],
            TrainingMatrixImport: [TrainingMatrixImport(id=1, tenant_id=TENANT, filename="atlas.xlsx")],
            TrainingMatrixPerson: [_person(pid=1, name="Pat"), _person(pid=2, name="Sam")],
            TrainingMatrixCourse: [_course(cid=1, key="first_aid")],
            TrainingMatrixCell: [_cell(person_id=1, course_id=1), _cell(person_id=2, course_id=1)],
        }
    )

    response = await board_routes.get_competence_coverage(db=db, current_user=_user())

    assert len(response.items) == 1
    item = response.items[0]
    assert item.current_m == 2
    assert item.required_n == 2
    assert item.met is True
    assert item.gap is False
    assert item.location_id == LOCATION_ID
    payload = item.model_dump()
    for person_field in ("people", "person_ids", "display_name", "atlas_person_id", "engineer_id"):
        assert person_field not in payload


@pytest.mark.asyncio
async def test_coverage_endpoint_banners_a_missing_import(monkeypatch):
    monkeypatch.setattr(settings, "competence_board_enabled", True)
    db = _FakeDb(rows={CompetenceCoverageQuota: [_quota()]})

    response = await board_routes.get_competence_coverage(db=db, current_user=_user())

    assert response.banner == NO_IMPORT_BANNER
    assert response.items[0].unknown is True
    assert response.items[0].met is None


@pytest.mark.asyncio
async def test_quota_endpoints_create_list_and_delete(monkeypatch):
    monkeypatch.setattr(settings, "competence_board_enabled", True)
    db = _FakeDb(rows={Location: [_location()], ComplianceRequirementTemplate: [_template()]})
    payload = board_routes.CompetenceCoverageQuotaCreate(
        location_id=LOCATION_ID,
        role_key="first_aider",
        required_n=2,
        template_key=TEMPLATE_KEY,
        match_department=DEPARTMENT,
    )
    response = Response()

    created = await board_routes.create_competence_coverage_quota(
        payload=payload, db=db, current_user=_user(), response=response
    )
    assert response.status_code == 201
    assert created.required_n == 2

    again = await board_routes.create_competence_coverage_quota(
        payload=payload, db=db, current_user=_user(), response=response
    )
    assert response.status_code == 200
    assert again.id == created.id
    assert len(db.added_of(CompetenceCoverageQuota)) == 1

    listed = await board_routes.list_competence_coverage_quotas(db=db, current_user=_user())
    assert [item.id for item in listed.items] == [created.id]

    await board_routes.delete_competence_coverage_quota(quota_id=created.id, db=db, current_user=_user())
    assert db.bucket(CompetenceCoverageQuota) == []


def test_quota_payload_forbids_unexpected_fields_and_bad_values():
    with pytest.raises(PydanticValidationError):
        board_routes.CompetenceCoverageQuotaCreate(
            location_id=LOCATION_ID,
            role_key="first_aider",
            required_n=1,
            template_key=TEMPLATE_KEY,
            engineer_id=9,
        )
    with pytest.raises(PydanticValidationError):
        board_routes.CompetenceCoverageQuotaCreate(
            location_id=LOCATION_ID,
            role_key="first_aider",
            required_n=0,
            template_key=TEMPLATE_KEY,
        )
    with pytest.raises(PydanticValidationError):
        board_routes.CompetenceCoverageQuotaCreate(
            location_id=LOCATION_ID,
            role_key="site_warden",
            required_n=1,
            template_key=TEMPLATE_KEY,
        )


def test_every_role_key_the_api_accepts_is_a_role_the_counter_knows():
    annotation = board_routes.CompetenceCoverageQuotaCreate.model_fields["role_key"].annotation
    assert set(annotation.__args__) == set(COVERAGE_ROLE_KEYS)


# ------------------------------------------------- AC-06 schedule overlay


def _requirement(*, requirement_id=31, location_id=LOCATION_ID, template=None, is_active=True):
    row = ComplianceRequirement(
        id=requirement_id,
        tenant_id=TENANT,
        location_id=location_id,
        next_due_date=date(2027, 3, 1),
        is_active=is_active,
    )
    row.template = template
    return row


def test_coverage_targets_skip_org_wide_untemplated_and_retired_duties():
    """The guards mirror ``is_fra_ocr_eligible`` so no unloaded relationship is read."""
    template = _template()
    assert coverage_targets([_requirement(template=template)]) == [(31, LOCATION_ID, TEMPLATE_KEY)]
    assert coverage_targets([_requirement(location_id=None, template=template)]) == []
    assert coverage_targets([_requirement(template=None)]) == []
    assert coverage_targets([_requirement(template=template, is_active=False)]) == []


@pytest.mark.asyncio
async def test_schedule_overlay_reports_a_gap_without_moving_the_due_date():
    template = _template()
    requirement = _requirement(template=template)
    original_due = requirement.next_due_date
    db = _FakeDb(
        rows={
            CompetenceCoverageQuota: [_quota(required_n=2)],
            TrainingMatrixImport: [TrainingMatrixImport(id=1, tenant_id=TENANT, filename="atlas.xlsx")],
            TrainingMatrixPerson: [_person(pid=1, name="Pat")],
            TrainingMatrixCourse: [_course(cid=1, key="first_aid")],
            TrainingMatrixCell: [_cell(person_id=1, course_id=1)],
            ComplianceRequirement: [requirement],
        }
    )

    overlay = await load_coverage_overlay_async(
        db,
        tenant_id=TENANT,
        targets=[(requirement.id, LOCATION_ID, TEMPLATE_KEY)],
        today=TODAY,
    )

    state = overlay[requirement.id]
    assert state.gap is True
    assert state.current_m == 1
    assert state.required_n == 2
    assert requirement.next_due_date == original_due
    # ADR-0020: the gap is a second fact, never a new person-scoped row.
    assert db.added_of(ComplianceRequirement) == []
    assert db.bucket(ComplianceRequirement) == [requirement]


@pytest.mark.asyncio
async def test_schedule_overlay_ignores_a_requirement_with_no_matching_quota():
    db = _FakeDb(rows={CompetenceCoverageQuota: [_quota(location_id=99)]})
    assert (
        await load_coverage_overlay_async(
            db,
            tenant_id=TENANT,
            targets=[(31, LOCATION_ID, TEMPLATE_KEY)],
            today=TODAY,
        )
        == {}
    )


@pytest.mark.asyncio
async def test_schedule_overlay_ignores_a_quota_bound_to_another_template():
    db = _FakeDb(rows={CompetenceCoverageQuota: [_quota(template_key=FIRE_TEMPLATE_KEY)]})
    assert (
        await load_coverage_overlay_async(
            db,
            tenant_id=TENANT,
            targets=[(31, LOCATION_ID, TEMPLATE_KEY)],
            today=TODAY,
        )
        == {}
    )


@pytest.mark.asyncio
async def test_schedule_overlay_is_absent_while_the_board_flag_is_closed(monkeypatch):
    monkeypatch.setattr(settings, "competence_board_enabled", False)
    requirement = _requirement(template=_template())
    db = _FakeDb(rows={CompetenceCoverageQuota: [_quota(required_n=2)]})

    assert await schedule_routes._coverage_overlay(db, [requirement], tenant_id=TENANT) == {}
    # Kill switch means kill: the closed flag must not even reach the database.
    assert db.statements == []


@pytest.mark.asyncio
async def test_schedule_response_carries_the_coverage_fields_only_when_open(monkeypatch):
    template = _template()
    requirement = _requirement(template=template)
    requirement.external_id = "ext-31"
    requirement.reference_number = "CSR-2026-0031"
    requirement.template_id = template.id
    requirement.title = "First-aider Coverage (n of m)"
    requirement.taxonomy_id = "02.09"
    requirement.anchor = "schedule"
    requirement.statutory = True
    requirement.is_active = True
    requirement.frequency_months = 12
    requirement.created_at = datetime(2026, 9, 1, 9, 0, tzinfo=timezone.utc)

    closed = schedule_routes._requirement_response(requirement, coverage=None)
    assert closed.coverage_gap is False
    assert closed.coverage_met is None
    assert closed.coverage_current_m is None
    assert closed.next_due_date == date(2027, 3, 1)

    monkeypatch.setattr(settings, "competence_board_enabled", True)
    db = _FakeDb(
        rows={
            CompetenceCoverageQuota: [_quota(required_n=2)],
            TrainingMatrixImport: [TrainingMatrixImport(id=1, tenant_id=TENANT, filename="atlas.xlsx")],
            TrainingMatrixPerson: [_person(pid=1, name="Pat")],
            TrainingMatrixCourse: [_course(cid=1, key="first_aid")],
            TrainingMatrixCell: [_cell(person_id=1, course_id=1)],
        }
    )
    overlay = await schedule_routes._coverage_overlay(db, [requirement], tenant_id=TENANT)
    open_response = schedule_routes._requirement_response(requirement, coverage=overlay[requirement.id])
    assert open_response.coverage_gap is True
    assert open_response.coverage_met is False
    assert open_response.coverage_current_m == 1
    assert open_response.coverage_required_n == 2
    # The date-derived status is untouched: this obligation is not overdue.
    assert open_response.status == "current"
    assert open_response.next_due_date == date(2027, 3, 1)


@pytest.mark.asyncio
async def test_coverage_view_query_is_tenant_scoped(monkeypatch):
    db = _FakeDb(
        rows={
            CompetenceCoverageQuota: [_quota(tenant_id=OTHER_TENANT)],
            TrainingMatrixImport: [TrainingMatrixImport(id=1, tenant_id=OTHER_TENANT, filename="atlas.xlsx")],
        }
    )
    view = await build_coverage_view_async(db, TENANT, today=TODAY)
    assert view.items == []
    assert view.banner is None


# ------------------------------------------------------------ AC-07 catalogue


def test_catalogue_gains_the_coverage_quorum_templates_and_stays_in_range():
    keys = list(catalogue_template_keys())
    assert EXPECTED_TEMPLATE_COUNT_MIN <= len(keys) <= EXPECTED_TEMPLATE_COUNT_MAX
    for key in ("first_aider_coverage_quorum", "fire_marshal_coverage_quorum", "mhfa_coverage_quorum"):
        assert key in keys


def test_no_named_person_training_template_was_added():
    """The catalogue boundary holds: location duties only, never a named person."""
    from src.domain.data.compliance_schedule_catalogue import load_catalogue_templates

    for row in load_catalogue_templates():
        if not row["template_key"].endswith("_coverage_quorum"):
            continue
        assert "n of m" in row["title"].lower()
        assert "board" in (row["description"] or "").lower()


# ----------------------------------------------------------------- CUJ


@pytest.mark.asyncio
async def test_cuj_hr_advisor_lets_a_certificate_lapse_and_the_site_goes_to_gaps():
    """Two appointed first aiders, one expires, the location duty shows a gap."""
    quotas = [_quota(required_n=2)]
    people = [_person(pid=1, name="Pat"), _person(pid=2, name="Sam")]
    courses = [_course(cid=1, key="first_aid")]

    current = _snapshot(
        people=people,
        courses=courses,
        cells=[
            _cell(person_id=1, course_id=1, expires_on=date(2027, 1, 1)),
            _cell(person_id=2, course_id=1, expires_on=date(2027, 1, 1)),
        ],
    )
    [before] = assemble_coverage(quotas=quotas, snapshot=current, today=TODAY)
    assert before.met is True and before.gap is False

    lapsed = _snapshot(
        people=people,
        courses=courses,
        cells=[
            _cell(person_id=1, course_id=1, expires_on=date(2027, 1, 1)),
            _cell(person_id=2, course_id=1, expires_on=date(2026, 8, 1)),
        ],
    )
    [after] = assemble_coverage(quotas=quotas, snapshot=lapsed, today=TODAY)
    assert after.current_m == 1
    assert after.met is False
    assert after.gap is True


@pytest.mark.asyncio
async def test_cuj_a_quota_does_not_create_a_compliance_requirement():
    db = _FakeDb(rows={Location: [_location()], ComplianceRequirementTemplate: [_template()]})

    await create_quota_async(
        db,
        tenant_id=TENANT,
        location_id=LOCATION_ID,
        role_key="first_aider",
        required_n=2,
        template_key=TEMPLATE_KEY,
        match_department=DEPARTMENT,
    )

    assert db.added_of(ComplianceRequirement) == []
    assert db.bucket(ComplianceRequirement) == []
