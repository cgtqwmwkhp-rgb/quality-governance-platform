"""Write investigation JSON in the nested shape the report path reads, without dropping flat keys.

C3 gave readers one way to read ``data.sections.<section>.<field>`` or the flat ``data.<field>``
the workspace writes, but nothing wrote the nested shape at runtime. A finding typed on the
detail page therefore never reached the template closure walk (``iter_run_section_values``
descends ``data.sections`` and returns) or the generated pack.

This module dual-writes on the persist path:

* a non-empty flat key is copied into its section(s) when the nested slot is empty or absent;
* a non-empty nested value is copied onto the flat key when that is empty or absent.

Flat keys stay where they are — dropping the flat readers is the later contraction (C18) — so
reverting the writer leaves every row readable by both shapes. Nothing is invented: when both
sides are empty nothing is created, and when both hold content the nested value stands, which
is the C3 precedence rule. Calling it twice on one payload changes nothing the second time, so
it doubles as the lazy backfill for rows written before this PR.
"""

from __future__ import annotations

from typing import Any, Optional

_FINDINGS_SECTIONS = ("section_3_investigation_findings",)

# The RCA fields go to the contract v2.2 section *and* the ``rca`` alias, because the default
# template (id=1) declares its root-cause section as ``rca`` and the closure walk takes section
# keys from the template, not from the data. Writing one key only would leave the gate blind on
# whichever of the two templates a run happens to use.
_ROOT_CAUSE_SECTIONS = ("section_4_root_cause", "rca")

WORKSPACE_FIELD_SECTIONS: dict[str, tuple[str, ...]] = {
    "lead_investigator": _FINDINGS_SECTIONS,
    "findings": _FINDINGS_SECTIONS,
    "conclusion": _FINDINGS_SECTIONS,
    "problem_statement": _ROOT_CAUSE_SECTIONS,
    "root_cause": _ROOT_CAUSE_SECTIONS,
    "contributing_factors": _ROOT_CAUSE_SECTIONS,
    **{f"why_{index}": _ROOT_CAUSE_SECTIONS for index in range(1, 6)},
}

_MISSING = object()


def _is_empty(value: Any) -> bool:
    """Emptiness as the rest of the platform judges it (see ``audit_conditional._is_empty``).

    ``0`` and ``False`` are values, not blanks.
    """
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    if isinstance(value, (list, tuple, dict, set)):
        return len(value) == 0
    return False


def _is_usable(value: Any) -> bool:
    """True when a value is worth copying to the other shape."""
    return value is not _MISSING and not _is_empty(value)


def _is_fillable(value: Any) -> bool:
    """True when a slot can be filled from the other shape without destroying anything.

    Deliberately narrower than ``_is_empty``: an empty list or dict declares the field's type
    (the closure gate checks ``isinstance(list)`` for array fields), so a blank array is left
    alone rather than replaced with the workspace's text.
    """
    if value is _MISSING or value is None:
        return True
    return isinstance(value, str) and value.strip() == ""


