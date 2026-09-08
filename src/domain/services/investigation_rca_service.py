"""RCA for an investigation run, stored on ``five_whys_analyses`` (INV-C10).

Three jobs, in the order that hurts if they drift:

1. **Own the analysis** for this run on the existing ``five_whys_analyses``
   table — one tenant-scoped row the workspace reads and writes, with each Why
   as ``{level, why, answer, evidence}``. No second table, and no CAPA-per-Why
   column (INV-C11).
2. **Keep the legacy strings in step.** Closure and the generated pack still
   read ``why_1``..``why_5``, ``problem_statement``, ``root_cause`` and
   ``contributing_factors`` (flat and nested) until C13/C18. Every workspace
   write dual-writes those strings from the analysis. The strings are
   overwritten, not merged: after C10 the analysis is the author, and C4's
   blank-fill merge would leave a stale nested Why standing over a cleared
   analysis.
3. **Convert leftover strings once.** A migration backfill would scan every
   run. Instead the first GET or PUT for a run with no tenant-scoped analysis
   copies ``why_1``..``why_5`` (and the other RCA strings) into a row, under a
   row lock on the run. Empty / whitespace / non-string values produce no Why
   text — nothing is invented. A run nobody opens is never touched.

Fail closed: every query re-filters on ``tenant_id`` even though the caller has
already tenant-checked the run. A missing tenant id, a mismatch, or another
organisation's row is "no analysis", never a 500 and never a Why that does not
belong to this tenant.
"""

from __future__ import annotations

from typing import Any, Optional, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.investigation import InvestigationRun
from src.domain.models.rca_tools import FiveWhysAnalysis
from src.domain.services.investigation_data_reader import read_investigation_field, read_investigation_section_field
from src.domain.services.investigation_data_writer import WORKSPACE_FIELD_SECTIONS

WHY_LEVELS: tuple[int, ...] = (1, 2, 3, 4, 5)

RCA_STRING_FIELDS: tuple[str, ...] = (
    "problem_statement",
    "root_cause",
    "contributing_factors",
    *(f"why_{level}" for level in WHY_LEVELS),
)

#: Longest prose a workspace RCA field may carry. Matches the finding-body cap:
#: these are investigator sentences, not documents.
RCA_TEXT_MAX_LENGTH = 10000


def _as_text(value: Any) -> str:
    """A stored value as workspace text. Non-strings are not coerced into words."""
    return value if isinstance(value, str) else ""


def _usable_text(value: Any) -> str:
    """Strip for emptiness only. The words themselves are not rewritten."""
    return _as_text(value).strip()


def _legacy_text(data: Any, field: str) -> str:
    """Read one RCA string the way the workspace does: non-empty nested, then flat.

    ``read_investigation_field`` returns a nested key even when it is ``""``,
    which would hide a still-present flat ``why_1`` on a half-migrated row.
    Conversion must not invent text, but it also must not drop text that is
    already there. Nested *non-empty* wins (C3); otherwise the flat key.
    """
    for section in WORKSPACE_FIELD_SECTIONS.get(field, ()):
        candidate = read_investigation_section_field(data, section, field)
        if _usable_text(candidate):
            return str(candidate).strip()

    flat = read_investigation_field(data, field)
    # ``read_investigation_field`` may still return the nested empty string when
    # the key exists nested; the loop above already skipped those. The flat key
    # is the remaining source.
    if isinstance(data, dict):
        flat_value = data.get(field)
        if _usable_text(flat_value):
            return str(flat_value).strip()
    if _usable_text(flat):
        return str(flat).strip()
    return ""


def _factors_to_text(value: Any) -> str:
    """Render stored contributing factors as the one textarea string.

    The column is JSON (a list in the RCA-tools model). The workspace is one
    box. A list of existing strings is joined; a stored string is used as-is.
    Nothing is split or reworded.
    """
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        parts = [str(item).strip() for item in value if str(item).strip()]
        return "\n".join(parts)
    return ""


def _factors_from_text(text: str) -> list[str]:
    """Store the workspace string as a one-item list, or empty.

    Splitting on newlines would invent several factors from one box (C12 is
    ICAM; this PR does not).
    """
    cleaned = (text or "").strip()
    return [cleaned] if cleaned else []


