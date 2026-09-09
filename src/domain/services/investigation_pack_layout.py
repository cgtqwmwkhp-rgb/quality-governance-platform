"""Measured wrap and boxed frames for the investigation pack (INV-PACK-R4).

fpdf2 ``cell()`` paints past the column when the string is longer than the
width. Truncating with ``[:80]`` then drops the rest of the sentence. This
module wraps with :func:`wrap_text` and draws inside a reserved frame so a
line cannot leave its box.
"""

from __future__ import annotations

import re
from typing import Any, Sequence

from src.domain.services import investigation_pack_brand as brand
from src.domain.services.investigation_pack_draw import Frame, content_width, draw_rect, space_remaining, wrap_text

_CHAPTER_PREFIX = re.compile(r"^(\d{2})\b")

_LINE = 5.0
_PAD = 3.2
_BAR = 2.2
_LABEL_COL = 48.0
_DESCENT = 1.8
_FIRST_BASELINE = _PAD + 3.6
_WRAP_SLACK = 6.0  # Inter width vs paint; wrap a little tighter than the frame.
_FINDING_GAP = 6.5
_KV_ROW_GAP = 2.2


def inner_width(pdf: Any) -> float:
    return content_width(pdf)


def wrap_paragraphs(pdf: Any, text: str, max_width: float) -> list[str]:
    """Wrap each stored paragraph. Newlines are breaks, never glyphs."""
    lines: list[str] = []
    for para in str(text or "").replace("\r\n", "\n").split("\n"):
        piece = para.strip()
        if not piece:
            continue
        lines.extend(wrap_text(pdf, brand.text_safe(piece), max_width) or [brand.text_safe(piece)])
    return lines or [""]


def _box_height(line_count: int) -> float:
    count = max(1, line_count)
    return _FIRST_BASELINE + (count - 1) * _LINE + _DESCENT + _PAD


def _max_lines(avail: float) -> int:
    usable = avail - _FIRST_BASELINE - _DESCENT - _PAD
    if usable < _LINE:
        return 0
    return max(1, int(usable / _LINE))


def ensure_space(pdf: Any, height: float) -> None:
    """Break before drawing if this frame will not fit above the footer."""
    if height <= 0:
        return
    if space_remaining(pdf) < height + 1.0:
        pdf.add_page()


def _paint_lines(
    pdf: Any,
    lines: Sequence[str],
    *,
    x: float,
    y: float,
    leading: float,
    rgb: tuple[int, int, int] = brand.JET_GREY,
) -> None:
    pdf.set_text_color(*rgb)
    cursor = y
    for line in lines:
        pdf.text(x, cursor, line)
        cursor += leading


def write_wrapped_paragraph(pdf: Any, text: str, *, size: float = 10, leading: float = _LINE) -> None:
    """Body text that wraps to the content width. Never clips, never ellipsizes."""
    pdf.set_font(brand.FAMILY_REGULAR, "", size)
    pdf.set_text_color(*brand.JET_GREY)
    width = inner_width(pdf)
    lines = wrap_paragraphs(pdf, text, max(8.0, width - _WRAP_SLACK))
    for line in lines:
        ensure_space(pdf, leading + 0.5)
        pdf.set_x(pdf.l_margin)
        pdf.cell(width, leading, line, new_x="LMARGIN", new_y="NEXT")


def bind_section_destination(pdf: Any, title: str) -> None:
    """Point the contents link and PDF outline at this chapter banner.

    ``write_contents`` creates the link ids first. Numbered banners (``01 …``)
    call ``set_link`` here so a click on Contents lands on the heading, not the
    cover. Unnumbered titles (Contents itself) are not destinations.
    """
    text = brand.text_safe(title).strip()
    match = _CHAPTER_PREFIX.match(text)
    if match is None:
        return
    number = int(match.group(1))
    links = getattr(pdf, "_pack_toc_links", None) or {}
    link_id = links.get(number)
    if link_id is not None:
        pdf.set_link(link_id, y=float(pdf.get_y()), x=float(pdf.l_margin), page=int(pdf.page_no()))
    pdf.start_section(text, level=0, strict=False)


def write_section_banner(pdf: Any, title: str) -> None:
    """Crimson tracked chapter title — the model's 01 INCIDENT DETAILS chrome."""
    ensure_space(pdf, 16)
    bind_section_destination(pdf, title)
    raw = brand.text_safe(title).strip()
    display = raw.upper() if _CHAPTER_PREFIX.match(raw) else raw
    pdf.set_font(brand.FAMILY_MEDIUM, "", 11)
    pdf.set_text_color(*brand.CRIMSON)
    width = inner_width(pdf)
    lines = wrap_text(pdf, display, max(8.0, width - 10.0)) or [display]
    for line in lines:
        pdf.set_x(pdf.l_margin)
        brand.write_tracked(
            pdf,
            line,
            width=width,
            height=6.5,
            spacing=0.18,
            align="L",
            new_x="LMARGIN",
            new_y="NEXT",
        )
    y = float(pdf.get_y()) + 0.8
    pdf.set_draw_color(*brand.JET_GREY)
    pdf.set_line_width(0.55)
    pdf.line(float(pdf.l_margin), y, float(pdf.w) - float(pdf.r_margin), y)
    pdf.set_y(y + 4.5)
    pdf.set_text_color(*brand.JET_GREY)


