"""Unit tests for shared library file validation (F-1 / L-41)."""

from __future__ import annotations

import io
import zipfile
from unittest.mock import AsyncMock

import pytest

from src.domain.exceptions import FileValidationError
from src.infrastructure.file_validation import (
    refuse_ole2_or_macros,
    stub_malware_scan,
    validate_file_extension,
    validate_upload,
    verify_magic_number,
)


def test_refuse_ole2_magic() -> None:
    with pytest.raises(FileValidationError, match="OLE2"):
        refuse_ole2_or_macros(b"\xd0\xcf\x11\xe0" + b"rest", ".docx")


def test_refuse_legacy_extension() -> None:
    with pytest.raises(FileValidationError, match="not allowed"):
        validate_file_extension("policy.doc")


def test_docx_with_vba_project_refused() -> None:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("word/document.xml", "<w:document/>")
        zf.writestr("word/vbaProject.bin", b"macros")
    content = buf.getvalue()
    with pytest.raises(FileValidationError, match="Macro-enabled|vbaProject"):
        refuse_ole2_or_macros(content, ".docx")


def test_pdf_magic_ok() -> None:
    assert verify_magic_number(b"%PDF-1.7\n...", ".pdf") is True


def test_zip_magic_not_accepted_as_pdf() -> None:
    assert verify_magic_number(b"PK\x03\x04....", ".pdf") is False


def test_stub_scan_clean_for_payload() -> None:
    assert stub_malware_scan(b"%PDF-1.4") == "clean"


@pytest.mark.asyncio
async def test_validate_upload_pdf_ok() -> None:
    upload = AsyncMock()
    upload.filename = "policy.pdf"
    upload.read = AsyncMock(return_value=b"%PDF-1.4\n%EOF")
    upload.seek = AsyncMock()
    name, content, verdict = await validate_upload(upload)
    assert name.endswith(".pdf")
    assert content.startswith(b"%PDF")
    assert verdict == "clean"


@pytest.mark.asyncio
async def test_validate_upload_rejects_doc() -> None:
    upload = AsyncMock()
    upload.filename = "legacy.doc"
    upload.read = AsyncMock(return_value=b"\xd0\xcf\x11\xe0binary")
    upload.seek = AsyncMock()
    with pytest.raises(FileValidationError):
        await validate_upload(upload)
