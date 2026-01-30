"""
Compliance Checking Engine - Quality Governance Platform
Stage 12: AI Standards Automation (Security Hardened)

SECURITY NOTES:
- NO eval() USAGE - all rules use fixed, auditable functions
- Each rule is a pure function with explicit logic
- All conditions are deterministic and testable
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


class ComplianceSeverity(Enum):
    """Compliance issue severity."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class ComplianceViolation:
    """Single compliance violation."""

    rule_id: str
    rule_name: str
    severity: ComplianceSeverity
    message: str
    remediation: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "rule_name": self.rule_name,
            "severity": self.severity.value,
            "message": self.message,
            "remediation": self.remediation,
        }


@dataclass
class ComplianceCheckResult:
    """Compliance check result for an entity."""

    entity_id: str
    entity_type: str
    is_compliant: bool
    violations: List[ComplianceViolation]
    checked_at: datetime

    @property
    def error_count(self) -> int:
        return sum(1 for v in self.violations if v.severity == ComplianceSeverity.ERROR)

    @property
    def compliance_score(self) -> float:
        if not self.violations:
            return 100.0
        errors = self.error_count
        if errors == 0:
            return 100.0
        # Reduce score by 20% per error
        return max(0.0, 100.0 - (errors * 20.0))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "entity_type": self.entity_type,
            "is_compliant": self.is_compliant,
            "compliance_score": round(self.compliance_score, 1),
            "error_count": self.error_count,
            "violations": [v.to_dict() for v in self.violations],
            "checked_at": self.checked_at.isoformat(),
        }


# ===========================================================================
# COMPLIANCE RULES - FIXED FUNCTIONS (NO EVAL)
# ===========================================================================
# Each rule is a pure function that takes an entity dict and returns
# a violation if the rule is violated, or None if compliant.
# ===========================================================================


def _rule_inc_001(entity: Dict[str, Any]) -> Optional[ComplianceViolation]:
    """INC-001: High severity incidents must have root cause documented."""
    severity = str(entity.get("severity", "")).upper()
    root_cause = entity.get("root_cause")

    if severity in ("CRITICAL", "HIGH") and not root_cause:
        return ComplianceViolation(
            rule_id="INC-001",
            rule_name="High severity requires root cause",
            severity=ComplianceSeverity.ERROR,
            message="Critical/High severity incidents must have root cause documented",
            remediation="Document the root cause analysis",
        )
    return None


def _rule_inc_002(entity: Dict[str, Any]) -> Optional[ComplianceViolation]:
    """INC-002: Closed incidents must have corrective actions."""
    status = str(entity.get("status", "")).upper()
    corrective_actions = entity.get("corrective_actions")

    if status == "CLOSED" and not corrective_actions:
        return ComplianceViolation(
            rule_id="INC-002",
            rule_name="Closed requires corrective actions",
            severity=ComplianceSeverity.ERROR,
            message="Closed incidents must have corrective actions documented",
            remediation="Document corrective actions before closing",
        )
    return None


def _rule_inc_003(entity: Dict[str, Any]) -> Optional[ComplianceViolation]:
    """INC-003: Safety incidents should have immediate actions."""
    incident_type = str(entity.get("incident_type", "")).upper()
    immediate_actions = entity.get("immediate_actions")

    if incident_type == "SAFETY" and not immediate_actions:
        return ComplianceViolation(
            rule_id="INC-003",
            rule_name="Safety requires immediate actions",
            severity=ComplianceSeverity.WARNING,
            message="Safety incidents should document immediate actions taken",
            remediation="Document immediate actions taken",
        )
    return None


def _rule_inc_004(entity: Dict[str, Any]) -> Optional[ComplianceViolation]:
    """INC-004: Incidents open > 30 days need review."""
    status = str(entity.get("status", "")).upper()
    created_at = entity.get("created_at")

    if status != "CLOSED" and created_at:
        try:
            if isinstance(created_at, str):
                created = datetime.strptime(created_at[:10], "%Y-%m-%d")
            else:
                created = created_at
            days_open = (datetime.utcnow() - created).days
            if days_open > 30:
                return ComplianceViolation(
                    rule_id="INC-004",
                    rule_name="Incident age warning",
                    severity=ComplianceSeverity.WARNING,
                    message=f"Incident open for {days_open} days - review needed",
                    remediation="Review and update status or escalate",
                )
        except (ValueError, TypeError):
            pass
    return None


def _rule_comp_001(entity: Dict[str, Any]) -> Optional[ComplianceViolation]:
    """COMP-001: Resolved complaints must have resolution notes."""
    status = str(entity.get("status", "")).upper()
    resolution = entity.get("resolution")

    if status == "RESOLVED" and not resolution:
        return ComplianceViolation(
            rule_id="COMP-001",
            rule_name="Resolved requires resolution notes",
            severity=ComplianceSeverity.ERROR,
            message="Resolved complaints must have resolution documented",
            remediation="Document the resolution details",
        )
    return None


