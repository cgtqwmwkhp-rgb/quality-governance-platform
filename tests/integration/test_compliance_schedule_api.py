"""Integration tests for Compliance Schedule API (Wave 1)."""

from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from src.core.config import settings
from src.domain.models.compliance_schedule import ComplianceRequirementTemplate, ComplianceScheduleAnchor
from src.domain.services.compliance_schedule_kill_switch import reset_compliance_schedule_kill_switch_cache


@pytest.fixture
def enable_compliance_schedule(monkeypatch):
    monkeypatch.setattr(settings, "compliance_schedule_enabled", True)
    reset_compliance_schedule_kill_switch_cache()
    yield
    reset_compliance_schedule_kill_switch_cache()


@pytest.fixture
async def seeded_template(test_session):
    template = ComplianceRequirementTemplate(
        tenant_id=None,
        template_key="wave1-fra",
        title="Fire Risk Assessment",
        taxonomy_id="HS-01",
        description="Annual FRA",
        regulatory_basis="Regulatory Reform (Fire Safety) Order 2005",
        frequency_months=12,
        frequency_days=None,
        anchor=ComplianceScheduleAnchor.SCHEDULE,
        statutory=True,
        is_active=True,
    )
    test_session.add(template)
    await test_session.commit()
    await test_session.refresh(template)
    return template


def _cs_headers(permissions: str) -> dict[str, str]:
    from tests.integration.conftest import _generate_test_jwt

    token = _generate_test_jwt(
        user_id="1",
        role="admin",
        is_superuser=False,
        permissions=permissions,
    )
    return {"Authorization": f"Bearer {token}"}


def _tenant_headers(tenant_id: int, user_id: str = "1") -> dict[str, str]:
    """Admin headers scoped to a named tenant, for cross-tenant assertions."""
    from tests.integration.conftest import _generate_test_jwt

    token = _generate_test_jwt(user_id=user_id, tenant_id=tenant_id, role="admin", is_superuser=False)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_flag_off_returns_404(client: AsyncClient, auth_headers: dict, monkeypatch):
    monkeypatch.setattr(settings, "compliance_schedule_enabled", False)
    reset_compliance_schedule_kill_switch_cache()
    response = await client.get("/api/v1/compliance-schedule/stats", headers=auth_headers)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_kill_switch_engaged_returns_404(
    client: AsyncClient,
    auth_headers: dict,
    enable_compliance_schedule,
    monkeypatch,
):
    async def _closed() -> bool:
        return False

    monkeypatch.setattr(
        "src.api.routes.compliance_schedule.compliance_schedule_is_open",
        _closed,
    )
    response = await client.get("/api/v1/compliance-schedule/stats", headers=auth_headers)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_forbidden_without_permission(client: AsyncClient, enable_compliance_schedule):
    headers = _cs_headers("incident:read")
    response = await client.get("/api/v1/compliance-schedule/stats", headers=headers)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_happy_path_activate_complete(
    client: AsyncClient,
    enable_compliance_schedule,
    seeded_template,
    superuser_auth_headers: dict,
):
    headers = superuser_auth_headers

    catalogue = await client.get("/api/v1/compliance-schedule/catalogue", headers=headers)
    assert catalogue.status_code == 200
    keys = {item["template_key"] for item in catalogue.json()["items"]}
    assert "wave1-fra" in keys

    activate = await client.post(
        "/api/v1/compliance-schedule/catalogue/wave1-fra/activate",
        headers=headers,
        json={"next_due_date": "2026-04-01"},
    )
    assert activate.status_code == 201, activate.text
    requirement = activate.json()
    assert requirement["reference_number"].startswith("CSR-")
    assert requirement["next_due_date"] == "2026-04-01"
    assert requirement["status"] in {"current", "due_soon", "overdue"}
    assert "Expired" not in str(requirement)

    req_id = requirement["id"]
    complete = await client.post(
        f"/api/v1/compliance-schedule/requirements/{req_id}/records",
        headers=headers,
        json={
            "completed_at": datetime(2026, 4, 2, tzinfo=timezone.utc).isoformat(),
            "check_passed": True,
            "notes": "Completed on site",
        },
    )
    assert complete.status_code == 201, complete.text
    record = complete.json()
    assert record["reference_number"].startswith("CRC-")
    assert record["outcome"] == "completed"
    assert record["due_date"] == "2026-04-01"

    detail = await client.get(
        f"/api/v1/compliance-schedule/requirements/{req_id}",
        headers=headers,
    )
    assert detail.status_code == 200
    updated = detail.json()
    assert updated["next_due_date"] == "2027-04-01"
    assert updated["last_completed_at"] is not None

    stats = await client.get("/api/v1/compliance-schedule/stats", headers=headers)
    assert stats.status_code == 200
    body = stats.json()
    assert body["total_active"] >= 1
    assert set(body) >= {"total_active", "current", "due_soon", "overdue"}


