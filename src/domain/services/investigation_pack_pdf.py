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

from src.domain.services.investigation_pack_draw import (
    ChronologySet,
    chronology_summary_line,
    draw_chronology_figure,
    fit_text,
    format_stamp,
    humanise_key,
    normalise_chronology_events,
    pdf_safe,
    plural,
)

logger = logging.getLogger(__name__)

# Text and geometry helpers live in investigation_pack_draw (INV-C15) so the
# drawing layer and this renderer cannot drift apart. Aliased at their original
# private names because that is what the rest of this module already calls.
_pdf_safe = pdf_safe
_fit_cell_text = fit_text

_MAX_FIELD_CHARS = 4000
_MAX_ASSET_ROWS = 200
# Plantexpand primary — HSL 82 85% 25% (the web --primary token), not Tailwind blue.
_DEFAULT_BRAND_RGB = (78, 118, 10)
_WORDMARK = "PLANTEXPAND"

_AUDIENCE_LABELS: dict[str, str] = {
    "internal_customer": "Internal customer pack",
    "external_customer": "External customer pack",
}

_INTERNAL_CONFIDENTIALITY = (
    "Confidential. Issued for the named customer's internal use. Identities are retained; "
    "internal commentary is excluded."
)

# Section omits are approved withholdings, not field redactions. Everything else in the
# log is a field the redaction pass actually rewrote.
_SECTION_OMIT_TYPE = "SECTION_OMIT_APPROVED"

# Redaction matches an allow-list of identity field names, so it cannot reach a name written
# inside a description or a findings narrative. Saying so is the difference between a pack
# that is safe to release and one that only claims to be.
_REDACTION_SCOPE_NOTE = (
    "Redaction covers recorded identity fields only. Narrative text is reproduced as written "
    "and may still identify individuals - review this pack before releasing it."
)

# ---------------------------------------------------------------------------
# Chronology figure (INV-C15)
# ---------------------------------------------------------------------------

# Internal audiences only. Timeline entries are *not* covered by the pack
# redaction pass — that pass walks `content["sections"]` and rewrites recorded
# identity fields, and a chronology entry carries an actor name and the source
# record's running-sheet narrative instead. Drawing them into an external pack
# would release identities the pack claims to have redacted, so an external or
# unrecognised audience gets a stated withholding, not a figure. Widening this
# set is a product decision about redacting timeline data, not a rendering one.
_CHRONOLOGY_AUDIENCES = frozenset({"internal_customer"})

_CHRONOLOGY_ENTRY_ROWS = 12

_CHRONOLOGY_WITHHELD = (
    "The chronology is withheld from this pack. Timeline entries are outside the redaction pass "
    "applied to the sections above, so they are not released to this audience."
)

# Where the events came from, which decides whether the checksum in Pack
# integrity covers them. Saying so is the difference between a figure a reader
# can verify against the stored record and one they cannot.
_PROVENANCE_PACK = "pack"
_PROVENANCE_RENDER = "render"
_CHRONOLOGY_PROVENANCE = {
    _PROVENANCE_PACK: (
        "Chronology compiled from the stored pack payload, so it is covered by the content "
        "checksum recorded under Pack integrity."
    ),
    _PROVENANCE_RENDER: (
        "Chronology compiled from the investigation timeline when this document was rendered. "
        "It is not part of the stored pack payload and is not covered by the content checksum "
        "recorded under Pack integrity."
    ),
}


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


def count_field_redactions(redaction_log: Any) -> int:
    """Count field rewrites actually applied. Section omits are withholdings, not redactions."""
    if not isinstance(redaction_log, list):
        return 0
    return sum(
        1
        for entry in redaction_log
        if isinstance(entry, dict) and str(entry.get("redaction_type") or "") != _SECTION_OMIT_TYPE
    )


def confidentiality_notice(audience: Any, redaction_log: Any) -> str:
    """Audience notice stating what redaction did to *this* pack, never what it intends to do."""
    key = str(audience or "")
    if key == "internal_customer":
        return _INTERNAL_CONFIDENTIALITY
    if key != "external_customer":
        return ""

    applied = count_field_redactions(redaction_log)
    if applied == 1:
        applied_line = "1 field was redacted from the sections below."
    elif applied > 1:
        applied_line = f"{applied} fields were redacted from the sections below."
    else:
        applied_line = "No fields were redacted from the sections below."

    return (
        f"Confidential. Issued externally. {applied_line} Only externally-releasable evidence "
        f"is listed. {_REDACTION_SCOPE_NOTE}"
    )


