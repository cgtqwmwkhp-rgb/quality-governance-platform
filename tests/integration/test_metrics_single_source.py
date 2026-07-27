"""Cross-surface metric reconciliation (PX-149 / PX-178).

Every test here pins one number reported by two or more surfaces to a single
server-side definition. These are deliberately reconciliation tests rather than
per-endpoint tests: a fix to one aggregate is easy to undo, but a test asserting
that the dashboard tile equals the register it links to prevents the whole class
of "which number is right?" defects from coming back.

Two kinds of assertion appear below and the distinction matters:

* Cross-surface equality (``dashboard == register``) is asserted absolutely. It
  is the invariant under test and must hold whatever else is in the database.
* Counts of the rows a test seeds are asserted as deltas around the seed. The
  integration schema is only dropped between tests on SQLite; on PostgreSQL
  (which is what CI runs) rows from every earlier test are still present, so an
  absolute count would be asserting the state of the whole suite rather than the
  behaviour of the endpoint.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from src.domain.models.capa import CAPAAction, CAPAPriority, CAPASource, CAPAStatus, CAPAType
from src.domain.models.incident import (
    ActionStatus,
    Incident,
    IncidentAction,
    IncidentSeverity,
    IncidentStatus,
    IncidentType,
)
from src.domain.models.risk_register import EnterpriseRisk
from src.domain.models.tenant import Tenant
from src.infrastructure.database import async_session_maker

TENANT = 1
OTHER_TENANT_SLUG = "ssot-cross-tenant-control"

# Deltas the register seed below is expected to produce for a tenant-1 caller.
SEEDED_REGISTER_TOTAL = 4
SEEDED_REGISTER_ACTIVE = 3
SEEDED_REGISTER_HIGH_CRITICAL = 2
SEEDED_REGISTER_PENDING_TRIAGE = 1


async def _other_tenant_id() -> int:
    """Get-or-create a second tenant to act as the cross-tenant control.

    Its id is looked up rather than assumed: ``tenants`` is only truncated
    between tests on SQLite, and PostgreSQL enforces the foreign key that a
    hardcoded id would violate on a fresh database.
    """
    async with async_session_maker() as session:
        existing = (await session.execute(select(Tenant).where(Tenant.slug == OTHER_TENANT_SLUG))).scalar_one_or_none()
        if existing is not None:
            return int(existing.id)
        tenant = Tenant(
            name="SSOT cross-tenant control",
            slug=OTHER_TENANT_SLUG,
            admin_email="ssot-control@test.example.com",
            is_active=True,
            subscription_tier="standard",
        )
        session.add(tenant)
        await session.commit()
        return int(tenant.id)


def _aware_past(days: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=days)


def _naive_past(days: int) -> datetime:
    return _aware_past(days).replace(tzinfo=None)


def _risk(*, suffix: str, tenant_id: int, status: str, score: int, triage: str | None) -> EnterpriseRisk:
    return EnterpriseRisk(
        tenant_id=tenant_id,
        reference=f"RSK-SSOT-{suffix}"[:50],
        title=f"Single-source risk {suffix}",
        description="Seeded for metric reconciliation tests.",
        category="operational",
        inherent_likelihood=3,
        inherent_impact=3,
        inherent_score=9,
        residual_likelihood=min(5, max(1, score // 4 or 1)),
        residual_impact=min(5, max(1, score // 4 or 1)),
        residual_score=score,
        treatment_strategy="treat",
        status=status,
        suggestion_triage_status=triage,
        created_by=1,
    )


async def _seed_register() -> None:
    """Seed a register whose visible, active and high-risk populations all differ.

    Scores map onto the canonical 5x5 bands: 20 critical, 12 high, 6 medium,
    3 low.
    """
    tag = uuid.uuid4().hex[:8]
    other = await _other_tenant_id()
    rows = [
        _risk(suffix=f"{tag}-A", tenant_id=TENANT, status="active", score=20, triage=None),
        _risk(suffix=f"{tag}-B", tenant_id=TENANT, status="active", score=12, triage="accepted"),
        _risk(suffix=f"{tag}-C", tenant_id=TENANT, status="monitoring", score=6, triage=None),
        _risk(suffix=f"{tag}-D", tenant_id=TENANT, status="closed", score=3, triage=None),
        # Awaiting import triage: excluded from every headline view.
        _risk(suffix=f"{tag}-E", tenant_id=TENANT, status="active", score=25, triage="pending"),
        # Another tenant: must never appear in either surface.
        _risk(suffix=f"{tag}-F", tenant_id=other, status="active", score=25, triage=None),
    ]
    async with async_session_maker() as session:
        session.add_all(rows)
        await session.commit()


async def _seed_incidents(*, tenant_id: int, count: int) -> None:
    tag = uuid.uuid4().hex[:6]
    async with async_session_maker() as session:
        for i in range(count):
            session.add(
                Incident(
                    tenant_id=tenant_id,
                    reference_number=f"INC-SSOT-{tag}-{i:03d}",
                    title=f"Single-source incident {tag} {i}",
                    description="Seeded for metric reconciliation tests.",
                    incident_type=IncidentType.OTHER,
                    severity=IncidentSeverity.MEDIUM,
                    # Mixed statuses and dates: the register total must not be
                    # narrowed by a status exclusion or a reporting window.
                    status=IncidentStatus.CLOSED if i % 3 == 0 else IncidentStatus.REPORTED,
                    incident_date=_aware_past(i * 20),
                    reported_date=_aware_past(i * 20),
                    created_by_id=1,
                )
            )
        await session.commit()


def _capa(*, tag: str, suffix: str, status: CAPAStatus, due_days: int | None) -> CAPAAction:
    # MANAGEMENT_REVIEW with a null source_id: the audit-finding source carries a
    # tenant-scoped partial unique index on (tenant_id, source_id) in PostgreSQL,
    # so seeding several rows under it would collide.
    return CAPAAction(
        tenant_id=TENANT,
        reference_number=f"CAPA-SSOT-{tag}-{suffix}",
        title=f"CAPA {tag} {suffix}",
        description="Seeded for metric reconciliation tests.",
        capa_type=CAPAType.CORRECTIVE,
        status=status,
        priority=CAPAPriority.HIGH,
        source_type=CAPASource.MANAGEMENT_REVIEW,
        source_id=None,
        due_date=None if due_days is None else _naive_past(due_days),
        created_by_id=1,
        assigned_to_id=1,
    )


async def _seed_overdue_actions(*, capa: int, incident_actions: int) -> int:
    """Seed overdue actions across two stores.

    Also seeds two rows that are past due but must not be counted as overdue.
    Returns the number of genuinely overdue rows added.
    """
    tag = uuid.uuid4().hex[:6]
    async with async_session_maker() as session:
        for i in range(capa):
            session.add(_capa(tag=tag, suffix=f"{i:03d}", status=CAPAStatus.IN_PROGRESS, due_days=30))
        # A closed CAPA past its due date is not overdue — it is done.
        session.add(_capa(tag=tag, suffix="closed", status=CAPAStatus.CLOSED, due_days=30))
        # An open CAPA with no due date cannot be overdue.
        session.add(_capa(tag=tag, suffix="nodue", status=CAPAStatus.OPEN, due_days=None))

        incident = Incident(
            tenant_id=TENANT,
            # incidents.reference_number is varchar(20) in PostgreSQL.
            reference_number=f"INC-SSOTA-{tag}",
            title=f"Incident carrying overdue actions {tag}",
            description="Seeded for metric reconciliation tests.",
            incident_type=IncidentType.OTHER,
            severity=IncidentSeverity.MEDIUM,
            status=IncidentStatus.PENDING_ACTIONS,
            incident_date=_aware_past(40),
            reported_date=_aware_past(40),
            created_by_id=1,
        )
        session.add(incident)
        await session.flush()
        for i in range(incident_actions):
            session.add(
                IncidentAction(
                    tenant_id=TENANT,
                    incident_id=incident.id,
                    reference_number=f"IACT-SSOT-{tag}-{i:03d}",
                    title=f"Overdue incident action {tag} {i}",
                    description="Seeded for metric reconciliation tests.",
                    status=ActionStatus.OPEN,
                    due_date=_aware_past(15),
                    owner_id=1,
                )
            )
        await session.commit()
    return capa + incident_actions


async def _get(client: AsyncClient, path: str) -> dict:
    res = await client.get(path)
    assert res.status_code == 200, f"{path} -> {res.status_code} {res.text}"
    return res.json()


async def _register_total(client: AsyncClient) -> int:
    return int((await _get(client, "/api/v1/risk-register/?limit=1"))["total"])


async def _pending_triage_total(client: AsyncClient) -> int:
    return int((await _get(client, "/api/v1/risk-register/?suggestion_triage=pending&limit=1"))["total"])


async def _dashboard_risks(client: AsyncClient) -> dict:
    return (await _get(client, "/api/v1/executive-dashboard?period_days=30"))["risks"]


async def _dashboard_incident_total(client: AsyncClient) -> int:
    return int((await _get(client, "/api/v1/executive-dashboard?period_days=30"))["incidents"]["register_total"])


async def _incident_list_total(client: AsyncClient) -> int:
    return int((await _get(client, "/api/v1/incidents/?page_size=1"))["total"])


async def _operational_risk_total(client: AsyncClient) -> int:
    return int((await _get(client, "/api/v1/risks/"))["total"])


# ---------------------------------------------------------------------------
# Risk total: executive dashboard vs the Enterprise Risk Register
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dashboard_risk_total_matches_risk_register(admin_client: AsyncClient) -> None:
    """The executive risk tile and the register must count the same rows.

    Before the fix the dashboard counted the operational ``risks`` table, which
    nothing but ``POST /api/v1/risks/`` writes, so it read 0 against a populated
    register.
    """
    before = await _dashboard_risks(admin_client)

    await _seed_register()

    risks = await _dashboard_risks(admin_client)
    register_total = await _register_total(admin_client)

    assert risks["register_total"] == register_total
    assert risks["register_total"] - before["register_total"] == SEEDED_REGISTER_TOTAL
    assert risks["total_active"] - before["total_active"] == SEEDED_REGISTER_ACTIVE
    assert risks["high_critical"] - before["high_critical"] == SEEDED_REGISTER_HIGH_CRITICAL


@pytest.mark.asyncio
async def test_analytics_kpis_risk_total_matches_risk_register(admin_client: AsyncClient) -> None:
    """`/analytics/kpis` is a projection of the dashboard, so it must agree too."""
    await _seed_register()

    kpi_risks = (await _get(admin_client, "/api/v1/analytics/kpis"))["risks"]

    assert kpi_risks["total"] == await _register_total(admin_client)


@pytest.mark.asyncio
async def test_dashboard_risk_total_excludes_pending_and_other_tenants(admin_client: AsyncClient) -> None:
    """Rows hidden from the register must be hidden from the aggregate identically."""
    before_visible = (await _dashboard_risks(admin_client))["register_total"]
    before_pending = await _pending_triage_total(admin_client)

    await _seed_register()

    risks = await _dashboard_risks(admin_client)
    pending = await _pending_triage_total(admin_client)

    # Six rows were inserted; only the four visible tenant-1 rows may land in
    # the headline number, and the aggregate must agree with the list about it.
    assert risks["register_total"] == await _register_total(admin_client)
    assert risks["register_total"] - before_visible == SEEDED_REGISTER_TOTAL
    assert pending - before_pending == SEEDED_REGISTER_PENDING_TRIAGE


# ---------------------------------------------------------------------------
# Overdue actions: three surfaces, one predicate
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_overdue_action_count_agrees_across_every_surface(admin_client: AsyncClient) -> None:
    """Summary tile, view-count chip and analytics KPI must be one number.

    `/analytics/kpis` previously returned a hardcoded stub, which is why UAT saw
    an overdue count of 0 on the analytics surface while the Actions page said 10.
    """
    before = (await _get(admin_client, "/api/v1/actions/summary"))["overdue"]

    seeded = await _seed_overdue_actions(capa=9, incident_actions=1)

    summary_overdue = (await _get(admin_client, "/api/v1/actions/summary"))["overdue"]
    view_counts_overdue = (await _get(admin_client, "/api/v1/actions/view-counts"))["overdue"]
    kpi_overdue = (await _get(admin_client, "/api/v1/analytics/kpis"))["actions"]["overdue"]

    assert summary_overdue - before == seeded
    assert view_counts_overdue == summary_overdue
    assert kpi_overdue == summary_overdue


@pytest.mark.asyncio
async def test_analytics_kpis_action_total_is_not_a_stub(admin_client: AsyncClient) -> None:
    """The whole analytics actions block must be live, not just `overdue`."""
    await _seed_overdue_actions(capa=2, incident_actions=1)

    summary = await _get(admin_client, "/api/v1/actions/summary")
    kpi_actions = (await _get(admin_client, "/api/v1/analytics/kpis"))["actions"]

    by_display = summary["by_display_status"]
    assert kpi_actions["total"] == summary["total"]
    assert kpi_actions["open"] == by_display.get("open", 0) + by_display.get("in_progress", 0)
    assert kpi_actions["total"] > 0


@pytest.mark.asyncio
async def test_overdue_excludes_done_and_undated_actions(admin_client: AsyncClient) -> None:
    """Overdue means open and past due — not "has a due date in the past"."""
    before = await _get(admin_client, "/api/v1/actions/summary")

    seeded = await _seed_overdue_actions(capa=3, incident_actions=1)

    after = await _get(admin_client, "/api/v1/actions/summary")

    # Seed adds two extra CAPA rows (one closed past-due, one open undated),
    # both of which count towards the total but neither towards overdue.
    assert after["total"] - before["total"] == seeded + 2
    assert after["overdue"] - before["overdue"] == seeded


# ---------------------------------------------------------------------------
# Incident register total: executive dashboard vs the incident register
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dashboard_incident_register_total_matches_incident_register(admin_client: AsyncClient) -> None:
    """Both sides must derive from the tenant predicate and nothing else.

    Neither side may narrow by status, by reporting window or by a soft-delete
    flag: this is the guard that keeps `register_total` reconcilable with the
    list the user sees.
    """
    before = await _dashboard_incident_total(admin_client)

    await _seed_incidents(tenant_id=TENANT, count=7)
    await _seed_incidents(tenant_id=await _other_tenant_id(), count=2)

    dash_total = await _dashboard_incident_total(admin_client)

    assert dash_total == await _incident_list_total(admin_client)
    assert dash_total - before == 7, "the other tenant's incidents must be in neither number"


@pytest.mark.asyncio
async def test_superuser_incident_list_scope_differs_from_dashboard_scope(
    superuser_client: AsyncClient,
) -> None:
    """Characterises the open defect behind the reported 59 vs 60 gap.

    `GET /api/v1/incidents/` passes ``skip_tenant_check=is_superuser``, so for a
    superuser the register lists every tenant's rows, while the executive
    dashboard is always scoped to the caller's tenant. Nothing is excluded from
    the aggregate — the register is over-reporting.

    The fix belongs in ``src/api/routes/incidents.py`` / ``IncidentService``,
    which this change does not own. This test exists so that whoever tightens
    that scope is forced to come back and fold the superuser path into
    ``test_dashboard_incident_register_total_matches_incident_register`` above,
    rather than the divergence quietly persisting.
    """
    before_dash = await _dashboard_incident_total(superuser_client)
    before_list = await _incident_list_total(superuser_client)

    await _seed_incidents(tenant_id=TENANT, count=5)
    await _seed_incidents(tenant_id=await _other_tenant_id(), count=1)

    dash_total = await _dashboard_incident_total(superuser_client)
    list_total = await _incident_list_total(superuser_client)

    assert dash_total - before_dash == 5, "dashboard stays tenant-scoped"
    assert list_total - before_list == 6, "register list currently spans tenants for superusers"
    assert list_total > dash_total, "the gap is a wider list, not a narrower aggregate"


# ---------------------------------------------------------------------------
# One risk source
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_operational_risks_endpoint_is_advertised_as_deprecated(admin_client: AsyncClient) -> None:
    """`/risks/` is retained for existing consumers but must not look canonical."""
    res = await admin_client.get("/api/v1/risks/")
    assert res.status_code == 200, res.text
    assert res.headers.get("Deprecation") == "true"
    assert 'rel="successor-version"' in res.headers.get("Link", "")
    assert "/api/v1/risk-register/" in res.headers.get("Link", "")


@pytest.mark.asyncio
async def test_operational_risks_endpoint_does_not_serve_the_register(admin_client: AsyncClient) -> None:
    """The two paths are different stores; `/risks/` must not be read as the register.

    Documents why `/risks/` reported 0 against a populated register rather than
    leaving a future reader to assume a broken filter.
    """
    before = await _operational_risk_total(admin_client)

    await _seed_register()

    assert await _operational_risk_total(admin_client) == before, "register writes must not appear in /risks/"
    assert await _register_total(admin_client) >= SEEDED_REGISTER_TOTAL


def test_operational_risk_routes_are_deprecated_in_the_published_schema() -> None:
    from src.main import app

    paths = app.openapi()["paths"]
    operational = [(p, m) for p, ops in paths.items() if p.startswith("/api/v1/risks") for m, _ in ops.items()]
    assert operational, "operational risk paths should still be published"
    for path, method in operational:
        assert paths[path][method].get("deprecated") is True, f"{method.upper()} {path} not marked deprecated"

    # The successor must not be tarred with the same brush.
    assert paths["/api/v1/risk-register/"]["get"].get("deprecated") is not True
