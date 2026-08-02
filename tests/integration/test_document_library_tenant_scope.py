"""Superuser tenant scope on the document library list and stats (B-13 sibling).

``documents._scope_stmt_to_current_tenant`` returned the statement unscoped when
the caller was a superuser. Every surface that reached it therefore spanned the
estate: ``GET /api/v1/documents/`` enumerated every tenant's library, and
``GET /api/v1/documents/stats/overview`` counted every tenant's rows across both
``documents`` and ``document_chunks``.

This is the same defect #1510 fixed on the incident register, #1512 on the
near-miss, RTA and complaint registers and #1513/#1515 on the risk register and
its aggregates — expressed one level down, in a shared helper rather than inline
in each handler, which is why the existing guard (the helper calls
``require_tenant_id``) stayed green while the leak was open.

The list assertions are made through the ``search`` filter against a per-run uuid
tag rather than by paging. The integration schema is only dropped between tests
on SQLite; on PostgreSQL — which is what CI runs — every earlier test's rows are
still present, so a page-scanning assertion would depend on the state of the
whole suite. Tagging makes both the id set and the total exact.

The stats endpoint takes no filter, so those assertions are deltas around a seed
instead: nothing else writes ``documents`` while one test runs, so a count that
must not move is exact without depending on that state. The stats total is
deliberately not compared against the list total — ``list_documents`` filters on
``is_active`` and then drops ACL-denied rows, while the overview counts every
row, so the two are not the same population even when both are scoped correctly.

Cross-tenant access to one named document by id is deliberately untouched:
``_get_document_or_404`` keeps its superuser exemption through
``_scope_stmt_to_tenant_unless_superuser``, so an administrator can still open,
edit and approve a single record in another tenant. Only enumerating and
counting the library is withdrawn.
"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from src.domain.models.document import Document, FileType
from src.domain.models.tenant import Tenant
from src.infrastructure.database import async_session_maker

TENANT = 1
OTHER_TENANT_SLUG = "document-library-cross-tenant-control"


async def _other_tenant_id() -> int:
    """Get-or-create a second tenant to act as the cross-tenant control.

    Its id is looked up rather than assumed: ``tenants`` is only truncated
    between tests on SQLite, and ``documents.tenant_id`` is a NOT NULL foreign
    key that a hardcoded id would violate on a fresh PostgreSQL database.
    """
    async with async_session_maker() as session:
        existing = (await session.execute(select(Tenant).where(Tenant.slug == OTHER_TENANT_SLUG))).scalar_one_or_none()
        if existing is not None:
            return int(existing.id)
        tenant = Tenant(
            name="Document library cross-tenant control",
            slug=OTHER_TENANT_SLUG,
            admin_email="document-library-control@test.example.com",
            is_active=True,
            subscription_tier="standard",
        )
        session.add(tenant)
        await session.commit()
        return int(tenant.id)


async def _seed_documents(*, tenant_id: int, count: int, tag: str) -> list[int]:
    """Seed active documents whose titles carry ``tag`` so ``?search=`` finds exactly them.

    ``tag`` is shared by both tenants' seeds so one search sees both. The
    reference number therefore cannot be derived from it — it is unique
    platform-wide, not per tenant — so each row draws its own.

    ``access_level`` is left unset, which the library RBAC reads as
    ``all_staff``: the rows must be visible to the tenant admin as well as the
    superuser, or the control assertions below would pass for the wrong reason.
    """
    # documents.reference_number is varchar(20); "DOC-" + 14 hex is 18.
    rows = [
        Document(
            tenant_id=tenant_id,
            reference_number=f"DOC-{uuid.uuid4().hex[:14]}",
            title=f"Document library scope probe {tag} {i}",
            description="Seeded for the B-13 document library tenancy test.",
            file_name=f"scope-probe-{tag}-{i}.pdf",
            file_type=FileType.PDF,
            file_size=1024,
            file_path=f"seed/{tag}/{i}.pdf",
            is_active=True,
        )
        for i in range(count)
    ]
    async with async_session_maker() as session:
        session.add_all(rows)
        await session.commit()
        return [int(row.id) for row in rows]


async def _tagged(client: AsyncClient, tag: str) -> dict:
    res = await client.get(f"/api/v1/documents/?search={tag}&page_size=100")
    assert res.status_code == 200, f"/api/v1/documents/ -> {res.status_code} {res.text}"
    return res.json()


async def _stats(client: AsyncClient) -> dict:
    res = await client.get("/api/v1/documents/stats/overview")
    assert res.status_code == 200, f"/api/v1/documents/stats/overview -> {res.status_code} {res.text}"
    return res.json()


@pytest.mark.asyncio
async def test_superuser_document_library_excludes_other_tenants(superuser_client: AsyncClient) -> None:
    tag = uuid.uuid4().hex[:6]
    own = await _seed_documents(tenant_id=TENANT, count=3, tag=tag)
    other = await _seed_documents(tenant_id=await _other_tenant_id(), count=2, tag=tag)

    payload = await _tagged(superuser_client, tag)

    assert {int(item["id"]) for item in payload["items"]} == set(own), (
        "a superuser's document library must hold their own tenant only; "
        f"the control tenant's ids {other} must not appear"
    )
    # `total` is the count query, built separately from the page query — assert
    # it too, so a fix applied to only one of the two statements is caught.
    assert payload["total"] == 3


@pytest.mark.asyncio
async def test_superuser_document_stats_exclude_other_tenants(superuser_client: AsyncClient) -> None:
    before = await _stats(superuser_client)

    await _seed_documents(tenant_id=await _other_tenant_id(), count=2, tag=uuid.uuid4().hex[:6])

    after = await _stats(superuser_client)
    assert (
        after["total_documents"] == before["total_documents"]
    ), "another tenant's documents moved the superuser's total"


@pytest.mark.asyncio
async def test_superuser_can_still_open_a_cross_tenant_document_by_id(superuser_client: AsyncClient) -> None:
    """The by-id exemption is the thing this change must NOT take away.

    Withdrawing enumeration while leaving single-record administration intact is
    the whole shape of B-13; without this test a later "tidy-up" that scoped
    ``_get_document_or_404`` too would look like an improvement.
    """
    tag = uuid.uuid4().hex[:6]
    (other_id,) = await _seed_documents(tenant_id=await _other_tenant_id(), count=1, tag=tag)

    res = await superuser_client.get(f"/api/v1/documents/{other_id}")

    assert res.status_code == 200, f"superuser lost by-id access: {res.status_code} {res.text}"
    assert int(res.json()["id"]) == other_id


@pytest.mark.asyncio
async def test_tenant_admin_document_library_is_unchanged_by_this_fix(admin_client: AsyncClient) -> None:
    """The path that was already correct must stay exactly as it was.

    A tenant admin never took the bypass branch, so the library should be
    indistinguishable from before. Asserted alongside the superuser test so a
    future change cannot fix one caller class by breaking the other.
    """
    tag = uuid.uuid4().hex[:6]
    own = await _seed_documents(tenant_id=TENANT, count=2, tag=tag)
    await _seed_documents(tenant_id=await _other_tenant_id(), count=1, tag=tag)

    payload = await _tagged(admin_client, tag)

    assert {int(item["id"]) for item in payload["items"]} == set(own)
    assert payload["total"] == 2


@pytest.mark.asyncio
async def test_tenant_admin_document_stats_still_count_their_own_rows(admin_client: AsyncClient) -> None:
    """Without this, scoping the overview to nothing at all would pass every
    assertion above."""
    before = await _stats(admin_client)

    await _seed_documents(tenant_id=TENANT, count=2, tag=uuid.uuid4().hex[:6])

    after = await _stats(admin_client)
    assert after["total_documents"] == before["total_documents"] + 2
