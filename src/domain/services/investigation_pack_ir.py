"""Investigation pack document IR (INV-PACK-R1).

Pure data. No fpdf2, no ORM. PDF (R1) and Word (R3) both consume this so the
engine is not rewritten per format. Cover and contents are derived from
``PackDocument.meta`` / ``sections`` so they cannot disagree with the body.

``DocumentMeta`` has no tenant name and no tenant colour: the letterhead is the
brand kit. A writer that meets an unknown block type must raise, never skip.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Union


class Emphasis(str, Enum):
    BODY = "body"
    NOTE = "note"
    STRONG = "strong"
    CAPTION = "caption"


FIGURE_CHRONOLOGY = "chronology"
FIGURE_ICAM = "icam"


@dataclass(frozen=True)
class DocumentMeta:
    reference: str
    title: str
    audience_label: str
    status_label: str
    level_label: str
    generated_at_label: str
    pack_uuid: str
    content_sha256: str
    classification: str
    confidentiality: str
    incident_reference: str = ""


@dataclass(frozen=True)
class Heading:
    text: str
    level: int = 1
    number: str | None = None


@dataclass(frozen=True)
class Paragraph:
    text: str
    emphasis: Emphasis = Emphasis.BODY


@dataclass(frozen=True)
class KeyValueRow:
    label: str
    value: str


@dataclass(frozen=True)
class KeyValueBlock:
    rows: tuple[KeyValueRow, ...]


@dataclass(frozen=True)
class ListBlock:
    items: tuple[str, ...]
    ordered: bool = False
    empty_message: str | None = None


@dataclass(frozen=True)
class TableBlock:
    columns: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]
    empty_message: str | None = None
    #: Column fractions of the content width. When omitted, two columns are
    #: 28/72 (reference / action); otherwise equal.
    widths: tuple[float, ...] | None = None


@dataclass(frozen=True)
class FigureBlock:
    kind: str
    payload: Any
    caption: str | None = None
    fallback: tuple["Block", ...] = ()


@dataclass(frozen=True)
class LegacySectionWalk:
    """R1 escape hatch: existing section renderer. R2 deletes this type."""

    sections: dict[str, Any]
    pack_uuid: Any


Block = Union[
    Heading,
    Paragraph,
    KeyValueBlock,
    ListBlock,
    TableBlock,
    FigureBlock,
    LegacySectionWalk,
]


@dataclass(frozen=True)
class Section:
    id: str
    heading: str
    blocks: tuple[Block, ...]
    in_contents: bool = True


@dataclass(frozen=True)
class PackDocument:
    meta: DocumentMeta
    sections: tuple[Section, ...]

    def contents_entries(self) -> tuple[tuple[int, str], ...]:
        numbered = [section for section in self.sections if section.in_contents]
        return tuple((index + 1, section.heading) for index, section in enumerate(numbered))
