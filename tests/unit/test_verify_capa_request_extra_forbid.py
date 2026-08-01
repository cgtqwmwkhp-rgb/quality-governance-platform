"""B-10: VerifyCAPARequest must reject unknown body fields (extra=forbid)."""

import pytest
from pydantic import ValidationError

from src.api.routes.rca_tools import VerifyCAPARequest


def test_verify_capa_request_accepts_known_fields() -> None:
    m = VerifyCAPARequest(verification_notes="Recurrence check passed", is_effective=True)
    assert m.verification_notes == "Recurrence check passed"
    assert m.is_effective is True


def test_verify_capa_request_defaults() -> None:
    m = VerifyCAPARequest()
    assert m.verification_notes is None
    assert m.is_effective is True


def test_verify_capa_request_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError) as exc_info:
        VerifyCAPARequest(
            is_effective=False,
            tenant_id=1,  # type: ignore[call-arg]
        )
    assert "tenant_id" in str(exc_info.value)
    assert "extra" in str(exc_info.value).lower() or "forbidden" in str(exc_info.value).lower()
