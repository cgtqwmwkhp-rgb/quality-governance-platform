"""Documents list must not 500 on legacy JSON metadata shapes."""

from datetime import datetime, timezone
from types import SimpleNamespace

from src.api.routes.documents import (
    DocumentResponse,
    DocumentUploadResponse,
    _coerce_json_list,
    _document_reference_number,
    _document_to_response,
)


def test_coerce_json_list_drops_invalid_shapes():
    assert _coerce_json_list(["a"]) == ["a"]
    assert _coerce_json_list({"not": "a list"}) is None
    assert _coerce_json_list(None) is None


def _sample_doc(**overrides):
    base = dict(
        id=1,
        reference_number="DOC-1",
        title="Policy",
        description=None,
        file_name="policy.pdf",
        file_type=SimpleNamespace(value="pdf"),
        file_size=100,
        document_type=SimpleNamespace(value="policy"),
        category=None,
        department=None,
        sensitivity=SimpleNamespace(value="internal"),
        status=SimpleNamespace(value="approved"),
        version="1.0",
        ai_summary=None,
        ai_tags={"legacy": "dict"},
        ai_keywords="also-wrong",
        page_count=None,
        word_count=None,
        view_count=0,
        download_count=0,
        is_public=False,
        created_at=datetime.now(timezone.utc),
        indexed_at=None,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def test_document_to_response_tolerates_dict_ai_tags():
    response = _document_to_response(_sample_doc())
    assert isinstance(response, DocumentResponse)
    assert response.ai_tags is None
    assert response.ai_keywords is None


def test_document_reference_number_falls_back_when_null():
    assert _document_reference_number(_sample_doc(reference_number=None)) == "DOC-1"
    assert _document_reference_number(_sample_doc(id=42, reference_number=None)) == "DOC-42"
    assert _document_reference_number(_sample_doc(reference_number="  ")) == "DOC-1"


def test_document_to_response_tolerates_null_reference_number():
    response = _document_to_response(_sample_doc(id=7, reference_number=None))
    assert isinstance(response, DocumentResponse)
    assert response.reference_number == "DOC-7"


def test_document_upload_response_rejects_none_reference_number():
    """Guardrail: API contract requires a string reference (prod 500 root cause)."""
    try:
        DocumentUploadResponse(
            id=1,
            reference_number=None,  # type: ignore[arg-type]
            title="x",
            status="processing",
            message="ok",
        )
        raised = False
    except Exception:
        raised = True
    assert raised is True