@pytest.mark.asyncio
async def test_stats_are_scoped_to_the_callers_tenant(
    client: AsyncClient,
    enable_compliance_schedule,
):
    """An obligation raised in one tenant must not move another tenant's counts.

    These four counts are now published on the executive dashboard's Compliance
    Schedule tile, where they read as the whole organisation's obligation
    position. Asserted as a before/after delta on the second tenant rather than
    as "must be zero", so the test states tenant isolation itself and does not
    quietly become a check that the database happened to be empty.
    """
    tenant_a = _tenant_headers(1)
    tenant_b = _tenant_headers(2, user_id="2")

    def _counts(response) -> dict[str, int]:
        assert response.status_code == 200, response.text
        body = response.json()
        return {key: body[key] for key in ("total_active", "current", "due_soon", "overdue")}

    before_a = _counts(await client.get("/api/v1/compliance-schedule/stats", headers=tenant_a))
    before_b = _counts(await client.get("/api/v1/compliance-schedule/stats", headers=tenant_b))

    # Well beyond derive_status's 30-day due_soon horizon, computed rather than
    # written as a literal so the "current" assertion below does not expire.
    next_due = datetime.now(timezone.utc).date() + timedelta(days=400)
    created = await client.post(
        "/api/v1/compliance-schedule/requirements",
        headers=tenant_a,
        json={
            "title": "Tenant A only fire alarm test",
            "taxonomy_id": "HS-03",
            "frequency_months": 12,
            "next_due_date": next_due.isoformat(),
            "statutory": True,
        },
    )
    assert created.status_code == 201, created.text

    after_a = _counts(await client.get("/api/v1/compliance-schedule/stats", headers=tenant_a))
    after_b = _counts(await client.get("/api/v1/compliance-schedule/stats", headers=tenant_b))

    assert after_a["total_active"] == before_a["total_active"] + 1
    assert after_a["current"] == before_a["current"] + 1
    assert after_b == before_b


