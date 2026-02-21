"""KRI-specific calculation helpers.

Core KRI scoring and dashboard logic lives in
``src.domain.services.risk_scoring.KRIService``.  This module provides
supplementary pure-function calculations that were previously inline
in the KRI route file (e.g. SIF assessment field mapping).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


class KRICalculationService:
    """Pure-function service for KRI-adjacent calculations."""

    @staticmethod
    def apply_sif_assessment(
        incident: Any,
        assessment: Any,
        assessed_by_id: int,
    ) -> None:
        """Apply SIF/pSIF classification fields onto an incident.

        Mutates *incident* in-place so the caller can commit the session.
        """
        incident.is_sif = assessment.is_sif
        incident.is_psif = assessment.is_psif
        incident.sif_classification = assessment.sif_classification
        incident.sif_assessment_date = datetime.now(timezone.utc)
        incident.sif_assessed_by_id = assessed_by_id
        incident.sif_rationale = assessment.sif_rationale
        incident.life_altering_potential = assessment.life_altering_potential
        incident.precursor_events = assessment.precursor_events
        incident.control_failures = assessment.control_failures
