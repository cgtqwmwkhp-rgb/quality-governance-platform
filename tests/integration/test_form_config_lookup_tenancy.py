"""Tenancy round-trip tests for lookup options (PX-119, PX-120).

``FormConfigService.create_lookup_option`` accepted a ``tenant_id`` and never
wrote it to the row, while ``list_lookup_options`` filters on
``LookupOption.tenant_id == tenant_id``. Because ``NULL = 1`` is never true in
SQL, every option written through that path was permanently unreadable — the
admin lookup screen was a write-only black hole, and the portal's required
``person_role`` select came back empty, which is what made the incident journey
impossible to complete.

The absence of a write-then-read-back assertion is what let that ship, so that
is the shape of the test here: every mutation is verified through the read path
a real caller uses, not by inspecting the object the writer returned.

Each test works in its own generated lookup category. Integration tests share a
persistent schema on Postgres (see ``_seed_default_data`` in conftest), so a
test that asserted on the contents of a real category would be reading other
tests' rows and the deploy migration's rows as well as its own.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from httpx import AsyncClient

from src.api.schemas.form_config import LookupOptionCreate, LookupOptionUpdate
from src.domain.exceptions import NotFoundError
from src.domain.services.form_config_service import FormConfigService

TENANT = 1
# A tenant that does not exist: enough to prove the mutation is scoped, without
# inserting a second tenant into a schema other tests are also using.
FOREIGN_TENANT = 987_654


@pytest.fixture(autouse=True)
def _no_external_side_effects():
    """The service pings Redis and App Insights; neither is available in tests."""
    with (
        patch(
            "src.domain.services.form_config_service.invalidate_tenant_cache",
            new_callable=AsyncMock,
        ),
        patch("src.domain.services.form_config_service.track_metric"),
    ):
        yield


@pytest.fixture
def category() -> str:
    """A lookup category unique to this test."""
    return f"px119_{uuid4().hex[:12]}"


def _option(category: str, code: str, label: str) -> LookupOptionCreate:
    return LookupOptionCreate(
        category=category,
        code=code,
        label=label,
        description=None,
        is_active=True,
        display_order=1,
        parent_id=None,
    )


class TestServiceRoundTrip:
    """The regression test whose absence let the write-only black hole ship."""

    async def test_created_option_is_returned_by_list_for_the_same_tenant(self, test_session, category):
        service = FormConfigService(test_session)

        created = await service.create_lookup_option(
            category, data=_option(category, "field_engineer", "Field Engineer"), tenant_id=TENANT
        )
        assert created.tenant_id == TENANT, "the option was written without a tenant and is now unreadable"

        options = await service.list_lookup_options(category, tenant_id=TENANT)
        assert [o.code for o in options] == ["field_engineer"]

    async def test_round_trip_holds_for_several_options(self, test_session, category):
        service = FormConfigService(test_session)

        for code in ("mobile-engineer", "office", "trainee"):
            await service.create_lookup_option(category, data=_option(category, code, code.title()), tenant_id=TENANT)

        options = await service.list_lookup_options(category, tenant_id=TENANT)
        assert sorted(o.code for o in options) == ["mobile-engineer", "office", "trainee"]

    async def test_option_is_not_visible_to_another_tenant(self, test_session, category):
        service = FormConfigService(test_session)
        await service.create_lookup_option(category, data=_option(category, "driver", "Driver"), tenant_id=TENANT)

        assert await service.list_lookup_options(category, tenant_id=FOREIGN_TENANT) == []


class TestServiceCrossTenantMutation:
    """Update and delete looked rows up by id + category with no tenant filter."""

    async def test_update_from_another_tenant_is_rejected(self, test_session, category):
        service = FormConfigService(test_session)
        created = await service.create_lookup_option(
            category, data=_option(category, "supervisor", "Supervisor"), tenant_id=TENANT
        )

        with pytest.raises(NotFoundError):
            await service.update_lookup_option(
                category,
                created.id,
                data=LookupOptionUpdate(label="Hijacked"),
                tenant_id=FOREIGN_TENANT,
            )

        survivors = await service.list_lookup_options(category, tenant_id=TENANT)
        assert [o.label for o in survivors] == ["Supervisor"]

    async def test_delete_from_another_tenant_is_rejected(self, test_session, category):
        service = FormConfigService(test_session)
        created = await service.create_lookup_option(
            category, data=_option(category, "director", "Director"), tenant_id=TENANT
        )

        with pytest.raises(NotFoundError):
            await service.delete_lookup_option(category, created.id, tenant_id=FOREIGN_TENANT)

        assert len(await service.list_lookup_options(category, tenant_id=TENANT)) == 1

    async def test_owning_tenant_can_still_update_and_delete(self, test_session, category):
        service = FormConfigService(test_session)
        created = await service.create_lookup_option(
            category, data=_option(category, "apprentice", "Apprentice"), tenant_id=TENANT
        )

        await service.update_lookup_option(
            category, created.id, data=LookupOptionUpdate(label="Apprentice (Y1)"), tenant_id=TENANT
        )
        assert (await service.list_lookup_options(category, tenant_id=TENANT))[0].label == "Apprentice (Y1)"

        await service.delete_lookup_option(category, created.id, tenant_id=TENANT)
        assert await service.list_lookup_options(category, tenant_id=TENANT) == []


class TestApiRoundTrip:
    """The same round-trip over the live HTTP path the admin screen uses."""

    async def test_option_created_via_the_admin_api_is_listed_back(
        self, superuser_client: AsyncClient, admin_client: AsyncClient, category: str
    ):
        create = await superuser_client.post(
            f"/api/v1/admin/config/lookup/{category}",
            json={"code": "hs_advisor", "label": "Health & Safety Advisor", "is_active": True, "display_order": 1},
        )
        assert create.status_code == 201, create.text

        listed = await admin_client.get(f"/api/v1/admin/config/lookup/{category}?is_active=true")
        assert listed.status_code == 200, listed.text
        assert [item["code"] for item in listed.json()["items"]] == ["hs_advisor"]
