import io
import sys
import zipfile
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from starlette.datastructures import Headers, UploadFile

from src.api.routes import documents
from src.domain.models.document import DocumentStatus, FileType


class FakeDbSession:
    def __init__(self) -> None:
        self.added: list[object] = []
        self.commits = 0
        self.rollbacks = 0
        self._next_id = 1

    def add(self, obj: object) -> None:
        self.added.append(obj)

    async def flush(self) -> None:
        for obj in self.added:
            if getattr(obj, "id", None) is None:
                setattr(obj, "id", self._next_id)
                self._next_id += 1
            if hasattr(obj, "reference_number") and not getattr(obj, "reference_number", None):
                setattr(obj, "reference_number", f"DOC-{getattr(obj, 'id')}")

    async def commit(self) -> None:
        self.commits += 1

    async def refresh(self, obj: object) -> None:
        if hasattr(obj, "reference_number") and not getattr(obj, "reference_number", None):
            setattr(obj, "reference_number", f"DOC-{getattr(obj, 'id', 0) or 1}")

    async def rollback(self) -> None:
        self.rollbacks += 1


def _build_docx_bytes(text: str) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(
            "word/document.xml",
            f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
            <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
              <w:body>
                <w:p><w:r><w:t>{text}</w:t></w:r></w:p>
              </w:body>
            </w:document>""",
        )
    return buffer.getvalue()


def _build_xlsx_bytes() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(
            "xl/sharedStrings.xml",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
            <sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
              <si><t>Header</t></si>
              <si><t>Row Value</t></si>
            </sst>""",
        )
        archive.writestr(
            "xl/worksheets/sheet1.xml",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
            <worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
              <sheetData>
                <row r="1"><c r="A1" t="s"><v>0</v></c></row>
                <row r="2"><c r="A2" t="s"><v>1</v></c></row>
              </sheetData>
            </worksheet>""",
        )
    return buffer.getvalue()


def _make_upload_file(filename: str, content: bytes, content_type: str) -> UploadFile:
    return UploadFile(file=io.BytesIO(content), filename=filename, headers=Headers({"content-type": content_type}))


def test_extract_document_content_reads_docx_text() -> None:
    result = documents._extract_document_content(FileType.DOCX, "policy.docx", _build_docx_bytes("Policy controls"))

    assert result.text == "Policy controls"
    assert result.note is None


def test_extract_document_content_reads_xlsx_rows() -> None:
    result = documents._extract_document_content(FileType.XLSX, "register.xlsx", _build_xlsx_bytes())

    assert "Header" in result.text
    assert "Row Value" in result.text
    assert result.sheet_count == 1
    assert result.has_tables is True


def test_extract_pdf_text_uses_reader_when_available(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakePage:
        def __init__(self, text: str) -> None:
            self._text = text

        def extract_text(self) -> str:
            return self._text

    class FakeReader:
        def __init__(self, _stream: io.BytesIO) -> None:
            self.pages = [FakePage("Audit report page 1"), FakePage("Audit report page 2")]

    monkeypatch.setitem(sys.modules, "pypdf", SimpleNamespace(PdfReader=FakeReader))

    result = documents._extract_pdf_text(b"%PDF-1.4", "audit-report.pdf")

    assert "Audit report page 1" in result.text
    assert result.page_count == 2
    assert result.note is None


@pytest.mark.asyncio
async def test_upload_document_persists_blob_and_returns_status(monkeypatch: pytest.MonkeyPatch) -> None:
    db = FakeDbSession()
    current_user = SimpleNamespace(id=7, tenant_id=22, is_superuser=False)
    upload_file = _make_upload_file("governance.md", b"# Governance\nDocumented control.\n", "text/markdown")

    upload_mock = AsyncMock(return_value="documents/2026/03/test/governance.md")
    monkeypatch.setattr(documents, "storage_service", lambda: SimpleNamespace(upload=upload_mock))

    async def fake_process(*_args, **_kwargs) -> None:
        doc = _args[1]
        doc.status = DocumentStatus.APPROVED
        doc.ai_summary = "Processed"

    monkeypatch.setattr(documents, "_process_uploaded_document", fake_process)

    response = await documents.upload_document(
        db=db,
        current_user=current_user,
        file=upload_file,
        title="Governance",
        description="Document library upload",
        document_type="other",
        category=None,
        department=None,
        sensitivity="internal",
    )

    stored_document = db.added[0]
    assert response.status == "approved"
    assert response.id == stored_document.id
    assert stored_document.file_path.startswith("documents/")
    upload_mock.assert_awaited_once()
    assert upload_mock.await_args.kwargs["storage_key"] == stored_document.file_path
    assert upload_mock.await_args.kwargs["metadata"]["uploaded_by"] == "7"


@pytest.mark.asyncio
async def test_get_document_signed_url_increments_download_count(monkeypatch: pytest.MonkeyPatch) -> None:
    db = FakeDbSession()
    current_user = SimpleNamespace(id=3, tenant_id=9, is_superuser=False)
    document = SimpleNamespace(
        id=15,
        file_name="policy.pdf",
        file_path="documents/2026/03/policy.pdf",
        download_count=2,
        mime_type="application/pdf",
        last_accessed_at=None,
    )

    monkeypatch.setattr(documents, "_get_document_or_404", AsyncMock(return_value=document))
    monkeypatch.setattr(
        documents,
        "storage_service",
        lambda: SimpleNamespace(get_signed_url=lambda **kwargs: "/api/v1/evidence-assets/download?key=test"),
    )

    response = await documents.get_document_signed_url(document_id=15, db=db, current_user=current_user, expires_in=3600)

    assert response.document_id == 15
    assert response.signed_url.endswith("key=test")
    assert document.download_count == 3
    assert db.commits == 1
