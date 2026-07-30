"""B-10: AddCertificationRequest must reject unknown body fields (extra=forbid)."""

from datetime import datetime

import pytest
from pydantic import ValidationError

from src.api.routes.auditor_competence import AddCertificationRequest


def test_add_certification_request_accepts_known_fields() -> None:
    m = AddCertificationRequest(
        certification_name="Lead Auditor",
        certification_body="IRCA",
        issued_date=datetime(2024, 1, 15),
        expiry_date=datetime(2027, 1, 15),
        certification_number="LA-123",
        standard_code="ISO9001",
        certification_level="lead",
    )
    assert m.certification_name == "Lead Auditor"
    assert m.certification_body == "IRCA"
    assert m.certification_number == "LA-123"


def test_add_certification_request_optionals_default_none() -> None:
    m = AddCertificationRequest(
        certification_name="Internal Auditor",
        certification_body="CQI",
        issued_date=datetime(2024, 6, 1),
    )
    assert m.expiry_date is None
    assert m.certification_number is None
    assert m.standard_code is None
    assert m.certification_level is None


def test_add_certification_request_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError) as exc_info:
        AddCertificationRequest(
            certification_name="Lead Auditor",
            certification_body="IRCA",
            issued_date=datetime(2024, 1, 15),
            user_id=99,  # type: ignore[call-arg]
        )
    assert "user_id" in str(exc_info.value)
    assert "extra" in str(exc_info.value).lower() or "forbidden" in str(exc_info.value).lower()
