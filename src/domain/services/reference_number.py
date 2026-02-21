"""Reference number generation service."""

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession


class ReferenceNumberService:
    """Service for generating unique reference numbers."""

    # Prefix mapping for different record types
    PREFIXES = {
        "audit_template": "TPL",
        "audit_run": "AUD",
        "audit_finding": "FND",
        "risk": "RSK",
        "incident": "INC",
        "rta": "RTA",
        "complaint": "COMP",
        "near_miss": "NM",
        "policy": "POL",
        "incident_action": "INA",
        "rta_action": "RTAACT",
        "complaint_action": "CMA",
        "capa": "CAPA",
    }

    @classmethod
    async def generate(
        cls,
        db: AsyncSession,
        record_type: str,
        model_class: type[Any],  # type: ignore[misc]  # TYPE-IGNORE: MYPY-001
        year: Optional[int] = None,
    ) -> str:
        """
        Generate a unique reference number in format: PREFIX-YYYY-####

        Args:
            db: Database session
            record_type: Type of record (e.g., "audit_run", "incident")
            model_class: SQLAlchemy model class to query
            year: Optional year override (defaults to current year)

        Returns:
            Unique reference number string
        """
        prefix = cls.PREFIXES.get(record_type, "REF")
        current_year = year or datetime.now().year

        # Find the highest sequence number for this prefix and year
        pattern = f"{prefix}-{current_year}-%"

        result = await db.execute(
            select(func.max(model_class.reference_number)).where(model_class.reference_number.like(pattern))
        )
        max_ref = result.scalar()

        if max_ref:
            # Extract sequence number and increment
            try:
                sequence = int(max_ref.split("-")[-1]) + 1
            except (ValueError, IndexError):
                sequence = 1
        else:
            sequence = 1

        return f"{prefix}-{current_year}-{sequence:04d}"

    @classmethod
    def parse(cls, reference_number: str) -> dict:
        """
        Parse a reference number into its components.

        Args:
            reference_number: Reference number string

        Returns:
            Dictionary with prefix, year, and sequence
        """
        try:
            parts = reference_number.split("-")
            return {
                "prefix": parts[0],
                "year": int(parts[1]),
                "sequence": int(parts[2]),
            }
        except (ValueError, IndexError):
            return {
                "prefix": None,
                "year": None,
                "sequence": None,
            }
