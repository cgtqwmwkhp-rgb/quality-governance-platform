"""B-10: AutoTagRequest must reject unknown body fields (extra=forbid)."""

import pytest
from pydantic import ValidationError

from src.api.routes.compliance import AutoTagRequest


def test_auto_tag_request_accepts_known_fields() -> None:
    m = AutoTagRequest(content="Working at height controls", min_confidence=40.0, use_ai=True)
    assert m.content == "Working at height controls"
    assert m.use_ai is True


def test_auto_tag_request_defaults() -> None:
    m = AutoTagRequest(content="Working at height controls")
    assert m.min_confidence == 30.0
    assert m.use_ai is False


def test_auto_tag_request_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError) as exc_info:
        AutoTagRequest(
            content="Working at height controls",
            tenant_id=1,  # type: ignore[call-arg]
        )
    assert "tenant_id" in str(exc_info.value)
    assert "extra" in str(exc_info.value).lower() or "forbidden" in str(exc_info.value).lower()