class _Sections:
    """Read/write access to ``data.sections`` in whichever shape the row already uses.

    The shape is preserved, never converted. ``iter_run_section_values`` and the pack builder
    treat dict- and list-shaped payloads differently — the closure walk cannot see a list at all —
    so rewriting one shape into the other here would silently change what those callers report.

    Anything that is neither a dict, a list, nor absent (a stray string, say) is frozen: read as
    empty, never written. A section whose value is not a dict is skipped the same way, so a
    malformed row loses nothing and does not 500.
    """

    def __init__(self, raw: Any) -> None:
        self.dirty = False
        self._frozen = False
        self._dict: dict[str, Any] = {}
        self._list: Optional[list[Any]] = None
        # Containers already copied for writing, keyed by section, so a second write to one
        # section does not re-copy the original and drop the first field.
        self._open: dict[str, dict[str, Any]] = {}

        if isinstance(raw, dict):
            self._dict = dict(raw)
        elif isinstance(raw, list):
            self._list = list(raw)
        elif raw is not None:
            self._frozen = True

    def get(self, section: str, field: str) -> Any:
        container = self._read_container(section)
        if container is None or field not in container:
            return _MISSING
        return container[field]

    def set(self, section: str, field: str, value: Any) -> None:
        container = self._write_container(section)
        if container is None:
            return
        container[field] = value
        self.dirty = True

    def materialise(self) -> Any:
        return self._dict if self._list is None else self._list

    # -- internals ---------------------------------------------------------

    def _read_container(self, section: str) -> Optional[dict[str, Any]]:
        if self._frozen:
            return None
        if self._list is None:
            value = self._dict.get(section)
            return value if isinstance(value, dict) else None
        index = self._list_index(section)
        if index is None:
            return None
        return self._entry_fields(self._list[index])

    def _write_container(self, section: str) -> Optional[dict[str, Any]]:
        if self._frozen:
            return None
        already_open = self._open.get(section)
        if already_open is not None:
            return already_open

        if self._list is None:
            current = self._dict.get(section)
            if current is None:
                container: dict[str, Any] = {}
            elif isinstance(current, dict):
                container = dict(current)
            else:
                # A section that is not a dict is somebody else's data; never overwrite it.
                return None
            self._dict[section] = container
            self._open[section] = container
            return container

        index = self._list_index(section)
        if index is None:
            container = {}
            self._list.append({"id": section, "fields": container})
            self._open[section] = container
            return container

        entry = dict(self._list[index])
        fields = entry.get("fields")
        if isinstance(fields, dict):
            container = dict(fields)
            entry["fields"] = container
        else:
            # Entries without a ``fields`` map hold their fields inline, as the C3 reader reads them.
            container = entry
        self._list[index] = entry
        self._open[section] = container
        return container

    def _list_index(self, section: str) -> Optional[int]:
        if self._list is None:
            return None
        for index, entry in enumerate(self._list):
            if not isinstance(entry, dict):
                continue
            key = str(entry.get("id") or entry.get("section_id") or f"section_{index}")
            if key == section:
                return index
        return None

    @staticmethod
    def _entry_fields(entry: Any) -> Optional[dict[str, Any]]:
        if not isinstance(entry, dict):
            return None
        fields = entry.get("fields")
        return fields if isinstance(fields, dict) else entry


def merge_nested_workspace_fields(data: Any) -> Any:
    """Return ``data`` with the known workspace fields present in both shapes.

    Idempotent, additive, and value-preserving:

    * both sides empty — nothing is created, so an untouched blob comes back unchanged;
    * one side empty — the side with content is copied to the other;
    * both sides hold content — the nested value stands and the flat key is left alone.

    A payload that is not a dict (``None`` from a PATCH, a list, a string) is returned unchanged
    rather than coerced into ``{}``, so this can sit on any persist path. Unrelated keys —
    ``source_snapshot``, ``customer_pack_visibility``, mapping logs, every other section — are
    carried over untouched, and the input dict is not mutated.
    """
    if not isinstance(data, dict):
        return data

    merged: dict[str, Any] = dict(data)
    sections = _Sections(merged.get("sections"))

    for field, target_sections in WORKSPACE_FIELD_SECTIONS.items():
        nested_value: Any = _MISSING
        for section in target_sections:
            candidate = sections.get(section, field)
            if _is_usable(candidate):
                nested_value = candidate
                break

        flat_value = merged.get(field, _MISSING)

        if nested_value is not _MISSING:
            if _is_fillable(flat_value):
                merged[field] = nested_value
            source = nested_value
        elif _is_usable(flat_value):
            source = flat_value
        else:
            continue

        for section in target_sections:
            if _is_fillable(sections.get(section, field)):
                sections.set(section, field, source)

    if sections.dirty:
        merged["sections"] = sections.materialise()
    return merged
