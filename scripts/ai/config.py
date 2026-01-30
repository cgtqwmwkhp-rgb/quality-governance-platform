"""
AI Engine Configuration - Quality Governance Platform
Stage 12: AI Standards Automation (Security Hardened)

Configuration for AI/ML models with security-first defaults.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class RiskLevel(Enum):
    """Risk classification levels."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class ClassificationConfig:
    """Text classification configuration."""

    complaint_categories: Dict[str, List[str]] = field(
        default_factory=lambda: {
            "SERVICE": ["service", "delay", "late", "waiting", "response time"],
            "QUALITY": ["quality", "defect", "broken", "faulty", "poor quality"],
            "SAFETY": ["safety", "danger", "hazard", "injury", "accident"],
            "COMMUNICATION": ["communication", "contact", "phone", "email", "response"],
            "STAFF": ["staff", "employee", "rude", "unprofessional"],
            "BILLING": ["billing", "invoice", "payment", "charge", "refund"],
            "ENVIRONMENTAL": ["environmental", "pollution", "waste", "spill"],
        }
    )

    incident_types: Dict[str, List[str]] = field(
        default_factory=lambda: {
            "SAFETY": ["injury", "accident", "fall", "collision", "fire"],
            "SECURITY": ["theft", "stolen", "break-in", "unauthorized", "breach"],
            "QUALITY": ["defect", "failure", "malfunction", "error", "deviation"],
            "ENVIRONMENTAL": ["spill", "leak", "emission", "pollution", "waste"],
            "NEAR_MISS": ["near miss", "close call", "almost", "nearly", "potential"],
        }
    )

    urgency_indicators: Dict[str, List[str]] = field(
        default_factory=lambda: {
            "URGENT": ["urgent", "immediately", "critical", "emergency", "asap"],
            "HIGH": ["important", "priority", "significant", "major", "severe"],
            "NORMAL": ["request", "inquiry", "question", "general", "routine"],
        }
    )

    min_confidence: float = 0.3

    # SECURITY: PII extraction disabled by default
    extract_pii: bool = False


@dataclass
class RiskScoringConfig:
    """Risk scoring configuration."""

    severity_weights: Dict[str, int] = field(
        default_factory=lambda: {
            "CRITICAL": 40,
            "HIGH": 30,
            "MEDIUM": 20,
            "LOW": 10,
        }
    )

    type_risk_factors: Dict[str, float] = field(
        default_factory=lambda: {
            "SAFETY": 1.5,
            "SECURITY": 1.3,
            "ENVIRONMENTAL": 1.4,
            "QUALITY": 1.0,
            "NEAR_MISS": 0.8,
            "OTHER": 1.0,
        }
    )

    status_factors: Dict[str, float] = field(
        default_factory=lambda: {
            "REPORTED": 1.2,
            "IN_PROGRESS": 1.0,
            "CLOSED": 0.5,
        }
    )


@dataclass
class ComplianceConfig:
    """Compliance checking configuration."""

    # SECURITY: No eval() - rules are defined as fixed functions
    # Rule definitions are for documentation only
    enabled_rules: List[str] = field(
        default_factory=lambda: [
            "INC-001",  # High severity requires root cause
            "INC-002",  # Closed requires corrective actions
            "INC-003",  # Safety requires immediate actions
            "COMP-001",  # Resolved requires resolution notes
            "COMP-002",  # Urgent requires acknowledgment
            "RTA-001",  # Approved requires root cause
            "RTA-002",  # Approved requires corrective actions
        ]
    )


@dataclass
class AIEngineConfig:
    """Master AI engine configuration."""

    classification: ClassificationConfig = field(default_factory=ClassificationConfig)
    risk_scoring: RiskScoringConfig = field(default_factory=RiskScoringConfig)
    compliance: ComplianceConfig = field(default_factory=ComplianceConfig)

    # SECURITY: PII settings
    redact_pii: bool = True
    hash_pii: bool = True


def get_ai_config() -> AIEngineConfig:
    """Get AI engine configuration with security defaults."""
    return AIEngineConfig()
