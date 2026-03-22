import types
from unittest.mock import AsyncMock, Mock

import pytest

from src.api.routes.kri import create_kri
from src.api.routes.policy_acknowledgment import get_my_pending_acknowledgments
from src.api.routes.rca_tools import CompleteAnalysisRequest, complete_five_whys_analysis
from src.api.routes.workflow import create_workflow_rule
from src.api.schemas.kri import KRICreate
from src.api.schemas.workflow import WorkflowRuleCreate


class _FakeResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


@pytest.mark.asyncio
async def test_create_workflow_rule_uses_user_attributes(monkeypatch):
    monkeypatch.setattr("src.api.routes.workflow.WorkflowRuleResponse.from_orm", lambda obj: obj)

    db = types.SimpleNamespace(add=Mock(), commit=AsyncMock(), refresh=AsyncMock())
    current_user = types.SimpleNamespace(id=17, email="owner@example.com", tenant_id=None)

    rule = await create_workflow_rule(
        WorkflowRuleCreate(
            name="Escalate critical incidents",
            rule_type="escalation",
            entity_type="incident",
            trigger_event="created",
            action_type="send_email",
            action_config={"to": "ops@example.com"},
        ),
        db,
        current_user,
    )

    assert rule.created_by_id == 17
    assert rule.tenant_id is None


@pytest.mark.asyncio
async def test_create_kri_uses_user_email_attribute(monkeypatch):
    monkeypatch.setattr("src.api.routes.kri.KRIResponse.from_orm", lambda obj: obj)

    db = types.SimpleNamespace(
        execute=AsyncMock(return_value=_FakeResult(None)),
        add=Mock(),
        commit=AsyncMock(),
        refresh=AsyncMock(),
    )
    current_user = types.SimpleNamespace(id=23, email="risk@example.com", tenant_id=51)

    kri = await create_kri(
        KRICreate(
            code="KRI-001",
            name="Open incidents",
            category="safety",
            unit="count",
            data_source="incidents",
            green_threshold=5,
            amber_threshold=10,
            red_threshold=15,
        ),
        db,
        current_user,
    )

    assert kri.created_by_id == 23
    assert kri.tenant_id == 51


@pytest.mark.asyncio
async def test_get_my_pending_acknowledgments_uses_user_id(monkeypatch):
    captured = {}

    class _FakePolicyAcknowledgmentService:
        def __init__(self, _db):
            pass

        async def get_user_pending_acknowledgments(self, user_id):
            captured["user_id"] = user_id
            return []

    monkeypatch.setattr(
        "src.api.routes.policy_acknowledgment.PolicyAcknowledgmentService",
        _FakePolicyAcknowledgmentService,
    )

    response = await get_my_pending_acknowledgments(
        types.SimpleNamespace(),
        types.SimpleNamespace(id=31, email="reader@example.com"),
    )

    assert captured["user_id"] == 31
    assert response.total == 0
    assert response.items == []


@pytest.mark.asyncio
async def test_complete_five_whys_analysis_uses_user_id(monkeypatch):
    captured = {}

    class _FakeFiveWhysService:
        def __init__(self, _db):
            pass

        async def complete_analysis(self, analysis_id, user_id, proposed_actions):
            captured["analysis_id"] = analysis_id
            captured["user_id"] = user_id
            captured["proposed_actions"] = proposed_actions
            return types.SimpleNamespace(id=analysis_id, completed=True, completed_at=None)

    monkeypatch.setattr("src.api.routes.rca_tools.FiveWhysService", _FakeFiveWhysService)

    response = await complete_five_whys_analysis(
        44,
        CompleteAnalysisRequest(proposed_actions=[{"title": "Train team"}]),
        types.SimpleNamespace(),
        types.SimpleNamespace(id=99, email="investigator@example.com"),
    )

    assert captured == {
        "analysis_id": 44,
        "user_id": 99,
        "proposed_actions": [{"title": "Train team"}],
    }
    assert response["completed"] is True
