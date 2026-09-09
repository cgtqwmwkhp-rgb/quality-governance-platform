"""Investigation customer pack export — branded PDF rendering (PX-143).

The customer pack has always been generated as a JSON payload. JSON is not a
client deliverable, so this module renders the *same already-redacted pack
content* as a PDF. It never reads the investigation directly: whatever the
redaction rules removed stays removed, because this only sees the stored pack.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from src.domain.services import investigation_pack_brand as pack_brand
from src.domain.services.investigation_pack_draw import (
    ChronologySet,
    IcamFactorSet,
    chronology_summary_line,
    draw_chronology_figure,
    draw_icam_factors_figure,
    fit_text,
    format_stamp,
    humanise_key,
    icam_summary_line,
    normalise_chronology_events,
    normalise_icam_factors,
    plural,
)
from src.domain.services.investigation_pack_ir import (
    DocumentMeta,
    KeyValueBlock,
    KeyValueRow,
    PackDocument,
    Section,
    TableBlock,
)
from src.domain.services.investigation_pack_layout import (
    write_finding_card,
    write_panel,
    write_section_banner,
    write_why_card,
    write_wrapped_paragraph,
    write_wrapped_table,
)
from src.domain.services.investigation_pack_pdf_writer import create_pack_pdf, write_block, write_contents, write_cover

logger = logging.getLogger(__name__)

# Text and geometry helpers live in investigation_pack_draw (INV-C15) so the
# drawing layer and this renderer cannot drift apart. Aliased at their original
# private names because that is what the rest of this module already calls.
_pdf_safe = pack_brand.text_safe
_fit_cell_text = fit_text

_MAX_FIELD_CHARS = 4000
_MAX_ASSET_ROWS = 200

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

_EMPTY_FINDINGS = "No findings were recorded."
_EMPTY_WHYS = "No 5-Whys were recorded."
_EMPTY_ROOT_CAUSE = "No root-cause statement was recorded."
_EMPTY_CONTRIBUTING = "No contributing-factor text was recorded."
_EMPTY_CAPA = "No CAPA actions were recorded."
_PACK_FINDINGS = "findings"
_PACK_ROOT_CAUSE = "root-cause"
_PACK_CAPA = "capa"

# Catalogue titles replace humanised snake_case so contents and body match the
# template's 01 Incident details … 09 Pack integrity numbering.
_CATALOGUE_TITLES = {
    "section_1_details": "Incident details",
    _PACK_FINDINGS: "Findings",
    _PACK_ROOT_CAUSE: "Root cause analysis",
    "contributing-factors": "Contributing factors",
    "icam-factors": "ICAM contributing factors",
    _PACK_CAPA: "CAPA",
}

_ISO_DATE = re.compile(r"^(\d{4}-\d{2}-\d{2})([Tt ].+)?$")

# ---------------------------------------------------------------------------
# ICAM contributing-factor diagram (INV-C16)
# ---------------------------------------------------------------------------

# Field inside the stored `root-cause` section, written by
# investigation_pack_content.serialize_rca_section. Nothing else supplies it:
# the diagram is drawn from the stored, checksum-covered payload, so an approved
# omit of `root-cause` withholds the figure by taking the section away rather
# than by a rule here that could be forgotten.
_PACK_ICAM_FACTORS = "icam_factors"

_ICAM_HEADING = "ICAM contributing factors"
_ICAM_FIGURE_NOTE = (
    "The diagram groups the recorded contributing factors by ICAM category and shows the HSG245 causal depth "
    "recorded against each. Factor wording is wrapped in the category block; it is not shortened with an ellipsis."
)
_ICAM_FIGURE_FAILED = (
    "The ICAM contributing-factor diagram could not be drawn for this pack. The factors are listed below."
)


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


def _catalogue_title(section_key: Any) -> str:
    key = str(section_key or "")
    return _CATALOGUE_TITLES.get(key, humanise_key(key))


def _icam_payload(fields: dict[str, Any]) -> Any:
    """Stored ICAM snapshot, or None when the pack never consulted factors."""
    if "icam_factors" not in fields:
        return None
    raw = fields.get("icam_factors")
    if raw is None:
        return None
    return raw


def _contents_sections(section_map: dict[str, Any], *, include_chronology: bool) -> list[Section]:
    """Contents headings, including template chapters 04/05 when ICAM is stored."""
    contents_list: list[Section] = []
    for key in section_map:
        contents_list.append(Section(id=str(key), heading=_catalogue_title(key), blocks=(), in_contents=True))
        if str(key) != _PACK_ROOT_CAUSE:
            continue
        fields = section_map[key]
        if isinstance(fields, dict) and _icam_payload(fields) is not None:
            contents_list.append(
                Section(id="contributing-factors", heading="Contributing factors", blocks=(), in_contents=True)
            )
            contents_list.append(
                Section(id="icam-factors", heading="ICAM contributing factors", blocks=(), in_contents=True)
            )
    if include_chronology:
        contents_list.append(Section(id="chronology", heading="Chronology", blocks=(), in_contents=True))
    contents_list.extend(
        (
            Section(id="evidence", heading="Evidence schedule", blocks=(), in_contents=True),
            Section(id="redaction", heading="Redaction summary", blocks=(), in_contents=True),
            Section(id="integrity", heading="Pack integrity", blocks=(), in_contents=True),
        )
    )
    return contents_list


def _uk_stamp(value: str) -> str | None:
    """UK date (and optional UTC time) from an ISO-8601 stored stamp, else None."""
    raw = value.strip()
    if not _ISO_DATE.match(raw):
        return None
    try:
        stamp = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if stamp.tzinfo is None and len(raw) == 10:
        return f"{stamp.day} {stamp.strftime('%B %Y')}"
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    stamp = stamp.astimezone(timezone.utc)
    return f"{stamp.day} {stamp.strftime('%B %Y')}, {stamp.strftime('%H:%M')} UTC"


def format_pack_field(value: Any) -> str:
    """Like format_field_value, but ISO timestamps in the body become UK dates."""
    if isinstance(value, str):
        uk = _uk_stamp(value)
        if uk is not None:
            return uk
    return format_field_value(value)


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


def _human_generated_label(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return "Not recorded"
    try:
        stamp = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return raw
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    stamp = stamp.astimezone(timezone.utc)
    return f"{stamp.day} {stamp.strftime('%B %Y')}, {stamp.strftime('%H:%M')} UTC"


def _incident_reference(pack: dict[str, Any], content: dict[str, Any]) -> str:
    sections = content.get("sections")
    details = sections.get("section_1_details") if isinstance(sections, dict) else None
    if isinstance(details, dict):
        for key in ("reference_number", "incident_reference", "incident_ref"):
            found = details.get(key)
            if found:
                return str(found)
    return ""


def _write_line(pdf: Any, text: str, *, height: float = 5) -> None:
    """Write wrapped text from the left margin. ``height`` is kept for callers; wrap is measured."""
    _ = height
    write_wrapped_paragraph(pdf, text)


def _set_pack_font(pdf: Any, *, bold: bool = False, size: float = 10) -> None:
    """Body type on a pack page. Never italic — Inter has no italic slot in this lock."""
    pdf.set_font(pack_brand.FAMILY_REGULAR, "B" if bold else "", size)
    pdf.set_text_color(*pack_brand.JET_GREY)


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

        ``organisation_name`` and ``primary_color`` are accepted and ignored.
        Letterhead is the brand kit, not the tenant row (INV-PACK-R1).
        """
        # Fail closed before a page is drawn if Inter or the lockup is missing.
        pack_brand.resolve_typeface()

        raw_content = pack.get("content")
        content: dict[str, Any] = raw_content if isinstance(raw_content, dict) else {}
        audience = str(pack.get("audience") or "")
        audience_label = _AUDIENCE_LABELS.get(audience, humanise_key(audience) or "Customer pack")
        reference = pack.get("investigation_reference") or content.get("investigation_reference") or "Unknown"
        title = pack.get("investigation_title") or content.get("title") or "Investigation report"
        generated_at = pack.get("generated_at") or datetime.now(timezone.utc).isoformat()
        _ = organisation_name
        _ = primary_color
        brand = pack_brand.CRIMSON
        confidentiality = confidentiality_notice(audience, pack.get("redaction_log"))

        meta = DocumentMeta(
            reference=str(reference),
            title=str(title),
            audience_label=audience_label,
            status_label=humanise_key(content.get("status") or "unknown"),
            level_label=humanise_key(content.get("level") or "unknown"),
            generated_at_label=_human_generated_label(generated_at),
            pack_uuid=str(pack.get("pack_uuid") or "unknown"),
            content_sha256=str(pack.get("checksum_sha256") or "not recorded"),
            classification=pack_brand.CLASSIFICATION,
            confidentiality=confidentiality,
            incident_reference=_incident_reference(pack, content),
        )
        raw_sections = content.get("sections")
        section_map: dict[str, Any] = raw_sections if isinstance(raw_sections, dict) else {}
        chronology_feed_data, _chronology_provenance = chronology_feed(pack, content, timeline_events)
        document = PackDocument(
            meta=meta,
            sections=tuple(_contents_sections(section_map, include_chronology=chronology_feed_data is not None)),
        )

        pdf = create_pack_pdf(meta)
        write_cover(pdf, meta)
        write_contents(pdf, document)

        chapter = self._render_report_sections(
            pdf, section_map, brand=brand, pack_uuid=pack.get("pack_uuid"), start_at=1
        )

        omitted = content.get("omitted_sections")
        if isinstance(omitted, list) and omitted:
            self._section_heading(pdf, "Sections withheld from this pack", brand)
            _set_pack_font(pdf, size=10)
            _write_line(
                pdf,
                "The following sections were approved for omission and are not reproduced above:",
                height=4.5,
            )
            for section_key in omitted:
                _write_line(pdf, f"- {_catalogue_title(section_key)}", height=4.5)
            pdf.ln(1)

        if chronology_feed_data is not None:
            self._render_chronology(
                pdf,
                pack=pack,
                content=content,
                audience=audience,
                brand=brand,
                timeline_events=timeline_events,
                heading=f"{chapter:02d} Chronology",
            )
            chapter += 1

        self._section_heading(pdf, f"{chapter:02d} Evidence schedule", brand)
        chapter += 1
        raw_assets = pack.get("included_assets")
        assets: list[Any] = raw_assets if isinstance(raw_assets, list) else []
        _set_pack_font(pdf, size=10)
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
        self._section_heading(pdf, f"{chapter:02d} Redaction summary", brand)
        chapter += 1
        _set_pack_font(pdf, size=10)
        if not redactions:
            _write_line(pdf, "No redactions were applied to this pack.")
        else:
            for kind, count in redactions:
                _write_line(pdf, f"{humanise_key(kind)}: {count}")
        pdf.ln(1)

        self._section_heading(pdf, f"{chapter:02d} Pack integrity", brand)
        write_panel(
            pdf,
            f"Pack UUID: {pack.get('pack_uuid') or 'unknown'}\n"
            f"Content SHA-256: {pack.get('checksum_sha256') or 'not recorded'}\n"
            "This PDF renders the stored pack payload. The SHA-256 above is the checksum of that "
            "payload, so this document can be checked against the record it was issued from.",
            bar=pack_brand.CRIMSON,
        )

        try:
            return bytes(pdf.output())
        except Exception as exc:  # noqa: BLE001 - surfaced to the caller as a 500
            logger.exception("Investigation pack PDF render failed for pack %s", pack.get("pack_uuid"))
            raise RuntimeError(f"Investigation pack PDF build failed: {exc}") from exc

    def _render_report_sections(
        self,
        pdf: Any,
        raw_sections: Any,
        *,
        brand: tuple[int, int, int],
        pack_uuid: Any = None,
        start_at: int = 1,
    ) -> int:
        """Report sections. Investigation lists (findings, Whys, CAPA) are shaped, not dumped.

        ``brand`` and ``pack_uuid`` are only needed by the RCA section, which
        draws the ICAM figure (INV-C16) and logs the pack when it cannot. They
        are bound onto that one renderer rather than pushed onto every section.
        Returns the next unused chapter number so contents and body stay aligned.
        """
        sections: dict[str, Any] = raw_sections if isinstance(raw_sections, dict) else {}
        if not sections:
            _set_pack_font(pdf, size=10)
            _write_line(pdf, "No report sections were recorded on this investigation.")
            return start_at
        renderers: dict[str, Callable[[Any, dict[str, Any]], None]] = {
            _PACK_FINDINGS: self._render_findings_section,
            _PACK_CAPA: self._render_capa_section,
        }
        chapter = start_at
        for section_key, fields in sections.items():
            if str(section_key) == _PACK_ROOT_CAUSE and isinstance(fields, dict):
                self._section_heading(pdf, f"{chapter:02d} {_catalogue_title(section_key)}", brand)
                chapter += 1
                if not fields:
                    _write_line(pdf, "No content recorded for this section.", height=4.5)
                    pdf.ln(1)
                    continue
                self._render_rca_core(pdf, fields)
                if _icam_payload(fields) is not None:
                    self._section_heading(pdf, f"{chapter:02d} Contributing factors", brand)
                    chapter += 1
                    self._render_contributing_factors(pdf, fields)
                    self._section_heading(pdf, f"{chapter:02d} {_ICAM_HEADING}", brand)
                    chapter += 1
                    self._render_icam_factors(pdf, fields, brand=brand, pack_uuid=pack_uuid)
                pdf.ln(1)
                continue
            self._section_heading(pdf, f"{chapter:02d} {_catalogue_title(section_key)}", brand)
            chapter += 1
            _set_pack_font(pdf, size=10)
            if not isinstance(fields, dict) or not fields:
                _write_line(pdf, "No content recorded for this section.", height=4.5)
                pdf.ln(1)
                continue
            renderer = renderers.get(str(section_key))
            if renderer is not None:
                renderer(pdf, fields)
            else:
                self._render_generic_section_fields(pdf, fields)
            pdf.ln(1)
        return chapter

    @staticmethod
    def _render_generic_section_fields(pdf: Any, fields: dict[str, Any]) -> None:
        write_block(
            pdf,
            KeyValueBlock(
                rows=tuple(
                    KeyValueRow(label=humanise_key(field_key), value=format_pack_field(field_value))
                    for field_key, field_value in fields.items()
                )
            ),
        )

    @staticmethod
    def _render_findings_section(pdf: Any, fields: dict[str, Any]) -> None:
        items = fields.get("items")
        if not isinstance(items, list) or not items:
            _write_line(pdf, _EMPTY_FINDINGS, height=4.5)
            return
        for index, item in enumerate(items, start=1):
            if isinstance(item, dict):
                body = item.get("body")
            else:
                body = item
            rendered = format_field_value(body)
            write_finding_card(pdf, index, _pdf_safe(f"{index:02d}. {rendered}", max_len=_MAX_FIELD_CHARS))

    @staticmethod
    def _render_why_entries(pdf: Any, whys: Any) -> None:
        _set_pack_font(pdf, bold=True, size=9)
        _write_line(pdf, "5 Whys", height=4.5)
        _set_pack_font(pdf, size=10)
        if not isinstance(whys, list) or not whys:
            _write_line(pdf, _EMPTY_WHYS, height=4.5)
            return
        for raw in whys:
            if not isinstance(raw, dict):
                continue
            level_raw = raw.get("level")
            if level_raw is None:
                continue
            try:
                level = int(level_raw)
            except (TypeError, ValueError):
                continue
            question = raw.get("why")
            question_text = question.strip() if isinstance(question, str) and question.strip() else None
            evidence = raw.get("evidence")
            evidence_text = evidence.strip() if isinstance(evidence, str) and evidence.strip() else None
            write_why_card(
                pdf,
                level,
                _pdf_safe(format_pack_field(raw.get("answer")), max_len=_MAX_FIELD_CHARS),
                _pdf_safe(evidence_text, max_len=_MAX_FIELD_CHARS) if evidence_text else None,
                _pdf_safe(question_text, max_len=_MAX_FIELD_CHARS) if question_text else None,
            )

    @staticmethod
    def _render_stated_field(pdf: Any, heading: str, value: Any, empty_message: str, *, panel: bool = False) -> None:
        _set_pack_font(pdf, bold=True, size=9)
        _write_line(pdf, heading, height=4.5)
        _set_pack_font(pdf, size=10)
        if isinstance(value, str) and not value.strip():
            _write_line(pdf, empty_message, height=4.5)
            return
        if isinstance(value, list) and not value:
            _write_line(pdf, empty_message, height=4.5)
            return
        body = _pdf_safe(format_field_value(value), max_len=_MAX_FIELD_CHARS)
        if panel:
            write_panel(pdf, body, bar=pack_brand.CRIMSON)
            return
        _write_line(pdf, body, height=4.5)

    def _render_rca_core(self, pdf: Any, fields: dict[str, Any]) -> None:
        """Problem, 5 Whys, root cause. Contributing prose stays here only when ICAM was never stored."""
        self._render_stated_field(
            pdf, "Problem statement", fields.get("problem_statement"), "No problem statement was recorded."
        )
        self._render_why_entries(pdf, fields.get("whys"))
        self._render_stated_field(pdf, "Root cause", fields.get("root_cause"), _EMPTY_ROOT_CAUSE, panel=True)
        if _icam_payload(fields) is None:
            self._render_stated_field(
                pdf, "Contributing factors", fields.get("contributing_factors"), _EMPTY_CONTRIBUTING
            )

    @staticmethod
    def _render_contributing_factors(pdf: Any, fields: dict[str, Any]) -> None:
        """Template chapter 04: category / factor / depth from stored ICAM rows."""
        raw = _icam_payload(fields)
        factors = normalise_icam_factors(raw)
        if factors.factors:
            rows: list[tuple[str, str, str]] = []
            for factor in factors.factors:
                if factor.sub_causes:
                    bullets = "\n".join(f"- {sub}" for sub in factor.sub_causes)
                    body = f"{factor.cause}\n{bullets}"
                else:
                    body = factor.cause
                rows.append((factor.category_label, body, factor.depth_label or "—"))
            write_wrapped_table(
                pdf,
                ("ICAM category", "Contributing factor", "HSG245 causal depth"),
                rows,
                widths=(0.22, 0.56, 0.22),
            )
            return
        InvestigationPackPdfService._render_stated_field(
            pdf, "Contributing factors", fields.get("contributing_factors"), _EMPTY_CONTRIBUTING
        )

    def _render_icam_factors(
        self,
        pdf: Any,
        fields: dict[str, Any],
        *,
        brand: tuple[int, int, int],
        pack_uuid: Any = None,
    ) -> None:
        """The ICAM contributing-factor diagram (INV-C16), or an honest line instead of one.

        Three outcomes, and the difference between them matters:

        * The stored section carries no ``icam_factors`` key — nothing is
          rendered. A pack generated before this change never consulted the
          factors, and printing "none are recorded" for it would claim something
          was checked that was not. Same rule as the chronology feed.
        * The key is present and yields no factor — the pack says so. "None were
          ever recorded" and "every one was deleted" are the same fact, and it is
          the one the reader needs.
        * Otherwise — the summary line, the four-band figure, the note that says
          what the figure is, and what the figure could not show.

        An approved omit of ``root-cause`` withholds the diagram without a check
        here: the withheld section never reaches ``content["sections"]``, so this
        method is never reached for it.

        Unlike the chronology, the figure is *not* audience-gated. Every word it
        draws is already in the ``Contributing factors`` text above it — INV-C12
        derives that text from these same rows — and both go through the same
        redaction pass. Withholding the diagram would hide nothing the pack has
        not already released, while making an external pack look as though the
        ICAM analysis had not been done.

        A figure that fails to draw degrades to the factors in words with the
        failure stated. Losing a graphic is recoverable; failing a client's pack
        export is not.
        """
        raw = fields.get(_PACK_ICAM_FACTORS)
        if raw is None:
            return

        factors = normalise_icam_factors(raw)
        _set_pack_font(pdf, size=10)
        _write_line(pdf, icam_summary_line(factors), height=4.5)

        if factors.factors:
            try:
                draw_icam_factors_figure(pdf, factors, brand=brand)
            except Exception:  # noqa: BLE001 - a pack without its figure beats a failed export
                logger.exception("Investigation pack ICAM figure failed for pack %s", pack_uuid)
                _set_pack_font(pdf, size=9)
                _write_line(pdf, _ICAM_FIGURE_FAILED, height=4.5)
                self._render_icam_entries(pdf, factors)
            else:
                _set_pack_font(pdf, size=8)
                _write_line(pdf, _ICAM_FIGURE_NOTE, height=4)

        self._render_icam_gaps(pdf, factors)

    @staticmethod
    def _render_icam_entries(pdf: Any, factors: IcamFactorSet) -> None:
        """The factors in words, in the line shape INV-C12 already writes them in."""
        _set_pack_font(pdf, size=9)
        for factor in factors.factors:
            line = f"- {factor.category_label}: {factor.label}"
            depth_label = factor.depth_label
            if depth_label:
                line = f"{line} [{depth_label.lower()}]"
            _write_line(pdf, _pdf_safe(line, max_len=_MAX_FIELD_CHARS), height=4.2)

    @staticmethod
    def _render_icam_gaps(pdf: Any, factors: IcamFactorSet) -> None:
        """State what the diagram could not show, rather than quietly showing less."""
        if not factors.omitted and not factors.unpresentable:
            return
        _set_pack_font(pdf, size=9)
        if factors.omitted:
            _write_line(
                pdf,
                f"{plural(factors.omitted, 'further factor', 'further factors')} "
                f"{'is' if factors.omitted == 1 else 'are'} not shown in the diagram, which is capped at the "
                f"first {len(factors.factors)} in ICAM category order.",
                height=4.2,
            )
        if factors.unpresentable:
            _write_line(
                pdf,
                f"{plural(factors.unpresentable, 'stored cause', 'stored causes')} could not be presented "
                "on the diagram.",
                height=4.2,
            )
            if factors.unmapped_categories:
                named = ", ".join(humanise_key(name) for name in factors.unmapped_categories)
                _write_line(
                    pdf,
                    f"That count includes causes stored under {named} - outside the four ICAM categories, so "
                    "they are counted here rather than recategorised.",
                    height=4.2,
                )

    @staticmethod
    def _render_capa_section(pdf: Any, fields: dict[str, Any]) -> None:
        items = fields.get("items")
        if not isinstance(items, list) or not items:
            _write_line(pdf, _EMPTY_CAPA, height=4.5)
            return
        rows: list[tuple[str, str]] = []
        for item in items:
            if not isinstance(item, dict):
                rows.append(("", format_pack_field(item)))
                continue
            title = str(item.get("title") or "").strip()
            reference = str(item.get("reference") or "").strip()
            action = title or "—"
            why_level = item.get("why_level")
            if why_level is not None:
                try:
                    action = f"{action} (Why {int(why_level)})"
                except (TypeError, ValueError):
                    pass
            rows.append((reference or "—", action))
        write_block(
            pdf,
            TableBlock(
                columns=("Reference", "Action"),
                rows=tuple(rows),
                widths=(0.28, 0.72),
            ),
        )

    def _render_chronology(
        self,
        pdf: Any,
        *,
        pack: dict[str, Any],
        content: dict[str, Any],
        audience: str,
        brand: tuple[int, int, int],
        timeline_events: Any = None,
        heading: str = "Chronology",
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
        self._section_heading(pdf, heading, brand)
        _set_pack_font(pdf, size=10)

        if not chronology.events:
            _write_line(pdf, chronology_summary_line(chronology), height=4.5)
            self._render_chronology_gaps(pdf, chronology)
            pdf.ln(1)
            return

        if audience not in _CHRONOLOGY_AUDIENCES:
            _set_pack_font(pdf, size=9)
            _write_line(pdf, _CHRONOLOGY_WITHHELD, height=4.5)
            pdf.ln(1)
            return

        _write_line(pdf, chronology_summary_line(chronology), height=4.5)
        try:
            draw_chronology_figure(pdf, chronology, brand=brand)
        except Exception:  # noqa: BLE001 - a pack without its figure beats a failed export
            logger.exception("Investigation pack chronology figure failed for pack %s", pack.get("pack_uuid"))
            _set_pack_font(pdf, size=9)
            _write_line(
                pdf,
                "The chronology figure could not be drawn for this pack. The entries are listed below.",
                height=4.5,
            )

        self._render_chronology_entries(pdf, chronology)
        self._render_chronology_gaps(pdf, chronology)
        _set_pack_font(pdf, size=8)
        _write_line(pdf, _CHRONOLOGY_PROVENANCE[provenance], height=4)
        pdf.ln(1)

    @staticmethod
    def _render_chronology_entries(pdf: Any, chronology: ChronologySet) -> None:
        """The newest entries in words, because markers alone cannot be read."""
        events = list(reversed(chronology.events))[:_CHRONOLOGY_ENTRY_ROWS]
        _set_pack_font(pdf, bold=True, size=9)
        _write_line(pdf, f"Most recent entries ({len(events)} of {len(chronology.events)})", height=5)
        _set_pack_font(pdf, size=9)
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
        _set_pack_font(pdf, size=9)
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
        _ = brand
        write_section_banner(pdf, title)