def chronology_feed(
    pack: dict[str, Any],
    content: dict[str, Any],
    timeline_events: Any = None,
) -> tuple[Any, str]:
    """Find the chronology events for this pack, and say where they came from.

    Three accepted sources, highest precedence first:

    1. ``timeline_events`` passed by the caller — render-time.
    2. ``pack["timeline_events"]`` on the payload dict — render-time.
    3. ``content["chronology"]`` inside the stored pack content, either a list of
       events or a mapping with an ``events`` list — checksum-covered.

    Every one of them takes the shape ``GET /investigations/{id}/timeline``
    serialises, so origin is read from ``event_metadata["origin"]`` exactly as
    INV-C9 writes it. This renderer only ever sees the payload handed to it: it
    does not query the timeline, the parent audit log or the running sheets, so
    it cannot reach content the pack withheld.

    That also fixes where tenant scoping lives. The feed must already be the
    authorised, tenant-scoped timeline for this investigation — which is what
    ``load_parent_timeline_rows`` produces, tenant-filtered and fail-closed. This
    function has no session and no tenant id, so it can neither verify that nor
    widen it; supplying an unscoped feed would be a defect in the caller.

    Returns ``(None, "")`` when no source supplied a list at all — meaning the
    section is omitted entirely. That is not the same as an empty list, which
    means a source said there is nothing to show and the pack can say so.
    """
    if isinstance(timeline_events, list):
        return timeline_events, _PROVENANCE_RENDER

    payload_events = pack.get("timeline_events")
    if isinstance(payload_events, list):
        return payload_events, _PROVENANCE_RENDER

    stored = content.get("chronology")
    if isinstance(stored, dict):
        stored = stored.get("events")
    if isinstance(stored, list):
        return stored, _PROVENANCE_PACK

    return None, ""


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


