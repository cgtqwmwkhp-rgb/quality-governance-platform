"""Superuser tenant scope on the operational risk register (B-13).

``GET /api/v1/risks/`` guarded its tenant filter with an inline
``if not current_user.is_superuser:`` — the same defect #1510 fixed on the
incident register and #1512 fixed on the near-miss, RTA and complaint
registers, written the same way. A superuser's register therefore enumerated
every tenant's operational risks, which are classified C3-confidential and sit
in a FORCE-RLS table whose policies are inert while the application connects as
a ``rolbypassrls`` role: the route predicate was the only thing scoping them.

Assertions are made through the ``search`` filter against a per-run uuid tag
rather than by paging the register. The integration schema is only dropped
between tests on SQLite; on PostgreSQL — which is what CI runs — every earlier
test's rows are still present, so a page-scanning assertion would depend on the
state of the whole suite. Tagging makes both the id set and the total exact.

Cross-tenant access to one named risk by id is deliberately untouched:
``get_risk``, ``update_risk`` and ``_get_risk_tenant_checked`` keep their
superuser exemption, so an administrator can still open and edit a single
record in another tenant. Only enumerating the estate is withdrawn.
"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from src.domain.models.risk import Risk, RiskStatus
from src.domain.models.tenant import Tenant
from src.infrastructure.database import async_session_maker

TENANT = 1
OTHER_TENANT_SLUG = "operational-risk-cross-tenant-control"


async def _other_tenant_id() -> int:
    """Get-or-create a second tenant to act as the cross-tenant control.

    Its id is looked up rather than assumed: ``tenants`` is only truncated
    between tests on SQLite, and ``risks.tenant_id`` is a NOT NULL foreign key
    that a hardcoded id would violate on a fresh PostgreSQL database.
    """
    async with async_session_maker() as session:
        existing = (await session.execute(select(Tenant).where(Tenant.slug == OTHER_TENANT_SLUG))).scalar_one_or_none()
        if existing is not None:
            return int(existing.id)
        tenant = Tenant(
            name="Operational risk cross-tenant control",
            slug=OTHER_TENANT_SLUG,
            admin_email="operational-risk-control@test.example.com",
            is_active=True,
            subscription_tier="standard",
        )
        session.add(tenant)
        await session.commit()
        return int(tenant.id)


async def _seed_risks(*, tenant_id: int, count: int, tag: str) -> list[int]:
    """Seed active risks whose titles carry ``tag`` so ``?search=`` finds exactly them.

    ``tag`` is shared by both tenants' seeds so one search sees both. The
    reference number therefore cannot be derived from it — it is unique
    platform-wide, not per tenant — so each row draws its own.
    """
    # risks.reference_number is varchar(20); "RSK-" + 14 hex is 18.
    rows = [
        Risk(
            tenant_id=tenant_id,
            reference_number=f"RSK-{uuid.uuid4().hex[:14]}",
            title=f"Operational risk scope probe {tag} {i}",
            description="Seeded for the B-13 operational risk register tenancy test.",
            category="operational",
            likelihood=2,
            impact=3,
            risk_score=6,
            risk_level="medium",
            status=RiskStatus.OPEN,
            is_active=True,
        )
        for i in range(count)
    ]
    async with async_session_maker() as session:
        session.add_all(rows)
        await session.commit()
        return [int(row.id) for row in rows]


async def _tagged(client: AsyncClient, tag: str) -> dict:
    res = await client.get(f"/api/v1/risks/?search={tag}&page_size=100")
    assert res.status_code == 200, f"/api/v1/risks/ -> {res.status_code} {res.text}"
    return res.json()


@pytest.mark.asyncio
async def test_superuser_risk_register_excludes_other_tenants(superuser_client: AsyncClient) -> None:
    tag = uuid.uuid4().hex[:6]
    own = await _seed_risks(tenant_id=TENANT, count=3, tag=tag)
    other = await _seed_risks(tenant_id=await _other_tenant_id(), count=2, tag=tag)

    payload = await _tagged(superuser_client, tag)

    assert {int(item["id"]) for item in payload["items"]} == set(own), (
        "a superuser's operational risk register must hold their own tenant only; "
        f"the control tenant's ids {other} must not appear"
    )
    # `total` is the count query, built separately from the page query — assert
    # it too, so a fix applied to only one of the two statements is caught.
    assert payload["total"] == 3


@pytest.mark.asyncio
async def test_superuser_can_still_open_a_cross_tenant_risk_by_id(superuser_client: AsyncClient) -> None:
    """The by-id exemption is the thing this change must NOT take away.

    Withdrawing enumeration while leaving single-record administration intact is
    the whole shape of B-13; without this test a later "tidy-up" that scopes
    ``get_risk`` too would look like an improvement.
    """
    tag = uuid.uuid4().hex[:6]
    (other_id,) = await _seed_risks(tenant_id=await _other_tenant_id(), count=1, tag=tag)

    res = await superuser_client.get(f"/api/v1/risks/{other_id}")

    assert res.status_code == 200, f"superuser lost by-id access: {res.status_code} {res.text}"
    assert int(res.json()["id"]) == other_id


@pytest.mark.asyncio
async def test_tenant_admin_risk_register_is_unchanged_by_this_fix(admin_client: AsyncClient) -> None:
    """The path that was already correct must stay exactly as it was.

    A tenant admin never took the bypass branch, so the register should be
    indistinguishable from before. Asserted alongside the superuser test so a
    future change cannot fix one caller class by breaking the other.
    """
    tag = uuid.uuid4().hex[:6]
    own = await _seed_risks(tenant_id=TENANT, count=2, tag=tag)
    await _seed_risks(tenant_id=await _other_tenant_id(), count=1, tag=tag)

    payload = await _tagged(admin_client, tag)

    assert {int(item["id"]) for item in payload["items"]} == set(own)
    assert payload["total"] == 2
