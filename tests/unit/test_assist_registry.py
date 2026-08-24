"""FR-ASSIST-CORE-01: Assist tool registry contracts."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from src.domain.authz.catalogue import ENFORCED_PERMISSIONS
from src.domain.authz.extraction import _resolve_assist_tool_tokens
from src.domain.services.assist.permissions import tool_is_visible
from src.domain.services.assist.registry import ASSIST_TOOLS, get_assist_tool, validate_assist_registry
from src.domain.services.copilot_grounding import GROUNDED_INTENTS, detect_grounded_intent


def test_assist_registry_validates():
    validate_assist_registry()


def test_assist_tool_names_match_grounded_intents():
    names = {t.name for t in ASSIST_TOOLS}
    assert names == set(GROUNDED_INTENTS)


def test_assist_required_permissions_are_enforced():
    for tool in ASSIST_TOOLS:
        if tool.required_permission is None:
            assert tool.auth_only_reason
            continue
        assert tool.required_permission in ENFORCED_PERMISSIONS


def test_resolve_assist_tool_tokens_matches_registry():
    src_root = Path(__file__).resolve().parents[2] / "src"
    derived = _resolve_assist_tool_tokens(src_root)
    expected = {t.required_permission for t in ASSIST_TOOLS if t.required_permission}
    assert derived == expected


def test_tool_is_visible_requires_permission():
    tool = get_assist_tool("incident_count")
    assert tool is not None
    assert tool_is_visible(None, tool) is False
    denied = SimpleNamespace(is_superuser=False, has_permission=lambda p: False)
    assert tool_is_visible(denied, tool) is False
    allowed = SimpleNamespace(is_superuser=False, has_permission=lambda p: p == "incident:read")
    assert tool_is_visible(allowed, tool) is True
    admin = SimpleNamespace(is_superuser=True, has_permission=lambda p: False)
    assert tool_is_visible(admin, tool) is True


def test_vehicle_intents_detect():
    assert detect_grounded_intent("biggest issues for vehicle checks") == "vehicle_check_top_failures"
    assert detect_grounded_intent("how many open vehicle defects") == "vehicle_check_defect_summary"