def _make_pack_pdf_class(fpdf_cls: Any) -> Any:
    """FPDF subclass with a branded footer. Built here so a missing fpdf2 still fails closed."""

    class PackPdf(fpdf_cls):
        def __init__(self, brand: tuple[int, int, int], org: str, audience_label: str) -> None:
            super().__init__(orientation="P", unit="mm", format="A4")
            self._brand = brand
            self._org = org
            self._audience_label = audience_label

        def footer(self) -> None:  # noqa: N802 - fpdf2 hook
            self.set_y(-14)
            self.set_text_color(*self._brand)
            self.set_font("Helvetica", "", 8)
            if self._org:
                separator_and_wordmark = f"  |  {_WORDMARK}"
                org_width = 95 - self.get_string_width(separator_and_wordmark)
                left = f"{_fit_cell_text(self, self._org, org_width)}{separator_and_wordmark}"
            else:
                left = _WORDMARK
            right = _pdf_safe(f"{self._audience_label}  |  Page {self.page_no()} of {{nb}}")
            self.cell(95, 8, left, align="L")
            self.cell(0, 8, right, align="R")
            self.set_text_color(0, 0, 0)

    return PackPdf


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
        timeline_events: Any = None,
    ) -> bytes:
        """Render pack bytes. Raises RuntimeError when fpdf2 is unavailable or rendering fails.

        ``timeline_events`` is the optional chronology feed described in
        :func:`chronology_feed`, in the shape the timeline endpoint serialises.
        Omit it and the pack renders exactly as it did before INV-C15.
        """
        try:
            from fpdf import FPDF
        except ModuleNotFoundError as exc:
            raise RuntimeError("PDF export unavailable: fpdf2 is not installed in this environment") from exc

        raw_content = pack.get("content")
        content: dict[str, Any] = raw_content if isinstance(raw_content, dict) else {}
        audience = str(pack.get("audience") or "")
        audience_label = _AUDIENCE_LABELS.get(audience, humanise_key(audience) or "Customer pack")
        reference = pack.get("investigation_reference") or content.get("investigation_reference") or "Unknown"
        title = pack.get("investigation_title") or content.get("title") or "Investigation report"
        generated_at = pack.get("generated_at") or datetime.now(timezone.utc).isoformat()
        org = (organisation_name or "").strip()
        brand = _brand_rgb(primary_color)

        pdf = _make_pack_pdf_class(FPDF)(brand, org, audience_label)
        pdf.alias_nb_pages()
        pdf.set_auto_page_break(auto=True, margin=18)
        pdf.set_margins(left=16, top=14, right=16)
        pdf.add_page()

        # Branded header band — tenant colour, bundled wordmark. No remote logo fetch.
        pdf.set_fill_color(*brand)
        pdf.rect(0, 0, 210, 26, style="F")
        pdf.set_text_color(255, 255, 255)
        pdf.set_xy(16, 7)
        pdf.set_font("Helvetica", "B", 14)
        pdf.cell(110, 6, _fit_cell_text(pdf, org or "Investigation report", 110), align="L")
        pdf.set_xy(126, 7)
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(68, 6, _WORDMARK, align="R")
        pdf.set_xy(16, 15)
        pdf.set_font("Helvetica", "", 9)
        pdf.cell(0, 5, _pdf_safe(audience_label), align="L")
        pdf.set_text_color(0, 0, 0)
        pdf.set_y(32)

        pdf.set_font("Helvetica", "B", 16)
        _write_line(pdf, str(title), height=8)
        pdf.set_font("Helvetica", "", 10)
        _write_line(pdf, f"Investigation reference: {reference}")
        _write_line(pdf, f"Status: {humanise_key(content.get('status') or 'unknown')}")
        _write_line(pdf, f"Investigation level: {humanise_key(content.get('level') or 'unknown')}")
        _write_line(pdf, f"Generated: {generated_at}")
        pdf.ln(2)

        confidentiality = confidentiality_notice(audience, pack.get("redaction_log"))
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

        self._render_chronology(
            pdf,
            pack=pack,
            content=content,
            audience=audience,
            brand=brand,
            timeline_events=timeline_events,
        )

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

    def _render_chronology(
        self,
        pdf: Any,
        *,
        pack: dict[str, Any],
        content: dict[str, Any],
        audience: str,
        brand: tuple[int, int, int],
        timeline_events: Any = None,
    ) -> None:
        """Chronology section (INV-C15): the figure, its entries, or an honest gap.

        Four outcomes, and the difference between them matters:

        * No feed supplied at all — the section is omitted. Printing "no events"
          when nobody asked the timeline would be inventing a fact about the
          investigation.
        * A feed that yields no placeable event — the section says so.
        * A feed on a pack whose audience is not allowed the chronology — the
          section states the withholding instead of drawing it.
        * Otherwise — summary line, figure, the most recent entries, and where
          the events came from.

        A figure that fails to draw degrades to the entry list with the failure
        stated. A pack export is a client deliverable; losing the graphic is
        recoverable, returning a 500 to someone trying to issue a report is not.
        """
        feed, provenance = chronology_feed(pack, content, timeline_events)
        if feed is None:
            return

        chronology = normalise_chronology_events(feed)
        self._section_heading(pdf, "Chronology", brand)
        pdf.set_font("Helvetica", "", 10)

        if not chronology.events:
            _write_line(pdf, chronology_summary_line(chronology), height=4.5)
            self._render_chronology_gaps(pdf, chronology)
            pdf.ln(1)
            return

        if audience not in _CHRONOLOGY_AUDIENCES:
            pdf.set_font("Helvetica", "I", 9)
            _write_line(pdf, _CHRONOLOGY_WITHHELD, height=4.5)
            pdf.ln(1)
            return

        _write_line(pdf, chronology_summary_line(chronology), height=4.5)
        try:
            draw_chronology_figure(pdf, chronology, brand=brand)
        except Exception:  # noqa: BLE001 - a pack without its figure beats a failed export
            logger.exception("Investigation pack chronology figure failed for pack %s", pack.get("pack_uuid"))
            pdf.set_font("Helvetica", "I", 9)
            _write_line(
                pdf,
                "The chronology figure could not be drawn for this pack. The entries are listed below.",
                height=4.5,
            )

        self._render_chronology_entries(pdf, chronology)
        self._render_chronology_gaps(pdf, chronology)
        pdf.set_font("Helvetica", "I", 8)
        _write_line(pdf, _CHRONOLOGY_PROVENANCE[provenance], height=4)
        pdf.ln(1)

    @staticmethod
    def _render_chronology_entries(pdf: Any, chronology: ChronologySet) -> None:
        """The newest entries in words, because markers alone cannot be read."""
        events = list(reversed(chronology.events))[:_CHRONOLOGY_ENTRY_ROWS]
        pdf.set_font("Helvetica", "B", 9)
        _write_line(pdf, f"Most recent entries ({len(events)} of {len(chronology.events)})", height=5)
        pdf.set_font("Helvetica", "", 9)
        for event in events:
            line = f"- {format_stamp(event.at)} - {event.origin_label} - {event.label}"
            if event.detail:
                line = f"{line}: {event.detail}"
            _write_line(pdf, line, height=4.2)

    @staticmethod
    def _render_chronology_gaps(pdf: Any, chronology: ChronologySet) -> None:
        """State what the chronology could not show, rather than quietly showing less."""
        if not chronology.omitted and not chronology.unplaceable:
            return
        pdf.set_font("Helvetica", "", 9)
        if chronology.omitted:
            _write_line(
                pdf,
                f"{plural(chronology.omitted, 'earlier entry', 'earlier entries')} "
                f"{'is' if chronology.omitted == 1 else 'are'} not shown: the chronology is capped at "
                f"the newest {len(chronology.events)}.",
                height=4.2,
            )
        if chronology.unplaceable:
            _write_line(
                pdf,
                f"{plural(chronology.unplaceable, 'timeline entry', 'timeline entries')} carried no readable "
                "date and could not be placed on the chronology.",
                height=4.2,
            )

    @staticmethod
    def _section_heading(pdf: Any, title: str, brand: tuple[int, int, int]) -> None:
        pdf.set_text_color(*brand)
        pdf.set_font("Helvetica", "B", 12)
        _write_line(pdf, title, height=7)
        pdf.set_text_color(0, 0, 0)
        pdf.set_font("Helvetica", "", 10)
