"""B-10: CreateExportRequest must reject unknown body fields (extra=forbid)."""

import pytest
from pydantic import ValidationError

from src.api.schemas.exports import CreateExportRequest


def test_create_export_request_accepts_known_fields() -> None:
    m = CreateExportRequest(module="incidents", format="csv")
    assert m.module == "incidents"
    assert m.format == "csv"


def test_create_export_request_accepts_xlsx_and_pdf() -> None:
    assert CreateExportRequest(module="documents", format="xlsx").format == "xlsx"
    assert CreateExportRequest(module="documents", format="pdf").format == "pdf"


def test_create_export_request_format_defaults_to_csv() -> None:
    m = CreateExportRequest(module="actions")
    assert m.format == "csv"


def test_create_export_request_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError) as exc_info:
        CreateExportRequest(
            module="audits",
            format="csv",
            tenant_id=99,  # type: ignore[call-arg]
        )
    assert "tenant_id" in str(exc_info.value)
    assert "extra" in str(exc_info.value).lower() or "forbidden" in str(exc_info.value).lower()


def test_create_export_request_rejects_column_picker_fields() -> None:
    """WA-3 / L-07: column pickers must not reach the IMS052 builder."""
    for forbidden_key in ("columns", "fields", "visible_columns"):
        with pytest.raises(ValidationError) as exc_info:
            CreateExportRequest(
                module="documents",
                format="csv",
                **{forbidden_key: ["Document Name"]},  # type: ignore[arg-type]
            )
        assert forbidden_key in str(exc_info.value).lower()
