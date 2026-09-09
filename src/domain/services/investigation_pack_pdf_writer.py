"""fpdf2 writer for the pack IR — cover, running chrome, block dispatch (INV-PACK-R1).

Stay on fpdf2 so chronology/ICAM vector figures keep working. The writer is
pure and re-runnable so R2 can two-pass for contents page numbers.
"""

from __future__ import annotations

from typing import Any, Callable, Optional

from src.domain.services import investigation_pack_brand as brand
from src.domain.services.investigation_pack_ir import (
    Block,
    DocumentMeta,
    FigureBlock,
    Heading,
    KeyValueBlock,
    LegacySectionWalk,
    ListBlock,
    PackDocument,
    Paragraph,
    TableBlock,
)
from src.domain.services.investigation_pack_layout import (
    write_kv_rows,
    write_section_banner,
    write_wrapped_paragraph,
    write_wrapped_table,
)

_PackFPDF: Any = None
_COVER_BAND_H = 16.0


def _require_fpdf() -> Any:
    """Return the pack FPDF subclass. Cover is outside the PAGE n count."""
    global _PackFPDF
    try:
        from fpdf import FPDF
        from fpdf.line_break import TotalPagesSubstitutionFragment
    except ModuleNotFoundError as exc:
        raise RuntimeError("PDF export unavailable: fpdf2 is not installed in this environment") from exc
    if _PackFPDF is not None:
        return _PackFPDF

    class PackFPDF(FPDF):
        def output(self, *args: Any, **kwargs: Any) -> Any:
            orig = TotalPagesSubstitutionFragment.render_text_substitution

            def _body_total(fragment: Any, replacement_text: str) -> str:
                _ = replacement_text
                return orig(fragment, str(max(len(self.pages) - 1, 0)))

            TotalPagesSubstitutionFragment.render_text_substitution = _body_total
            try:
                return super().output(*args, **kwargs)
            finally:
                TotalPagesSubstitutionFragment.render_text_substitution = orig

    _PackFPDF = PackFPDF
    return PackFPDF


class UnknownBlockError(RuntimeError):
    """A writer must not skip a block type it does not know."""


def _attach_chrome(pdf: Any, meta: DocumentMeta) -> None:
    """Bind header/footer as instance callables so mypy is not asked to subclass a variable."""

    def header() -> None:  # noqa: N802 - fpdf2 hook
        if pdf.page_no() == 1:
            return
        pdf.set_y(10)
        pdf.image(str(brand.lockup_path()), x=pdf.l_margin, y=10, w=42)
        pdf.set_xy(pdf.l_margin + 46, 12)
        pdf.set_font(brand.FAMILY_MEDIUM, "", 8)
        pdf.set_text_color(*brand.JET_GREY)
        brand.write_tracked(
            pdf,
            f"INVESTIGATION REPORT  ·  {meta.reference}",
            width=0,
            height=5,
            spacing=0.42,
            align="R",
        )
        pdf.set_draw_color(*brand.JET_GREY)
        pdf.set_line_width(0.15)
        pdf.line(pdf.l_margin, 24, 210 - pdf.r_margin, 24)
        pdf.set_y(32)
        pdf.set_text_color(*brand.JET_GREY)

    def footer() -> None:  # noqa: N802 - fpdf2 hook
        if pdf.page_no() == 1:
            return
        pdf.set_y(-16)
        pdf.set_draw_color(*brand.JET_GREY)
        pdf.set_line_width(0.15)
        pdf.line(pdf.l_margin, pdf.get_y(), 210 - pdf.r_margin, pdf.get_y())
        pdf.set_y(-14)
        pdf.set_x(pdf.l_margin)
        pdf.set_font(brand.FAMILY_MEDIUM, "", 7)
        pdf.set_text_color(*brand.JET_GREY)
        left = f"{meta.reference}  ·  {meta.classification}"
        body_page = pdf.page_no() - 1
        brand.write_tracked(pdf, left, width=100, height=4, spacing=0.28, align="L")
        pdf.set_font(brand.FAMILY_MEDIUM, "", 7)
        pdf.set_char_spacing(0.28)
        try:
            pdf.cell(
                0,
                4,
                brand.text_safe(f"{meta.audience_label.upper()}  ·  PAGE {body_page} OF ") + "{nb}",
                align="R",
            )
        finally:
            pdf.set_char_spacing(0)

    pdf.header = header
    pdf.footer = footer


