"""B-10: CreateFindingCapaRequest must reject unknown body fields (extra=forbid)."""

import pytest
from pydantic import ValidationError

from src.api.schemas.audit import CreateFindingCapaRequest


def test_create_finding_capa_request_accepts_known_fields() -> None:
    m = CreateFindingCapaRequest(
        title="Corrective action",
        description="Fix root cause",
        assignee_email="owner@example.com",
    )
    assert m.title == "Corrective action"
    assert m.description == "Fix root cause"
    assert m.assignee_email == "owner@example.com"


def test_create_finding_capa_request_all_fields_optional() -> None:
    m = CreateFindingCapaRequest()
    assert m.title is None
    assert m.description is None
    assert m.assignee_email is None


def test_create_finding_capa_request_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError) as exc_info:
        CreateFindingCapaRequest(
            title="CAPA",
            finding_id=99,  # type: ignore[call-arg]
        )
    assert "finding_id" in str(exc_info.value)
    assert "extra" in str(exc_info.value).lower() or "forbidden" in str(exc_info.value).lower()
