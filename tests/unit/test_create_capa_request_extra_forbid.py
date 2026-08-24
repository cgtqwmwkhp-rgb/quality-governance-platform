"""B-10: CreateCAPARequest must reject unknown body fields (extra=forbid)."""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from src.api.routes.rca_tools import CreateCAPARequest


def test_create_capa_request_accepts_known_fields() -> None:
    m = CreateCAPARequest(
        action_type="corrective",
        title="Replace brake pads",
        description="Worn pads caused stopping distance exceedance",
        priority="high",
        due_date=datetime(2026, 8, 1, tzinfo=timezone.utc),
    )
    assert m.action_type == "corrective"
    assert m.title == "Replace brake pads"
    assert m.priority == "high"


def test_create_capa_request_defaults() -> None:
    m = CreateCAPARequest(
        action_type="preventive",
        title="Update checklist",
        description="Add brake inspection step",
    )
    assert m.priority == "medium"
    assert m.five_whys_id is None


def test_create_capa_request_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError) as exc_info:
        CreateCAPARequest(
            action_type="corrective",
            title="Replace brake pads",
            description="Worn pads",
            tenant_id=1,  # type: ignore[call-arg]
        )
    assert "tenant_id" in str(exc_info.value)
    assert "extra" in str(exc_info.value).lower() or "forbidden" in str(exc_info.value).lower()
