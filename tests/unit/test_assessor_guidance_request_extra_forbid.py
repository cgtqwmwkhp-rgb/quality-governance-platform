"""B-10: AssessorGuidanceRequest must reject unknown body fields (extra=forbid)."""

import pytest
from pydantic import ValidationError

from src.api.routes.ai_templates import AssessorGuidanceRequest


def test_assessor_guidance_request_accepts_known_fields() -> None:
    m = AssessorGuidanceRequest(question_text="What to check?", asset_type="MEWP")
    assert m.question_text == "What to check?"
    assert m.asset_type == "MEWP"


def test_assessor_guidance_request_asset_type_optional() -> None:
    m = AssessorGuidanceRequest(question_text="What to check?")
    assert m.asset_type is None


def test_assessor_guidance_request_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError) as exc_info:
        AssessorGuidanceRequest(
            question_text="What to check?",
            tenant_id=1,  # type: ignore[call-arg]
        )
    assert "tenant_id" in str(exc_info.value)
    assert "extra" in str(exc_info.value).lower() or "forbidden" in str(exc_info.value).lower()
