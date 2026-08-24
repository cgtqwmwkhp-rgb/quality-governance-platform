"""B-10: CreateProfileRequest must reject unknown body fields (extra=forbid)."""

import pytest
from pydantic import ValidationError

from src.api.routes.auditor_competence import CreateProfileRequest


def test_create_profile_request_accepts_known_fields() -> None:
    m = CreateProfileRequest(
        user_id=42,
        job_title="Lead Auditor",
        department="Quality",
        years_experience=5.5,
    )
    assert m.user_id == 42
    assert m.job_title == "Lead Auditor"
    assert m.department == "Quality"
    assert m.years_experience == 5.5


def test_create_profile_request_optionals_default() -> None:
    m = CreateProfileRequest(user_id=7)
    assert m.job_title is None
    assert m.department is None
    assert m.years_experience == 0


def test_create_profile_request_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError) as exc_info:
        CreateProfileRequest(
            user_id=42,
            tenant_id=1,  # type: ignore[call-arg]
        )
    assert "tenant_id" in str(exc_info.value)
    assert "extra" in str(exc_info.value).lower() or "forbidden" in str(exc_info.value).lower()
