"""Shared eligibility rules for automatic audit-finding risk creation."""

from __future__ import annotations

from typing import Protocol


class RiskCandidateFinding(Protocol):
    # Properties keep Protocol matching covariant for ORM str fields and Optional duck types.
    @property
    def finding_type(self) -> str | None: ...

    @property
    def severity(self) -> str | None: ...


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