def create_pack_pdf(meta: DocumentMeta) -> Any:
    """Build a branded FPDF instance with Inter registered and chrome hooked."""
    fpdf_cls = _require_fpdf()
    brand.resolve_typeface()
    pdf = fpdf_cls(orientation="P", unit="mm", format="A4")
    brand.register_fonts(pdf)
    _attach_chrome(pdf, meta)
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=22)
    pdf.set_margins(left=16, top=32, right=16)
    return pdf


def _paint_cover_band(pdf: Any) -> None:
    """Solid Jet Grey foot on the cover — address lives here, not in the running footer."""
    y = float(pdf.h) - _COVER_BAND_H
    pdf.set_fill_color(*brand.JET_GREY)
    pdf.rect(0, y, 210, _COVER_BAND_H, style="F")
    pdf.set_text_color(*brand.WHITE)
    pdf.set_font(brand.FAMILY_MEDIUM, "", 7)
    pdf.set_xy(pdf.l_margin, y + 5.2)
    band = f"{brand.LEGAL_NAME}  ·  {brand.ADDRESS_LINE}  ·  {brand.PHONE}"
    brand.write_tracked(
        pdf,
        band.upper(),
        width=210 - pdf.l_margin - pdf.r_margin,
        height=5,
        spacing=0.48,
        align="C",
    )
    pdf.set_text_color(*brand.JET_GREY)


def write_cover(pdf: Any, meta: DocumentMeta) -> None:
    """Unnumbered cover — lockup, title, metadata, confidentiality, Jet band."""
    pdf.set_auto_page_break(auto=False)
    pdf.add_page()
    pdf.set_y(18)
    pdf.image(str(brand.lockup_path()), x=pdf.l_margin, y=16, w=72)
    pdf.set_y(42)
    pdf.set_font(brand.FAMILY_MEDIUM, "", 8)
    pdf.set_text_color(*brand.CRIMSON)
    brand.write_tracked(
        pdf,
        f"QUALITY GOVERNANCE PORTAL  ·  {meta.audience_label.upper()}",
        width=0,
        height=5,
        spacing=0.55,
        align="L",
        new_x="LMARGIN",
        new_y="NEXT",
    )
    pdf.ln(2)
    pdf.set_font(brand.FAMILY_REGULAR, "B", 28)
    pdf.set_text_color(*brand.JET_GREY)
    pdf.cell(0, 10, "Investigation", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 10, "Report", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)
    display = brand.text_safe(meta.incident_reference or meta.reference)
    pdf.set_font(brand.FAMILY_SEMIBOLD, "", 16)
    pdf.set_text_color(*brand.CRIMSON)
    pdf.cell(0, 8, display, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)
    pdf.set_draw_color(*brand.CRIMSON)
    pdf.set_line_width(0.6)
    pdf.line(pdf.l_margin, pdf.get_y(), 210 - pdf.r_margin, pdf.get_y())
    pdf.ln(6)

    rows = (
        ("Investigation reference", meta.reference),
        ("Incident reference", meta.incident_reference or meta.reference),
        ("Status", meta.status_label),
        ("Investigation level", meta.level_label),
        ("Pack title", meta.title),
        ("Pack type", meta.audience_label),
        ("Generated", meta.generated_at_label),
        ("Issued by", brand.ISSUED_BY),
    )
    band_ceiling = float(pdf.h) - _COVER_BAND_H - 6
    for label, value in rows:
        if float(pdf.get_y()) > band_ceiling:
            break
        pdf.set_x(pdf.l_margin)
        pdf.set_font(brand.FAMILY_MEDIUM, "", 8)
        pdf.set_text_color(*brand.CRIMSON)
        brand.write_tracked(pdf, label.upper(), width=48, height=5, spacing=0.38, align="L")
        pdf.set_font(brand.FAMILY_REGULAR, "", 10)
        pdf.set_text_color(*brand.JET_GREY)
        pdf.multi_cell(0, 5, brand.text_safe(value), new_x="LMARGIN", new_y="NEXT")

    if meta.confidentiality and float(pdf.get_y()) < band_ceiling - 12:
        pdf.ln(4)
        pdf.set_font(brand.FAMILY_MEDIUM, "", 8)
        pdf.set_text_color(*brand.CRIMSON)
        brand.write_tracked(
            pdf,
            "CONFIDENTIALITY",
            width=0,
            height=5,
            spacing=0.5,
            align="L",
            new_x="LMARGIN",
            new_y="NEXT",
        )
        pdf.set_font(brand.FAMILY_REGULAR, "", 9)
        pdf.set_text_color(*brand.JET_GREY)
        pdf.multi_cell(0, 4.5, brand.text_safe(meta.confidentiality), new_x="LMARGIN", new_y="NEXT")

    _paint_cover_band(pdf)
    pdf.set_auto_page_break(auto=True, margin=22)


