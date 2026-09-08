"""Findings as rows, with the legacy paragraph kept in step (INV-C7 / DEC-3).

Three jobs, in order of how much can go wrong:

1. **Split** the legacy ``findings`` string into rows without inventing content
   (:func:`split_legacy_findings`).
2. **Keep the string in step** with the rows, because the generated pack still
   reads it (:func:`sync_findings_text`). INV-C8 moved the *closure gate* onto
   rows; the pack still prints the concatenated string until C13/C15, so a
   mutation that left the string stale would still print the wrong paragraph.
   The string is therefore rewritten on every mutation.
3. **Own the rows** — list, create, update, delete, reorder, the one-shot
   lazy conversion, and the closure-gate read (:meth:`InvestigationFindingsService.has_non_empty_findings`).

Why the string is *overwritten* rather than merged
--------------------------------------------------
INV-C4's :func:`merge_nested_workspace_fields` only ever fills a blank: when
both the flat key and the nested slot hold text, the nested value stands and
nothing is copied. That is right for two independent editors of the same field,
and wrong here — after C7 the rows are the only author of ``findings``, so the
derived text has to replace whatever is in either shape. :func:`sync_findings_text`
therefore writes both shapes itself instead of calling the C4 merge. It follows
the same shape rules the merge does: the stored ``sections`` shape (dict, list,
or absent) is preserved rather than converted, a section whose value is not a
dict is left alone, and a nested slot holding a list or object is never
overwritten with text.

Why conversion is lazy
----------------------
A migration-time backfill would have to scan every run and write to rows the
workspace is saving into. Instead the first list or write for a run converts
that run's string, under a row lock on the run, and only when the run has no
rows yet — so it happens once, a second concurrent caller waits and then finds
the rows, and a run nobody opens is never touched.
"""

from __future__ import annotations

import re
from typing import Any, Optional, Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.investigation import InvestigationRun
from src.domain.models.investigation_finding import InvestigationFinding
from src.domain.services.investigation_data_reader import read_investigation_field
from src.domain.services.investigation_data_writer import WORKSPACE_FIELD_SECTIONS

#: The sections INV-C4 mirrors ``findings`` into. Read from the C4 map rather
#: than re-listed, so the two cannot drift apart.
FINDINGS_SECTIONS: tuple[str, ...] = tuple(WORKSPACE_FIELD_SECTIONS.get("findings", ()))

#: A line that opens a new finding: ``1.``  ``1)``  ``(1)``  ``-``  ``*``  ``•``.
#: Anchored and bounded on purpose — ``2026-03-01 the guard was removed`` is not a
#: list marker, and neither is a sentence that happens to contain a full stop.
_MARKER = re.compile(r"^\s*(?:\(?\d{1,3}[.)]|[-*\u2022\u2013])\s+")

_BLANK_LINE = re.compile(r"\n\s*\n")


def split_legacy_findings(text: Any) -> list[str]:
    """Split one legacy ``findings`` string into finding bodies.

    The rule, in the order the branches are tried:

    1. **Markers.** If any line opens with ``1.`` / ``1)`` / ``(1)`` / ``-`` / ``*``
       / ``•``, each such line starts a finding and the marker itself is dropped.
       Lines in between are continuations and stay attached, newlines included, so
       a wrapped sentence is not torn into two findings. Text before the first
       marker becomes its own finding rather than being discarded.
    2. **Paragraphs.** Otherwise, if a blank line appears anywhere, split on blank
       lines. A two-line paragraph is one finding, not two.
    3. **Lines.** Otherwise split on single newlines.

    Every branch strips each body and drops the empties, so trailing newlines and
    a marker with nothing after it produce no row. Nothing is added, merged or
    reworded: concatenating the results reproduces the original words. A value
    that is not a string, or is blank, gives ``[]`` — an empty findings string is
    an empty list, never one blank finding.
    """
    if not isinstance(text, str):
        return []
    body = text.replace("\r\n", "\n").replace("\r", "\n")
    if not body.strip():
        return []

    lines = body.split("\n")
    if any(_MARKER.match(line) for line in lines):
        chunks: list[list[str]] = []
        preamble: list[str] = []
        for line in lines:
            if _MARKER.match(line):
                chunks.append([_MARKER.sub("", line, count=1)])
            elif chunks:
                chunks[-1].append(line)
            else:
                preamble.append(line)
        parts = ["\n".join(preamble)] + ["\n".join(chunk) for chunk in chunks]
    elif _BLANK_LINE.search(body):
        parts = _BLANK_LINE.split(body)
    else:
        parts = lines

    return [part.strip() for part in parts if part.strip()]


