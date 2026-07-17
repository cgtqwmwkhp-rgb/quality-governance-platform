"""Documents list must not 500 on legacy JSON metadata shapes."""

from datetime import datetime, timezone
from types import SimpleNamespace

from src.api.routes.documents import DocumentResponse, _coerce_json_list, _document_to_response


def test_coerce_json_list_drops_invalid_shapes():
    assert _coerce_json_list(["a"]) == ["a"]
    assert _coerce_json_list({"not": "a list"}) is None
    assert _coerce_json_list(None) is None


def test_document_to_response_tolerates_dict_ai_tags():
    doc = SimpleNamespace(
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

    response = _document_to_response(doc)
    assert isinstance(response, DocumentResponse)
    assert response.ai_tags is None
    assert response.ai_keywords is None
