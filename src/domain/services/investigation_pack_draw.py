"""Vector drawing helpers and the pack figures for investigation packs (INV-C15 / INV-C16).

Absorbs PR-27 (drawing helpers), PR-28 (graphical chronology) and PR-29 (ICAM
contributing-factor diagram). Three parts, kept in one module on purpose so a
pack figure imports one place:

**Part 1 — primitives.** Text safety, colour arithmetic, page-space reservation
and the vector calls themselves (lines, rectangles, markers, arrows, legends).
Nothing here knows what an investigation is, so the figures below build on them
without importing pack semantics.

**Part 2 — the chronology figure.** Normalises timeline events into a placeable
set and draws them as a two-lane time axis: the parent record's chronology above
the axis, the investigation's own events below it. That split is exactly the
distinction INV-C9 put in ``event_metadata["origin"]`` — this module reads that
key and never re-derives origin from anything else.

**Part 3 — the ICAM contributing-factor figure.** Four bands, one per ICAM
category, listing the factors INV-C12 stores on ``fishbone_diagrams.causes``
with their sub-causes and their HSG245 causal depth. Not a 6M fishbone: there is
no fifth taxonomy, and a cause stored under a pre-DEC-1 6M key is counted and
named rather than recategorised into a band it was never classified under.

Deliberate non-coupling
-----------------------
``ORIGIN_SOURCE`` / ``ORIGIN_INVESTIGATION`` are re-declared here rather than
imported from :mod:`src.domain.services.investigation_parent_timeline`, and the
ICAM category and depth vocabulary rather than from
:mod:`src.domain.services.investigation_factors_service`, because both of those
modules import ORM models to run their queries and the drawing layer must stay
free of the database. Every copied spelling is pinned equal by a unit test, so a
rename on the owning side fails loudly instead of silently emptying a lane or a
band.

Nothing in this module reads the database, and nothing writes anywhere. It draws
the events it is handed, so tenant scoping and authorisation belong to whoever
loads them — which is the point of taking them as an argument rather than
querying: the pack renderer has no session, no tenant and no way to widen what
the caller was allowed to see.

fpdf2 notes
-----------
* ``pdf.text(x, y, s)`` places the text *baseline* at ``y``; every helper here
  that takes a ``y`` for text means the baseline.
* ``FPDF.circle`` changed its parameter meaning in fpdf2 2.8.1, so
  :func:`draw_marker` uses ``ellipse`` with an explicit centre instead. The
  drawing survives an fpdf2 upgrade inside the pinned ``>=2.8.0,<3.0.0`` range.
* Absolute drawing never triggers fpdf2's auto page break, so a figure must be
  placed inside a frame obtained from :func:`reserve_frame`, which breaks the
  page *before* drawing starts if the figure would not fit.
"""

from __future__ import annotations

import logging
import math
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterator, Mapping, Optional, Sequence

logger = logging.getLogger(__name__)

RGB = tuple[int, int, int]

BLACK: RGB = (0, 0, 0)
WHITE: RGB = (255, 255, 255)

# ---------------------------------------------------------------------------
# Part 1 — primitives
# ---------------------------------------------------------------------------

# Month names are spelled out rather than taken from ``strftime("%b")``: that is
# locale-dependent, and a figure whose axis labels change with the host locale
# cannot be pinned by a golden fixture.
_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def pdf_safe(value: Any, *, max_len: Optional[int] = None) -> str:
    """Helvetica (latin-1) safe text; never invent content on failure."""
    text = "" if value is None else str(value)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.encode("latin-1", errors="replace").decode("latin-1")
    if max_len is not None and len(text) > max_len:
        text = text[: max_len - 3].rstrip() + "..."
    return text


def humanise_key(key: Any) -> str:
    """Turn a stored section/field/event key into a report label (`root_cause` -> `Root cause`)."""
    raw = str(key or "").strip()
    if not raw:
        return "Untitled"
    words = raw.replace("-", " ").replace("_", " ").replace(".", " ").split()
    if not words:
        return raw
    first, *rest = words
    return " ".join([first[:1].upper() + first[1:], *(w.lower() for w in rest)])


def _safe_for_document(pdf: Any, value: Any, *, max_len: Optional[int] = None) -> str:
    """Use Inter coverage when the pack registered Inter; otherwise latin-1 Helvetica."""
    if getattr(pdf, "_pack_font_family", None):
        from src.domain.services.investigation_pack_brand import text_safe

        return text_safe(value, max_len=max_len)
    return pdf_safe(value, max_len=max_len)


def fit_text(pdf: Any, text: Any, max_width: float) -> str:
    """Ellipsize document-safe text so it cannot paint outside a fixed-width PDF cell."""
    safe_text = _safe_for_document(pdf, text)
    if pdf.get_string_width(safe_text) <= max_width:
        return safe_text

    ellipsis = "..."
    available_width = max_width - pdf.get_string_width(ellipsis)
    if available_width <= 0:
        return ""

    low, high = 0, len(safe_text)
    while low < high:
        midpoint = (low + high + 1) // 2
        if pdf.get_string_width(safe_text[:midpoint].rstrip()) <= available_width:
            low = midpoint
        else:
            high = midpoint - 1
    return safe_text[:low].rstrip() + ellipsis


def wrap_text(pdf: Any, text: Any, max_width: float) -> list[str]:
    """Split document-safe text onto lines that fit ``max_width``. Never ellipsizes.

    The chronology/ICAM Helvetica figures still use :func:`fit_text` so their
    golden fixtures stay byte-identical. The pack path (Inter) wraps instead of
    treating an ellipsis as layout.
    """
    safe_text = _safe_for_document(pdf, text)
    if not safe_text or max_width <= 0:
        return []
    if pdf.get_string_width(safe_text) <= max_width:
        return [safe_text]

    def _split_overlong(token: str) -> list[str]:
        parts: list[str] = []
        rest = token
        while rest:
            if pdf.get_string_width(rest) <= max_width:
                parts.append(rest)
                break
            low, high, cut = 1, len(rest), 1
            while low <= high:
                mid = (low + high) // 2
                if pdf.get_string_width(rest[:mid]) <= max_width:
                    cut = mid
                    low = mid + 1
                else:
                    high = mid - 1
            parts.append(rest[:cut])
            rest = rest[cut:]
        return parts

    lines: list[str] = []
    current = ""
    for word in safe_text.split(" "):
        candidate = word if not current else f"{current} {word}"
        if pdf.get_string_width(candidate) <= max_width:
            current = candidate
            continue
        if current:
            lines.append(current)
            current = ""
        chunks = _split_overlong(word)
        if not chunks:
            continue
        *full, last = chunks
        lines.extend(full)
        current = last
    if current:
        lines.append(current)
    return lines


