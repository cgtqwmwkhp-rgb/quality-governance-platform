"""The copilot runtime kill switch may close the surface and may never open it.

``AI_COPILOT_ENABLED`` is process configuration and costs a redeploy to change. The
switch is the fast path for closing a copilot that has started misbehaving, so the
properties worth pinning are that it closes promptly, that it cannot be talked out of a
close by an infrastructure failure, and — above all — that no database state can turn a
copilot on in an environment whose configuration says off.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from src.api.dependencies import get_current_user
from src.api.routes import copilot as copilot_routes
from src.core.config import settings
from src.domain.services import copilot_kill_switch as kill_switch_module
from src.domain.services.copilot_kill_switch import (
    copilot_kill_switch_engaged,
    copilot_kill_switch_last_known,
    reset_copilot_kill_switch_cache,
)

COPILOT_PREFIX = "/api/v1/copilot"


class _FakeSessionFactory:
    """Stands in for ``async_session_maker``, counting reads and forcing outcomes.

    Hermetic on purpose: the unit suite has no database in CI, and a test that proved
    the kill switch works only where Postgres happens to be listening would prove it
    where it is least likely to be needed.
    """

    def __init__(self, *, enabled: bool | None = False, error: Exception | None = None) -> None:
        self._enabled = enabled
        self._error = error
        self.reads = 0
        self.sessions_opened = 0

    def __call__(self) -> "_FakeSessionFactory":
        self.sessions_opened += 1
        return self

    async def __aenter__(self) -> "_FakeSessionFactory":
        return self

    async def __aexit__(self, *_exc_info: object) -> bool:
        return False

    async def execute(self, _statement: object) -> "_FakeSessionFactory":
        self.reads += 1
        if self._error is not None:
            raise self._error
        return self

    def scalar_one_or_none(self) -> bool | None:
        return self._enabled


@pytest.fixture(autouse=True)
def clean_kill_switch_cache():
    """The verdict cache is process-wide, so it has to be cleared either side of a test."""
    reset_copilot_kill_switch_cache()
    yield
    reset_copilot_kill_switch_cache()


@pytest.fixture
def copilot_configured_on(monkeypatch):
    monkeypatch.setattr(settings, "ai_copilot_enabled", True)
    monkeypatch.setattr(settings, "app_env", "production")


@pytest.fixture
def copilot_configured_off(monkeypatch):
    monkeypatch.setattr(settings, "ai_copilot_enabled", False)


@pytest.fixture
def authenticated_caller(app):
    async def _current_user():
        return SimpleNamespace(id=1, email="qhse@example.com", tenant_id=1, is_active=True, is_superuser=False)

    app.dependency_overrides[get_current_user] = _current_user
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def _install_switch(monkeypatch, factory) -> None:
    """Point the route module's session factory at a fake."""
    monkeypatch.setattr(copilot_routes, "async_session_maker", factory)


# --------------------------------------------------------------------------- #
# The property the whole design exists for: the switch subtracts, never adds
# --------------------------------------------------------------------------- #


def test_an_engaged_switch_cannot_open_a_copilot_configuration_has_closed(
    client: TestClient, copilot_configured_off, monkeypatch
):
    """The row that means "kill it" must not be readable as "allow it"."""
    _install_switch(monkeypatch, _FakeSessionFactory(enabled=True))

    assert client.get(f"{COPILOT_PREFIX}/actions").status_code == 404


def test_a_disengaged_switch_cannot_open_a_copilot_configuration_has_closed(
    client: TestClient, copilot_configured_off, monkeypatch
):
    _install_switch(monkeypatch, _FakeSessionFactory(enabled=False))

    assert client.get(f"{COPILOT_PREFIX}/actions").status_code == 404


def test_configuration_off_never_reaches_the_database(client: TestClient, copilot_configured_off, monkeypatch):
    """Structural half of the guarantee: the read is unreachable, not merely overruled.

    Asserted by counting rather than by exploding on contact. ``copilot_kill_switch_engaged``
    swallows everything a read can throw — that is its contract — so a factory that raised
    on use would have its objection caught and the test would pass on a copilot that
    consults the database before it consults its own configuration.
    """
    factory = _FakeSessionFactory(enabled=True)
    _install_switch(monkeypatch, factory)

    assert client.get(f"{COPILOT_PREFIX}/actions").status_code == 404
    assert factory.sessions_opened == 0, (
        "the kill switch was read while AI_COPILOT_ENABLED was off. Configuration has to short "
        "circuit first, or database state sits upstream of the decision to serve a copilot at all."
    )


# --------------------------------------------------------------------------- #
# Closing a configured-on copilot
# --------------------------------------------------------------------------- #


def test_engaging_the_switch_closes_the_http_surface(
    client: TestClient, copilot_configured_on, authenticated_caller, monkeypatch
):
    _install_switch(monkeypatch, _FakeSessionFactory(enabled=True))

    response = client.get(f"{COPILOT_PREFIX}/actions")

    assert response.status_code == 404
    assert response.json()["error"]["message"] == copilot_routes.COPILOT_DISABLED_DETAIL
    assert "create_incident" not in response.text


