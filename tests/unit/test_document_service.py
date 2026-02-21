"""Unit tests for document upload validation and metadata extraction."""

import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from src.domain.services.document_ai_service import DocumentAIService, DocumentAnalysis  # noqa: E402
from src.infrastructure.file_validation import (  # noqa: E402
    ALLOWED_EXTENSIONS,
    MAGIC_NUMBERS,
    MAX_FILE_SIZE,
    validate_file_content,
    validate_file_extension,
    validate_upload,
    verify_magic_number,
)

# ---------------------------------------------------------------------------
# File extension validation
# ---------------------------------------------------------------------------


def test_valid_pdf_extension():
    """PDF extension is accepted and filename is sanitized."""
    result = validate_file_extension("report.pdf")
    assert result.endswith(".pdf")


def test_valid_docx_extension():
    """DOCX extension is accepted."""
    result = validate_file_extension("document.docx")
    assert ".docx" in result.lower()


def test_reject_executable():
    """Executable extensions are rejected with HTTP 400."""
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc_info:
        validate_file_extension("virus.exe")
    assert exc_info.value.status_code == 400


def test_reject_script_extension():
    """Script extensions (.sh) are rejected."""
    from fastapi import HTTPException

    with pytest.raises(HTTPException):
        validate_file_extension("hack.sh")


def test_reject_empty_filename():
    """Empty filename raises HTTP 400."""
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc_info:
        validate_file_extension("")
    assert exc_info.value.status_code == 400


def test_path_traversal_sanitized():
    """Path traversal characters are stripped from filenames."""
    result = validate_file_extension("../../etc/passwd.pdf")
    assert ".." not in result
    assert "/" not in result


# ---------------------------------------------------------------------------
# File content / size validation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_validate_file_content_rejects_oversized():
    """File exceeding MAX_FILE_SIZE is rejected with 413."""
    from fastapi import HTTPException

    mock_file = AsyncMock()
    mock_file.read.return_value = b"x" * (MAX_FILE_SIZE + 1)

    with pytest.raises(HTTPException) as exc_info:
        await validate_file_content(mock_file)
    assert exc_info.value.status_code == 413


@pytest.mark.asyncio
async def test_validate_file_content_rejects_empty():
    """Empty file is rejected with 400."""
    from fastapi import HTTPException

    mock_file = AsyncMock()
    mock_file.read.return_value = b""

    with pytest.raises(HTTPException) as exc_info:
        await validate_file_content(mock_file)
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_validate_file_content_accepts_valid():
    """Valid-sized file content is returned as bytes."""
    mock_file = AsyncMock()
    mock_file.read.return_value = b"valid file content here"

    result = await validate_file_content(mock_file)
    assert result == b"valid file content here"
    mock_file.seek.assert_awaited_once_with(0)


# ---------------------------------------------------------------------------
# Magic number verification
# ---------------------------------------------------------------------------


def test_pdf_magic_number_matches():
    """PDF magic number (%PDF) matches .pdf extension."""
    assert verify_magic_number(b"%PDF-1.7 content...", ".pdf") is True


def test_png_magic_number_matches():
    """PNG magic number matches .png extension."""
    assert verify_magic_number(b"\x89PNG\r\n\x1a\n content", ".png") is True


def test_jpg_magic_number_matches():
    """JPEG magic number matches .jpg extension."""
    assert verify_magic_number(b"\xff\xd8\xff content", ".jpg") is True


def test_magic_number_mismatch():
    """PDF content declared as .png is rejected."""
    assert verify_magic_number(b"%PDF-1.4 content", ".png") is False


def test_unknown_extension_passes():
    """File type without a known magic number always passes."""
    assert verify_magic_number(b"name,value\n1,2", ".csv") is True


# ---------------------------------------------------------------------------
# Document metadata extraction (fallback analysis)
# ---------------------------------------------------------------------------


def test_fallback_detects_manual_type():
    """Filename containing 'manual' sets document_type to 'manual'."""
    with patch("src.domain.services.document_ai_service.settings"):
        svc = DocumentAIService()
    result = svc._fallback_analysis("content here", "safety_manual_v2.pdf")
    assert result.document_type == "manual"


def test_fallback_detects_guideline_type():
    """Filename containing 'guide' sets document_type to 'guideline'."""
    with patch("src.domain.services.document_ai_service.settings"):
        svc = DocumentAIService()
    result = svc._fallback_analysis("content", "user_guide.pdf")
    assert result.document_type == "guideline"


def test_fallback_detects_form_type():
    """Filename containing 'form' sets document_type to 'form'."""
    with patch("src.domain.services.document_ai_service.settings"):
        svc = DocumentAIService()
    result = svc._fallback_analysis("content", "incident_form.docx")
    assert result.document_type == "form"


def test_fallback_detects_faq_type():
    """Filename containing 'faq' sets document_type to 'faq'."""
    with patch("src.domain.services.document_ai_service.settings"):
        svc = DocumentAIService()
    result = svc._fallback_analysis("content", "employee_faq.pdf")
    assert result.document_type == "faq"


def test_fallback_extracts_top_keywords():
    """Fallback analysis extracts up to 10 keywords sorted by frequency."""
    with patch("src.domain.services.document_ai_service.settings"):
        svc = DocumentAIService()
    content = " ".join(["safety"] * 20 + ["inspection"] * 15 + ["policy"] * 10)
    result = svc._fallback_analysis(content, "report.txt")
    assert "safety" in result.keywords
    assert len(result.keywords) <= 10


def test_fallback_sensitivity_is_internal():
    """Fallback analysis defaults sensitivity to 'internal'."""
    with patch("src.domain.services.document_ai_service.settings"):
        svc = DocumentAIService()
    result = svc._fallback_analysis("any content", "doc.pdf")
    assert result.sensitivity == "internal"


if __name__ == "__main__":
    print("=" * 60)
    print("DOCUMENT SERVICE UNIT TESTS")
    print("=" * 60)

    test_valid_pdf_extension()
    test_valid_docx_extension()
    test_reject_executable()
    test_reject_script_extension()
    test_reject_empty_filename()
    test_path_traversal_sanitized()
    print("  File extension validation passed")

    test_pdf_magic_number_matches()
    test_png_magic_number_matches()
    test_jpg_magic_number_matches()
    test_magic_number_mismatch()
    test_unknown_extension_passes()
    print("  Magic number verification passed")

    test_fallback_detects_manual_type()
    test_fallback_detects_guideline_type()
    test_fallback_detects_form_type()
    test_fallback_detects_faq_type()
    test_fallback_extracts_top_keywords()
    test_fallback_sensitivity_is_internal()
    print("  Metadata extraction passed")

    print()
    print("ALL DOCUMENT SERVICE TESTS PASSED")
    print("=" * 60)
