"""PX-248 / PX-250 residual: when the copilot flag is on, simulated replies must
still refuse fabricated live-data figures and must never claim a write completed.
"""

from types import SimpleNamespace

import pytest

from src.domain.services.copilot_service import CopilotService


@pytest.fixture
def service():
    return CopilotService(db=SimpleNamespace())


def test_simulate_explains_capa_without_live_register_claim(service: CopilotService):
    """Demo prompt "what is CAPA" must return general CAPA guidance (no live register)."""
    content, action = service._simulate_ai_response("what is CAPA", {})
    assert action is None
    assert "Corrective and Preventive Action" in content
    assert "General guidance only" in content
    assert "CAPA-" not in content  # no fabricated reference numbers


def test_simulate_refuses_fabricated_compliance_percentage(service: CopilotService):
    content, action = service._simulate_ai_response("Compliance Status", {})
    assert "92%" not in content
    assert "Overall Compliance" not in content
    assert "cannot answer from live organisation data" in content.lower() or "not connected" in content.lower()
    assert action is not None
    assert action["honesty"] == "not_performed"
    assert action["action"] == "get_compliance_status"


def test_simulate_refuses_invented_named_risks(service: CopilotService):
    content, action = service._simulate_ai_response("Risk Summary", {})
    assert "Supply chain disruption" not in content
    assert "Cybersecurity" not in content
    assert "Critical Risks:** 2" not in content
    assert action is not None
    assert action["honesty"] == "not_performed"


def test_simulate_refuses_incident_create_without_false_proceed(service: CopilotService):
    content, action = service._simulate_ai_response("create an incident for a slip", {})
    assert "Shall I proceed" not in content
    assert "Nothing was written" in content or "cannot create" in content.lower()
    assert action is not None
    assert action["action"] == "create_incident"
    assert action["honesty"] == "not_performed"


@pytest.mark.asyncio
async def test_execute_action_never_marks_write_completed(service: CopilotService):
    class _Msg:
        action_result = None
        action_status = "pending"

    class _Db:
        async def commit(self):
            return None

    service.db = _Db()
    message = _Msg()
    await service._execute_action(
        message,
        {
            "action": "create_incident",
            "parameters": {"title": "slip"},
            "honesty": "not_performed",
        },
    )
    assert message.action_status == "not_performed"
    assert message.action_result["performed"] is False
    assert "INC-" not in str(message.action_result)


def test_actions_execute_route_never_returns_success_true(client, monkeypatch):
    """PX-250 residual on the HTTP execute surface when the flag is on."""
    from types import SimpleNamespace

    from src.api.dependencies import get_current_user
    from src.core.config import settings
    from src.main import app

    monkeypatch.setattr(settings, "ai_copilot_enabled", True)
    monkeypatch.setattr(settings, "app_env", "development")

    async def _current_user():
        return SimpleNamespace(id=1, email="qhse@example.com", tenant_id=1, is_active=True, is_superuser=False)

    app.dependency_overrides[get_current_user] = _current_user
    try:
        response = client.post(
            "/api/v1/copilot/actions/execute",
            json={"action_name": "create_incident", "parameters": {"title": "slip"}},
        )
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "not_performed"
    assert body["result"]["success"] is False
    assert body["result"]["performed"] is False
