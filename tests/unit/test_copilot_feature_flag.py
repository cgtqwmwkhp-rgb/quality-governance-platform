"""PX-248 containment: the AI Copilot API must stay closed while the flag is off,
and closed to anonymous callers when it is on.

Copilot replies are hardcoded simulations rather than inference over tenant data,
so every endpoint has to refuse before it can serve a fabricated payload.
"""

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from src.api.dependencies import get_current_user
from src.api.routes import copilot as copilot_routes
from src.core.config import settings

COPILOT_PREFIX = "/api/v1/copilot"

# Every copilot HTTP route currently mounted, as (method, path). Routes are identified by
# their published method and path rather than by FastAPI's route classes: the repo floats
# on ``fastapi>=0.109,<1.0``, and the internal route objects are not stable across that
# range, whereas method and path are the contract.
EXPECTED_HTTP_ROUTES = {
    ("DELETE", f"{COPILOT_PREFIX}/sessions/{{session_id}}"),
    ("GET", f"{COPILOT_PREFIX}/actions"),
    ("GET", f"{COPILOT_PREFIX}/actions/suggest"),
    ("GET", f"{COPILOT_PREFIX}/knowledge/search"),
    ("GET", f"{COPILOT_PREFIX}/sessions"),
    ("GET", f"{COPILOT_PREFIX}/sessions/active"),
    ("GET", f"{COPILOT_PREFIX}/sessions/{{session_id}}"),
    ("GET", f"{COPILOT_PREFIX}/sessions/{{session_id}}/messages"),
    ("POST", f"{COPILOT_PREFIX}/actions/execute"),
    ("POST", f"{COPILOT_PREFIX}/knowledge"),
    ("POST", f"{COPILOT_PREFIX}/messages/{{message_id}}/feedback"),
    ("POST", f"{COPILOT_PREFIX}/sessions"),
    ("POST", f"{COPILOT_PREFIX}/sessions/{{session_id}}/messages"),
}


def mounted_copilot_http_routes() -> set[tuple[str, str]]:
    """The copilot HTTP surface actually mounted on the app, as (method, path).

    HEAD is excluded because the framework derives it from GET, and the WebSocket route
    is excluded because it carries no ``methods`` and authenticates its own token.
    """
    from src.main import app

    return {
        (method, path)
        for route in app.routes
        for path in [getattr(route, "path", "")]
        if path.startswith(COPILOT_PREFIX)
        for method in (getattr(route, "methods", None) or ())
        if method != "HEAD"
    }


# One representative request per copilot HTTP route. None of these send credentials:
# the guard has to fire ahead of authentication so a disabled feature is never
# distinguishable from a missing one.
COPILOT_REQUESTS = [
    ("GET", "/actions", None),
    ("GET", "/actions/suggest", None),
    ("GET", "/sessions", None),
    ("GET", "/sessions/active", None),
    ("GET", "/sessions/1", None),
    ("DELETE", "/sessions/1", None),
    ("POST", "/sessions", {}),
    ("POST", "/sessions/1/messages", {"content": "what is our ISO 9001 compliance?"}),
    ("GET", "/sessions/1/messages", None),
    ("POST", "/messages/1/feedback", {"rating": 5, "feedback_type": "helpful"}),
    ("POST", "/actions/execute", {"action_name": "get_risk_summary", "parameters": {}}),
    ("GET", "/knowledge/search?query=capa", None),
    ("POST", "/knowledge?title=t&content=c&category=general", None),
]


@pytest.fixture
def copilot_disabled(monkeypatch):
    monkeypatch.setattr(settings, "ai_copilot_enabled", False)


@pytest.fixture
def copilot_enabled(monkeypatch):
    monkeypatch.setattr(settings, "ai_copilot_enabled", True)
    monkeypatch.setattr(settings, "app_env", "development")


@pytest.fixture
def authenticated_caller(app):
    """Stand in for a resolved bearer token so route bodies can be exercised."""

    async def _current_user():
        return SimpleNamespace(id=1, email="qhse@example.com", tenant_id=1, is_active=True, is_superuser=False)

    app.dependency_overrides[get_current_user] = _current_user
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_flag_defaults_to_off():
    """The shipped default must be OFF in every environment."""
    assert settings.ai_copilot_enabled is False


def test_production_refuses_even_when_the_flag_is_set(client: TestClient, monkeypatch):
    """Production is never eligible, mirroring the frontend gate — an env var cannot open it."""
    monkeypatch.setattr(settings, "ai_copilot_enabled", True)
    monkeypatch.setattr(settings, "app_env", "production")

    assert client.get(f"{COPILOT_PREFIX}/actions").status_code == 404