def _normalise_why_entry(raw: Any, fallback_level: int) -> dict[str, Any]:
    """Shape one stored Why. Missing keys become empty strings, never invented prose."""
    if not isinstance(raw, dict):
        return {"level": fallback_level, "why": "", "answer": "", "evidence": ""}
    try:
        level = int(raw.get("level") or fallback_level)
    except (TypeError, ValueError):
        level = fallback_level
    evidence = raw.get("evidence")
    return {
        "level": level,
        "why": _as_text(raw.get("why")),
        "answer": _as_text(raw.get("answer")),
        "evidence": _as_text(evidence) if evidence is not None else "",
    }


def workspace_whys(stored: Any) -> list[dict[str, str | int]]:
    """The Why chain the workspace renders: levels 1–5, plus any extra levels kept.

    Missing levels are empty slots, not invented answers. Extra levels from the
    generic RCA-tools editor are appended so a workspace save cannot drop them
    just because the tab only edits five.
    """
    by_level: dict[int, dict[str, Any]] = {}
    extras: list[dict[str, Any]] = []
    if isinstance(stored, list):
        for index, raw in enumerate(stored):
            entry = _normalise_why_entry(raw, index + 1)
            level = int(entry["level"])
            if level in WHY_LEVELS:
                by_level[level] = entry
            elif level > WHY_LEVELS[-1]:
                extras.append(entry)

    slots: list[dict[str, str | int]] = []
    for level in WHY_LEVELS:
        entry = by_level.get(level) or {"level": level, "why": "", "answer": "", "evidence": ""}
        slots.append(
            {
                "level": level,
                "why": str(entry.get("why") or ""),
                "answer": str(entry.get("answer") or ""),
                "evidence": str(entry.get("evidence") or ""),
            }
        )
    extras.sort(key=lambda item: int(item["level"]))
    for entry in extras:
        slots.append(
            {
                "level": int(entry["level"]),
                "why": str(entry.get("why") or ""),
                "answer": str(entry.get("answer") or ""),
                "evidence": str(entry.get("evidence") or ""),
            }
        )
    return slots


def legacy_why_strings(whys: Sequence[dict[str, Any]]) -> dict[str, str]:
    """``why_1``..``why_5`` from the analysis answers. Empty levels are ``""``."""
    by_level = {int(item["level"]): _as_text(item.get("answer")).strip() for item in whys if "level" in item}
    return {f"why_{level}": by_level.get(level, "") for level in WHY_LEVELS}


def empty_rca_payload(investigation_id: int) -> dict[str, Any]:
    """Honest empty: five blank Whys, no analysis ``id``, no invented text."""
    whys = workspace_whys([])
    payload: dict[str, Any] = {
        "id": None,
        "investigation_id": investigation_id,
        "problem_statement": "",
        "whys": whys,
        "root_cause": "",
        "contributing_factors": "",
    }
    payload.update(legacy_why_strings(whys))
    return payload


def _fillable_slot(current: Any) -> bool:
    """A nested slot text may be written into: absent, null, or already a string."""
    return current is None or isinstance(current, str)


def _list_index(entries: list[Any], section: str) -> Optional[int]:
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            continue
        key = str(entry.get("id") or entry.get("section_id") or f"section_{index}")
        if key == section:
            return index
    return None


