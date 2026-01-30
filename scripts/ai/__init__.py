"""
AI Standards Automation Engine - Quality Governance Platform
Stage 12: AI-Powered Intelligence (Security Hardened)

SECURITY NOTES:
- No eval() usage - all compliance rules use safe fixed functions
- PII extraction disabled by default - must be explicitly enabled
- All outputs are deterministic and auditable
"""

from .classifier import ClassificationResult, TextClassifier, UrgencyResult
from .compliance import ComplianceChecker, ComplianceCheckResult, ComplianceViolation
from .config import AIEngineConfig, ClassificationConfig, ComplianceConfig, RiskLevel, RiskScoringConfig, get_ai_config
from .engine import GovernanceAIEngine
from .risk_scorer import RiskAssessment, RiskScorer

__version__ = "1.0.0"
__all__ = [
    "AIEngineConfig",
    "ClassificationConfig",
    "ComplianceConfig",
    "RiskScoringConfig",
    "RiskLevel",
    "get_ai_config",
    "ClassificationResult",
    "TextClassifier",
    "UrgencyResult",
    "RiskAssessment",
    "RiskScorer",
    "ComplianceChecker",
    "ComplianceCheckResult",
    "ComplianceViolation",
    "GovernanceAIEngine",
]
