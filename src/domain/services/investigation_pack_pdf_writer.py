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


def _require_fpdf() -> Any:
    try:
        from fpdf import FPDF
    except ModuleNotFoundError as exc:
        raise RuntimeError("PDF export unavailable: fpdf2 is not installed in this environment") from exc
    return FPDF


class UnknownBlockError(RuntimeError):
    """A writer must not skip a block type it does not know."""


def _attach_chrome(pdf: Any, meta: DocumentMeta) -> None:
    """Bind header/footer as instance callables so mypy is not asked to subclass a variable."""

    def header() -> None:  # noqa: N802 - fpdf2 hook
        if pdf.page_no() == 1:
            return
        pdf.set_y(8)
        pdf.image(str(brand.lockup_path()), x=pdf.l_margin, y=8, w=42)
        pdf.set_xy(pdf.l_margin + 46, 10)
        pdf.set_font(brand.FAMILY_MEDIUM, "", 8)
        pdf.set_text_color(*brand.JET_GREY)
        pdf.cell(
            0,
            5,
            brand.text_safe(f"Investigation report · {meta.reference}"),
            align="R",
        )
        pdf.set_draw_color(*brand.CRIMSON)
        pdf.set_line_width(0.35)
        pdf.line(pdf.l_margin, 22, 210 - pdf.r_margin, 22)
        pdf.set_y(26)
        pdf.set_text_color(*brand.JET_GREY)

    def footer() -> None:  # noqa: N802 - fpdf2 hook
        pdf.set_y(-18)
        pdf.set_draw_color(*brand.JET_GREY)
        pdf.set_line_width(0.2)
        pdf.line(pdf.l_margin, pdf.get_y(), 210 - pdf.r_margin, pdf.get_y())
        pdf.set_y(-16)
        pdf.set_font(brand.FAMILY_REGULAR, "", 7)
        pdf.set_text_color(*brand.JET_GREY)
        left = brand.text_safe(f"Investigation report · {meta.reference}")
        right = brand.text_safe(
            f"{meta.reference} · {meta.classification} · " f"{meta.audience_label} · Page {pdf.page_no()} of {{nb}}"
        )
        pdf.cell(95, 4, left, align="L")
        pdf.cell(0, 4, right, align="R")
        pdf.set_y(-12)
        pdf.set_font(brand.FAMILY_REGULAR, "", 6.5)
        pdf.cell(0, 4, brand.text_safe(brand.legal_footer_line()), align="C")

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
    pdf.set_auto_page_break(auto=True, margin=26)
    pdf.set_margins(left=16, top=28, right=16)
    return pdf


def write_cover(pdf: Any, meta: DocumentMeta) -> None:
    """Page 1 — lockup, title, metadata, confidentiality, legal line."""
    pdf.add_page()
    pdf.set_y(18)
    pdf.image(str(brand.lockup_path()), x=pdf.l_margin, y=16, w=72)
    pdf.set_y(42)
    pdf.set_font(brand.FAMILY_MEDIUM, "", 8)
    pdf.set_text_color(*brand.CRIMSON)
    eyebrow = brand.text_safe(f"QUALITY GOVERNANCE PORTAL · {meta.audience_label.upper()}")
    pdf.cell(0, 5, eyebrow, new_x="LMARGIN", new_y="NEXT")
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
    for label, value in rows:
        pdf.set_x(pdf.l_margin)
        pdf.set_font(brand.FAMILY_MEDIUM, "", 8)
        pdf.set_text_color(*brand.CRIMSON)
        pdf.cell(48, 5, brand.text_safe(label.upper()), align="L")
        pdf.set_font(brand.FAMILY_REGULAR, "", 10)
        pdf.set_text_color(*brand.JET_GREY)
        pdf.multi_cell(0, 5, brand.text_safe(value), new_x="LMARGIN", new_y="NEXT")

    if meta.confidentiality:
        pdf.ln(4)
        pdf.set_font(brand.FAMILY_REGULAR, "B", 8)
        pdf.set_text_color(*brand.CRIMSON)
        pdf.cell(0, 5, "CONFIDENTIALITY", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font(brand.FAMILY_REGULAR, "", 9)
        pdf.set_text_color(*brand.JET_GREY)
        pdf.multi_cell(0, 4.5, brand.text_safe(meta.confidentiality), new_x="LMARGIN", new_y="NEXT")


def write_contents(pdf: Any, document: PackDocument) -> None:
    entries = document.contents_entries()
    if not entries:
        return
    pdf.add_page()
    write_section_banner(pdf, "Contents")
    for number, heading in entries:
        pdf.set_font(brand.FAMILY_REGULAR, "", 10)
        pdf.set_text_color(*brand.JET_GREY)
        pdf.cell(12, 6, f"{number:02d}", align="L")
        pdf.cell(0, 6, brand.text_safe(heading), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)


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
