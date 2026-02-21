"""File upload security validation."""

import os
from typing import BinaryIO

from fastapi import HTTPException, UploadFile, status

ALLOWED_EXTENSIONS = {
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".png", ".jpg", ".jpeg", ".gif", ".webp",
    ".csv", ".txt", ".json", ".xml",
    ".zip",
}

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB

MAGIC_NUMBERS = {
    b'%PDF': '.pdf',
    b'\x89PNG': '.png',
    b'\xff\xd8\xff': '.jpg',
    b'GIF87a': '.gif',
    b'GIF89a': '.gif',
    b'PK\x03\x04': '.zip',
    b'PK\x05\x06': '.zip',
}


def validate_file_extension(filename: str) -> str:
    """Validate and sanitize filename. Returns sanitized filename."""
    if not filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename is required",
        )
    sanitized = os.path.basename(filename)
    sanitized = "".join(c for c in sanitized if c.isalnum() or c in "._- ")

    _, ext = os.path.splitext(sanitized.lower())
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type '{ext}' is not allowed. Allowed types: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )
    return sanitized


async def validate_file_content(file: UploadFile) -> bytes:
    """Read and validate file content. Returns file bytes."""
    content = await file.read()
    await file.seek(0)

    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size exceeds maximum of {MAX_FILE_SIZE // (1024*1024)}MB",
        )

    if len(content) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Empty files are not allowed",
        )

    return content


def verify_magic_number(content: bytes, declared_extension: str) -> bool:
    """Verify file content matches declared type via magic numbers.

    Returns True if verification passes or if the type has no known magic number.
    """
    declared_ext = declared_extension.lower()

    for magic, ext in MAGIC_NUMBERS.items():
        if content[:len(magic)] == magic:
            if declared_ext in ('.zip', '.docx', '.xlsx', '.pptx'):
                if ext == '.zip':
                    return True
            return ext == declared_ext or (
                ext == '.jpg' and declared_ext == '.jpeg'
            ) or (
                declared_ext in ('.doc', '.xls', '.ppt') and ext == '.zip'
            )

    return True


async def validate_upload(file: UploadFile) -> tuple[str, bytes]:
    """Full upload validation pipeline. Returns (sanitized_filename, content)."""
    sanitized_name = validate_file_extension(file.filename or "")
    content = await validate_file_content(file)

    _, ext = os.path.splitext(sanitized_name.lower())
    if not verify_magic_number(content, ext):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File content does not match declared file type",
        )

    return sanitized_name, content
