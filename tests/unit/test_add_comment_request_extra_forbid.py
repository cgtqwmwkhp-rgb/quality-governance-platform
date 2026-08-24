"""B-10: AddCommentRequest must reject unknown body fields (extra=forbid)."""

import pytest
from pydantic import ValidationError

from src.api.routes.investigations import AddCommentRequest


def test_add_comment_request_accepts_known_fields() -> None:
    m = AddCommentRequest(
        content="Looks good",
        section_id="s1",
        field_id="f1",
        parent_comment_id=9,
    )
    assert m.content == "Looks good"
    assert m.section_id == "s1"
    assert m.parent_comment_id == 9


def test_add_comment_request_body_alias_maps_to_content() -> None:
    m = AddCommentRequest(body="via body")  # type: ignore[call-arg]
    assert m.content == "via body"


def test_add_comment_request_optionals_default_none() -> None:
    m = AddCommentRequest(content="hi")
    assert m.section_id is None
    assert m.field_id is None
    assert m.parent_comment_id is None


def test_add_comment_request_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError) as exc_info:
        AddCommentRequest(
            content="hi",
            tenant_id=1,  # type: ignore[call-arg]
        )
    assert "tenant_id" in str(exc_info.value)
    assert "extra" in str(exc_info.value).lower() or "forbidden" in str(exc_info.value).lower()
