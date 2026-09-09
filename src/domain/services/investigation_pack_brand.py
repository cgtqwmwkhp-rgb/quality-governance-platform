"""Plantexpand letterhead for investigation customer packs (INV-PACK-R1).

The letterhead is the brand kit, not the tenant row. Tenant name and
``primary_color`` (seeded Tailwind blue) must not paint a pack: that is how
the portal produced Default Organisation on a blue Helvetica band.

Assets live next to this module and are copied with ``src/`` into the image.
Missing fonts or the lockup fail closed — there is no Helvetica fallback,
because a customer cannot tell they received an off-brand pack, and INV-C17
would freeze those bytes at issue.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, FrozenSet, Optional

from src.domain.services.investigation_pack_ir import Emphasis

RGB = tuple[int, int, int]

CRIMSON: RGB = (176, 44, 48)  # #B02C30 — sampled from the Pantone lockup
JET_GREY: RGB = (68, 60, 56)  # #443C38 — sampled from the wordmark "Plant"
PLATINUM: RGB = (232, 228, 223)
WHITE: RGB = (255, 255, 255)
BLACK: RGB = (JET_GREY[0], JET_GREY[1], JET_GREY[2])

TAILWIND_BLUE: RGB = (59, 130, 246)  # #3B82F6 — seed tenant primary; never letterhead

LEGAL_NAME = "Plantexpand Ltd"
ADDRESS_LINE = "Unit 7 Buckingham Square, Hurricane Way, Wickford, Essex SS11 8YQ"
PHONE = "01268 204782"
WEB = "plantexpand.com"
CLASSIFICATION = "UNCONTROLLED WHEN PRINTED"
ISSUED_BY = "Plantexpand Ltd, Quality Governance Portal"

_ASSET_DIR = Path(__file__).resolve().parent / "pack_brand"
_FONT_FILES = {
    "regular": "Inter-Regular.ttf",
    "medium": "Inter-Medium.ttf",
    "semibold": "Inter-SemiBold.ttf",
    "bold": "Inter-Bold.ttf",
}
_LOCKUP_FILE = "plantexpand-lockup.png"
_OFL_FILE = "OFL.txt"

FAMILY_REGULAR = "Inter"
FAMILY_MEDIUM = "InterMedium"
FAMILY_SEMIBOLD = "InterSemiBold"


class BrandAssetError(RuntimeError):
    """Pack letterhead cannot be built; do not fall back to a core font."""


@dataclass(frozen=True)
class Typeface:
    """Maps a semantic emphasis role to an fpdf2 (family, style, size, rgb)."""

    def slot(self, emphasis: Emphasis, size: float) -> tuple[str, str, float, RGB]:
        if emphasis is Emphasis.STRONG:
            return FAMILY_REGULAR, "B", size, JET_GREY
        if emphasis is Emphasis.NOTE:
            return FAMILY_REGULAR, "", size, JET_GREY
        if emphasis is Emphasis.CAPTION:
            return FAMILY_MEDIUM, "", size, JET_GREY
        return FAMILY_REGULAR, "", size, JET_GREY


def asset_dir() -> Path:
    return _ASSET_DIR


def font_path(weight: str) -> Path:
    name = _FONT_FILES.get(weight)
    if name is None:
        raise BrandAssetError(f"Unknown Inter weight {weight!r}")
    path = _ASSET_DIR / name
    if not path.is_file():
        raise BrandAssetError(f"Pack typeface missing: {path.name}")
    return path


def lockup_path() -> Path:
    path = _ASSET_DIR / _LOCKUP_FILE
    if not path.is_file():
        raise BrandAssetError(f"Pack lockup missing: {path.name}")
    return path


def ofl_path() -> Path:
    path = _ASSET_DIR / _OFL_FILE
    if not path.is_file():
        raise BrandAssetError(f"Inter OFL licence missing: {path.name}")
    return path


def resolve_typeface() -> Typeface:
    """Fail closed if any bundled asset is absent — before a page is drawn."""
    for weight in _FONT_FILES:
        font_path(weight)
    lockup_path()
    ofl_path()
    return Typeface()


def register_fonts(pdf: Any) -> None:
    """Register Inter on an FPDF instance. Italic slots alias to regular/bold.

    fpdf2 raises if style ``I`` is requested on an unregistered family. The
    aliases exist so a missed call site degrades in weight rather than 500-ing
    a customer download. Pack code must still never request italic.
    """
    resolve_typeface()
    pdf.add_font(FAMILY_REGULAR, "", str(font_path("regular")))
    pdf.add_font(FAMILY_REGULAR, "B", str(font_path("bold")))
    pdf.add_font(FAMILY_REGULAR, "I", str(font_path("regular")))
    pdf.add_font(FAMILY_REGULAR, "BI", str(font_path("bold")))
    pdf.add_font(FAMILY_MEDIUM, "", str(font_path("medium")))
    pdf.add_font(FAMILY_SEMIBOLD, "", str(font_path("semibold")))
    pdf._pack_font_family = FAMILY_REGULAR  # noqa: SLF001 - read by the drawing layer


@lru_cache(maxsize=8)
def _cmap_codepoints(ttf_path: str) -> FrozenSet[int]:
    from fontTools.ttLib import TTFont

    font = TTFont(ttf_path, lazy=True)
    try:
        cmap = font.getBestCmap() or {}
        return frozenset(cmap.keys())
    finally:
        font.close()


def covered_codepoints() -> FrozenSet[int]:
    return _cmap_codepoints(str(font_path("regular")))


def text_safe(value: Any, *, max_len: Optional[int] = None) -> str:
    """Keep recorded text visible. Uncovered glyphs become ``?``, never vanish.

    fpdf2 with a unicode TTF silently deletes missing glyphs. That would drop a
    name from a customer pack. Mapping to ``?`` is the same honesty the latin-1
    Helvetica path already used.
    """
    text = "" if value is None else str(value)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    cleaned: list[str] = []
    for ch in text:
        code = ord(ch)
        if ch == "\n":
            cleaned.append(ch)
            continue
        if code < 32 or (127 <= code < 160) or (0xD800 <= code <= 0xDFFF):
            continue
        cleaned.append(ch)
    text = "".join(cleaned)
    cmap = covered_codepoints()
    text = "".join(ch if (ch == "\n" or ord(ch) in cmap) else "?" for ch in text)
    if max_len is not None and len(text) > max_len:
        text = text[: max_len - 3].rstrip() + "..."
    return text


def legal_footer_line() -> str:
    return f"{LEGAL_NAME} · {ADDRESS_LINE} · {PHONE} · {WEB.upper()}"


def write_tracked(
    pdf: Any,
    text: str,
    *,
    width: float,
    height: float,
    spacing: float = 0.32,
    align: str = "L",
    **cell_kw: Any,
) -> None:
    """Paint a caps label with letter-spacing. Always reset spacing afterwards."""
    pdf.set_char_spacing(spacing)
    try:
        pdf.cell(width, height, text_safe(text), align=align, **cell_kw)
    finally:
        pdf.set_char_spacing(0)
