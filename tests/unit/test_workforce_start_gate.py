"""Unit tests for the dependency-free QR passport start-gate decision."""

from datetime import date

import pytest

from src.domain.services.workforce_start_gate import (
    StartGateDecision,
    StartGateReason,
    WorkforcePassportSnapshot,
    evaluate_workforce_start_gate,
)

TODAY = date(2026, 7, 15)


def _passport(**overrides: object) -> WorkforcePassportSnapshot:
    values: dict[str, object] = {
        "passport_id": "passport-001",
        "tenant_id": 12,
        "worker_id": 44,
        "qr_reference": "qgp://passport/passport-001",
        "verified": True,
        "expires_on": date(2026, 12, 31),
    }
    values.update(overrides)
    return WorkforcePassportSnapshot(**values)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("passport", "tenant_id", "worker_id", "reason"),
    [
        (None, 12, 44, StartGateReason.PASSPORT_NOT_FOUND),
        (_passport(tenant_id=None), 12, 44, StartGateReason.TENANT_MISMATCH),
        (_passport(tenant_id=99), 12, 44, StartGateReason.TENANT_MISMATCH),
        (_passport(worker_id=45), 12, 44, StartGateReason.TENANT_MISMATCH),
        (_passport(qr_reference=""), 12, 44, StartGateReason.QR_REFERENCE_MISSING),
        (_passport(verified=False), 12, 44, StartGateReason.PASSPORT_NOT_VERIFIED),
        (_passport(expires_on=date(2026, 7, 14)), 12, 44, StartGateReason.PASSPORT_EXPIRED),
    ],
)
def test_gate_denies_invalid_or_cross_tenant_passports(
    passport: WorkforcePassportSnapshot | None, tenant_id: int, worker_id: int, reason: StartGateReason
) -> None:
    decision = evaluate_workforce_start_gate(tenant_id=tenant_id, worker_id=worker_id, passport=passport, today=TODAY)

    assert decision.allowed is False
    assert decision.reason is reason


def test_gate_requires_tenant_context_even_for_a_valid_passport() -> None:
    decision = evaluate_workforce_start_gate(tenant_id=None, worker_id=44, passport=_passport(), today=TODAY)

    assert decision == StartGateDecision(False, StartGateReason.TENANT_CONTEXT_REQUIRED)


def test_gate_allows_verified_unexpired_passport_for_its_tenant() -> None:
    decision = evaluate_workforce_start_gate(tenant_id=12, worker_id=44, passport=_passport(), today=TODAY)

    assert decision.allowed is True
    assert decision.reason is StartGateReason.ALLOWED
    assert decision.passport_id == "passport-001"