@pytest.mark.asyncio
async def test_activate_empty_catalogue_key_404(
    client: AsyncClient,
    enable_compliance_schedule,
    superuser_auth_headers: dict,
):
    response = await client.post(
        "/api/v1/compliance-schedule/catalogue/no-such-template/activate",
        headers=superuser_auth_headers,
        json={},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_create_with_due_overrides(
    client: AsyncClient,
    enable_compliance_schedule,
    superuser_auth_headers: dict,
):
    response = await client.post(
        "/api/v1/compliance-schedule/requirements",
        headers=superuser_auth_headers,
        json={
            "title": "Custom LEV",
            "taxonomy_id": "HS-02",
            "frequency_months": 14,
            "anchor": "completion",
            "next_due_date": "2026-06-15",
            "last_completed_at": "2025-04-15T10:00:00Z",
            "statutory": True,
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["next_due_date"] == "2026-06-15"
    assert body["last_completed_at"] is not None
    assert body["anchor"] == "completion"


# ---------------------------------------------------------------------------
# Duplicate activation
# ---------------------------------------------------------------------------
#
# These exercise the real SQL rather than a mocked session, because what is
# being asserted is the shape of the WHERE clause — which rows count as an
# existing activation — and a mock can only replay whatever it was told to
# return.
#
# Each test seeds its own uniquely-keyed template. The integration harness only
# drops tables on SQLite, so on PostgreSQL rows persist between tests in a
# session; a shared template key would collide and `_get_template_by_key` would
# raise on the second reader.


async def _seed_template(test_session) -> ComplianceRequirementTemplate:
    template = ComplianceRequirementTemplate(
        tenant_id=None,
        template_key=f"dup-{uuid4().hex[:12]}",
        title="Fire Risk Assessment",
        taxonomy_id="HS-01",
        description=None,
        regulatory_basis=None,
        frequency_months=12,
        frequency_days=None,
        anchor=ComplianceScheduleAnchor.SCHEDULE,
        statutory=True,
        is_active=True,
    )
    test_session.add(template)
    await test_session.commit()
    await test_session.refresh(template)
    return template


@pytest.fixture
async def unique_template(test_session):
    return await _seed_template(test_session)


async def _activate(client, headers, key, **body):
    return await client.post(
        f"/api/v1/compliance-schedule/catalogue/{key}/activate",
        headers=headers,
        json={"next_due_date": "2026-04-01", **body},
    )


@pytest.mark.asyncio
async def test_activating_the_same_template_twice_conflicts(
    client: AsyncClient,
    enable_compliance_schedule,
    unique_template,
    superuser_auth_headers: dict,
):
    key = unique_template.template_key
    first = await _activate(client, superuser_auth_headers, key)
    assert first.status_code == 201, first.text

    second = await _activate(client, superuser_auth_headers, key)
    assert second.status_code == 409, second.text

    body = second.json()
    # The user needs to know which obligation already covers this, not merely
    # that something does.
    assert first.json()["reference_number"] in str(body)


@pytest.mark.asyncio
async def test_a_refused_duplicate_leaves_exactly_one_obligation(
    client: AsyncClient,
    enable_compliance_schedule,
    unique_template,
    superuser_auth_headers: dict,
    test_session,
):
    key = unique_template.template_key
    first = await _activate(client, superuser_auth_headers, key)
    assert first.status_code == 201
    assert (await _activate(client, superuser_auth_headers, key)).status_code == 409

    # A second, different template that happens to share the title. This is here
    # so the assertion below has to be scoped by template rather than by title:
    # without a confounding row the two are indistinguishable on SQLite, which
    # the harness wipes between tests, and the test would only fail on
    # PostgreSQL, where rows persist across a session. It did exactly that.
    other = await _seed_template(test_session)
    confounder = await _activate(client, superuser_auth_headers, other.template_key)
    assert confounder.status_code == 201

    listing = await client.get(
        "/api/v1/compliance-schedule/requirements",
        headers=superuser_auth_headers,
        params={"page_size": 100},
    )
    assert listing.status_code == 200
    items = listing.json()["items"]

    same_template = [i for i in items if i["template_id"] == unique_template.id]
    assert len(same_template) == 1

    # The confounder is genuinely present, so the scoping above is doing work
    # rather than passing by coincidence.
    same_title = [i for i in items if i["title"] == unique_template.title]
    assert len(same_title) >= 2


@pytest.mark.asyncio
async def test_retiring_an_obligation_frees_the_template_again(
    client: AsyncClient,
    enable_compliance_schedule,
    unique_template,
    superuser_auth_headers: dict,
):
    key = unique_template.template_key
    first = await _activate(client, superuser_auth_headers, key)
    assert first.status_code == 201
    first_id = first.json()["id"]

    retire = await client.post(
        f"/api/v1/compliance-schedule/requirements/{first_id}/deactivate",
        headers=superuser_auth_headers,
    )
    assert retire.status_code == 200, retire.text

    again = await _activate(client, superuser_auth_headers, key)
    assert again.status_code == 201, again.text
    # A fresh obligation, not the retired one silently revived: reactivation is
    # a different operation with a different audit trail.
    assert again.json()["id"] != first_id


@pytest.mark.asyncio
async def test_the_same_template_at_two_sites_is_not_a_duplicate(
    client: AsyncClient,
    enable_compliance_schedule,
    unique_template,
    superuser_auth_headers: dict,
    test_session,
):
    from src.domain.models.location import Location, LocationKind

    sites = []
    for name in ("Depot A", "Depot B"):
        site = Location(tenant_id=1, name=f"{name} {uuid4().hex[:6]}", kind=LocationKind.SITE)
        test_session.add(site)
        sites.append(site)
    await test_session.commit()
    for site in sites:
        await test_session.refresh(site)

    key = unique_template.template_key
    a = await _activate(client, superuser_auth_headers, key, location_id=sites[0].id)
    assert a.status_code == 201, a.text
    b = await _activate(client, superuser_auth_headers, key, location_id=sites[1].id)
    assert b.status_code == 201, b.text

    # ...but a second one at the same site still is.
    again = await _activate(client, superuser_auth_headers, key, location_id=sites[0].id)
    assert again.status_code == 409, again.text


# ---------------------------------------------------------------------------
# Losing a completion race
# ---------------------------------------------------------------------------
#
# ``complete_requirement`` looks for an existing record for the occurrence and
# inserts when it finds none. Nothing holds a lock between the two, so two
# requests closing the same occurrence both read "absent" and both insert;
# ``uq_compliance_records_tenant_requirement_due`` refuses the second. What the
# loser's user sees is the subject of these tests.
#
# Assertions are scoped to the requirement id created by the test rather than to
# a count of rows in the table. The integration harness only drops tables on
# SQLite, so on PostgreSQL every earlier test's compliance records are still
# there and any global count is whatever the rest of the session happened to
# leave behind.

DUE = "2026-04-01"


async def _requirement_for_completion(client, headers, test_session) -> int:
    """An active obligation due ``DUE``, returned as a bare id.

    An id rather than the ORM row on purpose: reading an attribute off a
    fixture-owned instance after an intervening commit re-triggers a lazy load
    outside the greenlet that owns the session, which surfaces as
    ``MissingGreenlet`` rather than as anything resembling the real problem.
    """
    template = await _seed_template(test_session)
    response = await _activate(client, headers, template.template_key)
    assert response.status_code == 201, response.text
    return int(response.json()["id"])


async def _records_for(requirement_id: int) -> list:
    """Every compliance record for one requirement, read on its own connection."""
    from src.domain.models.compliance_schedule import ComplianceRecord
    from src.infrastructure.database import async_session_maker

    async with async_session_maker() as session:
        result = await session.execute(
            select(ComplianceRecord)
            .where(ComplianceRecord.requirement_id == requirement_id)
            .order_by(ComplianceRecord.id)
        )
        return list(result.scalars().all())


def _complete(client, headers, requirement_id: int, **body):
    return client.post(
        f"/api/v1/compliance-schedule/requirements/{requirement_id}/records",
        headers=headers,
        json={"completed_at": "2026-04-02T09:00:00Z", "check_passed": True, **body},
    )


async def _land_competing_record(requirement_id: int, due_date: date) -> None:
    """Commit a rival record for the same occurrence from a separate connection.

    This is the other request, reduced to the only part of it that matters: a
    committed row holding the key the caller is about to insert. It is a real
    connection committing a real row, so what refuses the caller afterwards is
    the live unique constraint and not a stand-in for it.
    """
    from src.domain.models.compliance_schedule import ComplianceFilingStatus, ComplianceRecord, ComplianceRecordOutcome
    from src.infrastructure.database import async_session_maker

    async with async_session_maker() as session:
        session.add(
            ComplianceRecord(
                tenant_id=1,
                reference_number=f"CRC-RIVAL-{uuid4().hex[:8]}",
                requirement_id=requirement_id,
                due_date=due_date,
                outcome=ComplianceRecordOutcome.COMPLETED,
                completed_at=datetime(2026, 4, 2, 8, 0, tzinfo=timezone.utc),
                check_passed=True,
                notes="rival writer",
                filing_status=ComplianceFilingStatus.NOT_FILED,
                created_by_id=1,
                updated_by_id=1,
            )
        )
        await session.commit()


@pytest.fixture
def arm_rival_writer(monkeypatch):
    """Arm a rival writer to land inside the window the race lives in.

    The gap being exercised runs from the duplicate check to the INSERT, and both
    are inside one service call, so the rival has to be committed while that call
    is in flight. ``ReferenceNumberService.generate`` is the one awaited step in
    between, which makes it the seam — the collision itself is left entirely to
    the database.

    What is simulated here is the timing, and only the timing. Under a real race
    the rival commits at a moment nobody chooses; here it commits at a moment the
    test chooses, so that the outcome is the same on every run. Everything the
    assertion turns on — a committed rival row, the constraint, the error the
    driver raises — is real.

    Yields a callable taking the requirement id and returning a list that the
    rival appends to, so a test can assert the race was genuinely provoked rather
    than trusting that it was.
    """
    from src.domain.services.reference_number import ReferenceNumberService

    original = ReferenceNumberService.generate.__func__

    def _arm(requirement_id: int) -> list[int]:
        landed: list[int] = []

        async def _generate_after_rival_lands(cls, db, record_type, model_class, year=None):
            if record_type == "compliance_record" and not landed:
                landed.append(requirement_id)
                await _land_competing_record(requirement_id, date.fromisoformat(DUE))
            return await original(cls, db, record_type, model_class, year)

        monkeypatch.setattr(
            ReferenceNumberService,
            "generate",
            classmethod(_generate_after_rival_lands),
        )
        return landed

    return _arm


@pytest.mark.asyncio
async def test_losing_a_completion_race_is_a_conflict_not_a_server_error(
    client: AsyncClient,
    enable_compliance_schedule,
    superuser_auth_headers: dict,
    test_session,
    arm_rival_writer,
):
    requirement_id = await _requirement_for_completion(client, superuser_auth_headers, test_session)
    landed = arm_rival_writer(requirement_id)

    response = await _complete(client, superuser_auth_headers, requirement_id)

    assert landed == [requirement_id], "the rival never landed; the race was not exercised"
    assert response.status_code == 409, response.text


@pytest.mark.asyncio
async def test_the_refused_completion_names_the_occurrence_it_lost(
    client: AsyncClient,
    enable_compliance_schedule,
    superuser_auth_headers: dict,
    test_session,
    arm_rival_writer,
):
    requirement_id = await _requirement_for_completion(client, superuser_auth_headers, test_session)
    arm_rival_writer(requirement_id)

    response = await _complete(client, superuser_auth_headers, requirement_id)
    assert response.status_code == 409, response.text

    body = response.json()
    # Whoever is looking at the screen has to be able to tell "already done" from
    # "your submission was lost", and the due date is what distinguishes them.
    assert DUE in str(body), body
    assert body["error"]["code"] == "DUPLICATE_ENTITY", body


@pytest.mark.asyncio
async def test_a_lost_completion_race_leaves_one_record_and_an_unmoved_schedule(
    client: AsyncClient,
    enable_compliance_schedule,
    superuser_auth_headers: dict,
    test_session,
    arm_rival_writer,
):
    requirement_id = await _requirement_for_completion(client, superuser_auth_headers, test_session)
    arm_rival_writer(requirement_id)

    assert (await _complete(client, superuser_auth_headers, requirement_id)).status_code == 409

    records = await _records_for(requirement_id)
    assert len(records) == 1, [r.reference_number for r in records]
    assert records[0].notes == "rival writer"

    # The loser must not have advanced the schedule. It rolls forward once per
    # occurrence closed, and only one was closed here — by the winner, whose
    # write went straight to the table and left next_due_date alone.
    detail = await client.get(
        f"/api/v1/compliance-schedule/requirements/{requirement_id}",
        headers=superuser_auth_headers,
    )
    assert detail.status_code == 200, detail.text
    assert detail.json()["next_due_date"] == DUE


@pytest.mark.asyncio
async def test_two_concurrent_completions_produce_one_record_and_no_server_error(
    client: AsyncClient,
    enable_compliance_schedule,
    superuser_auth_headers: dict,
    test_session,
):
    """The unchoreographed version: two real requests, in flight together.

    Which of the two paths refuses the loser — the duplicate check or the
    constraint — depends on how the event loop interleaves them, so this test
    deliberately asserts only what must hold either way. It is here because the
    choreographed tests above pick the moment the rival lands, and something has
    to check that the outcome survives when nobody picks it.
    """
    requirement_id = await _requirement_for_completion(client, superuser_auth_headers, test_session)

    first, second = await asyncio.gather(
        _complete(client, superuser_auth_headers, requirement_id),
        _complete(client, superuser_auth_headers, requirement_id),
    )

    statuses = sorted([first.status_code, second.status_code])
    assert 500 not in statuses, (first.text, second.text)
    assert statuses == [201, 409], (first.text, second.text)

    records = await _records_for(requirement_id)
    assert len(records) == 1, [r.reference_number for r in records]


# ---------------------------------------------------------------------------
# Retiring what is already retired
# ---------------------------------------------------------------------------
#
# ``deactivate_requirement`` delegates to ``update_requirement``, which audits
# the fields it changed. Setting is_active to false on a row where it is already
# false changes nothing, so there is nothing to audit and the request returned
# 200 having done and recorded nothing at all.
#
# Refused with 409 rather than returned as an idempotent success. Two reasons.
# The first is consistency: this file's other "already in that state" case,
# ``_assert_template_not_already_active``, is a 409, and a register where
# activating twice conflicts but retiring twice quietly succeeds is harder to
# predict than one where both refuse. The second is that a compliance register is
# an evidence trail, and a 200 that leaves no audit row is the one outcome an
# evidence trail cannot afford: it tells the caller a retirement happened at a
# time the log will never be able to account for.


@pytest.mark.asyncio
async def test_retiring_an_already_retired_obligation_conflicts(
    client: AsyncClient,
    enable_compliance_schedule,
    unique_template,
    superuser_auth_headers: dict,
):
    activate = await _activate(client, superuser_auth_headers, unique_template.template_key)
    assert activate.status_code == 201, activate.text
    requirement_id = activate.json()["id"]

    first = await client.post(
        f"/api/v1/compliance-schedule/requirements/{requirement_id}/deactivate",
        headers=superuser_auth_headers,
    )
    assert first.status_code == 200, first.text
    assert first.json()["is_active"] is False

    second = await client.post(
        f"/api/v1/compliance-schedule/requirements/{requirement_id}/deactivate",
        headers=superuser_auth_headers,
    )
    assert second.status_code == 409, second.text
    assert second.json()["error"]["code"] == "DUPLICATE_ENTITY", second.json()


@pytest.mark.asyncio
async def test_a_retirement_is_audited_exactly_once_however_often_it_is_asked_for(
    client: AsyncClient,
    enable_compliance_schedule,
    unique_template,
    superuser_auth_headers: dict,
):
    activate = await _activate(client, superuser_auth_headers, unique_template.template_key)
    assert activate.status_code == 201, activate.text
    requirement_id = activate.json()["id"]

    statuses = []
    for _ in range(3):
        response = await client.post(
            f"/api/v1/compliance-schedule/requirements/{requirement_id}/deactivate",
            headers=superuser_auth_headers,
        )
        statuses.append(response.status_code)

    # One retirement happened, so exactly one 200 and exactly one audit row. Both
    # assertions are needed: the count alone held before the fix as well, because
    # the surplus attempts recorded nothing — while still answering 200, which is
    # the half the count cannot see.
    assert statuses == [200, 409, 409], statuses

    retirements = await _retirement_audit_events(requirement_id)
    assert len(retirements) == 1, [e.changed_fields for e in retirements]


async def _retirement_audit_events(requirement_id: int) -> list:
    """Audit rows recording an is_active change on one requirement.

    Filtered on ``changed_fields`` rather than on the event type, because
    ``AuditLogEntry`` has no event_type column: ``record_audit_event`` maps the
    domain event onto ``action`` plus the changed field list, and the field list
    is the part that distinguishes a retirement from any other update.
    """
    from src.domain.models.audit_log import AuditLogEntry
    from src.infrastructure.database import async_session_maker

    async with async_session_maker() as session:
        result = await session.execute(
            select(AuditLogEntry).where(
                AuditLogEntry.entity_type == "compliance_requirement",
                AuditLogEntry.entity_id == str(requirement_id),
                AuditLogEntry.action == "update",
            )
        )
        entries = list(result.scalars().all())

    return [e for e in entries if "is_active" in (e.changed_fields or [])]


# ---------------------------------------------------------------------------
# A failed check owes a corrective action (W18)
# ---------------------------------------------------------------------------
#
# The unit tests for this path drive a mocked session, so they prove the service
# asks for the right row and never that the row can be written. These go through
# the API to a real schema: capa_actions.tenant_id and created_by_id are both NOT
# NULL, source_type is a database enum that had to gain the compliance_record
# label in 20260913_cs_wave0, and none of that is visible to a mock.


async def _compliance_capas_for(record_id: int) -> list:
    """CAPA rows raised for one compliance occurrence, on their own connection."""
    from src.domain.models.capa import CAPAAction, CAPASource
    from src.infrastructure.database import async_session_maker

    async with async_session_maker() as session:
        result = await session.execute(
            select(CAPAAction)
            .where(
                CAPAAction.source_type == CAPASource.COMPLIANCE_RECORD,
                CAPAAction.source_id == record_id,
            )
            .order_by(CAPAAction.id)
        )
        return list(result.scalars().all())


@pytest.mark.asyncio
async def test_a_failed_check_raises_one_capa_for_the_completing_tenant(
    client: AsyncClient,
    enable_compliance_schedule,
    superuser_auth_headers: dict,
    test_session,
):
    from src.domain.models.capa import CAPAPriority, CAPAStatus

    requirement_id = await _requirement_for_completion(client, superuser_auth_headers, test_session)

    completed = await _complete(
        client,
        superuser_auth_headers,
        requirement_id,
        check_passed=False,
        notes="Two fire doors failed inspection.",
    )
    assert completed.status_code == 201, completed.text
    record_id = completed.json()["id"]

    capas = await _compliance_capas_for(record_id)
    assert len(capas) == 1, [c.reference_number for c in capas]
    capa = capas[0]
    assert capa.tenant_id == 1
    # The occurrence identifies the failure; the obligation is the page to open.
    assert capa.source_id == record_id
    assert capa.source_reference == f"compliance_requirement:{requirement_id}"
    assert capa.status == CAPAStatus.OPEN
    # The seeded template is statutory, so this is the short-fuse branch.
    assert capa.priority == CAPAPriority.CRITICAL
    assert capa.reference_number.startswith("CAPA-")


@pytest.mark.asyncio
async def test_a_passed_check_raises_nothing(
    client: AsyncClient,
    enable_compliance_schedule,
    superuser_auth_headers: dict,
    test_session,
):
    requirement_id = await _requirement_for_completion(client, superuser_auth_headers, test_session)

    completed = await _complete(client, superuser_auth_headers, requirement_id, check_passed=True)
    assert completed.status_code == 201, completed.text

    assert await _compliance_capas_for(completed.json()["id"]) == []


@pytest.mark.asyncio
async def test_an_unrecorded_check_raises_nothing(
    client: AsyncClient,
    enable_compliance_schedule,
    superuser_auth_headers: dict,
    test_session,
):
    """A null check is "no pass/fail dimension", not a failure."""
    requirement_id = await _requirement_for_completion(client, superuser_auth_headers, test_session)

    completed = await _complete(client, superuser_auth_headers, requirement_id, check_passed=None)
    assert completed.status_code == 201, completed.text

    assert await _compliance_capas_for(completed.json()["id"]) == []


@pytest.mark.asyncio
async def test_the_raised_capa_is_reachable_from_the_actions_register(
    client: AsyncClient,
    enable_compliance_schedule,
    superuser_auth_headers: dict,
    test_session,
):
    """A CAPA nobody can find on the Actions board is not a corrective action.

    ``compliance_record`` had to be added to ``CAPA_ONLY_API_SOURCE_TYPES`` for
    this filter to reach capa_actions at all; without it the register answered
    an empty page and the Compliance schedule filter would have been a lie.
    """
    requirement_id = await _requirement_for_completion(client, superuser_auth_headers, test_session)
    completed = await _complete(
        client,
        superuser_auth_headers,
        requirement_id,
        check_passed=False,
    )
    assert completed.status_code == 201, completed.text
    record_id = completed.json()["id"]

    listing = await client.get(
        "/api/v1/actions/",
        headers=superuser_auth_headers,
        params={"source_type": "compliance_record", "page_size": 100},
    )
    assert listing.status_code == 200, listing.text
    items = listing.json()["items"]
    mine = [item for item in items if item["source_id"] == record_id]
    assert len(mine) == 1, items
    assert mine[0]["source_type"] == "compliance_record"
    # The obligation id survives hydration; the row needs it to build its link.
    assert mine[0]["source_reference"] == f"compliance_requirement:{requirement_id}"


@pytest.mark.asyncio
async def test_two_concurrent_failed_completions_raise_exactly_one_capa(
    client: AsyncClient,
    enable_compliance_schedule,
    superuser_auth_headers: dict,
    test_session,
):
    """One failure owes one corrective action, however many writers race for it.

    The loser is refused either by the duplicate check (nothing pending yet) or
    by the unique constraint (rolled back with its CAPA still in the session).
    Two CAPAs for one occurrence would mean the same remediation chased twice.
    """
    requirement_id = await _requirement_for_completion(client, superuser_auth_headers, test_session)

    first, second = await asyncio.gather(
        _complete(client, superuser_auth_headers, requirement_id, check_passed=False),
        _complete(client, superuser_auth_headers, requirement_id, check_passed=False),
    )

    assert sorted([first.status_code, second.status_code]) == [201, 409], (first.text, second.text)

    records = await _records_for(requirement_id)
    assert len(records) == 1, [r.reference_number for r in records]
    capas = await _compliance_capas_for(records[0].id)
    assert len(capas) == 1, [c.reference_number for c in capas]