def test_engaging_the_switch_closes_the_chat_socket(client: TestClient, copilot_configured_on, monkeypatch):
    """The socket has to refuse on handshake; it cannot answer with a 404."""
    _install_switch(monkeypatch, _FakeSessionFactory(enabled=True))

    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect(f"{COPILOT_PREFIX}/ws/1?token=irrelevant") as ws:
            ws.receive_text()

    assert exc_info.value.code == 4004


def test_a_disengaged_switch_leaves_a_configured_copilot_open(
    client: TestClient, copilot_configured_on, authenticated_caller, monkeypatch
):
    _install_switch(monkeypatch, _FakeSessionFactory(enabled=False))

    response = client.get(f"{COPILOT_PREFIX}/actions")

    assert response.status_code == 200
    assert "create_incident" in {action["name"] for action in response.json()}


def test_no_flag_row_leaves_a_configured_copilot_open(
    client: TestClient, copilot_configured_on, authenticated_caller, monkeypatch
):
    """The shipped state is no row at all, which must mean nobody has engaged the kill."""
    _install_switch(monkeypatch, _FakeSessionFactory(enabled=None))

    assert client.get(f"{COPILOT_PREFIX}/actions").status_code == 200


# --------------------------------------------------------------------------- #
# Behaviour of the read itself
# --------------------------------------------------------------------------- #


async def test_absent_row_reads_as_not_engaged():
    factory = _FakeSessionFactory(enabled=None)

    assert await copilot_kill_switch_engaged(factory) is False


async def test_a_verdict_is_reused_within_its_ttl():
    """One query per process per interval, not one per request."""
    factory = _FakeSessionFactory(enabled=True)

    assert await copilot_kill_switch_engaged(factory) is True
    assert await copilot_kill_switch_engaged(factory) is True

    assert factory.reads == 1


async def test_an_expired_verdict_is_re_read(monkeypatch):
    monkeypatch.setattr(kill_switch_module, "SUCCESS_TTL_SECONDS", 0.0)
    factory = _FakeSessionFactory(enabled=False)

    await copilot_kill_switch_engaged(factory)
    await copilot_kill_switch_engaged(factory)

    assert factory.reads == 2


async def test_clearing_the_switch_reopens_the_copilot(monkeypatch):
    """A kill is sticky against failure, not against an operator changing their mind."""
    monkeypatch.setattr(kill_switch_module, "SUCCESS_TTL_SECONDS", 0.0)

    assert await copilot_kill_switch_engaged(_FakeSessionFactory(enabled=True)) is True
    assert await copilot_kill_switch_engaged(_FakeSessionFactory(enabled=False)) is False


# --------------------------------------------------------------------------- #
# What an unreadable switch means
# --------------------------------------------------------------------------- #


async def test_an_unreadable_switch_that_was_never_observed_does_not_close_the_copilot():
    """Configuration decides, as it did before this module existed.

    Failing closed here would take the copilot down on any database wobble, which is a
    bigger behaviour change than the one being guarded against.
    """
    factory = _FakeSessionFactory(error=RuntimeError('relation "feature_flags" does not exist'))

    assert await copilot_kill_switch_engaged(factory) is False


async def test_an_unreadable_switch_cannot_reopen_a_kill_already_observed(monkeypatch):
    """The sticky property: infrastructure failure must not undo an operator's decision."""
    monkeypatch.setattr(kill_switch_module, "SUCCESS_TTL_SECONDS", 0.0)
    monkeypatch.setattr(kill_switch_module, "ERROR_RETRY_SECONDS", 0.0)

    assert await copilot_kill_switch_engaged(_FakeSessionFactory(enabled=True)) is True

    broken = _FakeSessionFactory(error=ConnectionRefusedError("database is gone"))
    assert await copilot_kill_switch_engaged(broken) is True
    assert await copilot_kill_switch_engaged(broken) is True


async def test_a_failed_read_never_propagates_to_the_caller():
    factory = _FakeSessionFactory(error=ValueError("anything at all"))

    assert await copilot_kill_switch_engaged(factory) is False


# --------------------------------------------------------------------------- #
# The service-layer second line
# --------------------------------------------------------------------------- #


async def test_last_known_reports_nothing_before_a_read_has_completed():
    assert copilot_kill_switch_last_known() is False


async def test_last_known_reports_an_observed_kill():
    await copilot_kill_switch_engaged(_FakeSessionFactory(enabled=True))

    assert copilot_kill_switch_last_known() is True


async def test_the_service_refuses_to_generate_once_a_kill_has_been_observed(monkeypatch):
    """Closes the non-HTTP caller, which no route guard covers."""
    from src.domain.services import copilot_service as copilot_service_module

    monkeypatch.setattr(settings, "ai_copilot_enabled", True)
    await copilot_kill_switch_engaged(_FakeSessionFactory(enabled=True))

    service = copilot_service_module.CopilotService(db=None)

    with pytest.raises(copilot_service_module.CopilotDisabledError):
        await service.send_message(session_id=1, content="what is a CAPA?", user_id=1, tenant_id=1)
