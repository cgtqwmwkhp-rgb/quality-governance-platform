"""Tests for file upload security validation."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from src.infrastructure.file_validation import (
    ALLOWED_EXTENSIONS,
    MAX_FILE_SIZE,
    validate_file_extension,
    verify_magic_number,
)


class TestFileValidation:
    """Tests for file validation utilities."""

    def test_valid_extension(self):
        """Test valid file extensions are accepted."""
        for ext in [".pdf", ".docx", ".png", ".csv", ".json"]:
            result = validate_file_extension(f"test{ext}")
            assert result.endswith(ext) or result.endswith(ext.replace(".", ""))

    def test_invalid_extension(self):
        """Test invalid extensions are rejected."""
        with pytest.raises(HTTPException) as exc_info:
            validate_file_extension("malware.exe")
        assert exc_info.value.status_code == 400

    def test_empty_filename(self):
        """Test empty filename is rejected."""
        with pytest.raises(HTTPException) as exc_info:
            validate_file_extension("")
        assert exc_info.value.status_code == 400

    def test_filename_sanitization(self):
        """Test path traversal in filename is sanitized."""
        result = validate_file_extension("../../etc/passwd.pdf")
        assert "/" not in result
        assert ".." not in result

    def test_pdf_magic_number(self):
        """Test PDF magic number verification."""
        pdf_content = b"%PDF-1.4 rest of file..."
        assert verify_magic_number(pdf_content, ".pdf") is True

    def test_png_magic_number(self):
        """Test PNG magic number verification."""
        png_content = b"\x89PNG\r\n\x1a\n rest of file..."
        assert verify_magic_number(png_content, ".png") is True

    def test_mismatched_magic_number(self):
        """Test mismatched magic number is detected."""
        pdf_content = b"%PDF-1.4 rest of file..."
        result = verify_magic_number(pdf_content, ".png")
        assert result is False

    def test_unknown_magic_number_passes(self):
        """Test files without known magic numbers pass."""
        csv_content = b"name,value\nfoo,bar"
        assert verify_magic_number(csv_content, ".csv") is True

    def test_allowed_extensions_list(self):
        """Test that all expected extensions are in the allowlist."""
        expected = {".pdf", ".doc", ".docx", ".xlsx", ".png", ".jpg", ".csv", ".json", ".xml"}
        assert expected.issubset(ALLOWED_EXTENSIONS)

    def test_max_file_size(self):
        """Test max file size is reasonable."""
        assert MAX_FILE_SIZE == 50 * 1024 * 1024