def write_panel(
    pdf: Any,
    text: str,
    *,
    bar: tuple[int, int, int] = brand.JET_GREY,
    fill: tuple[int, int, int] = brand.PLATINUM,
    size: float = 10,
) -> None:
    """Shaded box with a left bar. Splits across pages rather than overflowing."""
    pdf.set_font(brand.FAMILY_REGULAR, "", size)
    width = inner_width(pdf)
    inset = 4.0
    text_width = max(12.0, width - inset - _WRAP_SLACK)
    remaining = wrap_paragraphs(pdf, text, text_width)
    while remaining:
        avail = space_remaining(pdf)
        max_lines = _max_lines(avail)
        if max_lines < 1:
            pdf.add_page()
            continue
        chunk = remaining[:max_lines]
        remaining = remaining[max_lines:]
        height = _box_height(len(chunk))
        ensure_space(pdf, height)
        y = float(pdf.get_y())
        frame = Frame(float(pdf.l_margin), y, width, height)
        draw_rect(pdf, frame, fill=fill)
        draw_rect(pdf, Frame(frame.x, frame.y, _BAR, frame.h), fill=bar)
        _paint_lines(pdf, chunk, x=frame.x + inset, y=frame.y + _FIRST_BASELINE, leading=_LINE)
        pdf.set_y(frame.bottom + 2.0)


def write_finding_card(pdf: Any, index: int, body: str) -> None:
    """Display numeral 01–09 on white paper. No platinum slab, no left bar."""
    numeral = f"{index:02d}"
    numeral_w = 16.0
    width = inner_width(pdf)
    pdf.set_font(brand.FAMILY_REGULAR, "", 10)
    text_width = max(20.0, width - numeral_w - _WRAP_SLACK)
    remaining = wrap_paragraphs(pdf, body, text_width)
    while remaining:
        avail = space_remaining(pdf)
        max_lines = _max_lines(avail)
        if max_lines < 1:
            pdf.add_page()
            continue
        chunk = remaining[:max_lines]
        remaining = remaining[max_lines:]
        height = max(10.0, _box_height(len(chunk)))
        ensure_space(pdf, height)
        y = float(pdf.get_y())
        x = float(pdf.l_margin)
        pdf.set_font(brand.FAMILY_REGULAR, "B", 16)
        pdf.set_text_color(*brand.CRIMSON)
        pdf.text(x, y + 6.2, numeral)
        pdf.set_font(brand.FAMILY_REGULAR, "", 10)
        _paint_lines(
            pdf,
            chunk,
            x=x + numeral_w,
            y=y + _FIRST_BASELINE,
            leading=_LINE,
        )
        pdf.set_y(y + height + _FINDING_GAP)


def write_why_card(pdf: Any, level: int, answer: str, evidence: str | None, question: str | None) -> None:
    """WHY n / ANSWER / EVIDENCE on white. Empty questions are omitted, not Not recorded."""
    _ = question
    write_wrapped_table(
        pdf,
        ("WHY", "ANSWER", "EVIDENCE"),
        ((f"WHY {level}", answer, evidence or ""),),
        widths=(0.16, 0.52, 0.32),
        row_gap=3.0,
        boxed=False,
    )


def write_integrity(pdf: Any, pack_uuid: str, sha256: str, note: str) -> None:
    """Pack UUID as a kv row; checksum tracked (Inter stands in for the model's mono)."""
    write_kv_rows(pdf, (("Pack UUID", pack_uuid),), panel_keys=frozenset())
    pdf.set_font(brand.FAMILY_MEDIUM, "", 8)
    pdf.set_text_color(*brand.CRIMSON)
    write_wrapped_paragraph(pdf, "CONTENT SHA-256", size=8)
    pdf.set_font(brand.FAMILY_REGULAR, "", 8)
    pdf.set_text_color(*brand.JET_GREY)
    pdf.set_char_spacing(0.22)
    try:
        write_wrapped_paragraph(pdf, sha256, size=8)
    finally:
        pdf.set_char_spacing(0)
    pdf.set_font(brand.FAMILY_REGULAR, "", 9)
    write_wrapped_paragraph(pdf, note, size=9)
    pdf.ln(1)