@dataclass(frozen=True)
class Frame:
    """A rectangular region in millimetres, top-left origin (PDF user space)."""

    x: float
    y: float
    w: float
    h: float

    @property
    def right(self) -> float:
        return self.x + self.w

    @property
    def bottom(self) -> float:
        return self.y + self.h

    @property
    def cx(self) -> float:
        return self.x + self.w / 2

    @property
    def cy(self) -> float:
        return self.y + self.h / 2

    def inset(self, dx: float, dy: Optional[float] = None) -> "Frame":
        """Shrink by ``dx`` horizontally and ``dy`` (default ``dx``) vertically."""
        dy = dx if dy is None else dy
        return Frame(self.x + dx, self.y + dy, max(0.0, self.w - 2 * dx), max(0.0, self.h - 2 * dy))


def content_width(pdf: Any) -> float:
    """Printable width between the current left and right margins."""
    return float(pdf.w) - float(pdf.l_margin) - float(pdf.r_margin)


def space_remaining(pdf: Any) -> float:
    """Vertical space left on this page above the auto-page-break margin."""
    return float(pdf.h) - float(pdf.b_margin) - float(pdf.get_y())


def usable_page_height(pdf: Any) -> float:
    """Full printable height of a page, top margin to break margin."""
    return float(pdf.h) - float(pdf.b_margin) - float(pdf.t_margin)


def reserve_frame(pdf: Any, height: float, *, width: Optional[float] = None, top_gap: float = 0.0) -> Frame:
    """Reserve ``height`` mm at the cursor, breaking the page first if it will not fit.

    Absolute vector drawing bypasses fpdf2's auto page break, so a figure drawn
    at the foot of a page would paint over the footer. Reserving up front is the
    only ordering that cannot: the break happens before any ink is laid down.

    The cursor is advanced to the bottom of the returned frame, so the caller
    continues writing text underneath it.
    """
    if height <= 0:
        raise ValueError("reserve_frame needs a positive height")

    page_height = usable_page_height(pdf)
    if height > page_height:
        # Honest clamp: a figure taller than a page cannot be drawn on one, and
        # silently letting it overrun would paint over the footer.
        logger.warning("pack_draw_frame_clamped requested=%.1f page=%.1f", height, page_height)
        height = page_height

    y = float(pdf.get_y()) + max(0.0, top_gap)
    if height > float(pdf.h) - float(pdf.b_margin) - y:
        pdf.add_page()
        y = float(pdf.get_y())

    frame = Frame(float(pdf.l_margin), y, content_width(pdf) if width is None else width, height)
    pdf.set_y(frame.bottom)
    return frame


@contextmanager
def vector_state(pdf: Any) -> Iterator[None]:
    """Restore font, line width, dash and colours afterwards — including on failure.

    Colours cannot be read back off an ``FPDF`` portably, so they are restored to
    the document defaults (black ink, white fill) rather than to their previous
    values. Every text section in the pack sets its own font and colour before
    writing, so the default is the safe landing point.
    """
    family = str(getattr(pdf, "font_family", "") or getattr(pdf, "_pack_font_family", None) or "Helvetica")
    style = str(getattr(pdf, "font_style", "") or "")
    size = float(getattr(pdf, "font_size_pt", 10) or 10)
    line_width = float(getattr(pdf, "line_width", 0.2) or 0.2)
    try:
        yield
    finally:
        pdf.set_dash_pattern()
        pdf.set_line_width(line_width)
        pdf.set_draw_color(*BLACK)
        pdf.set_fill_color(*WHITE)
        pdf.set_text_color(*BLACK)
        pdf.set_font(family, style, size)


def _channel(value: float) -> int:
    return max(0, min(255, int(round(value))))


def mix(first: RGB, second: RGB, weight: float) -> RGB:
    """Blend two colours; ``weight`` 0 returns ``first``, 1 returns ``second``."""
    ratio = max(0.0, min(1.0, weight))
    return (
        _channel(first[0] + (second[0] - first[0]) * ratio),
        _channel(first[1] + (second[1] - first[1]) * ratio),
        _channel(first[2] + (second[2] - first[2]) * ratio),
    )


def tint(rgb: RGB, amount: float) -> RGB:
    """Lighten towards white."""
    return mix(rgb, WHITE, amount)


def shade(rgb: RGB, amount: float) -> RGB:
    """Darken towards black."""
    return mix(rgb, BLACK, amount)


def relative_luminance(rgb: RGB) -> float:
    """WCAG relative luminance, used to choose readable text over a fill."""

    def channel(raw: int) -> float:
        srgb = max(0, min(255, raw)) / 255
        return srgb / 12.92 if srgb <= 0.04045 else ((srgb + 0.055) / 1.055) ** 2.4

    return 0.2126 * channel(rgb[0]) + 0.7152 * channel(rgb[1]) + 0.0722 * channel(rgb[2])


def readable_text_rgb(background: RGB) -> RGB:
    """Black or white text, whichever contrasts better with ``background``."""
    return BLACK if relative_luminance(background) > 0.179 else WHITE


def draw_line(
    pdf: Any,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    *,
    rgb: RGB = BLACK,
    width: float = 0.3,
    dash: Optional[tuple[float, float]] = None,
) -> None:
    """Straight line. ``dash`` is ``(dash_mm, gap_mm)`` and is reset afterwards."""
    pdf.set_draw_color(*rgb)
    pdf.set_line_width(width)
    if dash is not None:
        pdf.set_dash_pattern(dash=dash[0], gap=dash[1])
    pdf.line(x1, y1, x2, y2)
    if dash is not None:
        pdf.set_dash_pattern()


def draw_rect(
    pdf: Any,
    frame: Frame,
    *,
    fill: Optional[RGB] = None,
    border: Optional[RGB] = None,
    width: float = 0.3,
) -> None:
    """Rectangle from a :class:`Frame`. Fill, border, or both."""
    if fill is None and border is None:
        border = BLACK
    if fill is not None:
        pdf.set_fill_color(*fill)
    pdf.set_draw_color(*(border if border is not None else fill or BLACK))
    pdf.set_line_width(width)
    style = "DF" if (fill is not None and border is not None) else ("F" if fill is not None else "D")
    pdf.rect(frame.x, frame.y, frame.w, frame.h, style=style)


