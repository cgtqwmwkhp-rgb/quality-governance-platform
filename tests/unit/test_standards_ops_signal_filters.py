"""Unit tests for operational exception clause filters."""

from src.domain.services.iso_compliance_service import OPERATIONAL_SIGNAL_TYPES


def test_operational_signal_types_are_inbound_cases() -> None:
    assert "nonconformity" in OPERATIONAL_SIGNAL_TYPES
    assert "gap" in OPERATIONAL_SIGNAL_TYPES
    assert "opportunity" in OPERATIONAL_SIGNAL_TYPES
    assert "evidence" not in OPERATIONAL_SIGNAL_TYPES


def test_exceptions_href_contract_params() -> None:
    """Frontend deep-link contract used by Standards → Knowledge Exceptions."""
    clause = "7.5"
    standard = "ISO9001"
    href = f"/knowledge-exceptions?clause={clause}&standard={standard}&operational=1"
    assert "clause=7.5" in href
    assert "standard=ISO9001" in href
    assert "operational=1" in href