def _rule_comp_002(entity: Dict[str, Any]) -> Optional[ComplianceViolation]:
    """COMP-002: Urgent complaints need acknowledgment within 24h."""
    priority = str(entity.get("priority", "")).upper()
    status = str(entity.get("status", "")).upper()
    received_date = entity.get("received_date")

    if priority == "URGENT" and status == "RECEIVED" and received_date:
        try:
            if isinstance(received_date, str):
                received = datetime.strptime(received_date[:10], "%Y-%m-%d")
            else:
                received = received_date
            days_open = (datetime.utcnow() - received).days
            if days_open > 1:
                return ComplianceViolation(
                    rule_id="COMP-002",
                    rule_name="Urgent requires acknowledgment",
                    severity=ComplianceSeverity.ERROR,
                    message="Urgent complaints must be acknowledged within 24 hours",
                    remediation="Acknowledge this urgent complaint immediately",
                )
        except (ValueError, TypeError):
            pass
    return None


def _rule_rta_001(entity: Dict[str, Any]) -> Optional[ComplianceViolation]:
    """RTA-001: Approved RTAs must have root cause."""
    status = str(entity.get("status", "")).upper()
    root_cause = entity.get("root_cause")

    if status == "APPROVED" and not root_cause:
        return ComplianceViolation(
            rule_id="RTA-001",
            rule_name="Approved requires root cause",
            severity=ComplianceSeverity.ERROR,
            message="Approved RTAs must have root cause documented",
            remediation="Document root cause before approving",
        )
    return None


def _rule_rta_002(entity: Dict[str, Any]) -> Optional[ComplianceViolation]:
    """RTA-002: Approved RTAs must have corrective actions."""
    status = str(entity.get("status", "")).upper()
    corrective_actions = entity.get("corrective_actions")

    if status == "APPROVED" and not corrective_actions:
        return ComplianceViolation(
            rule_id="RTA-002",
            rule_name="Approved requires corrective actions",
            severity=ComplianceSeverity.ERROR,
            message="Approved RTAs must have corrective actions documented",
            remediation="Document corrective actions before approving",
        )
    return None


# ===========================================================================
# RULE REGISTRY - Maps rule IDs to functions
# ===========================================================================

INCIDENT_RULES: List[Callable[[Dict[str, Any]], Optional[ComplianceViolation]]] = [
    _rule_inc_001,
    _rule_inc_002,
    _rule_inc_003,
    _rule_inc_004,
]

COMPLAINT_RULES: List[Callable[[Dict[str, Any]], Optional[ComplianceViolation]]] = [
    _rule_comp_001,
    _rule_comp_002,
]

RTA_RULES: List[Callable[[Dict[str, Any]], Optional[ComplianceViolation]]] = [
    _rule_rta_001,
    _rule_rta_002,
]


class ComplianceChecker:
    """
    Compliance checker with fixed, auditable rules.

    SECURITY: No eval() - all rules are pre-defined functions.
    """

    def __init__(self):
        self._rules = {
            "incident": INCIDENT_RULES,
            "complaint": COMPLAINT_RULES,
            "rta": RTA_RULES,
        }

    def check(self, entity: Dict[str, Any], entity_type: str) -> ComplianceCheckResult:
        """Check entity against compliance rules."""
        violations: List[ComplianceViolation] = []
        rules = self._rules.get(entity_type, [])

        for rule_fn in rules:
            violation = rule_fn(entity)
            if violation:
                violations.append(violation)

        # Compliant if no ERROR violations
        is_compliant = not any(v.severity == ComplianceSeverity.ERROR for v in violations)

        return ComplianceCheckResult(
            entity_id=str(entity.get("id", "unknown")),
            entity_type=entity_type,
            is_compliant=is_compliant,
            violations=violations,
            checked_at=datetime.utcnow(),
        )

    def check_incident(self, incident: Dict[str, Any]) -> ComplianceCheckResult:
        """Check an incident."""
        return self.check(incident, "incident")

    def check_complaint(self, complaint: Dict[str, Any]) -> ComplianceCheckResult:
        """Check a complaint."""
        return self.check(complaint, "complaint")

    def check_rta(self, rta: Dict[str, Any]) -> ComplianceCheckResult:
        """Check an RTA."""
        return self.check(rta, "rta")

    def get_remediation_plan(
        self,
        result: ComplianceCheckResult,
    ) -> List[Dict[str, Any]]:
        """Generate remediation plan for violations."""
        plan = []

        sorted_violations = sorted(
            result.violations,
            key=lambda v: 0 if v.severity == ComplianceSeverity.ERROR else 1,
        )

        for i, violation in enumerate(sorted_violations, 1):
            plan.append(
                {
                    "priority": i,
                    "rule_id": violation.rule_id,
                    "severity": violation.severity.value,
                    "issue": violation.message,
                    "action": violation.remediation,
                }
            )

        return plan
