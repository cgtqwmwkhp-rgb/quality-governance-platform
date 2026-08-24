"""B-10: BowTieElementCreate must reject unknown body fields (extra=forbid)."""

import pytest
from pydantic import ValidationError

from src.api.routes.risk_register import BowTieElementCreate


def test_bowtie_element_create_accepts_known_fields() -> None:
    m = BowTieElementCreate(element_type="cause", title="Human error at handoff")
    assert m.element_type == "cause"
    assert m.is_escalation_factor is False


def test_bowtie_element_create_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError) as exc_info:
        BowTieElementCreate(
            element_type="cause",
            title="Human error at handoff",
            tenant_id=1,  # type: ignore[call-arg]
        )
    assert "tenant_id" in str(exc_info.value)
    assert "extra" in str(exc_info.value).lower() or "forbidden" in str(exc_info.value).lower()
