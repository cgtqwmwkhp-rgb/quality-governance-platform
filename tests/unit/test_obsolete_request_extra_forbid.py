"""B-10: ObsoleteRequest must reject unknown body fields (extra=forbid)."""

import pytest
from pydantic import ValidationError

from src.api.routes.document_control import ObsoleteRequest


def test_obsolete_request_accepts_known_fields() -> None:
    m = ObsoleteRequest(
        obsolete_reason="Superseded by the 2026 procedure rewrite",
        superseded_by_id=42,
    )
    assert m.obsolete_reason == "Superseded by the 2026 procedure rewrite"
    assert m.superseded_by_id == 42


def test_obsolete_request_superseded_optional() -> None:
    m = ObsoleteRequest(obsolete_reason="No longer applicable after org change")
    assert m.superseded_by_id is None


def test_obsolete_request_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError) as exc_info:
        ObsoleteRequest(
            obsolete_reason="No longer applicable after org change",
            tenant_id=1,  # type: ignore[call-arg]
        )
    assert "tenant_id" in str(exc_info.value)
    assert "extra" in str(exc_info.value).lower() or "forbidden" in str(exc_info.value).lower()
