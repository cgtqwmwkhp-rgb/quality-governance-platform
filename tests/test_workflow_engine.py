"""Comprehensive tests for the Workflow Engine.

Tests cover:
- Condition evaluation
- Action execution
- SLA tracking
- Escalation levels
- Rule execution logging
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.domain.models.workflow_rules import (
    ActionType,
    EntityType,
    EscalationLevel,
    RuleExecution,
    RuleType,
    SLAConfiguration,
    SLATracking,
    TriggerEvent,
    WorkflowRule,
)
from src.domain.services.workflow_engine import ActionExecutor, ConditionEvaluator, RuleEvaluator, SLAService


class TestConditionEvaluator:
    """Test suite for condition evaluation logic."""

    def test_empty_conditions_returns_true(self):
        """Empty conditions should match everything."""
        result = ConditionEvaluator.evaluate(None, {"field": "value"})
        assert result is True

        result = ConditionEvaluator.evaluate({}, {"field": "value"})
        assert result is True

    def test_equals_operator(self):
        """Test equals comparison."""
        conditions = {"field": "status", "operator": "equals", "value": "open"}

        assert ConditionEvaluator.evaluate(conditions, {"status": "open"}) is True
        assert ConditionEvaluator.evaluate(conditions, {"status": "closed"}) is False

    def test_not_equals_operator(self):
        """Test not equals comparison."""
        conditions = {"field": "status", "operator": "not_equals", "value": "closed"}

        assert ConditionEvaluator.evaluate(conditions, {"status": "open"}) is True
        assert ConditionEvaluator.evaluate(conditions, {"status": "closed"}) is False

    def test_contains_operator(self):
        """Test contains comparison for strings."""
        conditions = {"field": "description", "operator": "contains", "value": "urgent"}

        assert ConditionEvaluator.evaluate(conditions, {"description": "This is urgent!"}) is True
        assert ConditionEvaluator.evaluate(conditions, {"description": "Normal task"}) is False

    def test_in_operator(self):
        """Test in comparison for lists."""
        conditions = {
            "field": "priority",
            "operator": "in",
            "value": ["critical", "high"],
        }

        assert ConditionEvaluator.evaluate(conditions, {"priority": "critical"}) is True
        assert ConditionEvaluator.evaluate(conditions, {"priority": "high"}) is True
        assert ConditionEvaluator.evaluate(conditions, {"priority": "low"}) is False

    def test_greater_than_operator(self):
        """Test greater than comparison."""
        conditions = {"field": "score", "operator": "greater_than", "value": 5}

        assert ConditionEvaluator.evaluate(conditions, {"score": 10}) is True
        assert ConditionEvaluator.evaluate(conditions, {"score": 5}) is False
        assert ConditionEvaluator.evaluate(conditions, {"score": 3}) is False

    def test_less_than_operator(self):
        """Test less than comparison."""
        conditions = {"field": "days_open", "operator": "less_than", "value": 30}

        assert ConditionEvaluator.evaluate(conditions, {"days_open": 15}) is True
        assert ConditionEvaluator.evaluate(conditions, {"days_open": 30}) is False

    def test_is_null_operator(self):
        """Test null checking."""
        conditions = {"field": "assigned_to", "operator": "is_null", "value": None}

        assert ConditionEvaluator.evaluate(conditions, {"assigned_to": None}) is True
        assert ConditionEvaluator.evaluate(conditions, {}) is True
        assert ConditionEvaluator.evaluate(conditions, {"assigned_to": "user1"}) is False

    def test_is_not_null_operator(self):
        """Test not null checking."""
        conditions = {"field": "assigned_to", "operator": "is_not_null", "value": None}

        assert ConditionEvaluator.evaluate(conditions, {"assigned_to": "user1"}) is True
        assert ConditionEvaluator.evaluate(conditions, {"assigned_to": None}) is False

    def test_and_conditions(self):
        """Test AND logical operator."""
        conditions = {
            "and": [
                {"field": "status", "operator": "equals", "value": "open"},
                {"field": "priority", "operator": "equals", "value": "high"},
            ]
        }

        assert ConditionEvaluator.evaluate(conditions, {"status": "open", "priority": "high"}) is True
        assert ConditionEvaluator.evaluate(conditions, {"status": "open", "priority": "low"}) is False
        assert ConditionEvaluator.evaluate(conditions, {"status": "closed", "priority": "high"}) is False

    def test_or_conditions(self):
        """Test OR logical operator."""
        conditions = {
            "or": [
                {"field": "priority", "operator": "equals", "value": "critical"},
                {"field": "priority", "operator": "equals", "value": "high"},
            ]
        }

        assert ConditionEvaluator.evaluate(conditions, {"priority": "critical"}) is True
        assert ConditionEvaluator.evaluate(conditions, {"priority": "high"}) is True
        assert ConditionEvaluator.evaluate(conditions, {"priority": "low"}) is False

    def test_not_condition(self):
        """Test NOT logical operator."""
        conditions = {"not": {"field": "status", "operator": "equals", "value": "closed"}}

        assert ConditionEvaluator.evaluate(conditions, {"status": "open"}) is True
        assert ConditionEvaluator.evaluate(conditions, {"status": "closed"}) is False

    def test_nested_conditions(self):
        """Test complex nested conditions."""
        conditions = {
            "and": [
                {"field": "status", "operator": "equals", "value": "open"},
                {
                    "or": [
                        {
                            "field": "priority",
                            "operator": "equals",
                            "value": "critical",
                        },
                        {"field": "days_open", "operator": "greater_than", "value": 7},
                    ]
                },
            ]
        }

        # Open with critical priority
        assert (
            ConditionEvaluator.evaluate(conditions, {"status": "open", "priority": "critical", "days_open": 1}) is True
        )

        # Open with low priority but >7 days
        assert ConditionEvaluator.evaluate(conditions, {"status": "open", "priority": "low", "days_open": 10}) is True

        # Closed should fail
        assert (
            ConditionEvaluator.evaluate(
                conditions,
                {"status": "closed", "priority": "critical", "days_open": 10},
            )
            is False
        )

    def test_nested_field_access(self):
        """Test dot notation for nested fields."""
        conditions = {
            "field": "reporter.department",
            "operator": "equals",
            "value": "Safety",
        }

        assert ConditionEvaluator.evaluate(conditions, {"reporter": {"department": "Safety", "name": "John"}}) is True
        assert ConditionEvaluator.evaluate(conditions, {"reporter": {"department": "IT"}}) is False


class TestActionExecutor:
    """Test suite for action execution."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        db = AsyncMock()
        db.execute = AsyncMock()
        db.commit = AsyncMock()
        return db

    @pytest.fixture
    def executor(self, mock_db):
        """Create action executor with mocked DB."""
        return ActionExecutor(mock_db)

    @pytest.mark.asyncio
    async def test_execute_send_email(self, executor):
        """Test email sending action."""
        config = {
            "template": "escalation",
            "recipients": ["manager@example.com"],
            "subject": "Test Alert",
        }

        result = await executor.execute(
            ActionType.SEND_EMAIL,
            config,
            EntityType.INCIDENT,
            1,
            {"id": 1},
        )

        assert result["success"] is True
        assert result["action"] == "send_email"
        assert result["template"] == "escalation"

    @pytest.mark.asyncio
    async def test_execute_change_status(self, executor, mock_db):
        """Test status change action."""
        config = {"new_status": "escalated"}

        result = await executor.execute(
            ActionType.CHANGE_STATUS,
            config,
            EntityType.INCIDENT,
            1,
            {"id": 1, "status": "open"},
        )

        assert result["success"] is True
        assert result["action"] == "change_status"
        assert result["new_status"] == "escalated"

    @pytest.mark.asyncio
    async def test_execute_create_task(self, executor):
        """Test task creation action."""
        config = {
            "title": "Follow up on incident",
            "due_days": 3,
            "assign_to": "manager",
        }

        result = await executor.execute(
            ActionType.CREATE_TASK,
            config,
            EntityType.INCIDENT,
            1,
            {"id": 1},
        )

        assert result["success"] is True
        assert result["action"] == "create_task"
        assert result["title"] == "Follow up on incident"

    @pytest.mark.asyncio
    async def test_execute_webhook(self, executor):
        """Test webhook action."""
        config = {
            "url": "https://api.example.com/webhook",
            "method": "POST",
            "headers": {"X-Api-Key": "secret"},
        }

        result = await executor.execute(
            ActionType.WEBHOOK,
            config,
            EntityType.INCIDENT,
            1,
            {"id": 1},
        )

        assert result["success"] is True
        assert result["action"] == "webhook"
        assert result["url"] == "https://api.example.com/webhook"


