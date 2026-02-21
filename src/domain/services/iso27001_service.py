"""ISO 27001 Information Security business logic.

Encapsulates risk score calculation, SoA compliance percentage,
and control implementation percentage computation.
"""

from __future__ import annotations


class ISO27001Service:
    """Pure-function service for ISO 27001 calculations."""

    @staticmethod
    def calculate_risk_scores(likelihood: int, impact: int) -> tuple[int, int]:
        """Calculate inherent and residual risk scores.

        Returns *(inherent_score, residual_score)* where residual assumes
        one level of mitigation on both likelihood and impact axes.
        """
        inherent = likelihood * impact
        residual = max((likelihood - 1) * (impact - 1), 1)
        return inherent, residual

    @staticmethod
    def calculate_soa_compliance_percentage(implemented: int, applicable: int) -> float:
        """Percentage of applicable controls that are fully implemented."""
        return round((implemented / max(applicable, 1)) * 100, 1)

    @staticmethod
    def calculate_implementation_percentage(implemented: int, total: int, excluded: int) -> float:
        """Percentage of non-excluded controls that are implemented."""
        denominator = max(total - excluded, 1)
        return round((implemented / denominator) * 100, 1)
