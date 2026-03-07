"""Reference number generation service."""

import logging
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class ReferenceNumberService:
    """Service for generating unique reference numbers."""

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
    async def _next_sequence(
        cls,
        db: AsyncSession,
        model_class: type[Any],
        pattern: str,
    ) -> int:
        """Get next sequence number using both MAX and COUNT for robustness."""
        try:
            await db.flush()
        except Exception:
            pass

        max_seq = 0
        result = await db.execute(
            select(func.max(model_class.reference_number)).where(model_class.reference_number.like(pattern))
        )
        max_ref = result.scalar()
        if max_ref:
            try:
                max_seq = int(max_ref.split("-")[-1])
            except (ValueError, IndexError):
                pass

        count_result = await db.execute(
            select(func.count()).select_from(model_class).where(model_class.reference_number.like(pattern))
        )
        count = count_result.scalar() or 0

        return max(max_seq, count) + 1

    @classmethod
    async def generate(
        cls,
        db: AsyncSession,
        record_type: str,
        model_class: type[Any],  # type: ignore[misc]  # TYPE-IGNORE: MYPY-001
        year: Optional[int] = None,
    ) -> str:
        """Generate a unique reference number in format: PREFIX-YYYY-####."""
        prefix = cls.PREFIXES.get(record_type, "REF")
        current_year = year or datetime.now().year
        pattern = f"{prefix}-{current_year}-%"

        sequence = await cls._next_sequence(db, model_class, pattern)

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
