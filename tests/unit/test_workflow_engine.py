"""Tests for WorkflowEngine – start, advance, routing, escalation, delegation."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from src.domain.services.workflow_engine import WorkflowTemplateEngine as WorkflowEngine


@pytest.fixture
def engine():
    return WorkflowEngine()


class TestStartWorkflow:
    def test_start_riddor_workflow(self, engine):
        result = engine.start_workflow(
            template_code="RIDDOR",
            entity_type="incident",
            entity_id="INC-001",
            initiated_by=1,
        )

        assert result["template_code"] == "RIDDOR"
        assert result["status"] == "in_progress"
        assert result["current_step"] == 0
        assert result["current_step_name"] == "Initial Review"
        assert result["total_steps"] == 4
        assert result["entity_type"] == "incident"
        assert result["entity_id"] == "INC-001"
        assert result["initiated_by"] == 1
        assert result["sla_breached"] is False
        assert result["id"].startswith("WF-")

    def test_start_capa_workflow(self, engine):
        result = engine.start_workflow(
            template_code="CAPA",
            entity_type="action",
            entity_id="ACT-001",
            initiated_by=2,
            priority="high",
        )

        assert result["priority"] == "high"
        assert result["template_name"] == "Corrective/Preventive Action Workflow"
        assert result["total_steps"] == 4

    def test_start_workflow_unknown_template(self, engine):
        result = engine.start_workflow(
            template_code="NONEXISTENT",
            entity_type="incident",
            entity_id="INC-001",
            initiated_by=1,
        )

        assert "error" in result
        assert "Template not found" in result["error"]

    def test_start_workflow_with_context(self, engine):
        ctx = {"department": "Engineering", "severity": "critical"}
        result = engine.start_workflow(
            template_code="NCR",
            entity_type="audit_finding",
            entity_id="AF-001",
            initiated_by=3,
            context=ctx,
        )

        assert result["context"] == ctx

    def test_start_workflow_default_priority(self, engine):
        result = engine.start_workflow(
            template_code="DOCUMENT_APPROVAL",
            entity_type="document",
            entity_id="DOC-001",
            initiated_by=1,
        )
        assert result["priority"] == "normal"

    def test_steps_initialised_correctly(self, engine):
        result = engine.start_workflow(
            template_code="RIDDOR",
            entity_type="incident",
            entity_id="INC-001",
            initiated_by=1,
        )

        steps = result["steps"]
        assert len(steps) == 4
        assert steps[0]["status"] == "in_progress"
        assert steps[0]["started_at"] is not None
        for step in steps[1:]:
            assert step["status"] == "pending"
            assert step["started_at"] is None

    def test_sla_timestamps_present(self, engine):
        result = engine.start_workflow(
            template_code="RIDDOR",
            entity_type="incident",
            entity_id="INC-001",
            initiated_by=1,
        )

        assert result["sla_due_at"] is not None
        assert result["sla_warning_at"] is not None
        sla_due = datetime.fromisoformat(result["sla_due_at"])
        sla_warn = datetime.fromisoformat(result["sla_warning_at"])
        assert sla_due > sla_warn


class TestRouting:
    def test_route_critical_incident(self, engine):
        result = engine.route_entity(
            entity_type="incident",
            entity_id="INC-001",
            entity_data={"severity": "critical"},
        )

        assert result["matched_rule"] == "RR-001"
        assert result["routed_to_role"] == "safety_director"
        assert result["priority"] == "critical"

    def test_route_major_incident(self, engine):
        result = engine.route_entity(
            entity_type="incident",
            entity_id="INC-002",
            entity_data={"severity": "major"},
        )

        assert result["matched_rule"] == "RR-002"
        assert result["routed_to_role"] == "safety_manager"

    def test_route_environmental_incident(self, engine):
        result = engine.route_entity(
            entity_type="incident",
            entity_id="INC-003",
            entity_data={"type": "environmental"},
        )

        assert result["matched_rule"] == "RR-003"
        assert result["routed_to_role"] == "environmental_manager"

    def test_route_complaint_high_severity(self, engine):
        result = engine.route_entity(
            entity_type="complaint",
            entity_id="COMP-001",
            entity_data={"severity": "high"},
        )

        assert result["matched_rule"] == "RR-004"
        assert result["routed_to_role"] == "customer_services_manager"

    def test_route_unknown_entity_type_default(self, engine):
        result = engine.route_entity(
            entity_type="unknown",
            entity_id="UNK-001",
            entity_data={"severity": "low"},
        )

        assert result["matched_rule"] is None
        assert result["routed_to_role"] == "default_handler"
        assert result["priority"] == "normal"

    def test_route_no_matching_condition_default(self, engine):
        result = engine.route_entity(
            entity_type="incident",
            entity_id="INC-004",
            entity_data={"severity": "low"},
        )

        assert result["matched_rule"] is None
        assert result["routed_to_role"] == "default_handler"


class TestMatchesCondition:
    def test_exact_match(self, engine):
        assert engine._matches_condition({"severity": "high"}, {"severity": "high"}) is True

    def test_no_match(self, engine):
        assert engine._matches_condition({"severity": "low"}, {"severity": "high"}) is False

    def test_missing_key(self, engine):
        assert engine._matches_condition({}, {"severity": "high"}) is False

    def test_list_condition_match(self, engine):
        assert (
            engine._matches_condition(
                {"severity": "critical"},
                {"severity": ["critical", "major"]},
            )
            is True
        )

    def test_list_condition_no_match(self, engine):
        assert (
            engine._matches_condition(
                {"severity": "low"},
                {"severity": ["critical", "major"]},
            )
            is False
        )

    def test_multi_key_condition(self, engine):
        assert (
            engine._matches_condition(
                {"severity": "critical", "type": "environmental"},
                {"severity": "critical", "type": "environmental"},
            )
            is True
        )

    def test_multi_key_partial_match_fails(self, engine):
        assert (
            engine._matches_condition(
                {"severity": "critical", "type": "safety"},
                {"severity": "critical", "type": "environmental"},
            )
            is False
        )


# TestApprovalManagement stood here, and its assertions were the fiction stated
# outright: result["status"] == "approved", result["approved_by"] == 5, and
# processed == 3 from a loop that never looked an id up. The methods held no
# state, so nothing was approved and nothing was recorded, and the tests could
# only ever pass. get_pending_approvals was pinned as isinstance(result, list),
# which was true of the [] it returned to every user forever.
#
# Deleted with the methods in FR-APPROVALS-01. Outstanding decisions are now read
# from the domains that hold them (tests/unit/test_approvals_read_model.py,
# tests/integration/test_approvals_my_decisions.py), and each decision is
# recorded by the domain that owns the record.


class TestEscalation:
    def test_check_escalations_returns_empty_without_persistence(self, engine):
        # Honest empty list — in-memory engine does not fabricate SLA breaches.
        escalations = engine.check_escalations()
        assert escalations == []

    def test_escalate(self, engine):
        result = engine.escalate(
            workflow_id="WF-001",
            escalate_to=10,
            reason="SLA breach",
            new_priority="critical",
        )

        assert result["escalated_to"] == 10
        assert result["new_priority"] == "critical"
        assert result["reason"] == "SLA breach"
        assert "escalated_at" in result

    def test_escalate_default_priority(self, engine):
        result = engine.escalate(
            workflow_id="WF-001",
            escalate_to=10,
            reason="Overdue",
        )
        assert result["new_priority"] == "high"


# TestDelegation stood here. set_delegation returned a dict it had just built and
# stored nowhere, so a delegation was forgotten before the response was
# serialised; get_active_delegations was asserted to return len(result) >= 1,
# which held because the method handed every caller the same hardcoded
# "Jane Smith / Annual leave" record. That assertion is why the invented row could
# not be deleted without a test going red.
#
# Deleted with the methods in FR-APPROVALS-01. Delegation is not reimplemented
# anywhere: the read model attributes a decision only to the user its own domain
# names on the record.


class TestRoutingRules:
    def test_get_routing_rules_incident(self, engine):
        rules = engine.get_routing_rules("incident")
        assert len(rules) == 3

    def test_get_routing_rules_complaint(self, engine):
        rules = engine.get_routing_rules("complaint")
        assert len(rules) == 1

    def test_get_routing_rules_unknown(self, engine):
        rules = engine.get_routing_rules("vehicle")
        assert rules == []


# TestWorkflowStats stood here. Its own most recent tests were honest about the
# engine — active_workflows is None, by_template == {} — which is exactly why the
# endpoint above them had nothing left to say: every figure it could not measure
# was null, and the one it could (pending_approvals) counted a queue that was
# always empty.
#
# Deleted with get_workflow_stats in FR-APPROVALS-01 rather than kept as a tile of
# nulls. A count of what genuinely needs the caller's decision now comes from
# GET /api/v1/approvals/my-decisions, which reads three domains and names any it
# could not.


class TestDefaultTemplates:
    def test_all_expected_templates_loaded(self, engine):
        expected = {"RIDDOR", "CAPA", "NCR", "INCIDENT_INVESTIGATION", "DOCUMENT_APPROVAL"}
        assert set(engine.templates.keys()) == expected

    def test_all_templates_have_required_fields(self, engine):
        required = {"code", "name", "description", "category", "trigger_entity_type", "steps"}
        for code, template in engine.templates.items():
            for field in required:
                assert field in template, f"Template {code} missing field {field}"

    def test_all_steps_have_name_and_type(self, engine):
        for code, template in engine.templates.items():
            for i, step in enumerate(template["steps"]):
                assert "name" in step, f"{code} step {i} missing name"
                assert "type" in step, f"{code} step {i} missing type"
                assert step["type"] in ("approval", "task"), f"{code} step {i} has invalid type"