@pytest.mark.parametrize("method,path,body", COPILOT_REQUESTS)
def test_endpoints_refuse_when_disabled(client: TestClient, copilot_disabled, method, path, body):
    response = client.request(method, f"{COPILOT_PREFIX}{path}", json=body)

    assert response.status_code == 404, f"{method} {path} returned {response.status_code}: {response.text}"


def test_disabled_response_carries_no_simulated_payload(client: TestClient, copilot_disabled):
    """A refusal must not leak the mock content the endpoint would otherwise return."""
    response = client.get(f"{COPILOT_PREFIX}/actions")

    assert response.status_code == 404
    assert response.json()["error"]["message"] == copilot_routes.COPILOT_DISABLED_DETAIL
    assert "create_incident" not in response.text


def test_websocket_refuses_when_disabled(client: TestClient, copilot_disabled):
    """The chat socket closes on handshake instead of streaming simulated replies."""
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect(f"{COPILOT_PREFIX}/ws/1?token=irrelevant") as ws:
            ws.receive_text()

    assert exc_info.value.code == 4004


def test_actions_endpoint_still_works_when_enabled(client: TestClient, copilot_enabled, authenticated_caller):
    """Flag on preserves the action catalogue — for authenticated callers only."""
    response = client.get(f"{COPILOT_PREFIX}/actions")

    assert response.status_code == 200
    action_names = {action["name"] for action in response.json()}
    assert "create_incident" in action_names
    assert "get_risk_summary" in action_names


def test_suggest_actions_still_works_when_enabled(client: TestClient, copilot_enabled, authenticated_caller):
    response = client.get(f"{COPILOT_PREFIX}/actions/suggest", params={"context_type": "incident"})

    assert response.status_code == 200
    assert [item["action"] for item in response.json()] == ["create_action", "search_incidents"]


@pytest.mark.parametrize("path", ["/actions", "/actions/suggest"])
def test_action_routes_reject_anonymous_callers_when_enabled(client: TestClient, copilot_enabled, path):
    """PX-248 follow-up: both action routes shipped with no authentication dependency."""
    response = client.get(f"{COPILOT_PREFIX}{path}")

    assert response.status_code in {401, 403}, f"GET {path} served an anonymous caller: {response.text}"
    assert "create_incident" not in response.text


@pytest.mark.parametrize("path", ["/actions", "/actions/suggest"])
def test_action_routes_reject_invalid_tokens_when_enabled(client: TestClient, copilot_enabled, path):
    response = client.get(f"{COPILOT_PREFIX}{path}", headers={"Authorization": "Bearer not-a-real-token"})

    assert response.status_code == 401
    assert "create_incident" not in response.text


def test_the_mounted_copilot_surface_is_exactly_the_matrix_above():
    """Tripwire: a route added later must be added to COPILOT_REQUESTS, not silently skipped.

    COPILOT_REQUESTS and the authentication contract in
    tests/unit/test_copilot_openapi_exclusion.py are both driven from that list, so an
    unlisted route would be checked by neither.
    """
    assert mounted_copilot_http_routes() == EXPECTED_HTTP_ROUTES


def test_authenticated_routes_reach_auth_when_enabled(client: TestClient, copilot_enabled):
    """With the flag on, the guard is transparent: unauthenticated calls fail on auth, not 404."""
    response = client.post(f"{COPILOT_PREFIX}/sessions", json={})

    assert response.status_code in {401, 403}


@pytest.mark.parametrize(
    "flag,app_env,expected",
    [
        (False, "development", False),
        (False, "production", False),
        (True, "production", False),
        (True, "staging", True),
        (True, "development", True),
    ],
)
def test_copilot_is_enabled_requires_opt_in_outside_production(monkeypatch, flag, app_env, expected):
    from src.domain.services.copilot_service import copilot_is_enabled

    monkeypatch.setattr(settings, "ai_copilot_enabled", flag)
    monkeypatch.setattr(settings, "app_env", app_env)

    assert copilot_is_enabled() is expected


async def test_service_refuses_to_generate_when_disabled(monkeypatch):
    """Non-HTTP callers cannot bypass the flag to produce fabricated content."""
    from src.domain.services import copilot_service as copilot_service_module

    monkeypatch.setattr(settings, "ai_copilot_enabled", False)
    service = copilot_service_module.CopilotService(db=None)

    with pytest.raises(copilot_service_module.CopilotDisabledError):
        await service.send_message(session_id=1, content="what is our risk summary?", user_id=1)
