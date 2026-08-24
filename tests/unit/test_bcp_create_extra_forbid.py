"""B-10: BCPCreate must reject unknown body fields (extra=forbid)."""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from src.api.routes.iso27001 import BCPCreate


def _valid_kwargs() -> dict:
    return {
        "name": "Core Systems BCP",
        "description": "Recovery plan for core data processing systems.",
        "scope": "Core data processing systems",
        "rto_hours": 4,
        "rpo_hours": 1,
        "effective_date": datetime(2026, 1, 1, tzinfo=timezone.utc),
    }


def test_bcp_create_accepts_known_fields() -> None:
    m = BCPCreate(**_valid_kwargs())
    assert m.name == "Core Systems BCP"
    assert m.rto_hours == 4
    assert m.test_frequency_months == 12
    assert m.version == "1.0"


def test_bcp_create_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError) as exc_info:
        BCPCreate(
            **_valid_kwargs(),
            tenant_id=1,  # type: ignore[call-arg]
        )
    assert "tenant_id" in str(exc_info.value)
    assert "extra" in str(exc_info.value).lower() or "forbidden" in str(exc_info.value).lower()
