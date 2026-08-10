"""The inventory endpoint: what it demands, what it discloses, what it refuses to do.

Three properties matter more than the response shape:

* **It is permission-gated.** Read from the route's own dependency graph, not from
  reading the source, because a decorator can be edited without the test noticing.
* **It leaks nothing.** The channel status helpers exist to report configuration,
  and one of them returns a real VAPID public key. Secret material must not reach
  this payload even though the helper is willing to hand some over.
* **It does not write.** ``GET /feature-flags/{key}`` seeds missing Compliance
  Schedule rows, which is right for a page about to toggle them and wrong for a
  report. A read that mutates the thing it measures is not a read.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI

from src.api.routes.notification_inventory import _flag_states, _readiness_payloads, get_notification_inventory, router
from src.domain.authz.extraction import REQUIRED_PERMISSION_ATTR, walk_mounted_app
from src.domain.notifications.inventory import NOT_CONFIGURED, referenced_flag_keys

#: Every environment variable the status helpers read that must never be echoed.
SECRET_ENV = {
    "SMTP_PASSWORD": "smtp-password-sentinel",
    "TWILIO_AUTH_TOKEN": "twilio-token-sentinel",
    "VAPID_PRIVATE_KEY": "vapid-private-sentinel",
    # Public by construction and served by the subscribe flow, and still not this
    # report's business: an inventory has no use for the key material itself.
    "VAPID_PUBLIC_KEY": "vapid-public-sentinel",
}


class _Scalars:
    def __init__(self, items):
        self._items = items

    def all(self):
        return self._items


class _Result:
    def __init__(self, items):
        self._items = items

    def scalars(self):
        return _Scalars(self._items)


def _db(flags=()):
    """A session that can be read and that fails the test if written to."""
    return SimpleNamespace(
        execute=AsyncMock(return_value=_Result(list(flags))),
        add=MagicMock(side_effect=AssertionError("the inventory must not write")),
        commit=AsyncMock(side_effect=AssertionError("the inventory must not commit")),
        flush=AsyncMock(side_effect=AssertionError("the inventory must not flush")),
    )


# --------------------------------------------------------------------------- #
# Authorisation
# --------------------------------------------------------------------------- #


def test_the_endpoint_requires_the_admin_manage_permission() -> None:
    """Read off the mounted dependency graph, so an edited decorator shows up here.

    A mini app rather than ``src.main``: the whole-app guarantee is the census
    test's job, and this only needs to know what this route demands.
    """
    app = FastAPI()
    app.include_router(router, prefix="/api/v1/notifications/inventory")

    mounted = walk_mounted_app(app)
    endpoints = [e for e in mounted.endpoints if e.path == "/api/v1/notifications/inventory"]

    assert endpoints, "the inventory route is not mounted, so this proves nothing"
    tokens = {
        token
        for endpoint in endpoints
        for call in endpoint.calls
        if isinstance(token := getattr(call, REQUIRED_PERMISSION_ATTR, None), str)
    }
    assert tokens == {"admin:manage"}, (
        f"the inventory endpoint demands {sorted(tokens)}. It names every module that produces a "
        "notification and every channel that is not configured, so it must not be readable by any "
        "authenticated caller."
    )


def test_the_permission_is_one_the_catalogue_already_enforces() -> None:
    from src.domain.authz.catalogue import ENFORCED_PERMISSIONS

    assert "admin:manage" in ENFORCED_PERMISSIONS


# --------------------------------------------------------------------------- #
# Disclosure
# --------------------------------------------------------------------------- #


def test_no_secret_environment_value_reaches_the_readiness_payloads(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set every secret the helpers read, then look for it in the output."""
    for name, value in SECRET_ENV.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setenv("SMTP_USER", "ops@example.com")
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "sid-not-secret")
    monkeypatch.setenv("EMAIL_ENABLED", "true")

    serialised = repr(_readiness_payloads())

    for name, value in SECRET_ENV.items():
        assert value not in serialised, f"{name} was echoed into the inventory payload"


