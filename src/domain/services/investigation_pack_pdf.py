"""Investigation customer pack export — branded PDF rendering (PX-143).

The customer pack has always been generated as a JSON payload. JSON is not a
client deliverable, so this module renders the *same already-redacted pack
content* as a PDF. It never reads the investigation directly: whatever the
redaction rules removed stays removed, because this only sees the stored pack.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)

_MAX_FIELD_CHARS = 4000
_MAX_ASSET_ROWS = 200
_DEFAULT_BRAND_RGB = (59, 130, 246)

_AUDIENCE_LABELS: dict[str, str] = {
    "internal_customer": "Internal customer pack",
    "external_customer": "External customer pack",
}

_AUDIENCE_CONFIDENTIALITY: dict[str, str] = {
    "internal_customer": (
        "Confidential. Issued for the named customer's internal use. Identities are retained; "
        "internal commentary is excluded."
    ),
    "external_customer": (
        "Confidential. Issued externally. Personal identities are redacted and only "
        "externally-releasable evidence is listed."
    ),
}


def _pdf_safe(value: Any, *, max_len: Optional[int] = None) -> str:
    """Helvetica (latin-1) safe text; never invent content on failure."""
    text = "" if value is None else str(value)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.encode("latin-1", errors="replace").decode("latin-1")
    if max_len is not None and len(text) > max_len:
        text = text[: max_len - 3].rstrip() + "..."
    return text


def humanise_key(key: Any) -> str:
    """Turn a stored section/field key into a report label (`root_cause` -> `Root cause`)."""
    raw = str(key or "").strip()
    if not raw:
        return "Untitled"
    words = raw.replace("-", " ").replace("_", " ").replace(".", " ").split()
    if not words:
        return raw
    first, *rest = words
    return " ".join([first[:1].upper() + first[1:], *(w.lower() for w in rest)])


def format_field_value(value: Any) -> str:
    """Render a stored field value without inventing or hiding content."""
    if value is None:
        return "Not recorded"
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return value.strip() or "Not recorded"
    if isinstance(value, list):
        if not value:
            return "None recorded"
        return "\n".join(f"- {format_field_value(item)}" for item in value)
    if isinstance(value, dict):
        if not value:
            return "None recorded"
        return "\n".join(f"{humanise_key(k)}: {format_field_value(v)}" for k, v in value.items())
    return str(value)


def summarise_redactions(redaction_log: Any) -> list[tuple[str, int]]:
    """Count redaction-log entries by type, sorted by type, so the pack owns its gaps."""
    counts: dict[str, int] = {}
    if isinstance(redaction_log, list):
        for entry in redaction_log:
            if not isinstance(entry, dict):
                continue
            kind = str(entry.get("redaction_type") or "REDACTION")
            counts[kind] = counts.get(kind, 0) + 1
    return sorted(counts.items())


def _brand_rgb(primary_color: Optional[str]) -> tuple[int, int, int]:
    """Parse a `#rrggbb` tenant brand colour; fall back to the platform default."""
    raw = (primary_color or "").strip().lstrip("#")
    if len(raw) != 6:
        return _DEFAULT_BRAND_RGB
    try:
        return (int(raw[0:2], 16), int(raw[2:4], 16), int(raw[4:6], 16))
    except ValueError:
        return _DEFAULT_BRAND_RGB


def _write_line(pdf: Any, text: str, *, height: float = 5) -> None:
    """Write wrapped text from the left margin (avoids fpdf2 mid-line multi_cell errors)."""
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(0, height, _pdf_safe(text), new_x="LMARGIN", new_y="NEXT")


class InvestigationPackPdfService:
    """Render a stored investigation customer pack as a branded PDF."""

    @staticmethod
    def pdf_filename(investigation_reference: Any, pack_uuid: Any) -> str:
        ref = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in str(investigation_reference or "pack"))
        suffix = str(pack_uuid or "")[:8] or "pack"
        return f"investigation-report-{ref}-{suffix}.pdf"

    def build_pdf_bytes(  # noqa: C901 - one linear pass over pack sections
        self,
        pack: dict[str, Any],
        *,
        organisation_name: Optional[str] = None,
        primary_color: Optional[str] = None,
    ) -> bytes:
        """Render pack bytes. Raises RuntimeError when fpdf2 is unavailable or rendering fails."""
        try:
            from fpdf import FPDF
        except ModuleNotFoundError as exc:
            raise RuntimeError("PDF export unavailable: fpdf2 is not installed in this environment") from exc

        raw_content = pack.get("content")
        content: dict[str, Any] = raw_content if isinstance(raw_content, dict) else {}
        audience = str(pack.get("audience") or "")
        reference = pack.get("investigation_reference") or content.get("investigation_reference") or "Unknown"
        title = pack.get("investigation_title") or content.get("title") or "Investigation report"
        generated_at = pack.get("generated_at") or datetime.now(timezone.utc).isoformat()
        org = (organisation_name or "").strip()
        brand = _brand_rgb(primary_color)

        pdf = FPDF(orientation="P", unit="mm", format="A4")
        pdf.set_auto_page_break(auto=True, margin=18)
        pdf.set_margins(left=16, top=14, right=16)
        pdf.add_page()

        # Branded header band — tenant name and brand colour, no remote assets fetched.
        pdf.set_fill_color(*brand)
        pdf.rect(0, 0, 210, 22, style="F")
        pdf.set_text_color(255, 255, 255)
        pdf.set_xy(16, 6)
        pdf.set_font("Helvetica", "B", 14)
        pdf.cell(0, 6, _pdf_safe(org or "Investigation report"), new_x="LMARGIN", new_y="NEXT")
        pdf.set_x(16)
        pdf.set_font("Helvetica", "", 9)
        pdf.cell(
            0,
            5,
            _pdf_safe(_AUDIENCE_LABELS.get(audience, humanise_key(audience) or "Customer pack")),
            new_x="LMARGIN",
            new_y="NEXT",
        )
        pdf.set_text_color(0, 0, 0)
        pdf.set_y(28)

        pdf.set_font("Helvetica", "B", 16)
        _write_line(pdf, str(title), height=8)
        pdf.set_font("Helvetica", "", 10)
        _write_line(pdf, f"Investigation reference: {reference}")
        _write_line(pdf, f"Status: {humanise_key(content.get('status') or 'unknown')}")
        _write_line(pdf, f"Investigation level: {humanise_key(content.get('level') or 'unknown')}")
        _write_line(pdf, f"Generated: {generated_at}")
        pdf.ln(2)

        confidentiality = _AUDIENCE_CONFIDENTIALITY.get(audience)
        if confidentiality:
            pdf.set_font("Helvetica", "I", 9)
            _write_line(pdf, confidentiality, height=4.5)
            pdf.ln(1)

        self._section_heading(pdf, "Report sections", brand)
        raw_sections = content.get("sections")
        sections: dict[str, Any] = raw_sections if isinstance(raw_sections, dict) else {}
        if not sections:
            pdf.set_font("Helvetica", "", 10)
            _write_line(pdf, "No report sections were recorded on this investigation.")
        else:
            for section_key, fields in sections.items():
                pdf.set_font("Helvetica", "B", 11)
                _write_line(pdf, humanise_key(section_key), height=6)
                pdf.set_font("Helvetica", "", 10)
                if not isinstance(fields, dict) or not fields:
                    _write_line(pdf, "No content recorded for this section.", height=4.5)
                    pdf.ln(1)
                    continue
                for field_key, field_value in fields.items():
                    pdf.set_font("Helvetica", "B", 9)
                    _write_line(pdf, humanise_key(field_key), height=4.5)
                    pdf.set_font("Helvetica", "", 10)
                    _write_line(pdf, _pdf_safe(format_field_value(field_value), max_len=_MAX_FIELD_CHARS), height=4.5)
                pdf.ln(1)
        pdf.ln(1)

        omitted = content.get("omitted_sections")
        if isinstance(omitted, list) and omitted:
            self._section_heading(pdf, "Sections withheld from this pack", brand)
            pdf.set_font("Helvetica", "", 10)
            _write_line(
                pdf,
                "The following sections were approved for omission and are not reproduced above:",
                height=4.5,
            )
            for section_key in omitted:
                _write_line(pdf, f"- {humanise_key(section_key)}", height=4.5)
            pdf.ln(1)

        self._section_heading(pdf, "Evidence schedule", brand)
        raw_assets = pack.get("included_assets")
        assets: list[Any] = raw_assets if isinstance(raw_assets, list) else []
        pdf.set_font("Helvetica", "", 10)
        if not assets:
            _write_line(pdf, "No evidence assets are linked to this investigation.")
        else:
            included = [a for a in assets[:_MAX_ASSET_ROWS] if isinstance(a, dict) and a.get("included")]
            excluded = [a for a in assets[:_MAX_ASSET_ROWS] if isinstance(a, dict) and not a.get("included")]
            _write_line(pdf, f"Released with this pack: {len(included)}")
            for asset in included:
                _write_line(
                    pdf,
                    f"- {asset.get('title') or 'Untitled evidence'} ({humanise_key(asset.get('asset_type'))})",
                    height=4.5,
                )
            _write_line(pdf, f"Withheld: {len(excluded)}")
            for asset in excluded:
                reason = humanise_key(asset.get("exclusion_reason")) if asset.get("exclusion_reason") else "Withheld"
                _write_line(
                    pdf,
                    f"- {asset.get('title') or 'Untitled evidence'} - {reason}",
                    height=4.5,
                )
        pdf.ln(1)

        redactions = summarise_redactions(pack.get("redaction_log"))
        self._section_heading(pdf, "Redaction summary", brand)
        pdf.set_font("Helvetica", "", 10)
        if not redactions:
            _write_line(pdf, "No redactions were applied to this pack.")
        else:
            for kind, count in redactions:
                _write_line(pdf, f"{humanise_key(kind)}: {count}")
        pdf.ln(1)

        self._section_heading(pdf, "Pack integrity", brand)
        pdf.set_font("Helvetica", "", 9)
        _write_line(pdf, f"Pack UUID: {pack.get('pack_uuid') or 'unknown'}", height=4.5)
        _write_line(pdf, f"Content SHA-256: {pack.get('checksum_sha256') or 'not recorded'}", height=4.5)
        _write_line(
            pdf,
            "This PDF renders the stored pack payload. The SHA-256 above is the checksum of that "
            "payload, so this document can be checked against the record it was issued from.",
            height=4.5,
        )

        try:
            return bytes(pdf.output())
        except Exception as exc:  # noqa: BLE001 - surfaced to the caller as a 500
            logger.exception("Investigation pack PDF render failed for pack %s", pack.get("pack_uuid"))
            raise RuntimeError(f"Investigation pack PDF build failed: {exc}") from exc

    @staticmethod
    def _section_heading(pdf: Any, title: str, brand: tuple[int, int, int]) -> None:
        pdf.set_text_color(*brand)
        pdf.set_font("Helvetica", "B", 12)
        _write_line(pdf, title, height=7)
        pdf.set_text_color(0, 0, 0)
        pdf.set_font("Helvetica", "", 10)
