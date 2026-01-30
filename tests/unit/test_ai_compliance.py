"""
Unit Tests for AI Compliance Checker - Quality Governance Platform
Stage 12: AI Standards Automation
"""

import pytest
from scripts.ai.compliance import (
    ComplianceChecker,
    ComplianceSeverity,
)


class TestIncidentRules:
    """Tests for incident compliance rules."""

    def test_inc_001_high_severity_no_root_cause(self):
        """INC-001: High severity without root cause should fail."""
        checker = ComplianceChecker()
        
        entity = {
            "id": "123",
            "severity": "CRITICAL",
            "root_cause": None,
        }
        
        result = checker.check_incident(entity)
        
        assert not result.is_compliant
        assert any(v.rule_id == "INC-001" for v in result.violations)

    def test_inc_001_high_severity_with_root_cause(self):
        """INC-001: High severity with root cause should pass."""
        checker = ComplianceChecker()
        
        entity = {
            "id": "123",
            "severity": "HIGH",
            "root_cause": "Equipment malfunction",
        }
        
        result = checker.check_incident(entity)
        
        # No INC-001 violation
        assert not any(v.rule_id == "INC-001" for v in result.violations)

    def test_inc_002_closed_no_corrective_actions(self):
        """INC-002: Closed without corrective actions should fail."""
        checker = ComplianceChecker()
        
        entity = {
            "id": "123",
            "status": "CLOSED",
            "corrective_actions": None,
        }
        
        result = checker.check_incident(entity)
        
        assert not result.is_compliant
        assert any(v.rule_id == "INC-002" for v in result.violations)

    def test_inc_003_safety_no_immediate_actions(self):
        """INC-003: Safety without immediate actions should warn."""
        checker = ComplianceChecker()
        
        entity = {
            "id": "123",
            "incident_type": "SAFETY",
            "immediate_actions": None,
        }
        
        result = checker.check_incident(entity)
        
        # Should have warning, but still compliant
        warnings = [v for v in result.violations if v.severity == ComplianceSeverity.WARNING]
        assert any(v.rule_id == "INC-003" for v in warnings)


class TestComplaintRules:
    """Tests for complaint compliance rules."""

    def test_comp_001_resolved_no_resolution(self):
        """COMP-001: Resolved without resolution should fail."""
        checker = ComplianceChecker()
        
        entity = {
            "id": "123",
            "status": "RESOLVED",
            "resolution": None,
        }
        
        result = checker.check_complaint(entity)
        
        assert not result.is_compliant
        assert any(v.rule_id == "COMP-001" for v in result.violations)


class TestRTARules:
    """Tests for RTA compliance rules."""

    def test_rta_001_approved_no_root_cause(self):
        """RTA-001: Approved without root cause should fail."""
        checker = ComplianceChecker()
        
        entity = {
            "id": "123",
            "status": "APPROVED",
            "root_cause": None,
        }
        
        result = checker.check_rta(entity)
        
        assert not result.is_compliant
        assert any(v.rule_id == "RTA-001" for v in result.violations)

    def test_rta_002_approved_no_corrective_actions(self):
        """RTA-002: Approved without corrective actions should fail."""
        checker = ComplianceChecker()
        
        entity = {
            "id": "123",
            "status": "APPROVED",
            "root_cause": "Found the cause",
            "corrective_actions": None,
        }
        
        result = checker.check_rta(entity)
        
        assert not result.is_compliant
        assert any(v.rule_id == "RTA-002" for v in result.violations)

    def test_rta_fully_compliant(self):
        """Fully documented RTA should be compliant."""
        checker = ComplianceChecker()
        
        entity = {
            "id": "123",
            "status": "APPROVED",
            "root_cause": "Root cause identified",
            "corrective_actions": "Actions taken",
        }
        
        result = checker.check_rta(entity)
        
        assert result.is_compliant


class TestRemediationPlan:
    """Tests for remediation plan generation."""

    def test_generates_plan_for_violations(self):
        """Should generate remediation plan for violations."""
        checker = ComplianceChecker()
        
        entity = {
            "id": "123",
            "severity": "CRITICAL",
            "status": "CLOSED",
            "root_cause": None,
            "corrective_actions": None,
        }
        
        result = checker.check_incident(entity)
        plan = checker.get_remediation_plan(result)
        
        assert len(plan) > 0
        assert all("action" in item for item in plan)
        assert all("priority" in item for item in plan)

    def test_plan_ordered_by_severity(self):
        """Remediation plan should order errors first."""
        checker = ComplianceChecker()
        
        entity = {
            "id": "123",
            "severity": "CRITICAL",
            "status": "CLOSED",
            "incident_type": "SAFETY",
            "root_cause": None,
            "corrective_actions": None,
            "immediate_actions": None,
        }
        
        result = checker.check_incident(entity)
        plan = checker.get_remediation_plan(result)
        
        # First items should be errors
        if len(plan) > 1:
            assert plan[0]["severity"] == "error"