def write_kv_rows(pdf: Any, rows: Sequence[tuple[str, str]], *, panel_keys: frozenset[str] | None = None) -> None:
    """Label / value rows with a hairline rule. Platinum panels are opt-in (alerts only)."""
    panel_keys = panel_keys or frozenset()
    for label, value in rows:
        key = label.strip().lower()
        if key in panel_keys:
            pdf.set_font(brand.FAMILY_MEDIUM, "", 8)
            pdf.set_text_color(*brand.CRIMSON)
            write_wrapped_paragraph(pdf, label.upper(), size=8)
            write_panel(pdf, value, bar=brand.JET_GREY)
            continue
        pdf.set_font(brand.FAMILY_MEDIUM, "", 8)
        label_text = brand.text_safe(label.upper())
        pdf.set_font(brand.FAMILY_REGULAR, "", 10)
        value_width = max(20.0, inner_width(pdf) - _LABEL_COL - 2.0)
        lines = wrap_paragraphs(pdf, value, max(12.0, value_width - _WRAP_SLACK))
        height = max(6.0, len(lines) * _LINE + 1.5)
        ensure_space(pdf, height + 2.0)
        y = float(pdf.get_y())
        pdf.set_font(brand.FAMILY_MEDIUM, "", 8)
        pdf.set_text_color(*brand.CRIMSON)
        pdf.text(float(pdf.l_margin), y + 4.0, label_text)
        pdf.set_font(brand.FAMILY_REGULAR, "", 10)
        _paint_lines(pdf, lines, x=float(pdf.l_margin) + _LABEL_COL, y=y + 4.0, leading=_LINE)
        bottom = y + height
        pdf.set_draw_color(210, 206, 201)
        pdf.set_line_width(0.2)
        pdf.line(float(pdf.l_margin), bottom, float(pdf.w) - float(pdf.r_margin), bottom)
        pdf.set_y(bottom + _KV_ROW_GAP)


def _column_widths(pdf: Any, columns: Sequence[str], fractions: Sequence[float] | None) -> list[float]:
    width = inner_width(pdf)
    count = max(1, len(columns))
    if fractions and len(fractions) == count:
        return [width * float(part) for part in fractions]
    if count == 2:
        return [width * 0.28, width * 0.72]
    return [width / count] * count


def write_wrapped_table(
    pdf: Any,
    columns: Sequence[str],
    rows: Sequence[Sequence[str]],
    *,
    widths: Sequence[float] | None = None,
    empty_message: str | None = None,
    row_gap: float = 0.0,
    boxed: bool = True,
) -> None:
    """Header bar + wrapping cells. Repeats the header after a page break."""
    if not rows:
        if empty_message:
            write_wrapped_paragraph(pdf, empty_message)
        return

    col_w = _column_widths(pdf, columns, list(widths) if widths else None)
    header_h = 8.0

    def _header() -> None:
        ensure_space(pdf, header_h + 6.0)
        y = float(pdf.get_y())
        x = float(pdf.l_margin)
        draw_rect(pdf, Frame(x, y, inner_width(pdf), header_h), fill=brand.JET_GREY)
        pdf.set_font(brand.FAMILY_MEDIUM, "", 7.5)
        pdf.set_text_color(*brand.WHITE)
        cx = x
        for heading, width in zip(columns, col_w, strict=False):
            lines = wrap_paragraphs(pdf, str(heading).upper(), max(8.0, width - 3.0))
            pdf.text(cx + 1.6, y + 5.2, lines[0])
            cx += width
        pdf.set_y(y + header_h)

    _header()
    pdf.set_font(brand.FAMILY_REGULAR, "", 9)
    for row in rows:
        cells = list(row) + [""] * max(0, len(col_w) - len(row))
        wrapped: list[list[str]] = []
        for cell, width in zip(cells, col_w, strict=False):
            wrapped.append(wrap_paragraphs(pdf, str(cell), max(8.0, width - 3.2 - _WRAP_SLACK / 2)))
        row_h = _box_height(max(len(lines) for lines in wrapped))
        if space_remaining(pdf) < row_h + 1.0:
            pdf.add_page()
            _header()
            pdf.set_font(brand.FAMILY_REGULAR, "", 9)
        y = float(pdf.get_y())
        x = float(pdf.l_margin)
        if boxed:
            draw_rect(pdf, Frame(x, y, inner_width(pdf), row_h), border=(210, 206, 201))
        cx = x
        for lines, width in zip(wrapped, col_w, strict=False):
            _paint_lines(pdf, lines, x=cx + 1.6, y=y + _FIRST_BASELINE, leading=_LINE)
            cx += width
        pdf.set_y(y + row_h + row_gap)
    pdf.ln(2)
