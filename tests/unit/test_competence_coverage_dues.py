"""CB-UI-4: coverage shortfall dues the location occurrence + 30-day forecast.

Overlay GET still does not move ``next_due_date`` (CB-PR5). The due-pull is a
separate write after Atlas import / quota save. QGP never writes PAMS.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from src.domain.models.competence_coverage_quota import COVERAGE_ROLE_KEYS, CompetenceCoverageQuota
from src.domain.models.compliance_schedule import ComplianceRequirement
from src.domain.models.training_matrix import (
    TrainingMatrixCell,
    TrainingMatrixCourse,
    TrainingMatrixImport,
    TrainingMatrixPerson,
)
from src.domain.services.competence_coverage_due_service import apply_coverage_shortfall_dues_async
from src.domain.services.competence_coverage_service import assemble_coverage_forecast, load_coverage_overlay_async
from tests.unit.test_competence_coverage_quorum import (
    LOCATION_ID,
    TEMPLATE_KEY,
    TENANT,
    TODAY,
    _cell,
    _course,
    _FakeDb,
    _person,
    _quota,
    _requirement,
    _snapshot,
    _template,
)


@pytest.fixture
def silent_audit(monkeypatch):
    recorded = []

    async def _record(**kwargs):
        recorded.append(kwargs)
        return None

    monkeypatch.setattr(
        "src.domain.services.competence_coverage_due_service.record_audit_event",
        _record,
    )
    return recorded


def _atlas_rows(*, people, cells, courses=None):
    return {
        CompetenceCoverageQuota: [_quota(required_n=2)],
        TrainingMatrixImport: [TrainingMatrixImport(id=1, tenant_id=TENANT, filename="atlas.xlsx")],
        TrainingMatrixPerson: list(people),
        TrainingMatrixCourse: list(courses or [_course(cid=1, key="first_aid")]),
        TrainingMatrixCell: list(cells),
    }


@pytest.mark.asyncio
async def test_shortfall_pulls_the_location_due_to_today_and_not_a_person_row(silent_audit):
    template = _template()
    requirement = _requirement(template=template)
    original = requirement.next_due_date
    db = _FakeDb(
        rows={
            **_atlas_rows(
                people=[_person(pid=1, name="Pat")],
                cells=[_cell(person_id=1, course_id=1)],
            ),
            ComplianceRequirement: [requirement],
        }
    )

    pulled = await apply_coverage_shortfall_dues_async(db, tenant_id=TENANT, today=TODAY, actor_user_id=42)

    assert original == date(2027, 3, 1)
    assert requirement.next_due_date == TODAY
    assert [(row.requirement_id, row.previous_due, row.next_due) for row in pulled] == [
        (requirement.id, original, TODAY)
    ]
    assert db.added_of(ComplianceRequirement) == []
    assert silent_audit[0]["event_type"] == "compliance_schedule.coverage_shortfall_due"
    assert silent_audit[0]["changed_fields"] == ["next_due_date"]
    assert silent_audit[0]["tenant_id"] == TENANT


@pytest.mark.asyncio
async def test_unknown_quota_does_not_due_the_location(silent_audit):
    template = _template()
    requirement = _requirement(template=template)
    original = requirement.next_due_date
    db = _FakeDb(
        rows={
            CompetenceCoverageQuota: [_quota(required_n=2, match_department=None)],
            TrainingMatrixImport: [TrainingMatrixImport(id=1, tenant_id=TENANT, filename="atlas.xlsx")],
            TrainingMatrixPerson: [_person(pid=1, name="Pat")],
            TrainingMatrixCourse: [_course(cid=1, key="first_aid")],
            TrainingMatrixCell: [_cell(person_id=1, course_id=1)],
            ComplianceRequirement: [requirement],
        }
    )

    pulled = await apply_coverage_shortfall_dues_async(db, tenant_id=TENANT, today=TODAY)

    assert pulled == []
    assert requirement.next_due_date == original
    assert silent_audit == []


@pytest.mark.asyncio
async def test_already_overdue_date_is_kept(silent_audit):
    template = _template()
    requirement = _requirement(template=template)
    requirement.next_due_date = date(2026, 8, 1)
    db = _FakeDb(
        rows={
            **_atlas_rows(
                people=[_person(pid=1, name="Pat")],
                cells=[_cell(person_id=1, course_id=1)],
            ),
            ComplianceRequirement: [requirement],
        }
    )

    pulled = await apply_coverage_shortfall_dues_async(db, tenant_id=TENANT, today=TODAY)

    assert pulled == []
    assert requirement.next_due_date == date(2026, 8, 1)
    assert silent_audit == []


@pytest.mark.asyncio
async def test_restored_cover_does_not_roll_the_due_forward(silent_audit):
    template = _template()
    requirement = _requirement(template=template)
    requirement.next_due_date = TODAY
    db = _FakeDb(
        rows={
            **_atlas_rows(
                people=[_person(pid=1, name="Pat"), _person(pid=2, name="Sam")],
                cells=[_cell(person_id=1, course_id=1), _cell(person_id=2, course_id=1)],
            ),
            ComplianceRequirement: [requirement],
        }
    )

    pulled = await apply_coverage_shortfall_dues_async(db, tenant_id=TENANT, today=TODAY)

    assert pulled == []
    assert requirement.next_due_date == TODAY
    assert silent_audit == []


@pytest.mark.asyncio
async def test_overlay_read_still_does_not_move_the_due(silent_audit):
    template = _template()
    requirement = _requirement(template=template)
    original = requirement.next_due_date
    db = _FakeDb(
        rows={
            **_atlas_rows(
                people=[_person(pid=1, name="Pat")],
                cells=[_cell(person_id=1, course_id=1)],
            ),
            ComplianceRequirement: [requirement],
        }
    )

    await load_coverage_overlay_async(
        db,
        tenant_id=TENANT,
        targets=[(requirement.id, LOCATION_ID, TEMPLATE_KEY)],
        today=TODAY,
    )
    assert requirement.next_due_date == original
    assert silent_audit == []


def test_forecast_lists_the_person_whose_expiry_drops_the_site_below_n():
    quotas = [_quota(required_n=2)]
    people = [
        _person(pid=1, name="Pat"),
        _person(pid=2, name="Sam"),
        _person(pid=3, name="Lee"),
    ]
    snapshot = _snapshot(
        people=people,
        courses=[_course(cid=1, key="first_aid")],
        cells=[
            _cell(person_id=1, course_id=1, expires_on=date(2026, 9, 12)),
            _cell(person_id=2, course_id=1, expires_on=date(2026, 9, 20)),
            _cell(person_id=3, course_id=1, expires_on=date(2027, 1, 1)),
        ],
    )
    rows = assemble_coverage_forecast(quotas=quotas, snapshot=snapshot, today=TODAY)
    assert [(row.atlas_name, row.expires_on) for row in rows] == [("Sam", date(2026, 9, 20))]
    assert rows[0].current_m == 3
    assert rows[0].required_n == 2


def test_forecast_omits_an_expiry_that_leaves_the_site_at_n():
    quotas = [_quota(required_n=2)]
    snapshot = _snapshot(
        people=[
            _person(pid=1, name="Pat"),
            _person(pid=2, name="Sam"),
            _person(pid=3, name="Lee"),
        ],
        courses=[_course(cid=1, key="first_aid")],
        cells=[
            _cell(person_id=1, course_id=1, expires_on=date(2026, 9, 12)),
            _cell(person_id=2, course_id=1, expires_on=date(2027, 1, 1)),
            _cell(person_id=3, course_id=1, expires_on=date(2027, 1, 1)),
        ],
    )
    assert assemble_coverage_forecast(quotas=quotas, snapshot=snapshot, today=TODAY) == []


def test_forecast_omits_unknown_and_already_short_quotas():
    unknown = _quota(quota_id=1, match_department=None)
    short = _quota(quota_id=2, required_n=2)
    snapshot = _snapshot(
        people=[_person(pid=1, name="Pat")],
        courses=[_course(cid=1, key="first_aid")],
        cells=[_cell(person_id=1, course_id=1, expires_on=date(2026, 9, 12))],
    )
    assert assemble_coverage_forecast(quotas=[unknown, short], snapshot=snapshot, today=TODAY) == []


def test_forecast_does_not_invent_fe_or_contract_roles():
    assert set(COVERAGE_ROLE_KEYS) == {"first_aider", "fire_marshal", "mhfa"}
    assert datetime(2026, 9, 2, tzinfo=timezone.utc).date() == TODAY
