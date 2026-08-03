"""Superuser tenant scope on the near-miss, RTA and complaint registers (B-13 siblings).

B-13 fixed `GET /api/v1/incidents/`, which passed ``skip_tenant_check=is_superuser``
into ``IncidentService``. These three registers carried the same defect written a
different way — an inline ``if not current_user.is_superuser:`` around the tenant
filter in the route — so for a superuser the list spanned every tenant while the
executive dashboard tile beside it stayed scoped to the caller's own.

Each surface is checked two ways:

* **Exclusion**, using the ``ids`` deep-link filter to name one row in the caller's
  tenant and one in another tenant. Naming both ids makes the assertion immune to
  ordering and to rows left behind by earlier tests, which matters because the
  integration schema is only dropped between tests on SQLite — on PostgreSQL (what
  CI runs) every earlier test's rows are still present.
* **Delta**, seeding into both tenants and asserting the register total moves by
  exactly the caller's own seed.

Cross-tenant access to a single record by id is deliberately not touched here:
``_get_near_miss_or_404``, ``_get_rta_or_404`` and the complaint/RTA mutators keep
their superuser exemption, so an administrator can still open and close one named
record in another tenant. Only enumerating the estate is withdrawn.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from src.domain.models.complaint import Complaint
from src.domain.models.near_miss import NearMiss
from src.domain.models.rta import RoadTrafficCollision
from src.domain.models.tenant import Tenant
from src.infrastructure.database import async_session_maker

TENANT = 1
OTHER_TENANT_SLUG = "sibling-register-cross-tenant-control"


async def _other_tenant_id() -> int:
    """Get-or-create a second tenant to act as the cross-tenant control.

    Its id is looked up rather than assumed: ``tenants`` is only truncated between
    tests on SQLite, and PostgreSQL enforces the foreign key a hardcoded id would
    violate on a fresh database.
    """
    async with async_session_maker() as session:
        existing = (await session.execute(select(Tenant).where(Tenant.slug == OTHER_TENANT_SLUG))).scalar_one_or_none()
        if existing is not None:
            return int(existing.id)
        tenant = Tenant(
            name="Sibling register cross-tenant control",
            slug=OTHER_TENANT_SLUG,
            admin_email="sibling-control@test.example.com",
            is_active=True,
            subscription_tier="standard",
        )
        session.add(tenant)
        await session.commit()
        return int(tenant.id)


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _seed_near_misses(*, tenant_id: int, count: int) -> list[int]:
    tag = uuid.uuid4().hex[:8]
    rows = [
        NearMiss(
            tenant_id=tenant_id,
            reference_number=f"NM-SIB-{tag}-{i:03d}",
            reporter_name="Sibling scope reporter",
            contract="Sibling scope contract",
            location="Sibling scope yard",
            event_date=_now() - timedelta(days=i),
            description="Seeded for the B-13 sibling tenancy tests.",
            status="reported",
            priority="MEDIUM",
        )
        for i in range(count)
    ]
    async with async_session_maker() as session:
        session.add_all(rows)
        await session.commit()
        return [int(row.id) for row in rows]


async def _seed_rtas(*, tenant_id: int, count: int) -> list[int]:
    # road_traffic_collisions.reference_number is varchar(20) in PostgreSQL.
    tag = uuid.uuid4().hex[:6]
    rows = [
        RoadTrafficCollision(
            tenant_id=tenant_id,
            reference_number=f"RTA-SIB-{tag}-{i:02d}",
            title=f"Sibling scope collision {i}",
            description="Seeded for the B-13 sibling tenancy tests.",
            collision_date=_now() - timedelta(days=i),
            reported_date=_now() - timedelta(days=i),
            location="A1 Junction, Northbound",
        )
        for i in range(count)
    ]
    async with async_session_maker() as session:
        session.add_all(rows)
        await session.commit()
        return [int(row.id) for row in rows]


async def _seed_complaints(*, tenant_id: int, count: int) -> list[int]:
    # complaints.reference_number is varchar(20) in PostgreSQL.
    tag = uuid.uuid4().hex[:6]
    rows = [
        Complaint(
            tenant_id=tenant_id,
            reference_number=f"CMP-SIB-{tag}-{i:02d}",
            title=f"Sibling scope complaint {i}",
            description="Seeded for the B-13 sibling tenancy tests.",
            complainant_name="Sibling scope complainant",
            received_date=_now() - timedelta(days=i),
        )
        for i in range(count)
    ]
    async with async_session_maker() as session:
        session.add_all(rows)
        await session.commit()
        return [int(row.id) for row in rows]


async def _get(client: AsyncClient, path: str) -> dict:
    res = await client.get(path)
    assert res.status_code == 200, f"{path} -> {res.status_code} {res.text}"
    return res.json()


async def _list_total(client: AsyncClient, path: str) -> int:
    return int((await _get(client, f"{path}?page_size=1"))["total"])


async def _ids_visible(client: AsyncClient, path: str, ids: list[int]) -> set[int]:
    """Ask the register for named ids and return the subset it will show."""
    joined = ",".join(str(i) for i in ids)
    payload = await _get(client, f"{path}?ids={joined}&page_size=100")
    return {int(item["id"]) for item in payload["items"]}


async def _dashboard(client: AsyncClient) -> dict:
    return await _get(client, "/api/v1/executive-dashboard?period_days=30")


# ---------------------------------------------------------------------------
# Near misses
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_superuser_near_miss_register_excludes_other_tenants(superuser_client: AsyncClient) -> None:
    before = await _list_total(superuser_client, "/api/v1/near-misses/")

    own = await _seed_near_misses(tenant_id=TENANT, count=3)
    other = await _seed_near_misses(tenant_id=await _other_tenant_id(), count=2)

    visible = await _ids_visible(superuser_client, "/api/v1/near-misses/", own + other)

    assert visible == set(own), "a superuser's near-miss register must hold their own tenant only"
    assert await _list_total(superuser_client, "/api/v1/near-misses/") - before == 3


# ---------------------------------------------------------------------------
# RTAs
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_superuser_rta_register_total_matches_the_dashboard(superuser_client: AsyncClient) -> None:
    """RTA is the surface where the two numbers must agree absolutely.

    Neither ``rtas.total`` on the executive dashboard nor the unfiltered register
    list narrows by anything but the tenant — ``road_traffic_collisions`` has no
    soft-delete column — so equality is the invariant, not merely a matching delta.
    """
    before_dash = int((await _dashboard(superuser_client))["rtas"]["total"])
    before_list = await _list_total(superuser_client, "/api/v1/rtas/")

    own = await _seed_rtas(tenant_id=TENANT, count=3)
    other = await _seed_rtas(tenant_id=await _other_tenant_id(), count=2)

    dash_total = int((await _dashboard(superuser_client))["rtas"]["total"])
    list_total = await _list_total(superuser_client, "/api/v1/rtas/")
    visible = await _ids_visible(superuser_client, "/api/v1/rtas/", own + other)

    assert dash_total == list_total, "a superuser's RTA register must reconcile with their dashboard"
    assert dash_total - before_dash == 3, "dashboard stays tenant-scoped"
    assert list_total - before_list == 3, "the other tenant's RTAs must be in neither number"
    assert visible == set(own)


# ---------------------------------------------------------------------------
# Complaints
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_superuser_complaint_register_excludes_other_tenants(superuser_client: AsyncClient) -> None:
    """Complaints are asserted as a matching delta rather than absolute equality.

    ``complaints`` carries a ``deleted_at`` column that the dashboard aggregate
    excludes and this list does not, so the two absolute numbers can legitimately
    differ by the soft-deleted rows. That gap is a separate defect and is not
    fixed here; both surfaces must still move by the same amount, and neither may
    move for another tenant's complaint.
    """
    before_dash = int((await _dashboard(superuser_client))["complaints"]["register_total"])
    before_list = await _list_total(superuser_client, "/api/v1/complaints/")

    own = await _seed_complaints(tenant_id=TENANT, count=3)
    other = await _seed_complaints(tenant_id=await _other_tenant_id(), count=2)

    dash_total = int((await _dashboard(superuser_client))["complaints"]["register_total"])
    list_total = await _list_total(superuser_client, "/api/v1/complaints/")
    visible = await _ids_visible(superuser_client, "/api/v1/complaints/", own + other)

    assert dash_total - before_dash == 3, "dashboard stays tenant-scoped"
    assert list_total - before_list == 3, "the other tenant's complaints must be in neither number"
    assert visible == set(own)


# ---------------------------------------------------------------------------
# Non-superuser control
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tenant_admin_registers_are_unchanged_by_this_fix(admin_client: AsyncClient) -> None:
    """The path that was already correct must stay exactly as it was.

    A tenant admin never took the bypass branch, so all three registers should be
    indistinguishable from before. Asserted alongside the superuser tests so a
    future change cannot fix one caller class by breaking the other.
    """
    other_tenant = await _other_tenant_id()

    own_nm = await _seed_near_misses(tenant_id=TENANT, count=2)
    other_nm = await _seed_near_misses(tenant_id=other_tenant, count=1)
    own_rta = await _seed_rtas(tenant_id=TENANT, count=2)
    other_rta = await _seed_rtas(tenant_id=other_tenant, count=1)
    own_cmp = await _seed_complaints(tenant_id=TENANT, count=2)
    other_cmp = await _seed_complaints(tenant_id=other_tenant, count=1)

    assert await _ids_visible(admin_client, "/api/v1/near-misses/", own_nm + other_nm) == set(own_nm)
    assert await _ids_visible(admin_client, "/api/v1/rtas/", own_rta + other_rta) == set(own_rta)
    assert await _ids_visible(admin_client, "/api/v1/complaints/", own_cmp + other_cmp) == set(own_cmp)
