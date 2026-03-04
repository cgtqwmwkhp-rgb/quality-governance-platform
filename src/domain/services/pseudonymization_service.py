"""Pseudonymization service for GDPR compliance.

Provides one-way hashing of PII fields using SHA-256 with a secret pepper,
supporting both record-level pseudonymization and full user erasure
(Right to Be Forgotten, GDPR Art. 17).
"""

import hashlib
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings

logger = logging.getLogger(__name__)

PII_FIELDS = ("email", "first_name", "last_name", "phone")


@dataclass
class PseudonymizationResult:
    """Captures what was (or would be) changed during pseudonymization."""

    entity_type: str
    entity_id: Any
    fields_affected: Dict[str, str] = field(default_factory=dict)
    dry_run: bool = False


class PseudonymizationService:
    """Hash-based pseudonymization of PII fields.

    Uses HMAC-style SHA-256 with a configurable pepper so that the same
    plaintext always maps to the same pseudonym within the same deployment,
    but cannot be reversed without the pepper.
    """

    def __init__(self, db: AsyncSession, *, dry_run: bool = False):
        self.db = db
        self.dry_run = dry_run
        self._pepper = settings.pseudonymization_pepper

    def _hash_value(self, value: str) -> str:
        """Produce a deterministic, irreversible pseudonym for *value*."""
        salted = f"{self._pepper}:{value}"
        return hashlib.sha256(salted.encode("utf-8")).hexdigest()

    def pseudonymize_record(
        self,
        record: dict,
        *,
        fields: Optional[List[str]] = None,
    ) -> PseudonymizationResult:
        """Pseudonymize PII fields in an arbitrary dict.

        Args:
            record: Mutable dictionary whose PII values will be replaced
                    in-place (unless dry_run is active).
            fields: Specific field names to pseudonymize.  Defaults to
                    the module-level ``PII_FIELDS`` tuple.

        Returns:
            A ``PseudonymizationResult`` describing what was changed.
        """
        target_fields = fields or list(PII_FIELDS)
        result = PseudonymizationResult(
            entity_type="record",
            entity_id=record.get("id"),
            dry_run=self.dry_run,
        )

        for f in target_fields:
            original = record.get(f)
            if original is None:
                continue
            hashed = self._hash_value(str(original))
            result.fields_affected[f] = f"{str(original)[:3]}*** -> {hashed[:12]}…"
            if not self.dry_run:
                record[f] = hashed

        if self.dry_run:
            logger.info(
                "DRY_RUN pseudonymize_record id=%s fields=%s",
                record.get("id"),
                list(result.fields_affected.keys()),
            )

        return result

    async def pseudonymize_user(
        self,
        user_id: int,
    ) -> PseudonymizationResult:
        """Pseudonymize all PII on a User row (Right to Be Forgotten).

        In DRY_RUN mode the database is not modified; the result object
        describes what *would* change.
        """
        from src.domain.models.user import User

        stmt = select(User).where(User.id == user_id)
        row = await self.db.execute(stmt)
        user = row.scalar_one_or_none()
        if user is None:
            from src.domain.exceptions import NotFoundError

            raise NotFoundError(f"User {user_id} not found")

        result = PseudonymizationResult(
            entity_type="user",
            entity_id=user_id,
            dry_run=self.dry_run,
        )

        for attr in PII_FIELDS:
            original = getattr(user, attr, None)
            if original is None:
                continue
            hashed = self._hash_value(str(original))
            result.fields_affected[attr] = f"{str(original)[:3]}*** -> {hashed[:12]}…"
            if not self.dry_run:
                setattr(user, attr, hashed)

        if not self.dry_run:
            user.is_active = False
            await self.db.flush()
            logger.info("Pseudonymized user %d (%d fields)", user_id, len(result.fields_affected))
        else:
            logger.info(
                "DRY_RUN pseudonymize_user id=%d would_affect=%s",
                user_id,
                list(result.fields_affected.keys()),
            )

        return result
