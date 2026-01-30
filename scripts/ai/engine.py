"""
Governance AI Engine - Quality Governance Platform
Stage 12: AI Standards Automation (Security Hardened)

Unified interface for all AI capabilities.
"""

from typing import Any, Dict, Optional

from .classifier import TextClassifier
from .compliance import ComplianceChecker
from .config import AIEngineConfig, get_ai_config
from .risk_scorer import RiskScorer


class GovernanceAIEngine:
    """
    Unified AI engine for governance automation.

    Combines:
    - Text classification
    - Risk scoring
    - Compliance checking
    """

    def __init__(self, config: Optional[AIEngineConfig] = None):
        self.config = config or get_ai_config()
        self.classifier = TextClassifier(self.config.classification)
        self.risk_scorer = RiskScorer(self.config.risk_scoring)
        self.compliance_checker = ComplianceChecker()

    def analyze_incident(self, incident: Dict[str, Any]) -> Dict[str, Any]:
        """Comprehensive incident analysis."""
        title = incident.get("title", "")
        description = incident.get("description", "")

        classification = self.classifier.classify_incident(description, title)
        urgency = self.classifier.detect_urgency(description, title)
        risk = self.risk_scorer.assess(incident, "incident")
        compliance = self.compliance_checker.check_incident(incident)

        return {
            "entity_id": incident.get("id"),
            "entity_type": "incident",
            "classification": classification.to_dict(),
            "urgency": urgency.to_dict(),
            "risk": risk.to_dict(),
            "compliance": compliance.to_dict(),
            "summary": {
                "predicted_type": classification.category,
                "risk_level": risk.risk_level.value,
                "risk_score": round(risk.total_score, 1),
                "is_compliant": compliance.is_compliant,
                "priority": urgency.priority,
            },
        }

    def analyze_complaint(self, complaint: Dict[str, Any]) -> Dict[str, Any]:
        """Comprehensive complaint analysis."""
        title = complaint.get("title", "")
        description = complaint.get("description", "")

        classification = self.classifier.classify_complaint(description, title)
        urgency = self.classifier.detect_urgency(description, title)
        compliance = self.compliance_checker.check_complaint(complaint)

        return {
            "entity_id": complaint.get("id"),
            "entity_type": "complaint",
            "classification": classification.to_dict(),
            "urgency": urgency.to_dict(),
            "compliance": compliance.to_dict(),
            "summary": {
                "predicted_category": classification.category,
                "priority": urgency.priority,
                "is_compliant": compliance.is_compliant,
            },
        }

    def analyze_rta(self, rta: Dict[str, Any]) -> Dict[str, Any]:
        """RTA analysis."""
        compliance = self.compliance_checker.check_rta(rta)
        remediation = self.compliance_checker.get_remediation_plan(compliance)

        return {
            "entity_id": rta.get("id"),
            "entity_type": "rta",
            "compliance": compliance.to_dict(),
            "remediation_plan": remediation,
            "summary": {
                "is_compliant": compliance.is_compliant,
                "compliance_score": round(compliance.compliance_score, 1),
            },
        }
