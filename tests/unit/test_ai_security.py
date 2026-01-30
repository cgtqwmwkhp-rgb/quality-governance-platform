"""
Security Tests for AI Engine - Quality Governance Platform
Stage 12: AI Standards Automation

CRITICAL: These tests prove:
1. No eval() usage in compliance module
2. No PII in default outputs
3. Deterministic scoring
"""

import ast
import os
from pathlib import Path

import pytest


class TestNoEvalUsage:
    """Prove that eval() is not used in AI modules."""

    def get_ai_module_files(self) -> list:
        """Get all Python files in scripts/ai/."""
        ai_dir = Path(__file__).parent.parent.parent / "scripts" / "ai"
        return list(ai_dir.glob("*.py"))

    def test_no_eval_in_compliance(self):
        """CRITICAL: compliance.py must not use eval()."""
        compliance_path = Path(__file__).parent.parent.parent / "scripts" / "ai" / "compliance.py"

        with open(compliance_path, "r") as f:
            content = f.read()

        # Check for eval function calls
        tree = ast.parse(content)

        eval_calls = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id == "eval":
                    eval_calls.append(node.lineno)

        assert len(eval_calls) == 0, f"eval() found on lines: {eval_calls}"

    def test_no_eval_in_any_ai_module(self):
        """CRITICAL: No AI module should use eval()."""
        for file_path in self.get_ai_module_files():
            with open(file_path, "r") as f:
                content = f.read()

            tree = ast.parse(content)

            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name) and node.func.id == "eval":
                        pytest.fail(f"eval() found in {file_path.name} on line {node.lineno}")

    def test_no_exec_in_ai_modules(self):
        """No AI module should use exec()."""
        for file_path in self.get_ai_module_files():
            with open(file_path, "r") as f:
                content = f.read()

            tree = ast.parse(content)

            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name) and node.func.id == "exec":
                        pytest.fail(f"exec() found in {file_path.name} on line {node.lineno}")


class TestNoPIIInOutputs:
    """Prove that PII is not extracted by default."""

    def test_pii_extraction_disabled_by_default(self):
        """PII extraction should be disabled by default."""
        from scripts.ai.config import ClassificationConfig

        config = ClassificationConfig()
        assert config.extract_pii is False, "extract_pii must be False by default"

    def test_classifier_returns_no_pii_by_default(self):
        """Classifier should not return emails/phones by default."""
        from scripts.ai.classifier import TextClassifier

        classifier = TextClassifier()

        # Text with PII
        text = "Contact john.doe@example.com or call 07123456789"

        result = classifier.extract_entities_safe(text)

        # Should have pii_redacted flag
        assert result.get("pii_redacted") is True

        # Should NOT have emails or phones keys
        assert "emails" not in result
        assert "phones" not in result

    def test_compliance_output_no_pii(self):
        """Compliance results should not contain PII."""
        from scripts.ai.compliance import ComplianceChecker

        checker = ComplianceChecker()

        # Entity with PII in fields
        entity = {
            "id": "123",
            "status": "CLOSED",
            "corrective_actions": None,
            "complainant_email": "test@example.com",  # PII
            "complainant_phone": "07123456789",  # PII
        }

        result = checker.check_incident(entity)
        result_dict = result.to_dict()

        # Serialize to string and check for PII
        import json

        result_str = json.dumps(result_dict)

        assert "test@example.com" not in result_str
        assert "07123456789" not in result_str


class TestDeterministicScoring:
    """Prove that scoring is deterministic."""

    def test_risk_score_deterministic(self):
        """Same input should produce same risk score."""
        from scripts.ai.risk_scorer import RiskScorer

        scorer = RiskScorer()

        entity = {
            "id": "123",
            "severity": "HIGH",
            "incident_type": "SAFETY",
            "status": "REPORTED",
            "incident_date": "2026-01-15",
        }

        # Run multiple times
        scores = [scorer.assess(entity).total_score for _ in range(10)]

        # All scores should be identical
        assert len(set(scores)) == 1, "Risk scores should be deterministic"

    def test_classification_deterministic(self):
        """Same text should produce same classification."""
        from scripts.ai.classifier import TextClassifier

        classifier = TextClassifier()

        text = "There was a safety incident involving equipment"

        # Run multiple times
        results = [classifier.classify_incident(text).category for _ in range(10)]

        # All results should be identical
        assert len(set(results)) == 1, "Classification should be deterministic"

    def test_compliance_check_deterministic(self):
        """Same entity should produce same compliance result."""
        from scripts.ai.compliance import ComplianceChecker

        checker = ComplianceChecker()

        entity = {
            "id": "123",
            "severity": "CRITICAL",
            "status": "CLOSED",
            "root_cause": None,
            "corrective_actions": None,
        }

        # Run multiple times
        results = [checker.check_incident(entity).is_compliant for _ in range(10)]

        # All results should be identical
        assert len(set(results)) == 1, "Compliance check should be deterministic"


class TestComplianceRulesAsFixedFunctions:
    """Verify compliance rules are fixed functions, not dynamic evaluation."""

    def test_rules_are_callable(self):
        """All rules should be callable functions."""
        from scripts.ai.compliance import COMPLAINT_RULES, INCIDENT_RULES, RTA_RULES

        for rule in INCIDENT_RULES + COMPLAINT_RULES + RTA_RULES:
            assert callable(rule), f"Rule {rule} is not callable"

    def test_rule_function_names(self):
        """Rules should have proper function names."""
        from scripts.ai.compliance import INCIDENT_RULES

        for rule in INCIDENT_RULES:
            assert rule.__name__.startswith("_rule_"), f"Rule {rule.__name__} should start with '_rule_'"

    def test_compliance_checker_uses_registry(self):
        """ComplianceChecker should use rule registry, not eval."""
        import inspect

        from scripts.ai.compliance import ComplianceChecker

        source = inspect.getsource(ComplianceChecker.check)

        assert "eval" not in source, "check() method should not use eval"
        assert "exec" not in source, "check() method should not use exec"
