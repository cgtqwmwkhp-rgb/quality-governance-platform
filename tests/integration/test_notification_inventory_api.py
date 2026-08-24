"""The inventory endpoint over HTTP: who may read it, and that reading changes nothing.

``tests/unit/test_notification_inventory.py`` holds the registry to the source it
describes. This file covers the three things that can only be checked against the
mounted app:

* **The gate.** The payload is a map of which channels are unwatched and which
  events notify nobody, so it is gated on a named permission. Both directions are
  checked: an authenticated administrator *without* ``admin:manage`` is refused,
  which is what fails if the dependency is ever dropped to authentication-only.
* **Read-only in fact, not just in intent.** ADMIN-03 is concurrently changing the
  dispatch path, and the agreement is that this surface stays a reader. So the
  router is required to declare no write, no write may be mounted at the path, and
  reading is required to leave the ``feature_flags`` table exactly as it was —
  ``GET /api/v1/feature-flags/{key}`` seeds rows, and this must not. ``DELETE`` on
  this path is answered by a pre-existing catch-all rather than a 405; that is
  recorded and proven inert rather than asserted away.
* **No key material.** The VAPID helper returns the public key, and the route drops
  it. The check sets a sentinel key and greps the whole response body for it,
  rather than asserting on the field name it happens to arrive under.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from src.domain.models.feature_flag import FeatureFlag
from src.domain.notifications.inventory import ABSENT_CHANNELS, CHANNELS, PRODUCERS, READINESS_VALUES, can_send
from tests.integration.conftest import _ADMIN_PERMS, _generate_test_jwt

INVENTORY_PATH = "/api/v1/notifications/inventory"

#: The permission the route declares. Written out rather than imported from the
#: route so that renaming the token in the handler shows up here as a failure.
INVENTORY_PERMISSION = "admin:manage"


@pytest.fixture
async def inventory_client():
    """A client holding ``admin:manage`` on top of the ordinary admin persona.

    ``_ADMIN_PERMS`` is one admin persona and does not include ``admin:manage``,
    so the grant is added explicitly here in the idiom the rest of this suite
    uses. Editing the shared persona instead would hand the token to every other
    integration test as a side effect.
    """
    from src.main import app

    token = _generate_test_jwt(user_id="1", role="admin", permissions=f"{_ADMIN_PERMS},{INVENTORY_PERMISSION}")
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={"Authorization": f"Bearer {token}"},
    ) as client:
        yield client


# --------------------------------------------------------------------------- #
# The gate
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_an_unauthenticated_caller_gets_no_inventory(unauth_client: AsyncClient) -> None:
    response = await unauth_client.get(INVENTORY_PATH)
    assert response.status_code in (401, 403), (
        f"unauthenticated read returned {response.status_code}. The inventory names every module that "
        "produces a notification and every channel that is not configured, which is a map of the "
        "deployment."
    )


@pytest.mark.asyncio
async def test_an_administrator_without_the_permission_is_refused(admin_client: AsyncClient) -> None:
    """The negative half of the gate.

    This is the case that fails if the dependency is ever relaxed to
    authentication-only: the caller here is a real, authenticated administrator
    who simply does not hold ``admin:manage``.
    """
    response = await admin_client.get(INVENTORY_PATH)
    assert response.status_code == 403, (
        f"an admin without {INVENTORY_PERMISSION} got {response.status_code}. Authentication is not the "
        "gate this endpoint declares."
    )


@pytest.mark.asyncio
async def test_a_permitted_caller_reads_the_inventory(inventory_client: AsyncClient) -> None:
    response = await inventory_client.get(INVENTORY_PATH)
    assert response.status_code == 200, response.text

    body = response.json()
    assert body["generated_at"]
    assert len(body["channels"]) == len(CHANNELS) + len(ABSENT_CHANNELS)
    assert len(body["producers"]) == len(PRODUCERS)

    summary = body["summary"]
    assert summary["producers_total"] == len(body["producers"])
    assert summary["producers_active"] + summary["producers_without_caller"] == summary["producers_total"]


@pytest.mark.asyncio
async def test_the_reported_channels_use_the_declared_vocabulary(inventory_client: AsyncClient) -> None:
    """Whatever this environment is configured for, the answers stay in vocabulary.

    Asserted rather than pinned to concrete readiness values because CI's
    environment is not fixed: what must hold in every environment is that
    ``readiness`` is a value the frontend knows how to render and that
    ``can_send`` never disagrees with it.
    """
    body = (await inventory_client.get(INVENTORY_PATH)).json()

    for channel in body["channels"]:
        assert channel["readiness"] in READINESS_VALUES, f"{channel['id']} reports {channel['readiness']}"
        assert channel["can_send"] is can_send(channel["readiness"]), (
            f"{channel['id']} reports readiness {channel['readiness']} with can_send="
            f"{channel['can_send']}, which contradicts it"
        )
        assert channel["note"].strip(), f"{channel['id']} is reported without an explanation"


# The content of the report — which producers notify nobody, and that an absent
# channel is named rather than omitted — is asserted where it is decided:
# ``tests/unit/test_notification_inventory.py`` for the registry and
# ``tests/unit/test_notification_inventory_route.py`` for the handler. Repeating
# those assertions over HTTP would add a second place to update and no new
# evidence, so this file stays on what only the mounted app can show.


# --------------------------------------------------------------------------- #
# Read-only in fact
# --------------------------------------------------------------------------- #


def test_the_inventory_router_declares_nothing_but_reads() -> None:
    """The router itself may hold no write, whatever it is mounted under.

    Asserted against the router rather than over HTTP because that is the actual
    constraint: ADMIN-03 owns the dispatch path, and this lane's undertaking is
    that its own surface only reads. A route table is also unambiguous, whereas an
    HTTP method probe can be answered by somebody else's route — which is exactly
    what happens to DELETE here, see below.
    """
    from src.api.routes import notification_inventory

    for route in notification_inventory.router.routes:
        methods = set(getattr(route, "methods", set()) or set())
        assert methods <= {"GET", "HEAD"}, (
            f"{getattr(route, 'path', route)} on the inventory router declares {sorted(methods)}. This "
            "router reports state and must not change it."
        )


@pytest.mark.asyncio
async def test_the_app_mounts_no_write_at_the_inventory_path() -> None:
    """No route of any router answers a write *at this exact path*.

    The route table is the authority: an HTTP probe would be satisfied by a 405
    that a different, broader route happened to produce.
    """
    from src.main import app

    non_reads = {
        (method, route.path)
        for route in app.routes
        if getattr(route, "path", None) == INVENTORY_PATH
        for method in (getattr(route, "methods", set()) or set())
        if method not in {"GET", "HEAD"}
    }
    assert not non_reads, f"a write is mounted at the inventory path: {sorted(non_reads)}"


@pytest.mark.parametrize("method", ["post", "put", "patch"])
@pytest.mark.asyncio
async def test_writing_to_the_inventory_path_is_refused(inventory_client: AsyncClient, method: str) -> None:
    """A write to the inventory path finds no handler.

    ``delete`` is deliberately absent from this list and covered by the test below:
    it is answered by a pre-existing route rather than 405, and asserting 405 for
    it would be asserting something untrue.
    """
    response = await getattr(inventory_client, method)(INVENTORY_PATH)
    assert response.status_code == 405, (
        f"{method.upper()} {INVENTORY_PATH} returned {response.status_code}, so something now accepts a "
        "write here. This surface is a reader."
    )


@pytest.mark.asyncio
async def test_delete_falls_through_to_the_pre_existing_notifications_catch_all(
    inventory_client: AsyncClient,
) -> None:
    """Records a pre-existing hazard this PR does not own, and proves it is inert.

    ``DELETE /api/v1/notifications/{notification_id}`` is declared in
    ``src/api/routes/notifications.py`` before this router is mounted, and
    ``{notification_id}`` is a single segment, so it matches
    ``/api/v1/notifications/inventory`` and answers instead of a 405. The same is
    already true of the ``preferences``, ``unread-count`` and ``mentions`` literals
    in that namespace, so this is a property of the namespace rather than something
    the inventory introduces.

    It is not fixed here because the fix is a re-ordering inside
    ``notifications.py``, which is adjacent to the dispatch path that ADMIN-03 is
    concurrently changing. What is asserted instead is that the fall-through cannot
    destroy anything: ``notification_id`` is an ``int``, so the path never resolves
    to a row, and no caller can delete a notification by aiming at this path.
    """
    response = await inventory_client.delete(INVENTORY_PATH)

    assert response.status_code >= 400, (
        f"DELETE {INVENTORY_PATH} returned {response.status_code}. It reaches the notifications "
        "catch-all, which must never treat 'inventory' as a deletable row."
    )
    assert response.status_code in (403, 422), (
        f"DELETE {INVENTORY_PATH} returned an unexpected {response.status_code}: expected 403 (the "
        "caller lacks notifications:delete) or 422 (the literal 'inventory' is not an int id)."
    )


@pytest.mark.asyncio
async def test_reading_the_inventory_seeds_no_feature_flag_rows(
    inventory_client: AsyncClient,
    test_session,
) -> None:
    """A report must not create the rows it reports on.

    ``GET /api/v1/feature-flags/{key}`` inserts the Compliance Schedule notify
    rows when they are missing, which is right for a page whose next action is a
    toggle and wrong for a read. Row identity is compared, not just the count, so
    an insert paired with a delete could not pass either.
    """
    before = (await test_session.execute(select(func.count()).select_from(FeatureFlag))).scalar()
    before_keys = set((await test_session.execute(select(FeatureFlag.key))).scalars().all())

    assert (await inventory_client.get(INVENTORY_PATH)).status_code == 200

    await test_session.rollback()  # see a fresh read, not this session's snapshot
    after = (await test_session.execute(select(func.count()).select_from(FeatureFlag))).scalar()
    after_keys = set((await test_session.execute(select(FeatureFlag.key))).scalars().all())

    assert after == before, f"reading the inventory changed the feature_flags row count from {before} to {after}"
    assert after_keys == before_keys, f"reading the inventory created flag rows: {sorted(after_keys - before_keys)}"


# --------------------------------------------------------------------------- #
# No key material
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_no_vapid_key_material_reaches_the_response(
    inventory_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The public key is safe to publish and still has no business here.

    The whole body is searched for the sentinel rather than the field the key
    would arrive under, so re-adding it under any name fails this. The private
    key is included in the search because the helper reads it from the same place;
    it has never been in the payload and must not become so.
    """
    public_sentinel = "VAPID-PUBLIC-SENTINEL-do-not-serve"
    private_sentinel = "VAPID-PRIVATE-SENTINEL-never-serve"
    monkeypatch.setenv("VAPID_PUBLIC_KEY", public_sentinel)
    monkeypatch.setenv("VAPID_PRIVATE_KEY", private_sentinel)

    response = await inventory_client.get(INVENTORY_PATH)
    assert response.status_code == 200, response.text

    assert public_sentinel not in response.text, "the VAPID public key is being served in the inventory response"
    assert private_sentinel not in response.text, "the VAPID private key is being served in the inventory response"

    push = next(channel for channel in response.json()["channels"] if channel["id"] == "push")
    assert push["diagnostics"].get("private_key_present") is True, (
        "with both keys set the report should still say the keys are present — dropping the value must "
        "not cost the operator the fact"
    )


# --------------------------------------------------------------------------- #
# The gate, as the census reads it
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_the_endpoint_is_authorisation_checked_by_a_named_permission() -> None:
    """Read the mounted app rather than trusting the source of the handler.

    The census is what ``route_declarations.py`` measures debt against. An
    endpoint that reported ``AUTHENTICATED_ONLY`` here would have to be declared
    as debt, and the point of this route is that it never is.
    """
    from src.domain.authz.census import Posture, take_census
    from src.main import app

    census = take_census(app)
    matches = [endpoint for endpoint in census.endpoints if endpoint.path == INVENTORY_PATH]

    assert matches, f"{INVENTORY_PATH} is not mounted; the census cannot see it"
    for endpoint in matches:
        assert endpoint.method == "GET", f"{endpoint} is mounted under the inventory prefix and is not a read"
        assert endpoint.posture is Posture.PERMISSION, f"{endpoint} reports posture {endpoint.posture.value}"
        assert (
            INVENTORY_PERMISSION in endpoint.permissions
        ), f"{endpoint} enforces {endpoint.permissions} rather than {INVENTORY_PERMISSION}"
