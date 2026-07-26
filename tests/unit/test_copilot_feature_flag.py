"""PX-248 containment: the AI Copilot API must stay closed while the flag is off.

Copilot replies are hardcoded simulations rather than inference over tenant data,
so every endpoint has to refuse before it can serve a fabricated payload.
"""

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from src.api.routes import copilot as copilot_routes
from src.core.config import settings

COPILOT_PREFIX = "/api/v1/copilot"

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


def test_actions_endpoint_still_works_when_enabled(client: TestClient, copilot_enabled):
    """Flag on preserves the pre-existing behaviour of the unauthenticated routes."""
    response = client.get(f"{COPILOT_PREFIX}/actions")

    assert response.status_code == 200
    action_names = {action["name"] for action in response.json()}
    assert "create_incident" in action_names
    assert "get_risk_summary" in action_names


def test_suggest_actions_still_works_when_enabled(client: TestClient, copilot_enabled):
    response = client.get(f"{COPILOT_PREFIX}/actions/suggest", params={"context_type": "incident"})

    assert response.status_code == 200
    assert [item["action"] for item in response.json()] == ["create_action", "search_incidents"]


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