def draw_marker(
    pdf: Any,
    cx: float,
    cy: float,
    size: float,
    *,
    shape: str = "circle",
    fill: Optional[RGB] = None,
    border: Optional[RGB] = None,
    width: float = 0.2,
) -> None:
    """Marker centred on ``(cx, cy)``, ``size`` mm across.

    Shape carries meaning as well as colour, so the figure still separates its
    series when the pack is printed in mono. Unknown shapes fall back to a
    circle rather than drawing nothing.
    """
    if fill is None and border is None:
        fill = BLACK
    if fill is not None:
        pdf.set_fill_color(*fill)
    pdf.set_draw_color(*(border if border is not None else fill or BLACK))
    pdf.set_line_width(width)
    style = "DF" if (fill is not None and border is not None) else ("F" if fill is not None else "D")
    half = size / 2

    if shape == "square":
        pdf.rect(cx - half, cy - half, size, size, style=style)
    elif shape == "diamond":
        pdf.polygon(
            [(cx, cy - half), (cx + half, cy), (cx, cy + half), (cx - half, cy)],
            style=style,
        )
    elif shape == "triangle":
        pdf.polygon([(cx, cy - half), (cx + half, cy + half), (cx - half, cy + half)], style=style)
    else:
        pdf.ellipse(cx - half, cy - half, size, size, style=style)


def draw_arrow(
    pdf: Any,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    *,
    rgb: RGB = BLACK,
    width: float = 0.3,
    head: float = 1.8,
) -> None:
    """Line with a filled arrowhead at ``(x2, y2)``. Zero-length arrows draw nothing."""
    span = math.hypot(x2 - x1, y2 - y1)
    if span <= 0:
        return

    angle = math.atan2(y2 - y1, x2 - x1)
    base_x = x2 - head * math.cos(angle)
    base_y = y2 - head * math.sin(angle)
    draw_line(pdf, x1, y1, base_x, base_y, rgb=rgb, width=width)

    spread = head / 2
    pdf.set_fill_color(*rgb)
    pdf.set_draw_color(*rgb)
    pdf.polygon(
        [
            (x2, y2),
            (base_x - spread * math.sin(angle), base_y + spread * math.cos(angle)),
            (base_x + spread * math.sin(angle), base_y - spread * math.cos(angle)),
        ],
        style="F",
    )


def draw_text(
    pdf: Any,
    x: float,
    y: float,
    text: Any,
    *,
    size: float = 8.0,
    style: str = "",
    rgb: RGB = BLACK,
    max_width: Optional[float] = None,
    align: str = "L",
    family: str | None = None,
) -> str:
    """Draw one line of text with its baseline at ``y``; returns what was drawn.

    ``align`` treats ``x`` as the left edge (``L``), the right edge (``R``) or the
    centre (``C``). Text is latin-1 sanitised and, when ``max_width`` is given,
    ellipsized so it cannot paint over its neighbour.
    """
    family = family or str(getattr(pdf, "_pack_font_family", None) or "Helvetica")
    if "I" in (style or "") and getattr(pdf, "_pack_font_family", None):
        style = (style or "").replace("I", "")
    pdf.set_font(family, style, size)
    pdf.set_text_color(*rgb)
    label = _safe_for_document(pdf, text)
    if max_width is not None:
        label = fit_text(pdf, label, max_width)
    if not label:
        return ""

    if align == "R":
        x -= pdf.get_string_width(label)
    elif align == "C":
        x -= pdf.get_string_width(label) / 2
    pdf.text(x, y, label)
    return label


@dataclass(frozen=True)
class LegendEntry:
    """One key in a figure legend."""

    label: str
    rgb: RGB
    shape: str = "circle"


def draw_legend(
    pdf: Any,
    x: float,
    y: float,
    entries: Sequence[LegendEntry],
    *,
    size: float = 7.0,
    marker: float = 1.8,
    gap: float = 5.0,
    max_width: Optional[float] = None,
) -> float:
    """Single-row legend with the baseline at ``y``; returns the width consumed.

    Stops early rather than overflowing when ``max_width`` is reached, so a long
    legend truncates instead of colliding with whatever sits to its right.
    """
    family = str(getattr(pdf, "_pack_font_family", None) or "Helvetica")
    cursor = x
    pdf.set_font(family, "", size)
    for entry in entries:
        label = _safe_for_document(pdf, entry.label)
        needed = marker + 1.2 + pdf.get_string_width(label)
        if max_width is not None and (cursor - x) + needed > max_width:
            break
        draw_marker(pdf, cursor + marker / 2, y - marker / 3, marker, shape=entry.shape, fill=entry.rgb)
        draw_text(pdf, cursor + marker + 1.2, y, label, size=size, family=family)
        pdf.set_font(family, "", size)
        cursor += needed + gap
    return max(0.0, cursor - x - gap) if cursor > x else 0.0


def linear_positions(values: Sequence[float], x0: float, x1: float) -> list[float]:
    """Map numbers onto the span ``x0..x1``.

    A zero span — one value, or every value identical — maps everything to the
    midpoint instead of dividing by zero. That is the honest reading: the events
    really did all happen at the same instant as far as the data records.
    """
    if not values:
        return []
    low, high = min(values), max(values)
    if high <= low:
        midpoint = (x0 + x1) / 2
        return [midpoint for _ in values]
    scale = (x1 - x0) / (high - low)
    return [x0 + (value - low) * scale for value in values]


def format_date(at: datetime) -> str:
    """``17 May 2026`` — locale-independent so a golden fixture can pin it."""
    return f"{at.day:02d} {_MONTHS[at.month - 1]} {at.year}"


def format_stamp(at: datetime) -> str:
    """``17 May 2026 09:40 UTC`` — the zone is named because every value is normalised to UTC."""
    return f"{format_date(at)} {at.hour:02d}:{at.minute:02d} UTC"


# ---------------------------------------------------------------------------
# Part 2 — the chronology figure
# ---------------------------------------------------------------------------

# Must match src.domain.services.investigation_parent_timeline (see module
# docstring for why these are copied rather than imported). Pinned by a test.
ORIGIN_SOURCE = "source"
ORIGIN_INVESTIGATION = "investigation"

ORIGIN_LABELS = {ORIGIN_SOURCE: "Source record", ORIGIN_INVESTIGATION: "Investigation"}

# The source lane is deliberately neutral grey: it is not the platform's own
# record, and colouring it with the tenant brand would imply it was.
SOURCE_RGB: RGB = (96, 96, 96)

# Newest N events considered. The timeline endpoint already caps its own merge
# window; this bounds a caller that hands over an unbounded list, and the excess
# is reported rather than dropped quietly.
CHRONOLOGY_EVENT_CAP = 500

CHRONOLOGY_FIGURE_HEIGHT = 40.0

_LABEL_CHARS = 120
_DETAIL_CHARS = 240

_AXIS_INSET = 5.0
_LANE_OFFSET = 7.0
_MARKER_SIZE = 1.9


