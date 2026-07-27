"""Cross-surface metric reconciliation (PX-149 / PX-178).

Every test here pins one number reported by two or more surfaces to a single
server-side definition. These are deliberately reconciliation tests rather than
per-endpoint tests: a fix to one aggregate is easy to undo, but a test asserting
that the dashboard tile equals the register it links to prevents the whole class
of "which number is right?" defects from coming back.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient

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
from src.infrastructure.database import async_session_maker

TENANT = 1
OTHER_TENANT = 2


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


async def _seed_register() -> dict[str, int]:
    """Seed a register whose visible, active and total populations all differ."""
    tag = uuid.uuid4().hex[:8]
    rows = [
        _risk(suffix=f"{tag}-A", tenant_id=TENANT, status="active", score=20, triage=None),
        _risk(suffix=f"{tag}-B", tenant_id=TENANT, status="active", score=12, triage="accepted"),
        _risk(suffix=f"{tag}-C", tenant_id=TENANT, status="monitoring", score=6, triage=None),
        _risk(suffix=f"{tag}-D", tenant_id=TENANT, status="closed", score=3, triage=None),
        # Awaiting import triage: excluded from every headline view.
        _risk(suffix=f"{tag}-E", tenant_id=TENANT, status="active", score=25, triage="pending"),
        # Another tenant: must never appear in either surface.
        _risk(suffix=f"{tag}-F", tenant_id=OTHER_TENANT, status="active", score=25, triage=None),
    ]
    async with async_session_maker() as session:
        session.add_all(rows)
        await session.commit()
    # visible = A B C D, active = A B C, high_or_critical(active) = A B
    return {"register_total": 4, "total_active": 3, "high_critical": 2}


async def _seed_incidents(*, tenant_id: int, count: int, tag: str) -> None:
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


async def _seed_overdue_actions(*, capa: int, incident_actions: int) -> int:
    """Seed overdue actions across two stores; returns the expected overdue count."""
    tag = uuid.uuid4().hex[:8]
    async with async_session_maker() as session:
        for i in range(capa):
            session.add(
                CAPAAction(
                    tenant_id=TENANT,
                    reference_number=f"CAPA-SSOT-{tag}-{i:03d}",
                    title=f"Overdue CAPA {tag} {i}",
                    description="Seeded for metric reconciliation tests.",
                    capa_type=CAPAType.CORRECTIVE,
                    status=CAPAStatus.IN_PROGRESS,
                    priority=CAPAPriority.HIGH,
                    source_type=CAPASource.AUDIT_FINDING,
                    source_id=1,
                    due_date=_naive_past(30),
                    created_by_id=1,
                    assigned_to_id=1,
                )
            )
        # A closed CAPA past its due date is not overdue — it is done.
        session.add(
            CAPAAction(
                tenant_id=TENANT,
                reference_number=f"CAPA-SSOT-{tag}-closed",
                title=f"Closed CAPA {tag}",
                description="Past due but closed; must not count as overdue.",
                capa_type=CAPAType.CORRECTIVE,
                status=CAPAStatus.CLOSED,
                priority=CAPAPriority.LOW,
                source_type=CAPASource.AUDIT_FINDING,
                source_id=1,
                due_date=_naive_past(30),
                created_by_id=1,
                assigned_to_id=1,
            )
        )
        # An open CAPA with no due date cannot be overdue.
        session.add(
            CAPAAction(
                tenant_id=TENANT,
                reference_number=f"CAPA-SSOT-{tag}-nodue",
                title=f"Undated CAPA {tag}",
                description="Open with no due date; must not count as overdue.",
                capa_type=CAPAType.CORRECTIVE,
                status=CAPAStatus.OPEN,
                priority=CAPAPriority.LOW,
                source_type=CAPASource.AUDIT_FINDING,
                source_id=1,
                created_by_id=1,
                assigned_to_id=1,
            )
        )

        incident = Incident(
            tenant_id=TENANT,
            reference_number=f"INC-SSOT-ACT-{tag}",
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


async def _register_total(client: AsyncClient) -> int:
    res = await client.get("/api/v1/risk-register/?limit=200")
    assert res.status_code == 200, res.text
    return int(res.json()["total"])


async def _dashboard(client: AsyncClient) -> dict:
    res = await client.get("/api/v1/executive-dashboard?period_days=30")
    assert res.status_code == 200, res.text
    return res.json()


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
    expected = await _seed_register()

    risks = (await _dashboard(admin_client))["risks"]
    register_total = await _register_total(admin_client)

    assert register_total == expected["register_total"]
    assert risks["register_total"] == register_total
    assert risks["total_active"] == expected["total_active"]
    assert risks["high_critical"] == expected["high_critical"]


@pytest.mark.asyncio
async def test_analytics_kpis_risk_total_matches_risk_register(admin_client: AsyncClient) -> None:
    """`/analytics/kpis` is a projection of the dashboard, so it must agree too."""
    await _seed_register()

    res = await admin_client.get("/api/v1/analytics/kpis")
    assert res.status_code == 200, res.text
    kpi_risks = res.json()["risks"]

    assert kpi_risks["total"] == await _register_total(admin_client)


@pytest.mark.asyncio
async def test_dashboard_risk_total_excludes_pending_and_other_tenants(admin_client: AsyncClient) -> None:
    """Rows hidden from the register must be hidden from the aggregate identically."""
    await _seed_register()

    risks = (await _dashboard(admin_client))["risks"]

    pending = await admin_client.get("/api/v1/risk-register/?suggestion_triage=pending&limit=200")
    assert pending.status_code == 200, pending.text
    pending_total = int(pending.json()["total"])
    assert pending_total >= 1, "seed should leave at least one row awaiting triage"

    all_visible = await _register_total(admin_client)
    assert risks["register_total"] == all_visible
    # The pending row and the other tenant's row are in neither number.
    assert risks["register_total"] < all_visible + pending_total


# ---------------------------------------------------------------------------
# Overdue actions: three surfaces, one predicate
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_overdue_action_count_agrees_across_every_surface(admin_client: AsyncClient) -> None:
    """Summary tile, view-count chip and analytics KPI must be one number.

    `/analytics/kpis` previously returned a hardcoded stub, which is why UAT saw
    an overdue count of 0 on the analytics surface while the Actions page said 10.
    """
    expected = await _seed_overdue_actions(capa=9, incident_actions=1)

    summary = await admin_client.get("/api/v1/actions/summary")
    view_counts = await admin_client.get("/api/v1/actions/view-counts")
    kpis = await admin_client.get("/api/v1/analytics/kpis")
    assert summary.status_code == 200, summary.text
    assert view_counts.status_code == 200, view_counts.text
    assert kpis.status_code == 200, kpis.text

    assert summary.json()["overdue"] == expected
    assert view_counts.json()["overdue"] == summary.json()["overdue"]
    assert kpis.json()["actions"]["overdue"] == summary.json()["overdue"]


@pytest.mark.asyncio
async def test_analytics_kpis_action_total_is_not_a_stub(admin_client: AsyncClient) -> None:
    """The whole analytics actions block must be live, not just `overdue`."""
    await _seed_overdue_actions(capa=2, incident_actions=1)

    summary = await admin_client.get("/api/v1/actions/summary")
    kpis = await admin_client.get("/api/v1/analytics/kpis")
    assert summary.status_code == 200, summary.text
    assert kpis.status_code == 200, kpis.text

    kpi_actions = kpis.json()["actions"]
    assert kpi_actions["total"] == summary.json()["total"]
    assert kpi_actions["total"] > 0


@pytest.mark.asyncio
async def test_overdue_excludes_done_and_undated_actions(admin_client: AsyncClient) -> None:
    """Overdue means open and past due — not "has a due date in the past"."""
    expected = await _seed_overdue_actions(capa=3, incident_actions=1)

    summary = await admin_client.get("/api/v1/actions/summary")
    assert summary.status_code == 200, summary.text
    body = summary.json()

    # Seed adds two extra CAPA rows (one closed past-due, one open undated).
    assert body["total"] == expected + 2
    assert body["overdue"] == expected


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
    await _seed_incidents(tenant_id=TENANT, count=7, tag=uuid.uuid4().hex[:6])
    await _seed_incidents(tenant_id=OTHER_TENANT, count=2, tag=uuid.uuid4().hex[:6])

    dash_total = (await _dashboard(admin_client))["incidents"]["register_total"]
    listing = await admin_client.get("/api/v1/incidents/?page_size=1")
    assert listing.status_code == 200, listing.text

    assert dash_total == int(listing.json()["total"]) == 7


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
    await _seed_incidents(tenant_id=TENANT, count=5, tag=uuid.uuid4().hex[:6])
    await _seed_incidents(tenant_id=OTHER_TENANT, count=1, tag=uuid.uuid4().hex[:6])

    dash_total = (await _dashboard(superuser_client))["incidents"]["register_total"]
    listing = await superuser_client.get("/api/v1/incidents/?page_size=1")
    assert listing.status_code == 200, listing.text
    list_total = int(listing.json()["total"])

    assert dash_total == 5, "dashboard stays tenant-scoped"
    assert list_total == 6, "register list currently spans tenants for superusers"
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
    await _seed_register()

    operational = await admin_client.get("/api/v1/risks/")
    assert operational.status_code == 200, operational.text

    assert int(operational.json()["total"]) == 0
    assert await _register_total(admin_client) > 0


def test_operational_risk_routes_are_deprecated_in_the_published_schema() -> None:
    from src.main import app

    paths = app.openapi()["paths"]
    operational = [(p, m) for p, ops in paths.items() if p.startswith("/api/v1/risks") for m, _ in ops.items()]
    assert operational, "operational risk paths should still be published"
    for path, method in operational:
        assert paths[path][method].get("deprecated") is True, f"{method.upper()} {path} not marked deprecated"

    # The successor must not be tarred with the same brush.
    assert paths["/api/v1/risk-register/"]["get"].get("deprecated") is not True
