"""Regression suite: an investigation run belongs to one tenant, on read and write.

The finding, from the review that produced #1389 and confirmed by reading the
call path rather than the names:

* ``_get_investigation_or_404`` selected the run by bare id and then deferred to
  ``_user_can_access_investigation``, which checks ``is_superuser``, the
  ``investigations:view_all`` permission and four user-id fields. Neither
  function mentioned a tenant, so every sub-resource read — timeline, comments,
  packs, the pack PDF, closure-validation — was reachable across tenants by any
  holder of ``investigations:view_all``, not only by superusers.
* ``GET``/``PATCH /investigations/{id}``, ``PATCH .../autosave``,
  ``POST .../approve`` and ``POST .../customer-pack`` loaded the run by bare id
  with no access check at all beyond their permission gate, so a cross-tenant
  read *and write* needed nothing more than ``investigation:update``.
* ``GET /investigations`` applied no tenant predicate whatsoever.

#1389 closed the closure path only, by refusing when the caller's tenant differs
from the run's. These probes cover the general read and write paths, and they go
through the app over HTTP so they exercise the dependency chain a real caller
does rather than a hand-built helper call.

Investigations are tenant-local here, including for app superusers. The evidence
is in the PR body; the short version is that ``investigation_runs`` carries a
FORCE RLS ``tenant_isolation`` policy with no superuser branch, cross-tenant
admin is a BYPASSRLS *database role* capability rather than an application flag,
and #1389 already refuses a superuser's cross-tenant closure.
"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient

pytestmark = [pytest.mark.asyncio, pytest.mark.requires_db]

FOREIGN_TITLE = "Other tenant investigation"
FOREIGN_FINDINGS = "Their findings, confidential to the other organisation"


async def _foreign_run(test_session) -> tuple[int, str]:
    """Seed a tenant, template and investigation run that tenant 1 does not own."""
    from src.domain.models.investigation import (
        AssignedEntityType,
        InvestigationRun,
        InvestigationStatus,
        InvestigationTemplate,
    )
    from tests.factories import TenantFactory

    tenant = TenantFactory.build(
        name="Other Tenant",
        slug=f"other-tenant-{uuid.uuid4().hex[:8]}",
        admin_email="admin@other.example.com",
        is_active=True,
    )
    test_session.add(tenant)
    await test_session.commit()
    await test_session.refresh(tenant)

    template = InvestigationTemplate(
        name="Other tenant template",
        version="1.0",
        is_active=True,
        structure={"sections": []},
        applicable_entity_types=[e.value for e in AssignedEntityType],
        created_by_id=1,
        updated_by_id=1,
        tenant_id=int(tenant.id),
    )
    test_session.add(template)
    await test_session.commit()
    await test_session.refresh(template)

    run = InvestigationRun(
        template_id=int(template.id),
        assigned_entity_type=AssignedEntityType.NEAR_MISS,
        assigned_entity_id=987654,
        title=FOREIGN_TITLE,
        description="Confidential to the other organisation",
        status=InvestigationStatus.IN_PROGRESS,
        level="medium",
        data={"findings": FOREIGN_FINDINGS, "conclusion": "Their conclusion"},
        version=1,
        reference_number=f"INV-OTHER-{uuid.uuid4().hex[:6]}",
        tenant_id=int(tenant.id),
        created_by_id=1,
        updated_by_id=1,
    )
    test_session.add(run)
    await test_session.commit()
    await test_session.refresh(run)
    return int(run.id), str(run.reference_number)


async def _reload(test_session, run_id: int):
    """Re-read the run from the database, ignoring anything cached in the session."""
    from src.domain.models.investigation import InvestigationRun

    test_session.expire_all()
    return await test_session.get(InvestigationRun, run_id)


def _error_code(response) -> str:
    """Read the error code out of the canonical envelope, tolerating older shapes."""
    body = response.json()
    error = body.get("error", body.get("detail", body)) if isinstance(body, dict) else body
    if isinstance(error, dict):
        return str(error.get("code") or error.get("error_code") or "")
    return ""


def _headers(permissions: str, *, user_id: str = "1") -> dict[str, str]:
    from tests.integration.conftest import _generate_test_jwt

    token = _generate_test_jwt(
        user_id=user_id,
        tenant_id=1,
        role="investigator",
        is_superuser=False,
        permissions=permissions,
    )
    return {"Authorization": f"Bearer {token}"}


class TestCrossTenantRead:
    async def test_detail_read_of_another_tenants_run_is_refused(self, admin_client: AsyncClient, test_session) -> None:
        """GET /investigations/{id} had no access check at all beyond authentication."""
        run_id, reference = await _foreign_run(test_session)

        response = await admin_client.get(f"/api/v1/investigations/{run_id}")

        assert response.status_code == 403, response.text
        assert _error_code(response) == "TENANT_ACCESS_DENIED"
        assert reference not in response.text
        assert FOREIGN_FINDINGS not in response.text

    async def test_list_does_not_include_another_tenants_run(self, admin_client: AsyncClient, test_session) -> None:
        """GET /investigations applied no tenant predicate, so it listed every tenant."""
        run_id, reference = await _foreign_run(test_session)

        response = await admin_client.get("/api/v1/investigations/?page_size=100")

        assert response.status_code == 200, response.text
        items = response.json()["items"]
        assert run_id not in {item["id"] for item in items}
        assert reference not in {item["reference_number"] for item in items}

    async def test_investigations_view_all_does_not_reach_across_tenants(
        self, client: AsyncClient, test_session
    ) -> None:
        """The permission means "every investigation in my tenant", not "everywhere".

        Its siblings in the four case registers (``rta:view_all``,
        ``complaint:view_all``, ``incident:view_all``) are only ever consulted
        after a tenant-scoped fetch, to widen a reporter-email restriction.
        """
        run_id, _reference = await _foreign_run(test_session)
        headers = _headers("investigation:read,investigations:view_all")

        for path in (
            f"/api/v1/investigations/{run_id}",
            f"/api/v1/investigations/{run_id}/timeline",
            f"/api/v1/investigations/{run_id}/comments",
            f"/api/v1/investigations/{run_id}/packs",
            f"/api/v1/investigations/{run_id}/closure-validation",
        ):
            response = await client.get(path, headers=headers)
            assert response.status_code == 403, f"{path} -> {response.status_code} {response.text}"
            assert _error_code(response) == "TENANT_ACCESS_DENIED", path

    async def test_superuser_is_scoped_to_their_own_tenant(self, superuser_client: AsyncClient, test_session) -> None:
        """Deliberate: investigations are tenant-local, so a superuser is too.

        #1389 already refuses a superuser's cross-tenant closure. A read that
        crossed where the close refuses would be exactly the read/write
        asymmetry #1382's B-2 was about, in reverse.
        """
        run_id, _reference = await _foreign_run(test_session)

        response = await superuser_client.get(f"/api/v1/investigations/{run_id}")

        assert response.status_code == 403, response.text
        assert _error_code(response) == "TENANT_ACCESS_DENIED"


class TestCrossTenantWrite:
    async def test_patch_is_refused_and_leaves_the_record_untouched(
        self, admin_client: AsyncClient, test_session
    ) -> None:
        """PATCH loaded the run by bare id: ``investigation:update`` was the only gate."""
        run_id, _reference = await _foreign_run(test_session)

        response = await admin_client.patch(
            f"/api/v1/investigations/{run_id}",
            json={"title": "Seized by tenant 1", "description": "Rewritten"},
        )

        assert response.status_code == 403, response.text
        assert _error_code(response) == "TENANT_ACCESS_DENIED"
        run = await _reload(test_session, run_id)
        assert run.title == FOREIGN_TITLE
        assert run.updated_by_id == 1

    async def test_autosave_is_refused_and_leaves_the_data_untouched(
        self, admin_client: AsyncClient, test_session
    ) -> None:
        run_id, _reference = await _foreign_run(test_session)

        response = await admin_client.patch(
            f"/api/v1/investigations/{run_id}/autosave?version=1",
            json={"findings": "Overwritten by tenant 1"},
        )

        assert response.status_code == 403, response.text
        assert _error_code(response) == "TENANT_ACCESS_DENIED"
        run = await _reload(test_session, run_id)
        assert run.data["findings"] == FOREIGN_FINDINGS
        assert run.version == 1

    async def test_approve_is_refused_and_leaves_the_status_untouched(
        self, admin_client: AsyncClient, test_session
    ) -> None:
        from src.domain.models.investigation import InvestigationStatus

        run_id, _reference = await _foreign_run(test_session)

        response = await admin_client.post(f"/api/v1/investigations/{run_id}/approve?approved=true")

        assert response.status_code == 403, response.text
        assert _error_code(response) == "TENANT_ACCESS_DENIED"
        run = await _reload(test_session, run_id)
        assert run.status == InvestigationStatus.IN_PROGRESS
        assert run.approved_by_id is None

    async def test_customer_pack_generation_is_refused(self, admin_client: AsyncClient, test_session) -> None:
        """A pack is the exportable copy of the record; generating one is a read too."""
        from sqlalchemy import func, select

        from src.domain.models.investigation import InvestigationCustomerPack

        run_id, _reference = await _foreign_run(test_session)

        response = await admin_client.post(f"/api/v1/investigations/{run_id}/customer-pack?audience=internal_customer")

        assert response.status_code == 403, response.text
        assert _error_code(response) == "TENANT_ACCESS_DENIED"
        assert FOREIGN_FINDINGS not in response.text
        test_session.expire_all()
        packs = await test_session.scalar(
            select(func.count())
            .select_from(InvestigationCustomerPack)
            .where(InvestigationCustomerPack.investigation_id == run_id)
        )
        assert packs == 0

    async def test_manual_timeline_entry_is_refused(self, admin_client: AsyncClient, test_session) -> None:
        run_id, _reference = await _foreign_run(test_session)

        response = await admin_client.post(
            f"/api/v1/investigations/{run_id}/timeline",
            json={"content": "Planted by tenant 1"},
        )

        assert response.status_code == 403, response.text
        assert _error_code(response) == "TENANT_ACCESS_DENIED"

    async def test_comment_creation_is_refused_with_the_shared_code(
        self, admin_client: AsyncClient, test_session
    ) -> None:
        """This path already refused, but as a 404 rather than the shared 403."""
        run_id, _reference = await _foreign_run(test_session)

        response = await admin_client.post(
            f"/api/v1/investigations/{run_id}/comments",
            json={"content": "Planted by tenant 1"},
        )

        assert response.status_code == 403, response.text
        assert _error_code(response) == "TENANT_ACCESS_DENIED"


class TestOwnTenantAccessIsUnchanged:
    """The fix must not cost a caller anything inside their own tenant."""

    async def test_the_callers_own_investigation_stays_fully_usable(
        self, admin_client: AsyncClient, near_miss_factory
    ) -> None:
        near_miss = await near_miss_factory()

        created = await admin_client.post(
            "/api/v1/investigations/from-record",
            json={
                "source_type": "near_miss",
                "source_id": near_miss["id"],
                "title": "Our own investigation",
            },
        )
        assert created.status_code == 201, created.text
        investigation_id = created.json()["id"]

        detail = await admin_client.get(f"/api/v1/investigations/{investigation_id}")
        assert detail.status_code == 200, detail.text

        patched = await admin_client.patch(
            f"/api/v1/investigations/{investigation_id}",
            json={"title": "Our own investigation, retitled"},
        )
        assert patched.status_code == 200, patched.text
        assert patched.json()["title"] == "Our own investigation, retitled"

        listing = await admin_client.get("/api/v1/investigations/?page_size=100")
        assert listing.status_code == 200, listing.text
        assert investigation_id in {item["id"] for item in listing.json()["items"]}

        for suffix in ("timeline", "comments", "packs", "closure-validation"):
            sub = await admin_client.get(f"/api/v1/investigations/{investigation_id}/{suffix}")
            assert sub.status_code == 200, f"{suffix} -> {sub.status_code} {sub.text}"
