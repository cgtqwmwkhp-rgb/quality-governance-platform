"""Shared eligibility rules for automatic audit-finding risk creation."""

from __future__ import annotations

from typing import Protocol


class RiskCandidateFinding(Protocol):
    finding_type: str | None
    severity: str | None


RISK_CREATING_FINDING_TYPES = frozenset(
    {
        "nonconformity",
        "major_nonconformity",
        "minor_nonconformity",
        "competence_gap",
        "finding",
        "flagged_item",
        "question_answered_no",
    }
)

AUDIT_RISK_SEVERITIES = frozenset({"low", "medium", "high", "critical"})
RISK_CREATING_SEVERITIES = AUDIT_RISK_SEVERITIES - {"low"}


def should_create_risk(finding: RiskCandidateFinding) -> bool:
    """Return whether a finding should automatically create an organisational risk."""
    finding_type = (finding.finding_type or "").strip().lower()
    severity = (finding.severity or "").strip().lower()
    return finding_type in RISK_CREATING_FINDING_TYPES and severity in RISK_CREATING_SEVERITIES