@dataclass(frozen=True)
class ChronologyEvent:
    """One placeable timeline entry: when, which side of the origin split, what."""

    at: datetime
    origin: str
    label: str
    detail: Optional[str] = None

    @property
    def origin_label(self) -> str:
        return ORIGIN_LABELS.get(self.origin, ORIGIN_LABELS[ORIGIN_INVESTIGATION])


@dataclass(frozen=True)
class ChronologySet:
    """Normalised events plus what had to be left out, so the pack can say so."""

    events: tuple[ChronologyEvent, ...] = ()
    unplaceable: int = 0
    omitted: int = 0

    def __bool__(self) -> bool:
        return bool(self.events)

    @property
    def first(self) -> Optional[datetime]:
        return self.events[0].at if self.events else None

    @property
    def last(self) -> Optional[datetime]:
        return self.events[-1].at if self.events else None

    def count_for(self, origin: str) -> int:
        return sum(1 for event in self.events if event.origin == origin)


def _as_utc(value: Any) -> Optional[datetime]:
    """Aware UTC datetime from a datetime or an ISO-8601 string, else None.

    Re-implemented rather than imported from the C9 timeline module, which pulls
    in ORM models. Naive values are read as UTC, matching that module: both the
    audit and running-sheet columns are documented UTC.
    """
    if isinstance(value, datetime):
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None
        if raw.endswith(("Z", "z")):
            raw = raw[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(raw)
        except ValueError:
            return None
        return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)
    return None


def _field(entry: Any, name: str) -> Any:
    """Read a field from a mapping or an object, so API dicts and rows both work."""
    if isinstance(entry, Mapping):
        return entry.get(name)
    return getattr(entry, name, None)


def _clean(value: Any, limit: int) -> Optional[str]:
    if value is None or isinstance(value, (Mapping, list, tuple, set)):
        return None
    text = str(value).strip()
    if not text:
        return None
    return pdf_safe(text, max_len=limit)


def _origin_of(metadata: Any) -> str:
    """`source` only when the C9 metadata says so; everything else is the investigation.

    A revision event written before C9 carries no ``origin`` key at all, and has
    always been the investigation's own event — which is exactly how the timeline
    route reads it.
    """
    if isinstance(metadata, Mapping) and str(metadata.get("origin") or "").strip().lower() == ORIGIN_SOURCE:
        return ORIGIN_SOURCE
    return ORIGIN_INVESTIGATION


def _label_of(entry: Any, metadata: Any, origin: str) -> str:
    """Row label: the C9 source label when there is one, else the humanised event type."""
    if origin == ORIGIN_SOURCE and isinstance(metadata, Mapping):
        source_label = _clean(metadata.get("source_label"), _LABEL_CHARS)
        if source_label:
            return source_label
    event_type = _clean(_field(entry, "event_type"), _LABEL_CHARS)
    if not event_type:
        return "Timeline entry"
    # Lowercased first: revision events are stored SHOUTING (`STATUS_CHANGED`),
    # and humanise_key preserves the first word's case, which would read
    # "STATUS changed" on the page.
    return humanise_key(event_type.lower())


def normalise_chronology_events(raw: Any, *, cap: int = CHRONOLOGY_EVENT_CAP) -> ChronologySet:
    """Turn timeline events into a placeable, oldest-first :class:`ChronologySet`.

    Accepts what ``GET /investigations/{id}/timeline`` serialises (mappings) and
    row objects with the same attribute names. Never raises and never invents:
    an entry with no readable timestamp cannot be placed on a chronology, so it
    is counted in ``unplaceable`` and the pack states the count.
    """
    if raw is None or isinstance(raw, (str, bytes, Mapping)) or not isinstance(raw, Sequence):
        return ChronologySet()

    placeable: list[tuple[datetime, int, ChronologyEvent]] = []
    unplaceable = 0
    for index, entry in enumerate(raw):
        at = _as_utc(_field(entry, "created_at"))
        if at is None:
            unplaceable += 1
            continue
        metadata = _field(entry, "event_metadata")
        origin = _origin_of(metadata)
        placeable.append(
            (
                at,
                index,
                ChronologyEvent(
                    at=at,
                    origin=origin,
                    label=_label_of(entry, metadata, origin),
                    detail=_clean(_field(entry, "new_value"), _DETAIL_CHARS),
                ),
            )
        )

    placeable.sort(key=lambda item: (item[0], item[1]))
    omitted = 0
    if cap > 0 and len(placeable) > cap:
        # Keep the newest, because that is the end of the story a reader needs;
        # the count dropped is reported rather than hidden.
        omitted = len(placeable) - cap
        placeable = placeable[-cap:]

    return ChronologySet(
        events=tuple(item[2] for item in placeable),
        unplaceable=unplaceable,
        omitted=omitted,
    )


def plural(count: int, singular: str, many: str) -> str:
    """``1 entry`` / ``4 entries`` — the count is always stated, never implied."""
    return f"{count} {singular if count == 1 else many}"


def chronology_summary_line(chronology: ChronologySet) -> str:
    """One factual sentence about the figure: counts per origin and the span covered."""
    if not chronology.events:
        return "No chronology entries are recorded for this investigation."

    source = chronology.count_for(ORIGIN_SOURCE)
    investigation = len(chronology.events) - source
    first = chronology.events[0].at
    last = chronology.events[-1].at
    span = f"on {format_date(first)}" if first == last else f"between {format_date(first)} and {format_date(last)}"
    return (
        f"{plural(len(chronology.events), 'entry', 'entries')} {span}: "
        f"{source} from the source record, {investigation} from the investigation."
    )


def draw_chronology_figure(
    pdf: Any,
    chronology: ChronologySet,
    *,
    brand: RGB,
    width: Optional[float] = None,
    height: float = CHRONOLOGY_FIGURE_HEIGHT,
) -> Frame:
    """Draw the two-lane chronology and return the frame it occupies.

    Source-record entries sit above the time axis, the investigation's own below
    it, positioned by time rather than by index — so a case that ran for a year
    before an investigation was raised looks like one. Overlapping markers are
    left overlapping: that density is real, and spacing them out would move
    events to times they did not happen at.

    Raises whatever fpdf2 raises; the caller decides whether a pack without a
    figure is better than no pack. Callers must not rely on the cursor position
    on failure beyond ``frame.bottom``.
    """
    frame = reserve_frame(pdf, height, width=width, top_gap=1.0)
    if not chronology.events:
        return frame

    with vector_state(pdf):
        _draw_chronology_body(pdf, frame, chronology, brand)
    return frame


