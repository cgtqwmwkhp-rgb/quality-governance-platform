"""Unit tests for NL search interpret (rules + allowlist + fail-closed)."""

from datetime import date
from unittest.mock import AsyncMock, patch

import pytest

from src.domain.services.search_interpret_service import (
    apply_date_range,
    interpret_search_query,
    interpret_with_rules,
    validate_intent,
)


def test_rules_overdue_actions_navigates():
    intent = interpret_with_rules("Show all overdue actions")
    assert intent is not None
    assert intent["module"] == "Actions"
    assert intent["navigate"] == "/actions?view=my_overdue"
    assert intent["source"] == "rules"


def test_rules_high_priority_incidents():
    intent = interpret_with_rules("Recent high-priority incidents")
    assert intent is not None
    assert intent["module"] == "Incidents"
    assert "open" in intent["status"]


def test_rules_pending_audits_month_dates():
    intent = interpret_with_rules("Pending ISO audits this month")
    assert intent is not None
    assert intent["module"] == "Audits"
    assert intent["date_from"] is not None
    assert intent["date_to"] is not None


def test_rules_unresolved_complaints():
    intent = interpret_with_rules("Unresolved customer complaints")
    assert intent is not None
    assert intent["module"] == "Complaints"


def test_validate_intent_rejects_unknown_module():
    out = validate_intent({"q": "x", "module": "Hacking", "source": "gemini"}, fallback_q="x")
    assert out["module"] is None
    assert out["q"] == "x"


def test_validate_intent_rejects_external_navigate():
    out = validate_intent({"q": "x", "navigate": "https://evil.example"}, fallback_q="x")
    assert out["navigate"] is None


def test_validate_intent_rejects_protocol_relative_navigate():
    out = validate_intent({"q": "x", "navigate": "//evil.example/phish"}, fallback_q="x")
    assert out["navigate"] is None


def test_apply_date_range_month():
    out = apply_date_range({"date_range": "month", "q": "a"}, today=date(2026, 7, 16))
    assert out["date_from"] == "2026-07-01"
    assert out["date_to"] == "2026-07-31"
    assert "date_range" not in out


@pytest.mark.asyncio
async def test_interpret_search_query_uses_rules_before_gemini():
    with patch(
        "src.domain.services.search_interpret_service.interpret_with_gemini",
        new_callable=AsyncMock,
    ) as gemini:
        result = await interpret_search_query("overdue actions")
        assert result["source"] == "rules"
        gemini.assert_not_called()


@pytest.mark.asyncio
async def test_interpret_search_query_falls_back_to_keyword():
    with patch(
        "src.domain.services.search_interpret_service.interpret_with_gemini",
        new_callable=AsyncMock,
        return_value=None,
    ):
        result = await interpret_search_query("policy")
        assert result["source"] == "keyword"
        assert result["q"] == "policy"
