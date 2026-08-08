"""File upload security validation.

Enhances the shared library upload gate (F-1 / L-41). Callers must use
``validate_upload`` for both create and revise so parity is enforced in one place.
"""

from __future__ import annotations

import io
import os
import zipfile
from typing import Literal

from fastapi import UploadFile

from src.domain.exceptions import BadRequestError, FileValidationError

# Library FileType-aligned allowlist (OLE2 / macro types excluded).
ALLOWED_EXTENSIONS = {
    ".pdf",
    ".docx",
    ".xlsx",
    ".csv",
    ".md",
    ".txt",
    ".png",
    ".jpg",
    ".jpeg",
}

# OOXML packages that are ZIP-based but must never carry VBA.
_OOXML_EXTENSIONS = {".docx", ".xlsx"}

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB

OLE2_MAGIC = b"\xd0\xcf\x11\xe0"

MAGIC_NUMBERS = {
    b"%PDF": ".pdf",
    b"\x89PNG": ".png",
    b"\xff\xd8\xff": ".jpg",
    b"GIF87a": ".gif",
    b"GIF89a": ".gif",
    b"PK\x03\x04": ".zip",
    b"PK\x05\x06": ".zip",
}

ScanVerdict = Literal["clean", "failed"]


def validate_file_extension(filename: str) -> str:
    """Validate and sanitize filename. Returns sanitized filename."""
    if not filename:
        raise FileValidationError("Filename is required")
    sanitized = os.path.basename(filename)
    sanitized = "".join(c for c in sanitized if c.isalnum() or c in "._- ")

    _, ext = os.path.splitext(sanitized.lower())
    if ext not in ALLOWED_EXTENSIONS:
        raise FileValidationError(
            f"File type '{ext}' is not allowed. Allowed types: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )
    return sanitized


async def validate_file_content(file: UploadFile) -> bytes:
    """Read and validate file content. Returns file bytes."""
    content = await file.read()
    await file.seek(0)

    if len(content) > MAX_FILE_SIZE:
        raise BadRequestError(
            f"File size exceeds maximum of {MAX_FILE_SIZE // (1024 * 1024)}MB",
            code="FILE_TOO_LARGE",
        )

    if len(content) == 0:
        raise FileValidationError("Empty files are not allowed")

    return content


def refuse_ole2_or_macros(content: bytes, declared_extension: str) -> None:
    """Refuse OLE2 binaries and macro-enabled OOXML packages."""
    declared_ext = declared_extension.lower()

    if content.startswith(OLE2_MAGIC):
        raise FileValidationError(
            "OLE2 / legacy Office binaries are not allowed (macro risk). "
            "Export as .docx/.xlsx/.pdf and re-upload."
        )

    if declared_ext in {".doc", ".xls", ".ppt", ".docm", ".xlsm", ".pptm"}:
        raise FileValidationError(
            f"File type '{declared_ext}' is not allowed (macro-capable / legacy Office)."
        )

    if declared_ext in _OOXML_EXTENSIONS and content[:2] == b"PK":
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as zf:
                namelist = list(zf.namelist())
                names_lower = {name.lower() for name in namelist}
                if any("vbaproject.bin" in name for name in names_lower):
                    raise FileValidationError(
                        "Macro-enabled Office documents are not allowed "
                        "(vbaProject.bin detected)."
                    )
                content_types_name = next(
                    (n for n in namelist if n.lower().endswith("[content_types].xml")),
                    None,
                )
                xml = ""
                if content_types_name is not None:
                    try:
                        xml = zf.read(content_types_name).decode("utf-8", errors="ignore")
                    except Exception:
                        xml = ""
                if "vnd.ms-office.vbaProject" in xml or "macroEnabled" in xml:
                    raise FileValidationError(
                        "Macro-enabled Office documents are not allowed."
                    )
        except zipfile.BadZipFile as exc:
            raise FileValidationError("OOXML package is not a valid ZIP archive") from exc


def verify_magic_number(content: bytes, declared_extension: str) -> bool:
    """Verify file content matches declared type via magic numbers.

    Returns True if verification passes or if the type has no known magic number.
    """
    declared_ext = declared_extension.lower()

    for magic, ext in MAGIC_NUMBERS.items():
        if content[: len(magic)] == magic:
            if declared_ext in _OOXML_EXTENSIONS or declared_ext == ".zip":
                return ext == ".zip"
            if ext == ".jpg" and declared_ext == ".jpeg":
                return True
            # Never accept OLE2/legacy declared types via ZIP magic (previous bug).
            return ext == declared_ext

    return True


def stub_malware_scan(content: bytes) -> ScanVerdict:
    """v1 sync stub — real AV lands later as an async worker.

    Validation already refused OLE2/macros/mismatched magic. A non-empty payload
    that passed those gates is marked clean so signed-URL gating has a defined state.
    """
    if not content:
        return "failed"
    return "clean"


async def validate_upload(file: UploadFile) -> tuple[str, bytes, ScanVerdict]:
    """Full upload validation pipeline.

    Returns ``(sanitized_filename, content, scan_verdict)``.
    """
    sanitized_name = validate_file_extension(file.filename or "")
    content = await validate_file_content(file)

    _, ext = os.path.splitext(sanitized_name.lower())
    refuse_ole2_or_macros(content, ext)

    if not verify_magic_number(content, ext):
        raise FileValidationError("File content does not match declared file type")

    verdict = stub_malware_scan(content)
    if verdict != "clean":
        raise FileValidationError("File failed malware scan gate")

    return sanitized_name, content, verdict
