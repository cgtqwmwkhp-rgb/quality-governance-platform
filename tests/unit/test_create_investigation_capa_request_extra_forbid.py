"""B-10: CreateInvestigationCapaRequest must reject unknown body fields (extra=forbid)."""

import pytest
from pydantic import ValidationError

from src.api.schemas.investigation import CreateInvestigationCapaRequest


def test_create_investigation_capa_request_accepts_why_link() -> None:
    m = CreateInvestigationCapaRequest(title="Install matting", why_level=3, five_whys_id=11)
    assert m.why_level == 3
    assert m.five_whys_id == 11


def test_create_investigation_capa_request_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError) as exc_info:
        CreateInvestigationCapaRequest(
            title="Install matting",
            invented="no",  # type: ignore[call-arg]
        )
    assert "invented" in str(exc_info.value)
    assert "extra" in str(exc_info.value).lower() or "forbidden" in str(exc_info.value).lower()
