"""Unit tests for CopilotService - can run standalone."""

import os
import sys
from unittest.mock import AsyncMock, MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from src.domain.services.copilot_service import COPILOT_ACTIONS, SYSTEM_PROMPT, CopilotService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_service() -> CopilotService:
    """Create a CopilotService with a mocked DB session."""
    db = AsyncMock()
    return CopilotService(db)


class MockSession:
    def __init__(self, **kwargs):
        self.current_page = kwargs.get("current_page", "/dashboard")
        self.context_type = kwargs.get("context_type", "incident")
        self.context_id = kwargs.get("context_id", "INC-001")
        self.context_data = kwargs.get("context_data", {"severity": "high"})


# ---------------------------------------------------------------------------
# COPILOT_ACTIONS registry tests
# ---------------------------------------------------------------------------


def test_action_registry_has_required_actions():
    """All core actions are registered."""
    required = ["create_incident", "search_incidents", "get_compliance_status", "navigate", "explain"]
    for action in required:
        assert action in COPILOT_ACTIONS, f"Missing action: {action}"
    print("✓ All required actions registered")


def test_action_definitions_have_required_fields():
    """Every action definition has name, description, and examples."""
    for name, defn in COPILOT_ACTIONS.items():
        assert "name" in defn, f"{name} missing 'name'"
        assert "description" in defn, f"{name} missing 'description'"
        assert "examples" in defn, f"{name} missing 'examples'"
        assert len(defn["examples"]) > 0, f"{name} has no examples"
    print("✓ All actions have required fields")


# ---------------------------------------------------------------------------
# _build_context tests
# ---------------------------------------------------------------------------


def test_build_context_includes_session_fields():
    """Context dict includes current_page, context_type, context_id, context_data."""
    svc = _make_service()
    session = MockSession()
    ctx = svc._build_context(session)
    assert ctx["current_page"] == "/dashboard"
    assert ctx["context_type"] == "incident"
    assert ctx["context_id"] == "INC-001"
    assert ctx["context_data"] == {"severity": "high"}
    print("✓ _build_context includes all session fields")


def test_build_context_handles_none_values():
    """Context works when optional session fields are None."""
    svc = _make_service()
    session = MockSession(current_page=None, context_type=None, context_id=None, context_data={})
    ctx = svc._build_context(session)
    assert ctx["current_page"] is None
    assert ctx["context_data"] == {}
    print("✓ _build_context handles None values")


# ---------------------------------------------------------------------------
# _simulate_ai_response tests
# ---------------------------------------------------------------------------


def test_simulate_create_incident():
    """'create incident' triggers create_incident action."""
    svc = _make_service()
    text, action = svc._simulate_ai_response("Create incident for broken handrail", {})
    assert action is not None
    assert action["action"] == "create_incident"
    assert "title" in action["parameters"]
    print("✓ create incident detected")


def test_simulate_compliance_iso_45001():
    """ISO 45001 mention triggers compliance action with correct standard."""
    svc = _make_service()
    text, action = svc._simulate_ai_response("How compliant are we with ISO 45001?", {})
    assert action is not None
    assert action["action"] == "get_compliance_status"
    assert action["parameters"]["standard"] == "iso45001"
    print("✓ ISO 45001 compliance detected")


def test_simulate_risk_query_returns_no_action():
    """Risk summary queries return informational text without an action."""
    svc = _make_service()
    text, action = svc._simulate_ai_response("Show me the risk summary", {})
    assert action is None
    assert "risk" in text.lower()
    print("✓ Risk query returns text, no action")


def test_simulate_navigation():
    """'Go to incidents' triggers navigate action."""
    svc = _make_service()
    text, action = svc._simulate_ai_response("Go to incidents", {})
    assert action is not None
    assert action["action"] == "navigate"
    assert action["parameters"]["destination"] == "/incidents"
    print("✓ Navigation detected")


def test_simulate_explain():
    """'What is CAPA?' returns explanation text, no action."""
    svc = _make_service()
    text, action = svc._simulate_ai_response("What is CAPA?", {})
    assert action is None
    assert "capa" in text.lower() or "CAPA" in text
    print("✓ Explanation returned for CAPA")


def test_simulate_default_response():
    """Unrecognized input returns default help text."""
    svc = _make_service()
    text, action = svc._simulate_ai_response("Tell me a joke", {})
    assert action is None
    assert "help you with" in text.lower() or "can help" in text.lower()
    print("✓ Default response for unrecognized input")


# ---------------------------------------------------------------------------
# System prompt tests
# ---------------------------------------------------------------------------


def test_system_prompt_has_placeholders():
    """SYSTEM_PROMPT contains {actions} and {context} placeholders."""
    assert "{actions}" in SYSTEM_PROMPT
    assert "{context}" in SYSTEM_PROMPT
    print("✓ SYSTEM_PROMPT has required placeholders")


if __name__ == "__main__":
    print("=" * 60)
    print("COPILOT SERVICE TESTS")
    print("=" * 60)
    print()

    test_action_registry_has_required_actions()
    test_action_definitions_have_required_fields()
    print()
    test_build_context_includes_session_fields()
    test_build_context_handles_none_values()
    print()
    test_simulate_create_incident()
    test_simulate_compliance_iso_45001()
    test_simulate_risk_query_returns_no_action()
    test_simulate_navigation()
    test_simulate_explain()
    test_simulate_default_response()
    print()
    test_system_prompt_has_placeholders()

    print()
    print("=" * 60)
    print("ALL TESTS PASSED ✅")
    print("=" * 60)
