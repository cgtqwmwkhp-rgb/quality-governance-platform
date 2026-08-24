"""B-10: CompleteAnalysisRequest must reject unknown body fields (extra=forbid)."""

import pytest
from pydantic import ValidationError

from src.api.routes.rca_tools import CompleteAnalysisRequest


def test_complete_analysis_request_accepts_known_fields() -> None:
    m = CompleteAnalysisRequest(proposed_actions=[{"title": "Retrain"}])
    assert m.proposed_actions == [{"title": "Retrain"}]


def test_complete_analysis_request_optional_default_none() -> None:
    m = CompleteAnalysisRequest()
    assert m.proposed_actions is None


def test_complete_analysis_request_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError) as exc_info:
        CompleteAnalysisRequest(
            proposed_actions=None,
            tenant_id=1,  # type: ignore[call-arg]
        )
    assert "tenant_id" in str(exc_info.value)
    assert "extra" in str(exc_info.value).lower() or "forbidden" in str(exc_info.value).lower()