def test_the_vapid_public_key_is_dropped_rather_than_relayed(monkeypatch: pytest.MonkeyPatch) -> None:
    """The helper returns the key; this endpoint has no use for it."""
    monkeypatch.setenv("VAPID_PUBLIC_KEY", "vapid-public-sentinel")
    monkeypatch.setenv("VAPID_PRIVATE_KEY", "vapid-private-sentinel")

    from src.infrastructure.push.vapid_status import get_vapid_readiness

    assert get_vapid_readiness()["public_key"] == "vapid-public-sentinel", (
        "the helper no longer returns the public key, so this test is no longer checking that the " "route drops it"
    )
    assert "public_key" not in _readiness_payloads()["vapid"]


def test_readiness_still_reports_that_the_keys_are_present(monkeypatch: pytest.MonkeyPatch) -> None:
    """Dropping the key must not cost the operator the answer they came for."""
    monkeypatch.setenv("VAPID_PUBLIC_KEY", "vapid-public-sentinel")
    monkeypatch.setenv("VAPID_PRIVATE_KEY", "vapid-private-sentinel")

    vapid = _readiness_payloads()["vapid"]

    assert vapid["status"] == "configured"
    assert vapid["public_key_present"] is True
    assert vapid["private_key_present"] is True


# --------------------------------------------------------------------------- #
# Reading flags without seeding them
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_absent_flag_rows_are_reported_unpersisted_and_not_created() -> None:
    """The endpoint must not seed the rows it is reporting on."""
    db = _db(flags=())

    states = await _flag_states(db)

    assert set(states) == set(referenced_flag_keys())
    assert all(value is None for value in states.values())
    db.add.assert_not_called()
    db.commit.assert_not_called()


@pytest.mark.asyncio
async def test_persisted_flag_rows_are_read_back() -> None:
    keys = referenced_flag_keys()
    rows = [SimpleNamespace(key=key, enabled=False) for key in keys]

    states = await _flag_states(_db(flags=rows))

    assert states == {key: False for key in keys}


@pytest.mark.asyncio
async def test_an_unreadable_flag_table_does_not_fail_the_report() -> None:
    """A broken flag read should cost the flag detail, not the whole inventory."""
    db = SimpleNamespace(execute=AsyncMock(side_effect=RuntimeError("no such table")))

    states = await _flag_states(db)

    assert states == {key: None for key in referenced_flag_keys()}


# --------------------------------------------------------------------------- #
# The handler
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_the_handler_reports_channels_producers_and_a_summary() -> None:
    response = await get_notification_inventory(db=_db(), current_user=SimpleNamespace(id=1))

    assert response.generated_at.endswith("+00:00"), "the snapshot time should be explicit about UTC"
    assert {channel.id for channel in response.channels} >= {"in_app", "email", "sms", "push"}
    assert response.summary.producers_total == len(response.producers)
    assert response.summary.producers_without_caller > 0, (
        "the report exists to name producers nothing reaches; a run finding none has almost "
        "certainly stopped looking"
    )


@pytest.mark.asyncio
async def test_the_handler_names_the_producers_that_notify_nobody() -> None:
    """The honesty payload: a caller can see which events reach no one."""
    response = await get_notification_inventory(db=_db(), current_user=SimpleNamespace(id=1))

    dead = {producer.id for producer in response.producers if producer.status == "no_production_caller"}

    assert {"sos_alert", "riddor_alert", "competency_expiry", "mention_fanout"} <= dead


@pytest.mark.asyncio
async def test_a_failing_status_helper_reports_not_configured_rather_than_500(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One channel's malformed environment must not take the whole report down."""
    import src.infrastructure.email.email_status as email_status

    def explode() -> dict:
        raise RuntimeError("malformed SMTP_PORT")

    monkeypatch.setattr(email_status, "get_email_readiness", explode)

    response = await get_notification_inventory(db=_db(), current_user=SimpleNamespace(id=1))
    email = next(channel for channel in response.channels if channel.id == "email")

    assert email.readiness == NOT_CONFIGURED
    assert email.can_send is False


@pytest.mark.asyncio
async def test_the_handler_writes_nothing() -> None:
    """Belt and braces: the fake session raises on every write path."""
    db = _db()

    await get_notification_inventory(db=db, current_user=SimpleNamespace(id=1))

    db.add.assert_not_called()
    db.commit.assert_not_called()
    db.flush.assert_not_called()
