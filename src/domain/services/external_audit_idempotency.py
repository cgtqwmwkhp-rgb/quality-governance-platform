"""Refuse twin external-audit run creates (FR-DEDUP-02).

Repeated Achilles / Planet Mark imports historically minted a new ``audit_runs``
row (and then a new ``uvdb_audit`` catalogue row) every time the same real-world
report id was pasted into ``external_reference``. Job-level idempotency only
keys on ``(run_id, asset, checksum)``, so it cannot stop the second run.

This module is the business-identity gate: when an external intake supplies a
non-empty ``external_reference``, look up an existing run for the same tenant
and refuse with 409 rather than minting another twin.
"""

from __future__ import annotations

from typing import Any, Optional, Sequence

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.audit import AuditRun, AuditStatus


def normalize_external_reference(value: str | None) -> str:
    """Trim and case-fold supplier / report ids for comparison."""
    if value is None:
        return ""
    return " ".join(str(value).strip().split()).casefold()


def _survivor_sort_key(run: AuditRun) -> tuple:
    """Prefer completed scored runs, then richer finding sets, then newest id."""
    completed = 1 if run.status == AuditStatus.COMPLETED else 0
    score = float(run.score_percentage) if run.score_percentage is not None else -1.0
    return (completed, score, run.id or 0)


async def find_existing_external_audit_run(
    db: AsyncSession,
    *,
    tenant_id: int,
    external_reference: str,
    assurance_scheme: str | None = None,
) -> Optional[AuditRun]:
    """Return the best existing twin for this external report identity, if any.

    Match is ``tenant_id`` + normalised ``external_reference``. When
    ``assurance_scheme`` is provided, prefer rows with the same scheme (case-insensitive)
    so an ISO certificate number cannot collide with an Achilles supplier id that
    happens to share digits — but if no scheme-matched row exists, still return a
    reference match (the historical Achilles twins often differ only by lifecycle).
    """
    normalised = normalize_external_reference(external_reference)
    if not normalised or tenant_id is None:
        return None

    result = await db.execute(
        sa.select(AuditRun).where(
            AuditRun.tenant_id == tenant_id,
            AuditRun.external_reference.is_not(None),
            sa.func.lower(sa.func.trim(AuditRun.external_reference)) == normalised,
        )
    )
    candidates: Sequence[AuditRun] = list(result.scalars().all())
    if not candidates:
        return None

    scheme_norm = normalize_external_reference(assurance_scheme)
    if scheme_norm:
        scheme_matched = [
            run
            for run in candidates
            if normalize_external_reference(run.assurance_scheme) == scheme_norm
        ]
        if scheme_matched:
            candidates = scheme_matched

    return max(candidates, key=_survivor_sort_key)


def conflict_details_for_run(run: AuditRun) -> dict[str, Any]:
    """Stable payload the FE can deep-link from a 409."""
    return {
        "existing_run_id": run.id,
        "existing_reference_number": run.reference_number,
        "existing_status": run.status.value if hasattr(run.status, "value") else str(run.status),
        "external_reference": run.external_reference,
    }
