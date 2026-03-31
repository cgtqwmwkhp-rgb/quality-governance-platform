"""Shared document extraction service for reusable native text extraction."""

from __future__ import annotations

import csv
import io
import logging
import zipfile
from dataclasses import dataclass, field

from defusedxml import ElementTree as ET

from src.domain.models.document import FileType

logger = logging.getLogger(__name__)


@dataclass
class ExtractedDocumentContent:
    """Normalized extraction result shared across document and audit workflows."""

    text: str
    page_count: int | None = None
    sheet_count: int | None = None
    has_tables: bool = False
    note: str | None = None
    page_texts: list[str] = field(default_factory=list)
    extraction_method: str = "native"


def extract_document_content(file_type: FileType, file_name: str, content: bytes) -> ExtractedDocumentContent:
    """Return searchable text for supported document formats."""
    if file_type in {FileType.TXT, FileType.MD}:
        return ExtractedDocumentContent(text=content.decode("utf-8", errors="ignore"))

    if file_type == FileType.CSV:
        decoded = content.decode("utf-8", errors="ignore")
        rows = [", ".join(cell.strip() for cell in row if cell.strip()) for row in csv.reader(io.StringIO(decoded))]
        filtered_rows = [row for row in rows if row]
        return ExtractedDocumentContent(text="\n".join(filtered_rows), has_tables=bool(filtered_rows))

    if file_type == FileType.PDF:
        return _extract_pdf_text(content, file_name)

    if file_type == FileType.DOCX:
        return _extract_docx_text(content, file_name)

    if file_type == FileType.XLSX:
        return _extract_xlsx_text(content, file_name)

    unsupported_notes = {
        FileType.DOC: "Stored successfully but legacy .doc extraction is not supported yet.",
        FileType.XLS: "Stored successfully but legacy .xls extraction is not supported yet.",
        FileType.PNG: "Stored successfully but image OCR is not supported yet.",
        FileType.JPG: "Stored successfully but image OCR is not supported yet.",
        FileType.JPEG: "Stored successfully but image OCR is not supported yet.",
    }
    return ExtractedDocumentContent(text="", note=unsupported_notes.get(file_type))


def _extract_pdf_text(content: bytes, file_name: str) -> ExtractedDocumentContent:
    """Extract searchable text from PDF using pdfplumber (table-aware) with pypdf fallback."""
    plumber_result = _extract_pdf_via_pdfplumber(content, file_name)
    if plumber_result is not None:
        return plumber_result

    try:
        from pypdf import PdfReader
    except ImportError:
        logger.warning("PDF extraction dependency missing for %s", file_name)
        return ExtractedDocumentContent(
            text="",
            note="Stored successfully but PDF extraction is unavailable in this environment.",
        )

    try:
        reader = PdfReader(io.BytesIO(content))
        page_text = [(page.extract_text() or "").strip() for page in reader.pages]
        filtered_pages = [part for part in page_text if part]
        text = "\n\n".join(filtered_pages)
        return ExtractedDocumentContent(
            text=text,
            page_count=len(reader.pages),
            page_texts=page_text,
        )
    except Exception as exc:
        logger.warning("PDF extraction failed for %s: %s", file_name, type(exc).__name__)
        return ExtractedDocumentContent(
            text="",
            note=f"Stored successfully but PDF extraction failed for {file_name}.",
        )


def _extract_pdf_via_pdfplumber(content: bytes, file_name: str) -> ExtractedDocumentContent | None:
    """Use pdfplumber for table-aware PDF extraction. Returns None if unavailable."""
    try:
        import pdfplumber  # noqa: F811
    except ImportError:
        return None

    try:
        page_texts: list[str] = []
        has_tables = False
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            page_count = len(pdf.pages)
            for page in pdf.pages:
                parts: list[str] = []
                tables = page.extract_tables()
                if tables:
                    has_tables = True
                    for table in tables:
                        for row in table:
                            cells = [str(c).strip() for c in row if c]
                            if cells:
                                parts.append(" | ".join(cells))
                plain = page.extract_text()
                if plain:
                    parts.append(plain.strip())
                page_texts.append("\n".join(parts))

        filtered = [p for p in page_texts if p.strip()]
        text = "\n\n".join(filtered)
        if not text.strip():
            return None

        return ExtractedDocumentContent(
            text=text,
            page_count=page_count,
            page_texts=page_texts,
            has_tables=has_tables,
            extraction_method="pdfplumber",
        )
    except Exception as exc:
        logger.warning("pdfplumber extraction failed for %s: %s — falling back to pypdf", file_name, type(exc).__name__)
        return None