def sync_rca_workspace_fields(  # noqa: C901 — three section shapes, many fields
    data: Any, fields: dict[str, str]
) -> Any:
    """Return ``data`` with the RCA strings written to both JSON shapes.

    Flat keys and every nested ``data["sections"][<rca section>][<field>]`` are
    set from ``fields``. Unrelated keys and unrelated sections are carried over
    and the input is not mutated.

    An empty value clears the flat key and any nested slot that already exists,
    but does not create a section just to hold ``""``. A nested slot holding a
    list or object is left alone — that slot belongs to a structured editor.
    The stored ``sections`` shape (dict, list, or absent) is preserved.
    """
    if not isinstance(data, dict):
        if not any(str(value).strip() for value in fields.values()):
            return data
        data = {}

    merged: dict[str, Any] = dict(data)
    for field, text in fields.items():
        merged[field] = text

    raw_sections = merged.get("sections")
    if isinstance(raw_sections, dict):
        sections = dict(raw_sections)
        touched = False
        for field, text in fields.items():
            for key in WORKSPACE_FIELD_SECTIONS.get(field, ()):
                current = sections.get(key)
                if current is None:
                    if not text:
                        continue
                    sections[key] = {field: text}
                    touched = True
                    continue
                if not isinstance(current, dict):
                    continue
                if not _fillable_slot(current.get(field)):
                    continue
                if field not in current and not text:
                    continue
                sections[key] = {**current, field: text}
                touched = True
        if touched:
            merged["sections"] = sections
        return merged

    if isinstance(raw_sections, list):
        entries = list(raw_sections)
        touched = False
        for field, text in fields.items():
            for key in WORKSPACE_FIELD_SECTIONS.get(field, ()):
                index = _list_index(entries, key)
                if index is None:
                    if not text:
                        continue
                    entries.append({"id": key, "fields": {field: text}})
                    touched = True
                    continue
                entry = entries[index]
                if not isinstance(entry, dict):
                    continue
                stored_fields = entry.get("fields")
                container = stored_fields if isinstance(stored_fields, dict) else entry
                if not _fillable_slot(container.get(field)):
                    continue
                if field not in container and not text:
                    continue
                updated = {**container, field: text}
                entries[index] = {**entry, "fields": updated} if isinstance(stored_fields, dict) else updated
                touched = True
        if touched:
            merged["sections"] = entries
        return merged

    if raw_sections is None:
        nested: dict[str, dict[str, str]] = {}
        for field, text in fields.items():
            if not text:
                continue
            for key in WORKSPACE_FIELD_SECTIONS.get(field, ()):
                nested.setdefault(key, {})[field] = text
        if nested:
            merged["sections"] = nested
    return merged


def _has_legacy_rca(data: Any) -> bool:
    return any(_legacy_text(data, field) for field in RCA_STRING_FIELDS)


def _whys_from_legacy(data: Any) -> list[dict[str, Any]]:
    """Copy ``why_1``..``why_5`` into analysis entries. Empty slots are omitted."""
    entries: list[dict[str, Any]] = []
    for level in WHY_LEVELS:
        answer = _legacy_text(data, f"why_{level}")
        if not answer:
            continue
        entries.append({"level": level, "why": "", "answer": answer, "evidence": None})
    return entries


def _entity_type(investigation: InvestigationRun) -> Optional[str]:
    value = getattr(investigation, "assigned_entity_type", None)
    if value is None:
        return None
    return value.value if hasattr(value, "value") else str(value)


