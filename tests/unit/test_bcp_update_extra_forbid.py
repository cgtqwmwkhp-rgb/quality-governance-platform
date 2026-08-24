"""B-10: BCPUpdate must reject unknown body fields (extra=forbid)."""

import pytest
from pydantic import ValidationError

from src.api.routes.iso27001 import BCPUpdate


def test_bcp_update_accepts_known_fields() -> None:
    m = BCPUpdate(name="Updated BCP", is_active=False, rto_hours=8)
    assert m.name == "Updated BCP"
    assert m.is_active is False
    assert m.rto_hours == 8


def test_bcp_update_partial_ok() -> None:
    m = BCPUpdate(description="Updated recovery narrative for the plan.")
    assert m.description.startswith("Updated")
    assert m.name is None


def test_bcp_update_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError) as exc_info:
        BCPUpdate(
            name="Updated BCP",
            tenant_id=1,  # type: ignore[call-arg]
        )
    assert "tenant_id" in str(exc_info.value)
    assert "extra" in str(exc_info.value).lower() or "forbidden" in str(exc_info.value).lower()