def _draw_chronology_body(pdf: Any, frame: Frame, chronology: ChronologySet, brand: RGB) -> None:
    axis_y = frame.y + 21.0
    x0 = frame.x + _AXIS_INSET
    x1 = frame.right - _AXIS_INSET
    events = chronology.events

    draw_legend(
        pdf,
        frame.x,
        frame.y + 4.0,
        [
            LegendEntry(ORIGIN_LABELS[ORIGIN_SOURCE], SOURCE_RGB, "circle"),
            LegendEntry(ORIGIN_LABELS[ORIGIN_INVESTIGATION], brand, "square"),
        ],
        max_width=frame.w * 0.7,
    )
    draw_text(
        pdf,
        frame.right,
        frame.y + 4.0,
        plural(len(events), "entry", "entries"),
        size=7.0,
        rgb=shade(brand, 0.2),
        align="R",
        max_width=frame.w * 0.28,
    )

    lane_rgb = tint(BLACK, 0.86)
    draw_line(pdf, x0, axis_y - _LANE_OFFSET, x1, axis_y - _LANE_OFFSET, rgb=lane_rgb, width=0.2, dash=(1.0, 1.0))
    draw_line(pdf, x0, axis_y + _LANE_OFFSET, x1, axis_y + _LANE_OFFSET, rgb=lane_rgb, width=0.2, dash=(1.0, 1.0))
    draw_line(pdf, x0, axis_y, x1, axis_y, rgb=shade(brand, 0.1), width=0.4)
    draw_line(pdf, x0, axis_y - 1.5, x0, axis_y + 1.5, rgb=shade(brand, 0.1), width=0.4)
    draw_line(pdf, x1, axis_y - 1.5, x1, axis_y + 1.5, rgb=shade(brand, 0.1), width=0.4)

    positions = linear_positions([event.at.timestamp() for event in events], x0, x1)
    for event, x in zip(events, positions):
        is_source = event.origin == ORIGIN_SOURCE
        draw_line(pdf, x, axis_y - 1.0, x, axis_y + 1.0, rgb=tint(BLACK, 0.7), width=0.2)
        draw_marker(
            pdf,
            x,
            axis_y - _LANE_OFFSET if is_source else axis_y + _LANE_OFFSET,
            _MARKER_SIZE,
            shape="circle" if is_source else "square",
            fill=SOURCE_RGB if is_source else brand,
        )

    _draw_axis_labels(pdf, frame, chronology, brand, x0=x0, x1=x1)


def _draw_axis_labels(pdf: Any, frame: Frame, chronology: ChronologySet, brand: RGB, *, x0: float, x1: float) -> None:
    """Date labels under the axis: both ends, or a single stamp when the span is zero."""
    first, last = chronology.first, chronology.last
    if first is None or last is None:
        return

    baseline = frame.bottom - 4.0
    label_rgb = shade(brand, 0.15)
    if first == last:
        draw_text(pdf, frame.cx, baseline, format_stamp(first), size=7.0, rgb=label_rgb, align="C", max_width=frame.w)
        return

    half = max(10.0, (x1 - x0) / 2 - 2.0)
    draw_text(pdf, x0, baseline, format_date(first), size=7.0, rgb=label_rgb, align="L", max_width=half)
    draw_text(pdf, x1, baseline, format_date(last), size=7.0, rgb=label_rgb, align="R", max_width=half)


# ---------------------------------------------------------------------------
# Part 3 — the ICAM contributing-factor figure
# ---------------------------------------------------------------------------

# Must match src.domain.services.investigation_factors_service (see module
# docstring for why these are copied rather than imported). Pinned by a test.
ICAM_CATEGORIES: tuple[str, ...] = (
    "organisational_factors",
    "task_environmental_conditions",
    "individual_team_actions",
    "absent_failed_defences",
)

ICAM_CATEGORY_LABELS: dict[str, str] = {
    "organisational_factors": "Organisational factors",
    "task_environmental_conditions": "Task and environmental conditions",
    "individual_team_actions": "Individual and team actions",
    "absent_failed_defences": "Absent or failed defences",
}

ICAM_DEPTHS: tuple[str, ...] = ("immediate", "underlying", "root")

ICAM_DEPTH_LABELS: dict[str, str] = {
    "immediate": "Immediate cause",
    "underlying": "Underlying cause",
    "root": "Root cause",
}

# Depth carries a shape as well as a colour, so the classification still reads
# when the pack is printed in mono.
ICAM_DEPTH_SHAPES: dict[str, str] = {"immediate": "circle", "underlying": "square", "root": "diamond"}

# Rows the figure will place. Past this the bands would not fit one page, and a
# diagram spread over two pages is no longer a diagram. The excess is reported
# rather than dropped quietly.
ICAM_FACTOR_CAP = 24

# Sub-causes read off one stored factor. Matches FACTOR_SUB_CAUSES_MAX in the
# factors service, so the figure cannot silently show fewer than were stored.
_ICAM_SUB_CAUSE_CAP = 20

_ICAM_CAUSE_CHARS = 300
_ICAM_SUB_CAUSE_CHARS = 120

_ICAM_HEADER_H = 6.0
_ICAM_COL_HEADER_H = 6.2
_ICAM_STRIP_H = 5.4
_ICAM_ROW_H = 4.8
_ICAM_WRAP_LEADING = 3.2
_ICAM_BAND_PAD = 1.2
_ICAM_BAND_GAP = 1.6
_ICAM_ROW_INSET = 2.2
_ICAM_MARKER_SIZE = 1.8
_ICAM_COUNT_COL = 26.0
_ICAM_DEPTH_COUNT = len(ICAM_DEPTHS)


@dataclass(frozen=True)
class IcamFactor:
    """One stored contributing factor as the diagram presents it.

    ``category`` and ``depth`` are the *stored* values, not labels: the figure
    resolves them through the maps above, so an unrecognised depth reads as no
    recorded depth rather than as a guessed one.
    """

    id: int
    category: str
    cause: str
    sub_causes: tuple[str, ...] = ()
    depth: Optional[str] = None

    @property
    def category_label(self) -> str:
        return ICAM_CATEGORY_LABELS.get(self.category, humanise_key(self.category))

    @property
    def depth_label(self) -> Optional[str]:
        """The recorded depth in words, or ``None`` — never a default."""
        return ICAM_DEPTH_LABELS.get(self.depth or "")

    @property
    def label(self) -> str:
        """``cause (sub; sub)`` — the INV-C12 line without its category prefix or depth bracket.

        Both of those are drawn separately (the category band, and the HSG245
        column), so repeating them in the cell would say the same thing twice.
        """
        if not self.sub_causes:
            return self.cause
        return f"{self.cause} ({'; '.join(self.sub_causes)})"