def write_contents(pdf: Any, document: PackDocument) -> None:
    entries = document.contents_entries()
    if not entries:
        return
    pdf.add_page()
    pdf.set_font(brand.FAMILY_MEDIUM, "", 9)
    pdf.set_text_color(*brand.CRIMSON)
    brand.write_tracked(
        pdf,
        "\u2014 CONTENTS",
        width=0,
        height=7,
        spacing=0.7,
        align="L",
        new_x="LMARGIN",
        new_y="NEXT",
    )
    pdf.ln(5)
    links: dict[int, int] = {}
    for number, heading in entries:
        link_id = pdf.add_link()
        links[number] = link_id
        pdf.set_font(brand.FAMILY_REGULAR, "", 11)
        pdf.set_text_color(*brand.JET_GREY)
        pdf.cell(10, 8, str(number), align="L", link=link_id)
        pdf.cell(0, 8, brand.text_safe(heading), new_x="LMARGIN", new_y="NEXT", link=link_id)
    pdf._pack_toc_links = links  # noqa: SLF001 - consumed by bind_section_destination
    pdf.ln(6)


def write_key_value_block(pdf: Any, block: KeyValueBlock) -> None:
    write_kv_rows(
        pdf,
        tuple((row.label, row.value) for row in block.rows),
        panel_keys=frozenset({"description"}),
    )


def write_block(
    pdf: Any,
    block: Block,
    *,
    on_legacy: Optional[Callable[[Any, LegacySectionWalk], None]] = None,
    on_figure: Optional[Callable[[Any, FigureBlock], None]] = None,
) -> None:
    if isinstance(block, Heading):
        label = f"{block.number} {block.text}".strip() if block.number else block.text
        if block.level <= 1:
            write_section_banner(pdf, label)
        else:
            pdf.set_font(brand.FAMILY_REGULAR, "B", 11)
            pdf.set_text_color(*brand.JET_GREY)
            write_wrapped_paragraph(pdf, label, size=11)
        return
    if isinstance(block, Paragraph):
        from src.domain.services.investigation_pack_ir import Emphasis

        size = 9 if block.emphasis is Emphasis.NOTE else 10
        write_wrapped_paragraph(pdf, block.text, size=size)
        pdf.ln(1)
        return
    if isinstance(block, KeyValueBlock):
        write_key_value_block(pdf, block)
        pdf.ln(1)
        return
    if isinstance(block, ListBlock):
        if not block.items and block.empty_message:
            write_wrapped_paragraph(pdf, block.empty_message)
            return
        for index, item in enumerate(block.items, start=1):
            prefix = f"{index}. " if block.ordered else "- "
            write_wrapped_paragraph(pdf, prefix + item)
        pdf.ln(1)
        return
    if isinstance(block, TableBlock):
        write_wrapped_table(
            pdf,
            block.columns,
            block.rows,
            widths=block.widths,
            empty_message=block.empty_message,
        )
        return
    if isinstance(block, FigureBlock):
        if on_figure is None:
            raise UnknownBlockError(f"No figure writer for {block.kind}")
        on_figure(pdf, block)
        return
    if isinstance(block, LegacySectionWalk):
        if on_legacy is None:
            raise UnknownBlockError("Legacy section walk has no writer")
        on_legacy(pdf, block)
        return
    raise UnknownBlockError(f"Unknown pack block {type(block).__name__}")


def write_document(
    pdf: Any,
    document: PackDocument,
    *,
    on_legacy: Optional[Callable[[Any, LegacySectionWalk], None]] = None,
    on_figure: Optional[Callable[[Any, FigureBlock], None]] = None,
) -> None:
    write_cover(pdf, document.meta)
    write_contents(pdf, document)
    for section in document.sections:
        write_section_banner(pdf, section.heading)
        for block in section.blocks:
            write_block(pdf, block, on_legacy=on_legacy, on_figure=on_figure)
