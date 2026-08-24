"""B-10: AssessEntityRequest must reject unknown body fields (extra=forbid)."""

import pytest
from pydantic import ValidationError

from src.api.routes.governed_knowledge import AssessEntityRequest


def test_assess_entity_request_accepts_known_fields() -> None:
    m = AssessEntityRequest(
        content="override",
        finding_type="gap",
        include_related_documents=False,
    )
    assert m.content == "override"
    assert m.finding_type == "gap"
    assert m.include_related_documents is False


def test_assess_entity_request_defaults() -> None:
    m = AssessEntityRequest()
    assert m.content is None
    assert m.finding_type is None
    assert m.include_related_documents is True


def test_assess_entity_request_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError) as exc_info:
        AssessEntityRequest(
            content="x",
            tenant_id=1,  # type: ignore[call-arg]
        )
    assert "tenant_id" in str(exc_info.value)
    assert "extra" in str(exc_info.value).lower() or "forbidden" in str(exc_info.value).lower()
