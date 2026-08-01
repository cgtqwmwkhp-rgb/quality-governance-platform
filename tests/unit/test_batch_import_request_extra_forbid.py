"""B-10: BatchImportRequest must reject unknown body fields (extra=forbid)."""

import pytest
from pydantic import ValidationError

from src.api.routes.xml_import import BatchImportRequest


def test_batch_import_request_accepts_known_fields() -> None:
    m = BatchImportRequest(directory_path="/tmp/xml-imports")
    assert m.directory_path == "/tmp/xml-imports"


def test_batch_import_request_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError) as exc_info:
        BatchImportRequest(
            directory_path="/tmp/xml-imports",
            tenant_id=1,  # type: ignore[call-arg]
        )
    assert "tenant_id" in str(exc_info.value)
    assert "extra" in str(exc_info.value).lower() or "forbidden" in str(exc_info.value).lower()
