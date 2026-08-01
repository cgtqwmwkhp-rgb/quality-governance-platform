"""B-10: CAPAStatusTransition must reject unknown body fields (extra=forbid)."""

import pytest
from pydantic import ValidationError

from src.api.routes.capa import CAPAStatusTransition
from src.domain.models.capa import CAPAStatus


def test_capa_status_transition_accepts_known_fields() -> None:
    m = CAPAStatusTransition(status=CAPAStatus.IN_PROGRESS, comment="Started")
    assert m.status == CAPAStatus.IN_PROGRESS
    assert m.comment == "Started"


def test_capa_status_transition_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError) as exc_info:
        CAPAStatusTransition(
            status=CAPAStatus.IN_PROGRESS,
            tenant_id=1,  # type: ignore[call-arg]
        )
    assert "tenant_id" in str(exc_info.value)
    assert "extra" in str(exc_info.value).lower() or "forbidden" in str(exc_info.value).lower()