@dataclass(frozen=True)
class IcamFactorSet:
    """Placeable factors plus what could not be presented, so the pack can say so."""

    factors: tuple[IcamFactor, ...] = ()
    #: Stored keys outside the ICAM four (typically pre-DEC-1 6M names). Named,
    #: never remapped.
    unmapped_categories: tuple[str, ...] = ()
    #: Stored causes this figure cannot place at all, including those under the
    #: categories named above. INV-C12's own count, carried through.
    unpresentable: int = 0
    #: Factors beyond :data:`ICAM_FACTOR_CAP`.
    omitted: int = 0

    def __bool__(self) -> bool:
        return bool(self.factors)

    def for_category(self, category: str) -> tuple[IcamFactor, ...]:
        return tuple(factor for factor in self.factors if factor.category == category)

    @property
    def recorded(self) -> int:
        """Factors this set was built from, including those the cap left out.

        The count a reader needs when the diagram is capped: "24 recorded" would
        be false on an investigation with 60 factors, even with the shortfall
        stated separately.
        """
        return len(self.factors) + self.omitted

    @property
    def with_depth(self) -> int:
        """Drawn factors carrying a recorded depth. Not a claim about the omitted ones."""
        return sum(1 for factor in self.factors if factor.depth is not None)


def _stored_value(value: Any) -> Any:
    """Unwrap an enum member to its stored value; anything else is itself.

    ``FishboneCategory`` and ``CausalDepth`` are ``str`` enums, and ``str()`` on
    a member of one renders ``FishboneCategory.ORGANISATIONAL`` rather than the
    value stored in the JSON. Reading ``.value`` is what makes an INV-C12
    ``InvestigationFactor`` object readable here as well as its payload dict.
    """
    return getattr(value, "value", value)


def _count(value: Any) -> int:
    """A non-negative integer from a stored number; anything unreadable is zero."""
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return max(0, value)
    if isinstance(value, float):
        return max(0, int(value))
    if isinstance(value, str):
        try:
            return max(0, int(value.strip() or 0))
        except ValueError:
            return 0
    return 0


def _icam_depth(value: Any) -> Optional[str]:
    """A recorded depth, or ``None`` for absent/unrecognised — never guessed.

    Mirrors the factors service, which stores no ``depth`` key at all when
    nobody recorded one: a factor whose depth was never classified must not read
    back as "immediate".
    """
    depth = str(_stored_value(value) or "").strip().lower()
    return depth if depth in ICAM_DEPTH_LABELS else None


def _icam_sub_causes(value: Any) -> tuple[str, ...]:
    """Stored sub-causes as bounded, latin-1-safe text. Order kept, blanks dropped."""
    if not isinstance(value, (list, tuple)):
        return ()
    cleaned: list[str] = []
    for item in list(value)[:_ICAM_SUB_CAUSE_CAP]:
        text = _clean(item, _ICAM_SUB_CAUSE_CHARS)
        if text:
            cleaned.append(text)
    return tuple(cleaned)


def normalise_icam_factors(raw: Any, *, cap: int = ICAM_FACTOR_CAP) -> IcamFactorSet:
    """Turn stored ICAM factors into a placeable set, in ICAM category order.

    Accepts what the pack payload stores — a mapping of ``factors`` plus
    INV-C12's ``unmapped_categories`` / ``unpresentable`` counts — a bare list of
    factor mappings, or objects carrying the same attribute names (an INV-C12
    :class:`~src.domain.services.investigation_factors_service.InvestigationFactor`
    works unchanged).

    Never raises and never invents. A cause stored under a key outside the ICAM
    four is counted and its key named, not moved into a band it was never
    classified under. An entry with no readable cause text is counted, not
    guessed at. Ordering is ICAM category order then stored order within a
    category — the same order INV-C12 reads the diagram in, so a pack rendered
    twice cannot draw the factors in a different sequence.
    """
    entries: Any = raw
    unmapped: list[str] = []
    unpresentable = 0

    if isinstance(raw, Mapping):
        entries = raw.get("factors")
        stored_names = raw.get("unmapped_categories")
        if isinstance(stored_names, (list, tuple)):
            unmapped = [text for name in stored_names if (text := _clean(name, _ICAM_SUB_CAUSE_CHARS))]
        unpresentable = _count(raw.get("unpresentable"))

    if entries is None or isinstance(entries, (str, bytes, Mapping)) or not isinstance(entries, Sequence):
        return IcamFactorSet(unmapped_categories=tuple(sorted(set(unmapped))), unpresentable=unpresentable)

    by_category: dict[str, list[IcamFactor]] = {category: [] for category in ICAM_CATEGORIES}
    for entry in entries:
        category = str(_stored_value(_field(entry, "category")) or "").strip()
        if category not in by_category:
            if category:
                unmapped.append(category)
            unpresentable += 1
            continue
        cause = _clean(_field(entry, "cause"), _ICAM_CAUSE_CHARS)
        if not cause:
            unpresentable += 1
            continue
        by_category[category].append(
            IcamFactor(
                id=_count(_field(entry, "id")),
                category=category,
                cause=cause,
                sub_causes=_icam_sub_causes(_field(entry, "sub_causes")),
                depth=_icam_depth(_field(entry, "depth")),
            )
        )

    ordered = [factor for category in ICAM_CATEGORIES for factor in by_category[category]]
    omitted = 0
    if cap > 0 and len(ordered) > cap:
        # Keep the first in ICAM order rather than the last: unlike a
        # chronology there is no "newest", and this is the order the
        # investigator worked through. The count dropped is reported.
        omitted = len(ordered) - cap
        ordered = ordered[:cap]

    return IcamFactorSet(
        factors=tuple(ordered),
        unmapped_categories=tuple(sorted(set(unmapped))),
        unpresentable=unpresentable,
        omitted=omitted,
    )


def icam_summary_line(factors: IcamFactorSet) -> str:
    """One factual sentence about the diagram: how many factors, how many classified.

    The count is always what is *recorded*, never what the figure happened to
    fit. When the cap bites, the sentence says so rather than reporting the
    drawn subset as the whole analysis.
    """
    if not factors.factors:
        return "No ICAM contributing factors are recorded for this investigation."
    if factors.omitted:
        return (
            f"{plural(factors.recorded, 'contributing factor', 'contributing factors')} recorded across the four "
            f"ICAM categories; the diagram shows the first {len(factors.factors)}, {factors.with_depth} of them "
            "with a recorded HSG245 causal depth."
        )
    return (
        f"{plural(len(factors.factors), 'contributing factor', 'contributing factors')} recorded across the "
        f"four ICAM categories, {factors.with_depth} with a recorded HSG245 causal depth."
    )