def join_findings_bodies(bodies: Sequence[str]) -> str:
    """Render ordered finding bodies as the one string the legacy readers expect.

    Two or more are numbered, and feeding that back through
    :func:`split_legacy_findings` returns the same bodies — multi-line ones
    included, since their continuation lines carry no marker.

    A single finding is rendered as its own text with no ``1.`` prefix. That is
    the overwhelmingly common legacy shape (one typed paragraph), and numbering it
    would rewrite the exact words the pack prints and the closure gate reads on
    the very first read of a run nobody has edited.

    An empty list renders as ``""``, so "every finding was deleted" and "there
    were never any" look the same to the gate — both are still blockers, which is
    the intended answer.
    """
    cleaned = [str(body).strip() for body in bodies if str(body).strip()]
    if not cleaned:
        return ""
    if len(cleaned) == 1:
        return cleaned[0]
    return "\n".join(f"{index}. {body}" for index, body in enumerate(cleaned, start=1))


def _fillable_slot(current: Any) -> bool:
    """A nested slot text may be written into: absent, null, or already a string.

    A list or a dict there belongs to a structured editor (the closure gate checks
    ``isinstance(list)`` for array fields), so it is left alone — the same rule
    INV-C4's writer applies.
    """
    return current is None or isinstance(current, str)


def sync_findings_text(data: Any, text: str) -> Any:
    """Return ``data`` with the derived findings string written to both shapes.

    Flat ``data["findings"]`` and every nested
    ``data["sections"][<findings section>]["findings"]`` are set to ``text``.
    Unrelated keys and unrelated sections are carried over untouched and the
    input is not mutated.

    A payload that is not a dict is returned unchanged rather than coerced, so
    this is safe on any persist path. The stored ``sections`` shape is preserved:
    a dict stays a dict, a list stays a list, and anything else (a stray string)
    is frozen — the value is not readable as sections and rewriting it would
    destroy data the pack builder may still understand. An empty ``text`` clears
    the flat key and any nested slot that already exists but does not create a
    section just to hold ``""``.
    """
    if not isinstance(data, dict):
        return data

    merged: dict[str, Any] = dict(data)
    merged["findings"] = text

    raw_sections = merged.get("sections")
    if isinstance(raw_sections, dict):
        sections = dict(raw_sections)
        touched = False
        for key in FINDINGS_SECTIONS:
            current = sections.get(key)
            if current is None:
                if not text:
                    continue
                sections[key] = {"findings": text}
                touched = True
                continue
            if not isinstance(current, dict):
                continue
            if not _fillable_slot(current.get("findings")):
                continue
            if "findings" not in current and not text:
                continue
            sections[key] = {**current, "findings": text}
            touched = True
        if touched:
            merged["sections"] = sections
        return merged

    if isinstance(raw_sections, list):
        entries = list(raw_sections)
        touched = False
        for key in FINDINGS_SECTIONS:
            index = _list_index(entries, key)
            if index is None:
                if not text:
                    continue
                entries.append({"id": key, "fields": {"findings": text}})
                touched = True
                continue
            entry = entries[index]
            if not isinstance(entry, dict):
                continue
            fields = entry.get("fields")
            # Entries without a ``fields`` map hold their fields inline, as the C3
            # reader reads them.
            container = fields if isinstance(fields, dict) else entry
            if not _fillable_slot(container.get("findings")):
                continue
            if "findings" not in container and not text:
                continue
            updated = {**container, "findings": text}
            entries[index] = {**entry, "fields": updated} if isinstance(fields, dict) else updated
            touched = True
        if touched:
            merged["sections"] = entries
        return merged

    if raw_sections is None and text and FINDINGS_SECTIONS:
        merged["sections"] = {key: {"findings": text} for key in FINDINGS_SECTIONS}
    return merged


