"""B-10: AnnotationCreate must reject unknown body fields (extra=forbid)."""

import pytest
from pydantic import ValidationError

from src.api.routes.documents import AnnotationCreate


def test_annotation_create_accepts_known_fields() -> None:
    m = AnnotationCreate(
        page_number=2,
        section_id="intro",
        highlight_text="clause",
        annotation_text="Review this",
        color="blue",
        annotation_type="highlight",
        is_shared=True,
    )
    assert m.annotation_text == "Review this"
    assert m.color == "blue"
    assert m.is_shared is True


def test_annotation_create_defaults() -> None:
    m = AnnotationCreate(annotation_text="note")
    assert m.color == "yellow"
    assert m.annotation_type == "note"
    assert m.is_shared is False
    assert m.page_number is None


def test_annotation_create_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError) as exc_info:
        AnnotationCreate(
            annotation_text="note",
            tenant_id=1,  # type: ignore[call-arg]
        )
    assert "tenant_id" in str(exc_info.value)
    assert "extra" in str(exc_info.value).lower() or "forbidden" in str(exc_info.value).lower()