def icam_figure_height(factors: IcamFactorSet) -> float:
    """Height the figure needs in mm — content-driven, because the bands are.

    Zero for an empty set: there is nothing to place, and reserving space for a
    blank rectangle would push the rest of the pack down the page to say
    nothing. Bounded by :data:`ICAM_FACTOR_CAP`, so the tallest figure this
    module will draw still fits inside one A4 page's printable height.
    """
    if not factors.factors:
        return 0.0
    body = 0.0
    for category in ICAM_CATEGORIES:
        entries = factors.for_category(category)
        columns, unclassified = _icam_split(entries)
        if not entries:
            body_h = _ICAM_ROW_H
        else:
            stacked = max(sum(_icam_helvetica_step(factor) for factor in columns[depth]) for depth in ICAM_DEPTHS)
            extra = sum(_icam_helvetica_step(factor) for factor in unclassified)
            body_h = stacked + extra if stacked or extra else _ICAM_ROW_H
        body += _ICAM_STRIP_H + _ICAM_BAND_PAD + _ICAM_BAND_GAP + body_h
    return _ICAM_HEADER_H + _ICAM_COL_HEADER_H + body


def _icam_wraps(pdf: Any) -> bool:
    return bool(getattr(pdf, "_pack_font_family", None))


def _icam_split(entries: Sequence[IcamFactor]) -> tuple[dict[str, list[IcamFactor]], list[IcamFactor]]:
    """Partition a category's factors into the three HSG245 columns, plus unclassified."""
    columns: dict[str, list[IcamFactor]] = {depth: [] for depth in ICAM_DEPTHS}
    unclassified: list[IcamFactor] = []
    for entry in entries:
        if entry.depth in columns:
            columns[entry.depth].append(entry)
        else:
            unclassified.append(entry)
    return columns, unclassified


def _icam_column_width(frame: Frame) -> float:
    return frame.w / float(_ICAM_DEPTH_COUNT)


def _icam_column_frame(frame: Frame, index: int) -> Frame:
    width = _icam_column_width(frame)
    return Frame(frame.x + index * width, frame.y, width, frame.h)


def _icam_cell_text_width(column_width: float) -> float:
    return max(6.0, column_width - 2 * _ICAM_ROW_INSET - _ICAM_MARKER_SIZE - 1.6)


def _icam_helvetica_step(factor: IcamFactor) -> float:
    lines = 1 + len(factor.sub_causes)
    return max(_ICAM_ROW_H, 2.0 + lines * _ICAM_WRAP_LEADING)


def _icam_cell_lines(pdf: Any, factor: IcamFactor, width: float) -> list[str]:
    """Cause, then each stored sub-cause. Never invents a sub-cause or a depth."""
    if _icam_wraps(pdf):
        pdf.set_font(str(pdf._pack_font_family), "", 7.5)
        lines = wrap_text(pdf, factor.cause, width)
        indent = max(6.0, width - 2.0)
        for sub in factor.sub_causes:
            lines.extend(wrap_text(pdf, f"- {sub}", indent))
        return lines
    lines = [fit_text(pdf, factor.cause, width)]
    indent = max(6.0, width - 2.0)
    for sub in factor.sub_causes:
        lines.append(fit_text(pdf, f"- {sub}", indent))
    return lines


def _icam_cell_step(pdf: Any, column_width: float, factor: IcamFactor) -> float:
    if not _icam_wraps(pdf):
        return _icam_helvetica_step(factor)
    width = _icam_cell_text_width(column_width)
    return max(_ICAM_ROW_H, 2.0 + max(1, len(_icam_cell_lines(pdf, factor, width))) * _ICAM_WRAP_LEADING)


def _icam_band_body_height(pdf: Any, frame: Frame, entries: Sequence[IcamFactor]) -> float:
    if not entries:
        return _ICAM_ROW_H
    columns, unclassified = _icam_split(entries)
    column_width = _icam_column_width(frame)
    stacked = max((_icam_stack_height(pdf, column_width, columns[depth]) for depth in ICAM_DEPTHS), default=0.0)
    extra = sum(_icam_cell_step(pdf, frame.w, factor) for factor in unclassified)
    body = stacked + extra
    return body if body else _ICAM_ROW_H


def _icam_stack_height(pdf: Any, column_width: float, entries: Sequence[IcamFactor]) -> float:
    return sum(_icam_cell_step(pdf, column_width, factor) for factor in entries)


def _icam_band_box_height(pdf: Any, frame: Frame, entries: Sequence[IcamFactor]) -> float:
    return _ICAM_STRIP_H + _ICAM_BAND_PAD + _icam_band_body_height(pdf, frame, entries)


def _icam_wrapped_figure_height(pdf: Any, factors: IcamFactorSet, width: float) -> float:
    probe = Frame(float(pdf.l_margin), 0.0, width, 10_000.0)
    bands = sum(
        _icam_band_box_height(pdf, probe, factors.for_category(category)) + _ICAM_BAND_GAP
        for category in ICAM_CATEGORIES
    )
    return _ICAM_HEADER_H + _ICAM_COL_HEADER_H + bands


def draw_icam_factors_figure(
    pdf: Any,
    factors: IcamFactorSet,
    *,
    brand: RGB,
    width: Optional[float] = None,
) -> Frame:
    """Draw the four ICAM bands across three HSG245 depth columns.

    One band per ICAM category, in the order INV-C12 works through them. Factors
    sit in the Immediate / Underlying / Root column matching the recorded depth.
    A factor with no recorded depth sits under the columns in that band, still
    without a depth claim. A category with nothing recorded says "None recorded"
    rather than being dropped: an empty band is a fact about the investigation,
    and hiding it would make a partial analysis look complete.

    An empty set draws nothing and reserves nothing — the caller should be
    printing :func:`icam_summary_line` instead of an empty diagram.

    Raises whatever fpdf2 raises; the caller decides whether a pack without its
    figure beats a failed export. Callers must not rely on the cursor position
    on failure beyond ``frame.bottom``.
    """
    if not factors.factors:
        return Frame(
            float(pdf.l_margin),
            float(pdf.get_y()),
            content_width(pdf) if width is None else width,
            0.0,
        )

    width_mm = content_width(pdf) if width is None else width
    height = _icam_wrapped_figure_height(pdf, factors, width_mm) if _icam_wraps(pdf) else icam_figure_height(factors)
    frame = reserve_frame(pdf, height, width=width, top_gap=1.0)
    with vector_state(pdf):
        _draw_icam_body(pdf, frame, factors, brand)
    return frame


def _icam_depth_rgb(brand: RGB, depth: Optional[str]) -> RGB:
    """Immediate to root as an increasing depth of the tenant's own brand hue.

    Deliberately not a red/amber/green scale: a root cause is not "worse" than
    an immediate one, it sits further back in the causal chain. Darkening one
    hue says "further" without asserting a severity nobody recorded.
    """
    if depth == "immediate":
        return tint(brand, 0.45)
    if depth == "root":
        return shade(brand, 0.35)
    return brand


