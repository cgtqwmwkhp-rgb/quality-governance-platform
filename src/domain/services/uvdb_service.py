"""UVDB Achilles Verify B2 business logic.

Encapsulates LTIFR calculation and audit reference number generation.
"""

from __future__ import annotations

from datetime import datetime


class UVDBService:
    """Pure-function service for UVDB audit calculations."""

    @staticmethod
    def calculate_ltifr(
        lost_time_incidents: int,
        riddor_reportable: int,
        total_man_hours: int | None,
    ) -> float | None:
        """Calculate the Lost Time Injury Frequency Rate.

        ``LTIFR = (lost_time + riddor) / man_hours * 1_000_000``

        Returns *None* when *total_man_hours* is missing or zero.
        """
        if not total_man_hours or total_man_hours <= 0:
            return None
        lost_time = lost_time_incidents + riddor_reportable
        return (lost_time / total_man_hours) * 1_000_000

    @staticmethod
    def generate_audit_reference(existing_count: int, year: int | None = None) -> str:
        """Generate the next sequential audit reference.

        Format: ``UVDB-{year}-{nnnn}``
        """
        if year is None:
            year = datetime.utcnow().year
        return f"UVDB-{year}-{(existing_count + 1):04d}"
