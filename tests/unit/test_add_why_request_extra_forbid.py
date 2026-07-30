"""B-10: AddWhyRequest must reject unknown body fields (extra=forbid)."""

import pytest
from pydantic import ValidationError

from src.api.routes.rca_tools import AddWhyRequest


def test_add_why_request_accepts_known_fields() -> None:
    m = AddWhyRequest(why_question="Why?", answer="Because", evidence="photo-1")
    assert m.why_question == "Why?"
    assert m.answer == "Because"
    assert m.evidence == "photo-1"


def test_add_why_request_evidence_optional() -> None:
    m = AddWhyRequest(why_question="Why?", answer="Because")
    assert m.evidence is None


def test_add_why_request_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError) as exc_info:
        AddWhyRequest(
            why_question="Why?",
            answer="Because",
            root_cause_id=12,  # type: ignore[call-arg]
        )
    assert "root_cause_id" in str(exc_info.value)
    assert "extra" in str(exc_info.value).lower() or "forbidden" in str(exc_info.value).lower()
