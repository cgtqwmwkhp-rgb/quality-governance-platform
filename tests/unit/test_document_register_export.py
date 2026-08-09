"""Unit tests for IMS052 document register export (WA-3 / L-07)."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.domain.services.document_register_export import (
    IMS052_COLUMNS,
    build_register_row,
    rows_to_csv,
    rows_to_pdf,
    rows_to_xlsx,
    serialize_register,
)


def test_ims052_columns_contract_is_locked():
    assert IMS052_COLUMNS == (
        "PEL Reference",
        "Legacy IMS Ref",
        "Legacy PLA Ref",
        "Document Name",
        "Reference",
        "Issue",
        "Status",
        "Function",
        "Level",
        "Category",
        "Last Review Date",
        "Next Review Date",
        "Location",
        "Access Rights",
        "Retention",
        "Hyperlink",
    )
    assert len(IMS052_COLUMNS) == 16


def test_build_register_row_maps_fields_and_keeps_legacy_empty():
    doc = SimpleNamespace(
        id=42,
        pel_doc_ref="PEL-IT-2014",
        title="InfoSec Policy",
        reference_number="DOC-2026-0042",
        version="2.1",
        status=SimpleNamespace(value="approved"),
        cascade_level=2,
        reviewed_at=datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc),
        review_date=datetime(2027, 1, 15, 0, 0, tzinfo=timezone.utc),
        access_level="managers",
        retention_until=datetime(2031, 1, 15, 0, 0, tzinfo=timezone.utc),
    )
    row = build_register_row(
        doc,
        function_name="IT & Information Security",
        category_name="Policies",
        location_name="Head Office",
    )
    assert row[0] == "PEL-IT-2014"
    assert row[1] == ""  # Legacy IMS — no field yet
    assert row[2] == ""  # Legacy PLA — no field yet
    assert row[3] == "InfoSec Policy"
    assert row[4] == "DOC-2026-0042"
    assert row[5] == "2.1"
    assert row[6] == "approved"
    assert row[7] == "IT & Information Security"
    assert row[8] == "L2"  # NS-1 cascade level, matching the 2### band
    assert row[9] == "Policies"
    assert row[10] == "2026-01-15"  # reviewed_at = Last Review
    assert row[11] == "2027-01-15"  # review_date = Next Review
    assert row[12] == "Head Office"
    assert row[13] == "managers"
    assert row[14] == "2031-01-15"
    assert row[15] == "/documents/42"


def test_build_register_row_leaves_level_blank_for_a_legacy_unbanded_document():
    """A document filed before NS-1 has no level, and the register must not invent one."""
    doc = SimpleNamespace(
        id=7,
        pel_doc_ref="PEL-HSEQ-0001",
        title="Legacy Procedure",
        reference_number="DOC-2025-0007",
        version="1.0",
        status="approved",
        cascade_level=None,
        reviewed_at=None,
        review_date=None,
        access_level=None,
        retention_until=None,
    )
    assert build_register_row(doc)[8] == ""


def test_build_register_row_does_not_transpose_review_dates():
    doc = SimpleNamespace(
        id=1,
        pel_doc_ref=None,
        title="T",
        reference_number="DOC-1",
        version="1.0",
        status="pending",
        reviewed_at=datetime(2025, 6, 1, tzinfo=timezone.utc),
        review_date=datetime(2026, 6, 1, tzinfo=timezone.utc),
        access_level=None,
        retention_until=None,
    )
    row = build_register_row(doc)
    assert row[10] == "2025-06-01"
    assert row[11] == "2026-06-01"


def test_formula_injection_prefixed_in_title():
    doc = SimpleNamespace(
        id=9,
        pel_doc_ref=None,
        title='=HYPERLINK("http://evil")',
        reference_number="DOC-9",
        version="1.0",
        status="approved",
        reviewed_at=None,
        review_date=None,
        access_level="all_staff",
        retention_until=None,
    )
    row = build_register_row(doc)
    assert row[3].startswith("'=")


def test_pathological_title_survives_csv_round_trip():
    title = "A" * 500 + ',"newline\ninject"'
    doc = SimpleNamespace(
        id=3,
        pel_doc_ref="PEL-HSEQ-0001",
        title=title,
        reference_number="DOC-3",
        version="1.0",
        status="approved",
        reviewed_at=None,
        review_date=None,
        access_level="",
        retention_until=None,
    )
    rows = [build_register_row(doc)]
    csv_bytes = rows_to_csv(rows)
    text = csv_bytes.decode("utf-8")
    header = text.splitlines()[0]
    assert header == ",".join(IMS052_COLUMNS)
    assert "PEL-HSEQ-0001" in text
    assert "DOC-3" in text


def test_xlsx_and_csv_share_the_same_rows():
    doc = SimpleNamespace(
        id=5,
        pel_doc_ref="PEL-OPS-0002",
        title="Ops Manual",
        reference_number="DOC-5",
        version="3.0",
        status="indexed",
        reviewed_at=None,
        review_date=None,
        access_level="all_staff",
        retention_until=None,
    )
    rows = [build_register_row(doc)]
    import io

    from openpyxl import load_workbook

    wb = load_workbook(io.BytesIO(rows_to_xlsx(rows)))
    sheet = wb.active
    header = [cell.value for cell in sheet[1]]
    body = [cell.value for cell in sheet[2]]
    assert tuple(header) == IMS052_COLUMNS
    assert ["" if v is None else v for v in body] == rows[0]


def test_serialize_register_formats():
    rows = [
        build_register_row(
            SimpleNamespace(
                id=1,
                pel_doc_ref=None,
                title="T",
                reference_number="DOC-1",
                version="1.0",
                status="pending",
                reviewed_at=None,
                review_date=None,
                access_level=None,
                retention_until=None,
            )
        )
    ]
    csv_content, csv_type, csv_ext = serialize_register(rows, "csv")
    assert csv_ext == "csv"
    assert csv_type.startswith("text/csv")
    assert csv_content.startswith(b"PEL Reference")

    xlsx_content, xlsx_type, xlsx_ext = serialize_register(rows, "xlsx")
    assert xlsx_ext == "xlsx"
    assert "spreadsheetml" in xlsx_type
    assert xlsx_content[:2] == b"PK"

    pdf_content, pdf_type, pdf_ext = serialize_register(rows, "pdf")
    assert pdf_ext == "pdf"
    assert pdf_type == "application/pdf"
    assert pdf_content.startswith(b"%PDF")


def test_rows_to_pdf_emits_pdf_bytes():
    rows = [
        build_register_row(
            SimpleNamespace(
                id=2,
                pel_doc_ref="PEL-FAC-0001",
                title="Fire Plan",
                reference_number="DOC-2",
                version="1.0",
                status="approved",
                reviewed_at=None,
                review_date=None,
                access_level="all_staff",
                retention_until=None,
            )
        )
    ]
    assert rows_to_pdf(rows).startswith(b"%PDF")


@pytest.mark.asyncio
async def test_build_document_register_rows_filters_inactive_and_acl():
    from src.domain.services.document_register_export import build_document_register_rows

    active_ok = SimpleNamespace(
        id=1,
        tenant_id=1,
        is_active=True,
        category_id=None,
        function_id=None,
        site_location_id=None,
        access_level="all_staff",
        pel_doc_ref="PEL-IT-0001",
        title="Visible",
        reference_number="DOC-1",
        version="1.0",
        status="approved",
        reviewed_at=None,
        review_date=None,
        retention_until=None,
    )
    active_restricted = SimpleNamespace(
        id=2,
        tenant_id=1,
        is_active=True,
        category_id=99,
        function_id=None,
        site_location_id=None,
        access_level="restricted",
        pel_doc_ref=None,
        title="Hidden",
        reference_number="DOC-2",
        version="1.0",
        status="approved",
        reviewed_at=None,
        review_date=None,
        retention_until=None,
    )

    class _Scalars:
        def __init__(self, values):
            self._values = values

        def all(self):
            return list(self._values)

    class _Result:
        def __init__(self, *, scalar=None, values=None, pairs=None):
            self._scalar = scalar
            self._values = list(values or [])
            self._pairs = list(pairs or [])

        def scalar_one(self):
            return self._scalar

        def scalars(self):
            return _Scalars(self._values)

        def all(self):
            return list(self._pairs)

    # execute order: documents select, taxonomy for restricted
    db = SimpleNamespace(
        execute=AsyncMock(
            side_effect=[
                _Result(values=[active_ok, active_restricted]),
                _Result(pairs=[(99, "02.08")]),  # restricted OH taxonomy
            ]
        )
    )
    staff = SimpleNamespace(is_superuser=False, has_permission=lambda _p: False)
    rows, total, truncated = await build_document_register_rows(db, 1, user=staff, row_limit=10_000)
    assert len(rows) == 1
    assert rows[0][3] == "Visible"
    assert total == 1
    assert truncated is False


@pytest.mark.asyncio
async def test_build_document_register_rows_applies_acl_before_export_limit():
    from src.domain.models.document import Document
    from src.domain.services.document_register_export import build_document_register_rows

    def _doc(doc_id: int, title: str, access_level: str, category_id: int | None = None):
        return SimpleNamespace(
            id=doc_id,
            tenant_id=1,
            is_active=True,
            category_id=category_id,
            function_id=None,
            site_location_id=None,
            access_level=access_level,
            pel_doc_ref=None,
            title=title,
            reference_number=f"DOC-{doc_id}",
            version="1.0",
            status="approved",
            reviewed_at=None,
            review_date=None,
            retention_until=None,
        )

    documents = [
        _doc(5, "Newest hidden", "restricted", 99),
        _doc(4, "Second hidden", "restricted", 99),
        _doc(3, "Readable A", "all_staff"),
        _doc(2, "Readable B", "all_staff"),
        _doc(1, "Readable C", "all_staff"),
    ]

    class _Scalars:
        def __init__(self, values):
            self._values = values

        def all(self):
            return list(self._values)

    class _Result:
        def __init__(self, *, values=None, pairs=None):
            self._values = list(values or [])
            self._pairs = list(pairs or [])

        def scalars(self):
            return _Scalars(self._values)

        def all(self):
            return list(self._pairs)

    async def _execute(statement):
        entity = statement.column_descriptions[0].get("entity")
        if entity is Document:
            # Model database LIMIT behavior so this test regresses if the cap
            # is ever moved back ahead of the ACL filter.
            limit_clause = getattr(statement, "_limit_clause", None)
            selected = documents
            if limit_clause is not None:
                selected = selected[: int(limit_clause.value)]
            return _Result(values=selected)
        return _Result(pairs=[(99, "02.08")])

    db = SimpleNamespace(execute=AsyncMock(side_effect=_execute))
    staff = SimpleNamespace(is_superuser=False, has_permission=lambda _p: False)

    rows, total, truncated = await build_document_register_rows(db, 1, user=staff, row_limit=2)

    assert [row[3] for row in rows] == ["Readable A", "Readable B"]
    assert total == 3
    assert truncated is True