def _extract_docx_text(content: bytes, file_name: str) -> ExtractedDocumentContent:
    """Extract text from DOCX packages without optional dependencies."""
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            document_xml = archive.read("word/document.xml")
    except Exception as exc:
        logger.warning("DOCX extraction failed for %s: %s", file_name, type(exc).__name__)
        return ExtractedDocumentContent(
            text="",
            note=f"Stored successfully but DOCX extraction failed for {file_name}.",
        )

    root = ET.fromstring(document_xml)
    paragraphs: list[str] = []
    for paragraph in root.iter():
        if paragraph.tag.endswith("}p"):
            runs = [node.text or "" for node in paragraph.iter() if node.tag.endswith("}t") and node.text]
            joined = "".join(runs).strip()
            if joined:
                paragraphs.append(joined)
    return ExtractedDocumentContent(text="\n".join(paragraphs))


def _read_xlsx_shared_strings(archive: zipfile.ZipFile) -> list[str]:
    """Load workbook shared strings for cell lookup."""
    try:
        raw = archive.read("xl/sharedStrings.xml")
    except KeyError:
        return []

    root = ET.fromstring(raw)
    values: list[str] = []
    for string_item in root.iter():
        if string_item.tag.endswith("}si"):
            parts = [node.text or "" for node in string_item.iter() if node.tag.endswith("}t") and node.text]
            values.append("".join(parts))
    return values


def _extract_xlsx_text(content: bytes, file_name: str) -> ExtractedDocumentContent:
    """Extract text rows from XLSX packages for indexing."""
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            shared_strings = _read_xlsx_shared_strings(archive)
            sheet_paths = sorted(name for name in archive.namelist() if name.startswith("xl/worksheets/sheet"))
            sheet_lines: list[str] = []

            for idx, sheet_path in enumerate(sheet_paths, start=1):
                root = ET.fromstring(archive.read(sheet_path))
                rows: list[str] = []
                for row in root.iter():
                    if not row.tag.endswith("}row"):
                        continue
                    values: list[str] = []
                    for cell in row:
                        if not cell.tag.endswith("}c"):
                            continue
                        cell_type = cell.attrib.get("t")
                        value = ""
                        inline_value = next(
                            (node.text for node in cell.iter() if node.tag.endswith("}t") and node.text),
                            None,
                        )
                        if inline_value:
                            value = inline_value
                        else:
                            raw_value = next(
                                (node.text for node in cell.iter() if node.tag.endswith("}v") and node.text),
                                "",
                            )
                            if cell_type == "s" and raw_value.isdigit():
                                shared_index = int(raw_value)
                                value = (
                                    shared_strings[shared_index] if shared_index < len(shared_strings) else raw_value
                                )
                            else:
                                value = raw_value
                        value = value.strip()
                        if value:
                            values.append(value)
                    if values:
                        rows.append(", ".join(values))

                if rows:
                    sheet_lines.append(f"Sheet {idx}")
                    sheet_lines.extend(rows)

        return ExtractedDocumentContent(
            text="\n".join(sheet_lines),
            sheet_count=len(sheet_paths),
            has_tables=bool(sheet_lines),
        )
    except Exception as exc:
        logger.warning("XLSX extraction failed for %s: %s", file_name, type(exc).__name__)
        return ExtractedDocumentContent(
            text="",
            note=f"Stored successfully but XLSX extraction failed for {file_name}.",
        )