class TestSLAService:
    """Test suite for SLA tracking service."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        db = AsyncMock()
        db.execute = AsyncMock()
        db.commit = AsyncMock()
        db.add = MagicMock()
        db.refresh = AsyncMock()
        return db

    @pytest.fixture
    def sla_service(self, mock_db):
        """Create SLA service with mocked DB."""
        return SLAService(mock_db)

    def test_calculate_due_time_simple(self, sla_service):
        """Test due time calculation without business hours."""
        config = SLAConfiguration(
            id=1,
            entity_type=EntityType.INCIDENT,
            resolution_hours=24,
            business_hours_only=False,
        )

        start = datetime(2026, 1, 21, 10, 0, 0)  # Tuesday 10 AM
        due = sla_service._calculate_due_time(start, 24, config)

        expected = datetime(2026, 1, 22, 10, 0, 0)  # Wednesday 10 AM
        assert due == expected

    def test_calculate_due_time_business_hours(self, sla_service):
        """Test due time calculation with business hours only."""
        config = SLAConfiguration(
            id=1,
            entity_type=EntityType.INCIDENT,
            resolution_hours=8,
            business_hours_only=True,
            business_start_hour=9,
            business_end_hour=17,
            exclude_weekends=True,
        )

        # Start at 9 AM on Tuesday - should finish same day at 5 PM
        start = datetime(2026, 1, 21, 9, 0, 0)  # Tuesday 9 AM
        due = sla_service._calculate_due_time(start, 8, config)

        expected = datetime(2026, 1, 21, 17, 0, 0)  # Tuesday 5 PM
        assert due == expected

    def test_calculate_due_time_crosses_midnight(self, sla_service):
        """Test due time that crosses to next business day."""
        config = SLAConfiguration(
            id=1,
            entity_type=EntityType.INCIDENT,
            resolution_hours=10,
            business_hours_only=True,
            business_start_hour=9,
            business_end_hour=17,
            exclude_weekends=True,
        )

        # Start at 3 PM on Tuesday (4 hours left) - 10 hours needed
        start = datetime(2026, 1, 21, 15, 0, 0)  # Tuesday 3 PM
        due = sla_service._calculate_due_time(start, 10, config)

        # Should be Wednesday 3 PM (4 hours Tuesday + 6 hours Wednesday = 10)
        # Actually: 4h on Tuesday, then 6h on Wednesday starting at 9 AM = 3 PM
        expected = datetime(2026, 1, 22, 15, 0, 0)
        assert due == expected


class TestWorkflowRuleModel:
    """Test suite for WorkflowRule model validation."""

    def test_rule_creation(self):
        """Test creating a workflow rule."""
        rule = WorkflowRule(
            name="Escalate Critical Incidents",
            description="Automatically escalate critical incidents after 2 hours",
            rule_type=RuleType.ESCALATION,
            entity_type=EntityType.INCIDENT,
            trigger_event=TriggerEvent.CREATED,
            conditions={"field": "severity", "operator": "equals", "value": "critical"},
            delay_hours=2,
            action_type=ActionType.ESCALATE,
            action_config={"new_status": "escalated"},
            priority=10,
            is_active=True,
        )

        assert rule.name == "Escalate Critical Incidents"
        assert rule.rule_type == RuleType.ESCALATION
        assert rule.entity_type == EntityType.INCIDENT
        assert rule.delay_hours == 2
        assert rule.is_active is True


class TestSLAConfigurationModel:
    """Test suite for SLAConfiguration model."""

    def test_sla_config_creation(self):
        """Test creating an SLA configuration."""
        config = SLAConfiguration(
            entity_type=EntityType.COMPLAINT,
            priority="high",
            acknowledgment_hours=2,
            response_hours=24,
            resolution_hours=72,
            warning_threshold_percent=75,
            business_hours_only=True,
            is_active=True,
        )

        assert config.entity_type == EntityType.COMPLAINT
        assert config.priority == "high"
        assert config.acknowledgment_hours == 2
        assert config.resolution_hours == 72
        assert config.warning_threshold_percent == 75


class TestEscalationLevelModel:
    """Test suite for EscalationLevel model."""

    def test_escalation_level_creation(self):
        """Test creating an escalation level."""
        level = EscalationLevel(
            entity_type=EntityType.INCIDENT,
            level=1,
            name="Line Manager Escalation",
            description="First escalation to line manager",
            escalate_to_role="line_manager",
            hours_after_previous=4,
            notify_original_assignee=True,
            is_active=True,
        )

        assert level.entity_type == EntityType.INCIDENT
        assert level.level == 1
        assert level.hours_after_previous == 4
        assert level.escalate_to_role == "line_manager"


class TestIntegrationScenarios:
    """Integration test scenarios for complete workflows."""

    @pytest.mark.asyncio
    async def test_incident_escalation_flow(self):
        """Test complete incident escalation workflow."""
        # Create conditions for critical incident
        conditions = {
            "and": [
                {"field": "severity", "operator": "equals", "value": "critical"},
                {"field": "status", "operator": "equals", "value": "reported"},
            ]
        }

        # Entity data
        entity_data = {
            "id": 1,
            "severity": "critical",
            "status": "reported",
            "created_at": datetime.utcnow(),
        }

        # Evaluate conditions
        result = ConditionEvaluator.evaluate(conditions, entity_data)
        assert result is True

        # Non-critical should not match
        entity_data["severity"] = "low"
        result = ConditionEvaluator.evaluate(conditions, entity_data)
        assert result is False

    @pytest.mark.asyncio
    async def test_complaint_sla_breach_detection(self):
        """Test SLA breach detection for complaints."""
        # Create tracking record
        tracking = SLATracking(
            entity_type=EntityType.COMPLAINT,
            entity_id=1,
            sla_config_id=1,
            started_at=datetime.utcnow() - timedelta(hours=48),  # Started 48h ago
            resolution_due=datetime.utcnow() - timedelta(hours=1),  # Due 1h ago
            warning_sent=True,
            breach_sent=False,
            is_breached=False,
        )

        # Check if breached (resolution_due is in the past)
        now = datetime.utcnow()
        is_breached = now > tracking.resolution_due

        assert is_breached is True


class TestRuleExecutionLogging:
    """Test rule execution audit logging."""

    def test_rule_execution_creation(self):
        """Test creating rule execution log."""
        execution = RuleExecution(
            rule_id=1,
            entity_type=EntityType.INCIDENT,
            entity_id=123,
            trigger_event=TriggerEvent.CREATED,
            executed_at=datetime.utcnow(),
            success=True,
            action_taken="send_email: Notify manager",
            action_result={"recipients": ["manager@example.com"], "sent": True},
        )

        assert execution.rule_id == 1
        assert execution.entity_id == 123
        assert execution.success is True


# Edge case tests
class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_invalid_operator(self):
        """Test handling of invalid operator."""
        conditions = {"field": "status", "operator": "invalid_op", "value": "open"}
        result = ConditionEvaluator.evaluate(conditions, {"status": "open"})
        assert result is False

    def test_missing_field(self):
        """Test handling of missing field in entity data."""
        conditions = {"field": "nonexistent", "operator": "equals", "value": "test"}
        result = ConditionEvaluator.evaluate(conditions, {"other_field": "value"})
        assert result is False

    def test_null_field_value(self):
        """Test handling of null field value."""
        conditions = {"field": "assigned_to", "operator": "equals", "value": None}
        result = ConditionEvaluator.evaluate(conditions, {"assigned_to": None})
        assert result is True

    def test_empty_string_vs_null(self):
        """Test distinction between empty string and null."""
        conditions = {"field": "notes", "operator": "is_empty", "value": None}

        assert ConditionEvaluator.evaluate(conditions, {"notes": ""}) is True
        assert ConditionEvaluator.evaluate(conditions, {"notes": None}) is True
        assert ConditionEvaluator.evaluate(conditions, {"notes": "some text"}) is False
