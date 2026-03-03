"""
Risk Scoring Engine - Quality Governance Platform
Stage 12: AI Standards Automation (Security Hardened)

Deterministic, auditable risk scoring without external dependencies.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from .config import RiskLevel, RiskScoringConfig, get_ai_config


@dataclass
class RiskFactor:
    """Individual risk factor."""

    name: str
    score: float
    weight: float
    contribution: float
    description: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "score": round(self.score, 1),
            "weight": round(self.weight, 2),
            "contribution": round(self.contribution, 1),
            "description": self.description,
        }


@dataclass
class RiskAssessment:
    """Complete risk assessment."""

    entity_id: str
    entity_type: str
    total_score: float
    risk_level: RiskLevel
    factors: List[RiskFactor]
    recommendations: List[str]
    assessed_at: datetime

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "entity_type": self.entity_type,
            "total_score": round(self.total_score, 1),
            "risk_level": self.risk_level.value,
            "factors": [f.to_dict() for f in self.factors],
            "recommendations": self.recommendations,
            "assessed_at": self.assessed_at.isoformat(),
        }


class RiskScorer:
    """
    Deterministic risk scoring engine.

    Uses weighted multi-factor model:
    - Severity (40%)
    - Type (20%)
    - Recency (20%)
    - Status (10%)
    - Completeness (10%)
    """

    def __init__(self, config: Optional[RiskScoringConfig] = None):
        self.config = config or get_ai_config().risk_scoring

    def _severity_score(self, severity: str) -> RiskFactor:
        """Calculate severity factor."""
        base = self.config.severity_weights.get(severity.upper(), 20)
        return RiskFactor(
            name="severity",
            score=base,
            weight=0.40,
            contribution=base * 0.40,
            description=f"{severity} severity",
        )

    def _type_score(self, incident_type: str, base_severity: float) -> RiskFactor:
        """Calculate type factor."""
        factor = self.config.type_risk_factors.get(incident_type.upper(), 1.0)
        adjusted = base_severity * factor
        return RiskFactor(
            name="type",
            score=adjusted,
            weight=0.20,
            contribution=adjusted * 0.20,
            description=f"{incident_type} (factor: {factor}x)",
        )

    def _recency_score(self, incident_date: Optional[datetime]) -> RiskFactor:
        """Calculate recency factor."""
        if not incident_date:
            incident_date = datetime.utcnow() - timedelta(days=7)

        days_ago = (datetime.utcnow() - incident_date).days

        if days_ago <= 7:
            base = 30
        elif days_ago <= 30:
            base = 20
        elif days_ago <= 90:
            base = 10
        else:
            base = 5

        return RiskFactor(
            name="recency",
            score=base,
            weight=0.20,
            contribution=base * 0.20,
            description=f"{days_ago} days ago",
        )

    def _status_score(self, status: str) -> RiskFactor:
        """Calculate status factor."""
        factor = self.config.status_factors.get(status.upper(), 1.0)

        if status.upper() == "REPORTED":
            base = 25
        elif status.upper() == "IN_PROGRESS":
            base = 20
        else:
            base = 10

        adjusted = base * factor
        return RiskFactor(
            name="status",
            score=adjusted,
            weight=0.10,
            contribution=adjusted * 0.10,
            description=f"Status: {status}",
        )

    def _completeness_score(self, entity: Dict[str, Any]) -> RiskFactor:
        """Calculate completeness penalty."""
        penalty = 0
        missing = []

        for field_name in ["root_cause", "corrective_actions", "description"]:
            if not entity.get(field_name):
                penalty += 10
                missing.append(field_name)

        score = min(30, penalty)
        description = "Complete" if not missing else f"Missing: {', '.join(missing)}"

        return RiskFactor(
            name="completeness",
            score=score,
            weight=0.10,
            contribution=score * 0.10,
            description=description,
        )

    def _determine_level(self, score: float) -> RiskLevel:
        """Map score to risk level."""
        if score >= 90:
            return RiskLevel.CRITICAL
        elif score >= 70:
            return RiskLevel.HIGH
        elif score >= 40:
            return RiskLevel.MEDIUM
        else:
            return RiskLevel.LOW

    def _generate_recommendations(
        self,
        factors: List[RiskFactor],
        risk_level: RiskLevel,
    ) -> List[str]:
        """Generate recommendations."""
        recommendations = []

        if risk_level in (RiskLevel.CRITICAL, RiskLevel.HIGH):
            recommendations.append("Escalate to management")

        for factor in factors:
            if factor.name == "completeness" and "Missing" in factor.description:
                recommendations.append("Complete missing documentation")

            if factor.name == "status" and "REPORTED" in factor.description:
                recommendations.append("Begin investigation")

        return recommendations[:5]

    def assess(self, entity: Dict[str, Any], entity_type: str = "incident") -> RiskAssessment:
        """Assess risk for an entity."""
        factors: List[RiskFactor] = []

        # Severity
        severity = entity.get("severity", "MEDIUM")
        sev_factor = self._severity_score(severity)
        factors.append(sev_factor)

        # Type
        inc_type = entity.get("incident_type", "OTHER")
        type_factor = self._type_score(inc_type, sev_factor.score)
        factors.append(type_factor)

        # Recency
        date_str = entity.get("incident_date")
        incident_date = None
        if date_str:
            try:
                if isinstance(date_str, str):
                    incident_date = datetime.strptime(date_str[:10], "%Y-%m-%d")
                else:
                    incident_date = date_str
            except (ValueError, TypeError):
                pass
        factors.append(self._recency_score(incident_date))

        # Status
        status = entity.get("status", "REPORTED")
        factors.append(self._status_score(status))

        # Completeness
        factors.append(self._completeness_score(entity))

        # Calculate total
        total = sum(f.contribution for f in factors)
        risk_level = self._determine_level(total)
        recommendations = self._generate_recommendations(factors, risk_level)

        return RiskAssessment(
            entity_id=str(entity.get("id", "unknown")),
            entity_type=entity_type,
            total_score=total,
            risk_level=risk_level,
            factors=factors,
            recommendations=recommendations,
            assessed_at=datetime.utcnow(),
        )
