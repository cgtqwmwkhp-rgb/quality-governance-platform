"""B-10: DefectCAPARequest must reject unknown body fields (extra=forbid)."""

import pytest
from pydantic import ValidationError

from src.api.routes.vehicles import DefectCAPARequest


def test_defect_capa_request_accepts_known_fields() -> None:
    m = DefectCAPARequest(defect_id=42)
    assert m.defect_id == 42


def test_defect_capa_request_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError) as exc_info:
        DefectCAPARequest(
            defect_id=42,
            tenant_id=1,  # type: ignore[call-arg]
        )
    assert "tenant_id" in str(exc_info.value)
    assert "extra" in str(exc_info.value).lower() or "forbidden" in str(exc_info.value).lower()
