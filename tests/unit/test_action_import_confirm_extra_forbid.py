"""B-10: ActionImportConfirm must reject unknown body fields (extra=forbid)."""

import pytest
from pydantic import ValidationError

from src.api.routes.planet_mark import ActionImportConfirm


def test_action_import_confirm_accepts_known_fields() -> None:
    m = ActionImportConfirm(session_id="sess-1", selected_indices=[0, 2])
    assert m.session_id == "sess-1"
    assert m.selected_indices == [0, 2]


def test_action_import_confirm_selected_indices_optional() -> None:
    m = ActionImportConfirm(session_id="sess-2")
    assert m.selected_indices is None


def test_action_import_confirm_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError) as exc_info:
        ActionImportConfirm(
            session_id="sess-1",
            tenant_id=1,  # type: ignore[call-arg]
        )
    assert "tenant_id" in str(exc_info.value)
    assert "extra" in str(exc_info.value).lower() or "forbidden" in str(exc_info.value).lower()
