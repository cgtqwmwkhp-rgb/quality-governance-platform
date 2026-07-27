"""Reference number generation service."""

import hashlib
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
        "audit_import": "AIM",
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
        "document": "DOC",
        "document_campaign": "CAM",
    }

    @classmethod
    def _ref_column(cls, model_class: type[Any]) -> Any:
        """Return the reference-number column, supporting both naming conventions."""
        col = getattr(model_class, "reference_number", None)
        if col is not None:
            return col
        col = getattr(model_class, "reference", None)
        if col is not None:
            return col
        raise AttributeError(f"{model_class.__name__} has neither 'reference_number' nor 'reference'")

    @staticmethod
    def _advisory_lock_key(pattern: str) -> int:
        """Stable signed 64-bit lock key for a prefix/year pattern.

        Derived in Python rather than with PostgreSQL's ``hashtext`` so the value
        does not depend on an undocumented server internal.
        """
        return int.from_bytes(hashlib.blake2b(pattern.encode("utf-8"), digest_size=8).digest(), "big", signed=True)

    @classmethod
    async def _serialize_minting(cls, db: AsyncSession, pattern: str) -> None:
        """Serialise concurrent minting of one prefix/year on PostgreSQL.

        The sequence is read with MAX/COUNT, so two transactions that read before
        either commits pick the same number and the second INSERT dies on the
        unique index — losing whoever committed last, which for portal intake is
        a member of staff losing a report they just filed.

        ``pg_advisory_xact_lock`` is held until the surrounding transaction ends,
        so the waiter only proceeds once the first writer's row is committed and
        therefore visible to its MAX. Other dialects (SQLite in tests) are left
        alone; a lock that cannot be taken is logged and skipped rather than
        allowed to block a record from being created at all.
        """
        try:
            bind = db.get_bind()
        except Exception:  # pragma: no cover - an unbound session cannot mint anyway
            return
        if getattr(getattr(bind, "dialect", None), "name", None) != "postgresql":
            return
        try:
            await db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": cls._advisory_lock_key(pattern)})
        except Exception:
            logger.warning("Could not serialise reference minting for %s; continuing unlocked", pattern, exc_info=True)

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

        await cls._serialize_minting(db, pattern)

        ref_col = cls._ref_column(model_class)

        max_seq = 0
        result = await db.execute(select(func.max(ref_col)).where(ref_col.like(pattern)))
        max_ref = result.scalar()
        if max_ref:
            try:
                max_seq = int(max_ref.split("-")[-1])
            except (ValueError, IndexError):
                pass

        count_result = await db.execute(select(func.count()).select_from(model_class).where(ref_col.like(pattern)))
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
