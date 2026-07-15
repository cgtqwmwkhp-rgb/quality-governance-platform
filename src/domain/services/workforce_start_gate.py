"""Pure domain decision stub for QR workforce passport start gates.

Route wiring and persistence are deliberately deferred: callers provide the
already-verified passport snapshot and must enforce the returned decision.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum


class StartGateReason(StrEnum):
    """Stable, auditable reasons a workforce start may be refused."""

    ALLOWED = "allowed"
    TENANT_CONTEXT_REQUIRED = "tenant_context_required"
    PASSPORT_NOT_FOUND = "passport_not_found"
    TENANT_MISMATCH = "tenant_mismatch"
    QR_REFERENCE_MISSING = "qr_reference_missing"
    PASSPORT_NOT_VERIFIED = "passport_not_verified"
    PASSPORT_EXPIRED = "passport_expired"


@dataclass(frozen=True)
class WorkforcePassportSnapshot:
    """The minimum verified passport data needed by the hard start gate."""

    passport_id: str
    tenant_id: int | None
    worker_id: int
    qr_reference: str | None
    verified: bool
    expires_on: date | None


@dataclass(frozen=True)
class StartGateDecision:
    """A deny-by-default gate result suitable for audit/event recording."""

    allowed: bool
    reason: StartGateReason
    passport_id: str | None = None


def evaluate_workforce_start_gate(
    *,
    tenant_id: int | None,
    worker_id: int,
    passport: WorkforcePassportSnapshot | None,
    today: date,
) -> StartGateDecision:
    """Evaluate a QR passport before work starts, with tenant isolation first.

    This function intentionally does not query persistence or decode a QR
    payload. The future adapter must resolve the token to a verified snapshot
    using the caller's tenant-scoped database session.
    """
    if tenant_id is None:
        return StartGateDecision(False, StartGateReason.TENANT_CONTEXT_REQUIRED)
    if passport is None:
        return StartGateDecision(False, StartGateReason.PASSPORT_NOT_FOUND)
    if passport.tenant_id != tenant_id or passport.worker_id != worker_id:
        return StartGateDecision(False, StartGateReason.TENANT_MISMATCH, passport.passport_id)
    if not passport.qr_reference:
        return StartGateDecision(False, StartGateReason.QR_REFERENCE_MISSING, passport.passport_id)
    if not passport.verified:
        return StartGateDecision(False, StartGateReason.PASSPORT_NOT_VERIFIED, passport.passport_id)
    if passport.expires_on is not None and passport.expires_on < today:
        return StartGateDecision(False, StartGateReason.PASSPORT_EXPIRED, passport.passport_id)
    return StartGateDecision(True, StartGateReason.ALLOWED, passport.passport_id)