def _draw_icam_body(pdf: Any, frame: Frame, factors: IcamFactorSet, brand: RGB) -> None:
    draw_legend(
        pdf,
        frame.x,
        frame.y + 3.8,
        [
            LegendEntry(ICAM_DEPTH_LABELS[depth], _icam_depth_rgb(brand, depth), ICAM_DEPTH_SHAPES[depth])
            for depth in ICAM_DEPTHS
        ],
        max_width=max(10.0, frame.w - _ICAM_COUNT_COL),
    )
    draw_text(
        pdf,
        frame.right,
        frame.y + 3.8,
        plural(len(factors.factors), "factor", "factors"),
        size=7.0,
        rgb=shade(brand, 0.2),
        align="R",
        max_width=_ICAM_COUNT_COL,
    )
    _draw_icam_column_headers(pdf, frame, brand)

    y = frame.y + _ICAM_HEADER_H + _ICAM_COL_HEADER_H
    for category in ICAM_CATEGORIES:
        y = _draw_icam_band(pdf, frame, y, category, factors.for_category(category), brand)


def _draw_icam_column_headers(pdf: Any, frame: Frame, brand: RGB) -> None:
    """HSG245 Immediate / Underlying / Root as the three columns of every band."""
    y = frame.y + _ICAM_HEADER_H
    for index, depth in enumerate(ICAM_DEPTHS):
        column = _icam_column_frame(frame, index)
        draw_marker(
            pdf,
            column.x + _ICAM_ROW_INSET + _ICAM_MARKER_SIZE / 2,
            y + 3.2,
            _ICAM_MARKER_SIZE,
            shape=ICAM_DEPTH_SHAPES[depth],
            fill=_icam_depth_rgb(brand, depth),
        )
        draw_text(
            pdf,
            column.x + _ICAM_ROW_INSET + _ICAM_MARKER_SIZE + 1.6,
            y + 3.8,
            ICAM_DEPTH_LABELS[depth],
            size=7.0,
            style="B",
            rgb=shade(brand, 0.2),
            max_width=max(8.0, column.w - 2 * _ICAM_ROW_INSET - _ICAM_MARKER_SIZE - 1.6),
        )


def _draw_icam_band(
    pdf: Any,
    frame: Frame,
    y: float,
    category: str,
    entries: Sequence[IcamFactor],
    brand: RGB,
) -> float:
    """One category band across the three depth columns. Returns the next band's top."""
    height = _icam_band_box_height(pdf, frame, entries)
    if y + height > frame.bottom + 0.05:
        # Unreachable through normalise_icam_factors, which caps the row count
        # so every band fits. A hand-built set can still overrun, and painting
        # over the footer is worse than stopping and saying so in the log.
        logger.warning("pack_draw_icam_band_clipped category=%s rows=%d", category, len(entries))
        return frame.bottom

    strip_rgb = tint(brand, 0.78)
    draw_rect(pdf, Frame(frame.x, y, frame.w, _ICAM_STRIP_H), fill=strip_rgb)
    draw_rect(pdf, Frame(frame.x, y, frame.w, height), border=tint(BLACK, 0.78))

    label_rgb = readable_text_rgb(strip_rgb)
    draw_text(
        pdf,
        frame.x + 2.0,
        y + 3.7,
        ICAM_CATEGORY_LABELS[category],
        size=7.5,
        style="B",
        rgb=label_rgb,
        max_width=max(10.0, frame.w - _ICAM_COUNT_COL - 4.0),
    )
    draw_text(
        pdf,
        frame.right - 2.0,
        y + 3.7,
        plural(len(entries), "factor", "factors"),
        size=7.0,
        rgb=label_rgb,
        align="R",
        max_width=_ICAM_COUNT_COL,
    )

    body_y = y + _ICAM_STRIP_H + _ICAM_BAND_PAD
    if not entries:
        draw_text(
            pdf,
            _icam_row_text_x(frame),
            body_y + 3.3,
            "None recorded.",
            size=7.5,
            style="I",
            rgb=tint(BLACK, 0.45),
            max_width=max(10.0, frame.w - 2 * _ICAM_ROW_INSET),
        )
        return y + height + _ICAM_BAND_GAP

    columns, unclassified = _icam_split(entries)
    column_width = _icam_column_width(frame)
    for index, depth in enumerate(ICAM_DEPTHS):
        row_y = body_y
        for entry in columns[depth]:
            _draw_icam_cell(pdf, _icam_column_frame(frame, index), row_y, entry, brand)
            row_y += _icam_cell_step(pdf, column_width, entry)

    unclassified_y = body_y + max(
        (_icam_stack_height(pdf, column_width, columns[depth]) for depth in ICAM_DEPTHS),
        default=0.0,
    )
    for entry in unclassified:
        _draw_icam_cell(pdf, frame, unclassified_y, entry, brand, marker=False)
        unclassified_y += _icam_cell_step(pdf, frame.w, entry)

    return y + height + _ICAM_BAND_GAP


def _icam_row_text_x(frame: Frame) -> float:
    """Left edge of the cause column, marker gutter included.

    Fixed whether or not this cell has a marker: a factor with no recorded depth
    must line up with the others rather than being indented differently, which
    would read as a second kind of row.
    """
    return frame.x + _ICAM_ROW_INSET + _ICAM_MARKER_SIZE + 1.6


def _draw_icam_cell(
    pdf: Any,
    frame: Frame,
    y: float,
    factor: IcamFactor,
    brand: RGB,
    *,
    marker: bool = True,
) -> None:
    """One factor in a depth column (or the unclassified strip)."""
    baseline = y + 3.3
    text_x = _icam_row_text_x(frame)
    available = max(6.0, frame.right - _ICAM_ROW_INSET - text_x)
    wrap = bool(getattr(pdf, "_pack_font_family", None))

    if marker and factor.depth is not None:
        draw_marker(
            pdf,
            frame.x + _ICAM_ROW_INSET + _ICAM_MARKER_SIZE / 2,
            baseline - 1.1,
            _ICAM_MARKER_SIZE,
            shape=ICAM_DEPTH_SHAPES.get(factor.depth, "circle"),
            fill=_icam_depth_rgb(brand, factor.depth),
        )

    if wrap:
        pdf.set_font(str(pdf._pack_font_family), "", 7.5)
        pdf.set_text_color(*BLACK)
        line_y = baseline
        for line in _icam_cell_lines(pdf, factor, available):
            pdf.text(text_x, line_y, line)
            line_y += _ICAM_WRAP_LEADING
        return
    line_y = baseline
    for line in _icam_cell_lines(pdf, factor, available):
        draw_text(pdf, text_x, line_y, line, size=7.5, max_width=available)
        line_y += _ICAM_WRAP_LEADING