def _list_index(entries: list[Any], section: str) -> Optional[int]:
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            continue
        key = str(entry.get("id") or entry.get("section_id") or f"section_{index}")
        if key == section:
            return index
    return None


class InvestigationFindingsService:
    """Row CRUD for one run's findings, plus the lazy legacy conversion.

    Every method takes the ``InvestigationRun`` the caller has *already*
    tenant-checked and re-filters the row query on ``tenant_id`` anyway. None of
    these commit: the route owns the transaction, so a failed JSON sync and a
    successful row write cannot land separately.
    """

    @staticmethod
    async def list_findings(
        db: AsyncSession,
        *,
        investigation: InvestigationRun,
        tenant_id: int,
    ) -> list[InvestigationFinding]:
        """Return the run's findings in order, converting the legacy string once."""
        await InvestigationFindingsService.ensure_converted(db, investigation=investigation, tenant_id=tenant_id)
        return await InvestigationFindingsService._ordered_rows(
            db, investigation_id=int(investigation.id), tenant_id=tenant_id
        )

    @staticmethod
    async def snapshot(
        db: AsyncSession,
        *,
        investigation: InvestigationRun,
        tenant_id: int,
    ) -> tuple[list[InvestigationFinding], str]:
        """The ordered rows and the exact string the legacy readers will see.

        Converts nothing — callers that may convert do so explicitly first, so a
        read that writes is never accidental.
        """
        rows = await InvestigationFindingsService._ordered_rows(
            db, investigation_id=int(investigation.id), tenant_id=tenant_id
        )
        return rows, join_findings_bodies([row.body for row in rows])

    @staticmethod
    async def has_non_empty_findings(
        db: AsyncSession,
        *,
        investigation: InvestigationRun,
        tenant_id: int,
    ) -> bool:
        """True iff this run has at least one non-empty finding row.

        Tenant-scoped on the row query even though the caller has already
        tenant-checked the run: a crafted tenant id must not see another
        organisation's findings, and must not convert the legacy string into
        the wrong tenant.

        When the table is empty, converts the leftover C4/C7 string once via
        :meth:`ensure_converted`. That split does not invent text — a blank
        or missing string stays empty and this returns False.

        Fail closed on a tenant mismatch or a missing run id. Probe errors
        propagate so the closure helper can refuse the close rather than
        guessing.
        """
        record_tenant = getattr(investigation, "tenant_id", None)
        investigation_id = getattr(investigation, "id", None)
        if investigation_id is None or record_tenant is None:
            return False
        try:
            if int(record_tenant) != int(tenant_id):
                return False
        except (TypeError, ValueError):
            return False

        scoped_investigation_id = int(investigation_id)
        scoped_tenant_id = int(tenant_id)

        async def _any_non_empty() -> bool:
            rows = await InvestigationFindingsService._ordered_rows(
                db, investigation_id=scoped_investigation_id, tenant_id=scoped_tenant_id
            )
            return any(str(getattr(row, "body", "") or "").strip() for row in rows)

        if await _any_non_empty():
            return True
        await InvestigationFindingsService.ensure_converted(db, investigation=investigation, tenant_id=scoped_tenant_id)
        return await _any_non_empty()

    @staticmethod
    async def ensure_converted(
        db: AsyncSession,
        *,
        investigation: InvestigationRun,
        tenant_id: int,
        actor_id: Optional[int] = None,
    ) -> list[InvestigationFinding]:
        """Turn the legacy ``findings`` string into rows, at most once per run.

        Idempotent by construction rather than by a marker column: the conversion
        only runs when the run has **zero** rows, so a second call — a second GET,
        a retried request, a concurrent tab — finds rows and does nothing. Deleting
        every finding also rewrites the string to ``""`` (see :meth:`_resync`), so
        an emptied list cannot be resurrected from stale text on the next read.

        The zero-row check and the insert are taken under a row lock on the run, so
        two concurrent first-reads cannot both decide the table is empty and insert
        the same findings twice. SQLite ignores ``FOR UPDATE``; there the guard is
        the single writer the database already enforces.

        Returns the rows it created, empty when there was nothing to convert.
        """
        investigation_id = int(investigation.id)
        if await InvestigationFindingsService._count(db, investigation_id, tenant_id):
            return []

        legacy = read_investigation_field(investigation.data, "findings")
        bodies = split_legacy_findings(legacy)
        if not bodies:
            return []

        # Serialise first-readers of this run against each other.
        await db.execute(select(InvestigationRun.id).where(InvestigationRun.id == investigation_id).with_for_update())
        if await InvestigationFindingsService._count(db, investigation_id, tenant_id):
            return []

        rows = [
            InvestigationFinding(
                tenant_id=tenant_id,
                investigation_id=investigation_id,
                sort_order=index,
                body=body,
                created_by_id=actor_id,
                updated_by_id=actor_id,
            )
            for index, body in enumerate(bodies)
        ]
        db.add_all(rows)
        await db.flush()
        # Re-render from the rows rather than keeping the original text: the
        # conversion may have dropped blank lines, and the string must describe
        # what is now stored.
        await InvestigationFindingsService._resync(db, investigation=investigation, tenant_id=tenant_id)
        return rows

    @staticmethod
    async def create_finding(
        db: AsyncSession,
        *,
        investigation: InvestigationRun,
        tenant_id: int,
        body: str,
        actor_id: Optional[int] = None,
    ) -> InvestigationFinding:
        """Append a finding. Converts the legacy string first, so nothing is lost."""
        investigation_id = int(investigation.id)
        await InvestigationFindingsService.ensure_converted(
            db, investigation=investigation, tenant_id=tenant_id, actor_id=actor_id
        )
        highest = await db.scalar(
            select(func.max(InvestigationFinding.sort_order)).where(
                InvestigationFinding.investigation_id == investigation_id,
                InvestigationFinding.tenant_id == tenant_id,
            )
        )
        row = InvestigationFinding(
            tenant_id=tenant_id,
            investigation_id=investigation_id,
            sort_order=0 if highest is None else int(highest) + 1,
            body=body.strip(),
            created_by_id=actor_id,
            updated_by_id=actor_id,
        )
        db.add(row)
        await db.flush()
        await InvestigationFindingsService._resync(db, investigation=investigation, tenant_id=tenant_id)
        return row

    @staticmethod
    async def update_finding(
        db: AsyncSession,
        *,
        investigation: InvestigationRun,
        tenant_id: int,
        finding_id: int,
        body: str,
        actor_id: Optional[int] = None,
    ) -> Optional[InvestigationFinding]:
        """Rewrite one finding's text. ``None`` when it is not this run's, or not this tenant's."""
        row = await InvestigationFindingsService._row(
            db, investigation_id=int(investigation.id), tenant_id=tenant_id, finding_id=finding_id
        )
        if row is None:
            return None
        row.body = body.strip()
        row.updated_by_id = actor_id
        await db.flush()
        await InvestigationFindingsService._resync(db, investigation=investigation, tenant_id=tenant_id)
        return row

    @staticmethod
    async def delete_finding(
        db: AsyncSession,
        *,
        investigation: InvestigationRun,
        tenant_id: int,
        finding_id: int,
    ) -> bool:
        """Remove one finding and close the gap in ``sort_order``."""
        row = await InvestigationFindingsService._row(
            db, investigation_id=int(investigation.id), tenant_id=tenant_id, finding_id=finding_id
        )
        if row is None:
            return False
        await db.delete(row)
        await db.flush()
        await InvestigationFindingsService._compact(db, int(investigation.id), tenant_id)
        await InvestigationFindingsService._resync(db, investigation=investigation, tenant_id=tenant_id)
        return True

    @staticmethod
    async def reorder_findings(
        db: AsyncSession,
        *,
        investigation: InvestigationRun,
        tenant_id: int,
        finding_ids: Sequence[int],
    ) -> Optional[list[InvestigationFinding]]:
        """Apply a new order.

        ``finding_ids`` must be exactly this run's findings, each once — a partial
        or padded list is refused with ``None`` rather than applied to whatever
        matched, because a reorder that silently dropped an id would look like a
        successful save and lose a finding's position without saying so.
        """
        investigation_id = int(investigation.id)
        rows = await InvestigationFindingsService._ordered_rows(
            db, investigation_id=investigation_id, tenant_id=tenant_id
        )
        requested = [int(value) for value in finding_ids]
        if sorted(requested) != sorted(row.id for row in rows):
            return None

        by_id = {row.id: row for row in rows}
        for position, finding_id in enumerate(requested):
            by_id[finding_id].sort_order = position
        await db.flush()
        await InvestigationFindingsService._resync(db, investigation=investigation, tenant_id=tenant_id)
        return [by_id[finding_id] for finding_id in requested]

    # -- internals -----------------------------------------------------------

    @staticmethod
    async def _resync(
        db: AsyncSession,
        *,
        investigation: InvestigationRun,
        tenant_id: int,
    ) -> str:
        """Rewrite ``data.findings`` (flat and nested) from the rows. Returns the text."""
        rows = await InvestigationFindingsService._ordered_rows(
            db, investigation_id=int(investigation.id), tenant_id=tenant_id
        )
        text = join_findings_bodies([row.body for row in rows])
        # ``sync_findings_text`` deliberately refuses to coerce a non-dict payload,
        # which is right on a shared persist path and wrong here: a run whose JSON
        # is null or corrupt would silently keep no findings string at all, and the
        # closure gate would go on reading nothing. Start from an empty object
        # instead, but only when there is text to record.
        blob: Any = investigation.data
        if not isinstance(blob, dict):
            if not text:
                return text
            blob = {}
        # Reassigned, never mutated in place: ``data`` is a plain JSON column with
        # no mutation tracking, so an in-place edit would not be persisted.
        investigation.data = sync_findings_text(blob, text)
        return text

    @staticmethod
    async def _ordered_rows(
        db: AsyncSession,
        *,
        investigation_id: int,
        tenant_id: int,
    ) -> list[InvestigationFinding]:
        result = await db.execute(
            select(InvestigationFinding)
            .where(
                InvestigationFinding.investigation_id == investigation_id,
                InvestigationFinding.tenant_id == tenant_id,
            )
            .order_by(InvestigationFinding.sort_order, InvestigationFinding.id)
        )
        return list(result.scalars().all())

    @staticmethod
    async def _row(
        db: AsyncSession,
        *,
        investigation_id: int,
        tenant_id: int,
        finding_id: int,
    ) -> Optional[InvestigationFinding]:
        result = await db.execute(
            select(InvestigationFinding).where(
                InvestigationFinding.id == finding_id,
                InvestigationFinding.investigation_id == investigation_id,
                InvestigationFinding.tenant_id == tenant_id,
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def _count(db: AsyncSession, investigation_id: int, tenant_id: int) -> int:
        total = await db.scalar(
            select(func.count(InvestigationFinding.id)).where(
                InvestigationFinding.investigation_id == investigation_id,
                InvestigationFinding.tenant_id == tenant_id,
            )
        )
        return int(total or 0)

    @staticmethod
    async def _compact(db: AsyncSession, investigation_id: int, tenant_id: int) -> None:
        """Renumber to 0..n-1 so a later append cannot collide with a deleted slot."""
        rows = await InvestigationFindingsService._ordered_rows(
            db, investigation_id=investigation_id, tenant_id=tenant_id
        )
        changed = False
        for position, row in enumerate(rows):
            if row.sort_order != position:
                row.sort_order = position
                changed = True
        if changed:
            await db.flush()


__all__ = [
    "FINDINGS_SECTIONS",
    "InvestigationFindingsService",
    "join_findings_bodies",
    "split_legacy_findings",
    "sync_findings_text",
]
