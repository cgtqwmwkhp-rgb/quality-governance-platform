"""Read investigation JSON whether it was written nested (from-record) or flat (detail page).

Creation-from-record stores ``data.sections.<section>.<field>``. The workspace
writes top-level keys such as ``data.findings``. Callers must not guess which
shape they have. This reader is the rollback target for later writer switches:
it understands both, prefers the nested value when both exist, and invents nothing.
"""

from __future__ import annotations

from typing import Any, Optional

_SKIP_SECTION_KEYS = frozenset({"id", "section_id", "title", "name", "fields"})


def _as_data_dict(data: Any) -> dict[str, Any]:
    return data if isinstance(data, dict) else {}


def _section_items(data: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    raw = data.get("sections")
    if isinstance(raw, dict):
        items: list[tuple[str, dict[str, Any]]] = []
        for key, value in raw.items():
            if isinstance(value, dict):
                items.append((str(key), value))
        return items
    if isinstance(raw, list):
        items = []
        for idx, entry in enumerate(raw):
            if not isinstance(entry, dict):
                continue
            key = str(entry.get("id") or entry.get("section_id") or f"section_{idx}")
            fields = entry.get("fields") if isinstance(entry.get("fields"), dict) else entry
            if isinstance(fields, dict):
                items.append((key, fields))
        return items
    return []


def read_investigation_field(data: Any, field: str) -> Optional[Any]:
    """Return ``field`` from nested sections if present, otherwise the top-level key.

    Missing data, a non-dict payload, and an unknown field all return None.
    An explicit empty string is returned as empty string — callers decide emptiness.
    """
    blob = _as_data_dict(data)
    name = str(field or "").strip()
    if not name:
        return None

    for _section_key, fields in _section_items(blob):
        if name in fields and name not in _SKIP_SECTION_KEYS:
            return fields[name]

    if name in blob and name != "sections":
        return blob[name]
    return None


def read_investigation_section_field(data: Any, section: str, field: str) -> Optional[Any]:
    """Return a field from a named section, falling back to the flat key."""
    blob = _as_data_dict(data)
    section_key = str(section or "").strip()
    field_key = str(field or "").strip()
    if not field_key:
        return None
    if section_key:
        for key, fields in _section_items(blob):
            if key == section_key and field_key in fields:
                return fields[field_key]
    return read_investigation_field(blob, field_key)
