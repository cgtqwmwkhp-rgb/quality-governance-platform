"""Unit tests for Workflow Engine Service - can run standalone."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

import pytest  # noqa: E402


def test_workflow_step_type_enum():
    """Test WorkflowStepType enum has all expected step types."""
    from src.domain.services.workflow_engine import WorkflowStepType

    expected = ["APPROVAL", "TASK", "NOTIFICATION", "CONDITIONAL", "PARALLEL", "AUTOMATIC"]
    for name in expected:
        assert hasattr(WorkflowStepType, name), f"Missing step type: {name}"
        assert WorkflowStepType[name].value == name.lower()
        print(f"✓ {name} = {WorkflowStepType[name].value}")

    print("\n✅ All WorkflowStepType values correct")


def test_workflow_status_enum():
    """Test WorkflowStatus enum has all expected statuses."""
    from src.domain.services.workflow_engine import WorkflowStatus

    expected = {
        "PENDING": "pending",
        "IN_PROGRESS": "in_progress",
        "AWAITING_APPROVAL": "awaiting_approval",
        "APPROVED": "approved",
        "REJECTED": "rejected",
        "COMPLETED": "completed",
        "CANCELLED": "cancelled",
        "ESCALATED": "escalated",
        "FAILED": "failed",
    }

    for name, value in expected.items():
        assert hasattr(WorkflowStatus, name), f"Missing status: {name}"
        assert WorkflowStatus[name].value == value
        print(f"✓ {name} = {value}")

    print("\n✅ All WorkflowStatus values correct")


def test_default_templates_structure():
    """Test DEFAULT_TEMPLATES contains required workflow templates with correct structure."""
    from src.domain.services.workflow_engine import DEFAULT_TEMPLATES

    expected_codes = {"RIDDOR", "CAPA", "NCR", "INCIDENT_INVESTIGATION", "DOCUMENT_APPROVAL"}
    actual_codes = {t["code"] for t in DEFAULT_TEMPLATES}
    assert expected_codes == actual_codes, f"Template codes mismatch: {actual_codes}"
    print(f"✓ All {len(expected_codes)} template codes present")

    required_fields = {"code", "name", "description", "category", "trigger_entity_type", "steps"}
    for tpl in DEFAULT_TEMPLATES:
        missing = required_fields - set(tpl.keys())
        assert not missing, f"Template {tpl['code']} missing fields: {missing}"
        assert len(tpl["steps"]) > 0, f"Template {tpl['code']} has no steps"
        print(f"✓ {tpl['code']}: {len(tpl['steps'])} steps, category={tpl['category']}")

    print("\n✅ DEFAULT_TEMPLATES structure is valid")


def test_default_templates_sla_configuration():
    """Test that SLA-sensitive templates have sla_hours and warning_hours."""
    from src.domain.services.workflow_engine import DEFAULT_TEMPLATES

    for tpl in DEFAULT_TEMPLATES:
        assert "sla_hours" in tpl, f"Template {tpl['code']} missing sla_hours"
        assert "warning_hours" in tpl, f"Template {tpl['code']} missing warning_hours"
        assert tpl["warning_hours"] < tpl["sla_hours"], (
            f"Template {tpl['code']}: warning_hours ({tpl['warning_hours']}) "
            f"should be less than sla_hours ({tpl['sla_hours']})"
        )
        print(f"✓ {tpl['code']}: SLA={tpl['sla_hours']}h, warning={tpl['warning_hours']}h")

    riddor = next(t for t in DEFAULT_TEMPLATES if t["code"] == "RIDDOR")
    assert riddor["sla_hours"] == 24, "RIDDOR SLA should be 24 hours"
    print("✓ RIDDOR SLA is 24 hours (regulatory requirement)")

    print("\n✅ All SLA configurations valid")


def test_condition_evaluator_basic_operators():
    """Test ConditionEvaluator with basic comparison operators."""
    from src.domain.services.workflow_engine import ConditionEvaluator

    entity = {"severity": "critical", "count": 10, "name": "Test Incident"}

    assert ConditionEvaluator.evaluate({"field": "severity", "operator": "equals", "value": "critical"}, entity) is True
    print("✓ equals operator works")

    assert ConditionEvaluator.evaluate({"field": "severity", "operator": "not_equals", "value": "low"}, entity) is True
    print("✓ not_equals operator works")

    assert ConditionEvaluator.evaluate({"field": "count", "operator": "greater_than", "value": 5}, entity) is True
    print("✓ greater_than operator works")

    assert ConditionEvaluator.evaluate({"field": "count", "operator": "less_than", "value": 5}, entity) is False
    print("✓ less_than operator works (correctly returns False)")

    assert ConditionEvaluator.evaluate({"field": "count", "operator": "greater_or_equal", "value": 10}, entity) is True
    print("✓ greater_or_equal operator works")

    assert ConditionEvaluator.evaluate({"field": "count", "operator": "less_or_equal", "value": 10}, entity) is True
    print("✓ less_or_equal operator works")

    print("\n✅ All basic operators work correctly")


def test_condition_evaluator_string_and_collection_operators():
    """Test ConditionEvaluator string and collection operators."""
    from src.domain.services.workflow_engine import ConditionEvaluator

    entity = {"name": "Critical Safety Issue", "tags": "safety,urgent", "empty_field": ""}

    assert ConditionEvaluator.evaluate({"field": "name", "operator": "contains", "value": "Safety"}, entity) is True
    print("✓ contains operator works")

    assert (
        ConditionEvaluator.evaluate({"field": "name", "operator": "not_contains", "value": "Quality"}, entity) is True
    )
    print("✓ not_contains operator works")

    assert (
        ConditionEvaluator.evaluate({"field": "name", "operator": "starts_with", "value": "Critical"}, entity) is True
    )
    print("✓ starts_with operator works")

    assert ConditionEvaluator.evaluate({"field": "name", "operator": "ends_with", "value": "Issue"}, entity) is True
    print("✓ ends_with operator works")

    assert ConditionEvaluator.evaluate({"field": "empty_field", "operator": "is_empty", "value": None}, entity) is True
    print("✓ is_empty operator works")

    assert ConditionEvaluator.evaluate({"field": "name", "operator": "is_not_empty", "value": None}, entity) is True
    print("✓ is_not_empty operator works")

    assert ConditionEvaluator.evaluate({"field": "missing_field", "operator": "is_null", "value": None}, entity) is True
    print("✓ is_null operator works")

    assert ConditionEvaluator.evaluate({"field": "name", "operator": "is_not_null", "value": None}, entity) is True
    print("✓ is_not_null operator works")

    print("\n✅ All string/collection operators work correctly")


def test_condition_evaluator_logical_combinators():
    """Test ConditionEvaluator AND/OR/NOT logical combinators."""
    from src.domain.services.workflow_engine import ConditionEvaluator

    entity = {"severity": "high", "priority": "urgent", "count": 5}

    and_cond = {
        "and": [
            {"field": "severity", "operator": "equals", "value": "high"},
            {"field": "priority", "operator": "equals", "value": "urgent"},
        ]
    }
    assert ConditionEvaluator.evaluate(and_cond, entity) is True
    print("✓ AND combinator (both true) works")

    and_cond_fail = {
        "and": [
            {"field": "severity", "operator": "equals", "value": "high"},
            {"field": "priority", "operator": "equals", "value": "low"},
        ]
    }
    assert ConditionEvaluator.evaluate(and_cond_fail, entity) is False
    print("✓ AND combinator (one false) correctly returns False")

    or_cond = {
        "or": [
            {"field": "severity", "operator": "equals", "value": "low"},
            {"field": "priority", "operator": "equals", "value": "urgent"},
        ]
    }
    assert ConditionEvaluator.evaluate(or_cond, entity) is True
    print("✓ OR combinator works")

    not_cond = {"not": {"field": "severity", "operator": "equals", "value": "low"}}
    assert ConditionEvaluator.evaluate(not_cond, entity) is True
    print("✓ NOT combinator works")

    assert ConditionEvaluator.evaluate(None, entity) is True
    print("✓ Empty/None conditions return True (match-all)")

    assert ConditionEvaluator.evaluate({}, entity) is True
    print("✓ Empty dict conditions return True")

    print("\n✅ All logical combinators work correctly")


def test_condition_evaluator_nested_value_access():
    """Test ConditionEvaluator handles nested (dot-notation) field access."""
    from src.domain.services.workflow_engine import ConditionEvaluator

    entity = {
        "incident": {
            "details": {
                "severity": "critical",
                "location": "Site A",
            },
            "reporter": "John",
        },
        "top_level": "value",
    }

    assert (
        ConditionEvaluator.evaluate(
            {"field": "incident.details.severity", "operator": "equals", "value": "critical"},
            entity,
        )
        is True
    )
    print("✓ Deep nested field access works (3 levels)")

    assert (
        ConditionEvaluator.evaluate(
            {"field": "incident.reporter", "operator": "equals", "value": "John"},
            entity,
        )
        is True
    )
    print("✓ Two-level nested access works")

    assert (
        ConditionEvaluator.evaluate(
            {"field": "incident.nonexistent.field", "operator": "is_null", "value": None},
            entity,
        )
        is True
    )
    print("✓ Missing nested path returns None (is_null)")

    assert (
        ConditionEvaluator.evaluate(
            {"field": "top_level", "operator": "equals", "value": "value"},
            entity,
        )
        is True
    )
    print("✓ Top-level field still works")

    print("\n✅ Nested value access works correctly")


@pytest.mark.asyncio
async def test_workflow_service_in_memory_initialization():
    """Test WorkflowService initializes with default workflow definitions."""
    from src.domain.services.workflow_engine import WorkflowService, WorkflowStatus

    service = WorkflowService()

    defs = await service.get_workflow_definitions()
    assert len(defs) == 3, f"Expected 3 default workflows, got {len(defs)}"
    print(f"✓ {len(defs)} default workflow definitions loaded")

    def_ids = {d.id for d in defs}
    assert "WF-INCIDENT-001" in def_ids
    assert "WF-RISK-001" in def_ids
    assert "WF-DOC-001" in def_ids
    print("✓ All expected definition IDs present")

    incident_defs = await service.get_workflow_definitions(module="incidents")
    assert len(incident_defs) == 1
    assert incident_defs[0].id == "WF-INCIDENT-001"
    print("✓ Module filtering works")

    stats = await service.get_workflow_stats()
    assert stats["total_workflows"] == 0
    assert stats["active"] == 0
    assert stats["completed"] == 0
    assert stats["pending_approvals"] == 0
    print("✓ Initial stats are all zero")

    print("\n✅ WorkflowService initialization correct")


@pytest.mark.asyncio
async def test_workflow_service_evaluate_conditions():
    """Test WorkflowService._evaluate_conditions with various inputs."""
    from src.domain.services.workflow_engine import WorkflowService

    service = WorkflowService()

    assert service._evaluate_conditions({"severity": ["high", "critical"]}, {"severity": "critical"}) is True
    print("✓ List condition match works")

    assert service._evaluate_conditions({"severity": ["high", "critical"]}, {"severity": "low"}) is False
    print("✓ List condition non-match works")

    assert service._evaluate_conditions({"severity": "high"}, {"severity": "high"}) is True
    print("✓ Scalar condition match works")

    assert service._evaluate_conditions({"severity": "high"}, {"severity": "low"}) is False
    print("✓ Scalar condition non-match works")

    assert (
        service._evaluate_conditions(
            {"severity": "high", "priority": "urgent"},
            {"severity": "high", "priority": "urgent"},
        )
        is True
    )
    print("✓ Multiple conditions (all match) works")

    assert (
        service._evaluate_conditions(
            {"severity": "high", "priority": "urgent"},
            {"severity": "high", "priority": "normal"},
        )
        is False
    )
    print("✓ Multiple conditions (partial match) correctly returns False")

    print("\n✅ Condition evaluation works correctly")


if __name__ == "__main__":
    import asyncio

    print("=" * 60)
    print("WORKFLOW ENGINE SERVICE TESTS")
    print("=" * 60)
    print()

    test_workflow_step_type_enum()
    print()
    test_workflow_status_enum()
    print()
    test_default_templates_structure()
    print()
    test_default_templates_sla_configuration()
    print()
    test_condition_evaluator_basic_operators()
    print()
    test_condition_evaluator_string_and_collection_operators()
    print()
    test_condition_evaluator_logical_combinators()
    print()
    test_condition_evaluator_nested_value_access()
    print()
    asyncio.run(test_workflow_service_in_memory_initialization())
    print()
    asyncio.run(test_workflow_service_evaluate_conditions())

    print()
    print("=" * 60)
    print("ALL WORKFLOW ENGINE TESTS PASSED ✅")
    print("=" * 60)