class InvestigationRcaService:
    """One investigation's 5-Whys analysis, plus lazy conversion and dual-write.

    None of these commit: the route owns the transaction, so a failed JSON sync
    and a successful analysis write cannot land separately.
    """

    @staticmethod
    def _tenants_match(investigation: InvestigationRun, tenant_id: int) -> bool:
        record_tenant = getattr(investigation, "tenant_id", None)
        investigation_id = getattr(investigation, "id", None)
        if investigation_id is None or record_tenant is None:
            return False
        try:
            return int(record_tenant) == int(tenant_id)
        except (TypeError, ValueError):
            return False

    @staticmethod
    def serialise(investigation: InvestigationRun, analysis: Optional[FiveWhysAnalysis]) -> dict[str, Any]:
        """The workspace payload. ``analysis is None`` is honest empty, not an error."""
        investigation_id = int(investigation.id)
        if analysis is None:
            return empty_rca_payload(investigation_id)
        whys = workspace_whys(analysis.whys)
        payload: dict[str, Any] = {
            "id": int(analysis.id) if analysis.id is not None else None,
            "investigation_id": investigation_id,
            "problem_statement": _as_text(analysis.problem_statement),
            "whys": whys,
            "root_cause": _as_text(analysis.primary_root_cause),
            "contributing_factors": _factors_to_text(analysis.contributing_factors),
        }
        payload.update(legacy_why_strings(whys))
        return payload

    @staticmethod
    async def get_workspace(
        db: AsyncSession,
        *,
        investigation: InvestigationRun,
        tenant_id: int,
        actor_id: Optional[int] = None,
    ) -> dict[str, Any]:
        """Return the workspace RCA, converting leftover strings once."""
        if not InvestigationRcaService._tenants_match(investigation, tenant_id):
            return empty_rca_payload(int(investigation.id) if investigation.id is not None else 0)

        await InvestigationRcaService.ensure_converted(
            db, investigation=investigation, tenant_id=tenant_id, actor_id=actor_id
        )
        analysis = await InvestigationRcaService._load(db, investigation_id=int(investigation.id), tenant_id=tenant_id)
        return InvestigationRcaService.serialise(investigation, analysis)

    @staticmethod
    async def upsert_workspace(
        db: AsyncSession,
        *,
        investigation: InvestigationRun,
        tenant_id: int,
        problem_statement: str,
        whys: Sequence[dict[str, Any]],
        root_cause: str,
        contributing_factors: str,
        actor_id: Optional[int] = None,
    ) -> Optional[dict[str, Any]]:
        """Create or replace this run's analysis and dual-write the legacy strings.

        Returns ``None`` when the tenant does not match — fail closed, no write.
        Converts leftover strings first so a first save cannot orphan what was
        already typed as ``why_1``.
        """
        if not InvestigationRcaService._tenants_match(investigation, tenant_id):
            return None

        await InvestigationRcaService.ensure_converted(
            db, investigation=investigation, tenant_id=tenant_id, actor_id=actor_id
        )
        analysis = await InvestigationRcaService._load(db, investigation_id=int(investigation.id), tenant_id=tenant_id)
        stored_whys = InvestigationRcaService._merge_whys(analysis.whys if analysis else None, whys)
        problem = (problem_statement or "").strip()
        root = (root_cause or "").strip()
        factors = _factors_from_text(contributing_factors)

        if analysis is None:
            analysis = FiveWhysAnalysis(
                tenant_id=tenant_id,
                investigation_id=int(investigation.id),
                entity_type=_entity_type(investigation),
                entity_id=getattr(investigation, "assigned_entity_id", None),
                problem_statement=problem,
                whys=stored_whys,
                primary_root_cause=root or None,
                root_causes=[root] if root else None,
                contributing_factors=factors,
                created_by_id=actor_id,
                updated_by_id=actor_id,
            )
            db.add(analysis)
        else:
            analysis.problem_statement = problem
            analysis.whys = stored_whys
            analysis.primary_root_cause = root or None
            analysis.root_causes = [root] if root else None
            analysis.contributing_factors = factors
            analysis.updated_by_id = actor_id
            if analysis.tenant_id is None:
                analysis.tenant_id = tenant_id

        await db.flush()
        await InvestigationRcaService._resync(db, investigation=investigation, analysis=analysis)
        return InvestigationRcaService.serialise(investigation, analysis)

    @staticmethod
    async def ensure_converted(
        db: AsyncSession,
        *,
        investigation: InvestigationRun,
        tenant_id: int,
        actor_id: Optional[int] = None,
    ) -> Optional[FiveWhysAnalysis]:
        """Turn leftover ``why_1``..``why_5`` into an analysis, at most once per run.

        Idempotent by construction: conversion only runs when this tenant has
        **no** analysis for the run. A claimed null-tenant row (linked to this
        investigation, ``tenant_id`` unset) is adopted rather than duplicated.
        Returns the row it created or claimed, or ``None`` when there was
        nothing to convert.
        """
        if not InvestigationRcaService._tenants_match(investigation, tenant_id):
            return None

        investigation_id = int(investigation.id)
        existing = await InvestigationRcaService._load(db, investigation_id=investigation_id, tenant_id=tenant_id)
        if existing is not None:
            return None

        claimable = await InvestigationRcaService._unscoped_for_run(db, investigation_id=investigation_id)
        has_legacy = _has_legacy_rca(investigation.data)
        if claimable is None and not has_legacy:
            return None

        await db.execute(select(InvestigationRun.id).where(InvestigationRun.id == investigation_id).with_for_update())
        existing = await InvestigationRcaService._load(db, investigation_id=investigation_id, tenant_id=tenant_id)
        if existing is not None:
            return None

        claimable = await InvestigationRcaService._unscoped_for_run(db, investigation_id=investigation_id)
        if claimable is not None:
            claimable.tenant_id = tenant_id
            claimable.updated_by_id = actor_id
            await db.flush()
            return claimable

        if not has_legacy:
            return None

        problem = _legacy_text(investigation.data, "problem_statement")
        root = _legacy_text(investigation.data, "root_cause")
        factors_text = _legacy_text(investigation.data, "contributing_factors")
        analysis = FiveWhysAnalysis(
            tenant_id=tenant_id,
            investigation_id=investigation_id,
            entity_type=_entity_type(investigation),
            entity_id=getattr(investigation, "assigned_entity_id", None),
            problem_statement=problem,
            whys=_whys_from_legacy(investigation.data),
            primary_root_cause=root or None,
            root_causes=[root] if root else None,
            contributing_factors=_factors_from_text(factors_text),
            created_by_id=actor_id,
            updated_by_id=actor_id,
        )
        db.add(analysis)
        await db.flush()
        await InvestigationRcaService._resync(db, investigation=investigation, analysis=analysis)
        return analysis

    @staticmethod
    def _merge_whys(existing: Any, incoming: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
        """Workspace levels 1–5 replace; extra stored levels above 5 are kept."""
        previous = workspace_whys(existing)
        extras = [item for item in previous if int(item["level"]) > WHY_LEVELS[-1]]
        previous_by_level = {int(item["level"]): item for item in previous}

        replacements: dict[int, dict[str, Any]] = {}
        for raw in incoming:
            if not isinstance(raw, dict):
                continue
            raw_level = raw.get("level")
            if raw_level is None:
                continue
            try:
                level = int(raw_level)
            except (TypeError, ValueError):
                continue
            if level < 1:
                continue
            prior = previous_by_level.get(level, {})
            question = _as_text(raw.get("why")).strip() or str(prior.get("why") or "")
            replacements[level] = {
                "level": level,
                "why": question,
                "answer": _as_text(raw.get("answer")).strip(),
                "evidence": _as_text(raw.get("evidence")).strip() or None,
            }

        # Levels 1–5 are a full replace so a cleared Why cannot resurrect from
        # the previous analysis. Extra levels above 5 stay unless the client
        # named them.
        merged: list[dict[str, Any]] = []
        for level in WHY_LEVELS:
            merged.append(
                replacements.get(
                    level,
                    {"level": level, "why": "", "answer": "", "evidence": None},
                )
            )
        for extra in extras:
            level = int(extra["level"])
            merged.append(replacements.get(level, extra))
        for level, entry in sorted(replacements.items()):
            if level > WHY_LEVELS[-1] and all(int(item["level"]) != level for item in extras):
                merged.append(entry)
        return merged

    @staticmethod
    async def _resync(
        db: AsyncSession,
        *,
        investigation: InvestigationRun,
        analysis: FiveWhysAnalysis,
    ) -> None:
        """Rewrite the legacy RCA strings from the analysis. Does not invent."""
        whys = workspace_whys(analysis.whys)
        fields = {
            "problem_statement": _as_text(analysis.problem_statement).strip(),
            "root_cause": _as_text(analysis.primary_root_cause).strip(),
            "contributing_factors": _factors_to_text(analysis.contributing_factors),
            **legacy_why_strings(whys),
        }
        blob: Any = investigation.data
        if not isinstance(blob, dict):
            if not any(fields.values()):
                return
            blob = {}
        investigation.data = sync_rca_workspace_fields(blob, fields)

    @staticmethod
    async def _load(
        db: AsyncSession,
        *,
        investigation_id: int,
        tenant_id: int,
    ) -> Optional[FiveWhysAnalysis]:
        result = await db.execute(
            select(FiveWhysAnalysis)
            .where(
                FiveWhysAnalysis.investigation_id == investigation_id,
                FiveWhysAnalysis.tenant_id == tenant_id,
            )
            .order_by(FiveWhysAnalysis.id.desc())
        )
        return result.scalars().first()

    @staticmethod
    async def _unscoped_for_run(
        db: AsyncSession,
        *,
        investigation_id: int,
    ) -> Optional[FiveWhysAnalysis]:
        """An analysis linked to this run whose tenant was never set.

        Claiming it (setting ``tenant_id``) is how a pre-C10 RCA-tools row
        becomes the workspace analysis without duplicating it. Another tenant's
        row is not selected: ``tenant_id IS NULL`` only.
        """
        result = await db.execute(
            select(FiveWhysAnalysis)
            .where(
                FiveWhysAnalysis.investigation_id == investigation_id,
                FiveWhysAnalysis.tenant_id.is_(None),
            )
            .order_by(FiveWhysAnalysis.id.desc())
        )
        return result.scalars().first()


__all__ = [
    "RCA_STRING_FIELDS",
    "RCA_TEXT_MAX_LENGTH",
    "WHY_LEVELS",
    "InvestigationRcaService",
    "empty_rca_payload",
    "legacy_why_strings",
    "sync_rca_workspace_fields",
    "workspace_whys",
]
