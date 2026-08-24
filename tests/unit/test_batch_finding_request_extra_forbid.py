"""B-10: BatchFindingRequest must reject unknown body fields (extra=forbid)."""

import pytest
from pydantic import ValidationError

from src.api.routes.ai_intelligence import BatchFindingRequest


def test_batch_finding_request_accepts_known_fields() -> None:
    m = BatchFindingRequest(findings=["Missing guardrail", "Incomplete LOTO"])
    assert m.findings == ["Missing guardrail", "Incomplete LOTO"]


def test_batch_finding_request_rejects_empty() -> None:
    with pytest.raises(ValidationError):
        BatchFindingRequest(findings=[])


def test_batch_finding_request_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError) as exc_info:
        BatchFindingRequest(
            findings=["Missing guardrail"],
            tenant_id=1,  # type: ignore[call-arg]
        )
    assert "tenant_id" in str(exc_info.value)
    assert "extra" in str(exc_info.value).lower() or "forbidden" in str(exc_info.value).lower()
