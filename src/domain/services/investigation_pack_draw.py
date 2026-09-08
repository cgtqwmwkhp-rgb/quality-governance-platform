"""Vector drawing helpers and the chronology figure for investigation packs (INV-C15).

Absorbs PR-27 (drawing helpers) and PR-28 (graphical chronology). Two parts, kept
in one module on purpose so a later diagram PR imports one place:

**Part 1 — primitives.** Text safety, colour arithmetic, page-space reservation
and the vector calls themselves (lines, rectangles, markers, arrows, legends).
Nothing here knows what an investigation is, so the ICAM diagram (C16) and any
pack figure C13 needs can build on it without importing pack semantics.

**Part 2 — the chronology figure.** Normalises timeline events into a placeable
set and draws them as a two-lane time axis: the parent record's chronology above
the axis, the investigation's own events below it. That split is exactly the
distinction INV-C9 put in ``event_metadata["origin"]`` — this module reads that
key and never re-derives origin from anything else.

Deliberate non-coupling
-----------------------
``ORIGIN_SOURCE`` / ``ORIGIN_INVESTIGATION`` are re-declared here rather than
imported from :mod:`src.domain.services.investigation_parent_timeline`, because
that module imports four ORM models to run its queries and the drawing layer must
stay free of the database. The two spellings are pinned equal by a unit test, so
a rename on the C9 side fails loudly instead of silently splitting the lanes.

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


def fit_text(pdf: Any, text: Any, max_width: float) -> str:
    """Ellipsize latin-1-safe text so it cannot paint outside a fixed-width PDF cell."""
    safe_text = pdf_safe(text)
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
    family = str(getattr(pdf, "font_family", "") or "Helvetica")
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
    family: str = "Helvetica",
) -> str:
    """Draw one line of text with its baseline at ``y``; returns what was drawn.

    ``align`` treats ``x`` as the left edge (``L``), the right edge (``R``) or the
    centre (``C``). Text is latin-1 sanitised and, when ``max_width`` is given,
    ellipsized so it cannot paint over its neighbour.
    """
    pdf.set_font(family, style, size)
    pdf.set_text_color(*rgb)
    label = pdf_safe(text)
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
    cursor = x
    pdf.set_font("Helvetica", "", size)
    for entry in entries:
        label = pdf_safe(entry.label)
        needed = marker + 1.2 + pdf.get_string_width(label)
        if max_width is not None and (cursor - x) + needed > max_width:
            break
        draw_marker(pdf, cursor + marker / 2, y - marker / 3, marker, shape=entry.shape, fill=entry.rgb)
        draw_text(pdf, cursor + marker + 1.2, y, label, size=size)
        pdf.set_font("Helvetica", "", size)
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
