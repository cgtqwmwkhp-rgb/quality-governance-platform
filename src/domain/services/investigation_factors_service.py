"""ICAM contributing factors for an investigation run (INV-C12 / DEC-1).

Four jobs, in the order that hurts if they drift:

1. **Own the factors** for one run on the existing ``fishbone_diagrams`` table
   — one tenant-scoped diagram per run, each factor a cause under one of the
   four ICAM categories, carrying its optional sub-causes and its HSG245
   causal depth. No second table: the diagram's ``causes`` column is already
   JSON keyed by category, and it already holds ``sub_causes``, so the only
   thing it was missing is ``depth`` — a key in a JSON object, not a schema
   change. An additive child table would have been a second store for the
   same fact.
2. **Address a factor by id, not by position.** Each entry carries an ``id``
   unique within the diagram. Two investigators editing the same run must not
   have "the third one under organisational factors" mean different rows.
3. **Keep the legacy readers in step.** Closure and the generated pack still
   read the ``contributing_factors`` string (flat and nested on
   ``investigation_runs.data``) and the RCA workspace still reads the
   ``five_whys_analyses.contributing_factors`` list, until C18. Every factor
   mutation rewrites both from the factors, so a reader that has not moved
   yet sees what is actually stored rather than a stale paragraph.
4. **Say what it cannot present.** A stored cause under a category that is not
   one of the ICAM four, or an entry with no usable text, is left in the JSON
   untouched and *reported* on the list payload rather than silently dropped
   or silently re-categorised.

Fail closed: every query re-filters on ``tenant_id`` even though the caller has
already tenant-checked the run. A missing tenant id, a mismatch, or another
organisation's diagram is "no factors", never a 500 and never a factor that
does not belong to this tenant.

Why ids are assigned lazily rather than backfilled
--------------------------------------------------
A cause written through the generic ``/rca-tools/fishbone`` routes before this
PR has no id. Reading assigns one **in memory**, deterministically (highest
stored id first, then ICAM category order, then stored position), so two reads
of an unchanged diagram agree; the first mutation persists exactly those ids.
Nothing here is a read that writes.
"""

from __future__ import annotations

from typing import Any, Optional, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.investigation import InvestigationRun
from src.domain.models.rca_tools import CausalDepth, FishboneCategory, FishboneDiagram, FiveWhysAnalysis
from src.domain.services.investigation_data_reader import read_investigation_field
from src.domain.services.investigation_rca_service import sync_rca_workspace_fields

#: The four ICAM categories, in the order an investigator works through them and
#: the order the derived paragraph is rendered in. Taken from the enum rather
#: than re-listed, so a change to the taxonomy cannot leave this behind.
ICAM_CATEGORY_ORDER: tuple[FishboneCategory, ...] = (
    FishboneCategory.ORGANISATIONAL,
    FishboneCategory.TASK_ENVIRONMENTAL,
    FishboneCategory.INDIVIDUAL_TEAM,
    FishboneCategory.ABSENT_FAILED_DEFENCES,
)

#: Plain English for the derived paragraph the pack and the closure gate read.
#: Not i18n keys: this text is stored in ``investigation_runs.data`` and printed
#: into a customer pack, so it has to be words rather than a lookup a reader of
#: the JSON cannot resolve.
CATEGORY_LABELS: dict[FishboneCategory, str] = {
    FishboneCategory.ORGANISATIONAL: "Organisational factors",
    FishboneCategory.TASK_ENVIRONMENTAL: "Task and environmental conditions",
    FishboneCategory.INDIVIDUAL_TEAM: "Individual and team actions",
    FishboneCategory.ABSENT_FAILED_DEFENCES: "Absent or failed defences",
}

DEPTH_LABELS: dict[CausalDepth, str] = {
    CausalDepth.IMMEDIATE: "immediate cause",
    CausalDepth.UNDERLYING: "underlying cause",
    CausalDepth.ROOT: "root cause",
}

#: Longest prose one factor may carry. Matches the workspace RCA and finding
#: caps: these are investigator sentences, not documents.
FACTOR_TEXT_MAX_LENGTH = 2000

#: Most sub-causes one factor may carry. ``causes`` is a single JSON column, so
#: an unbounded list is an unbounded row; twenty is far past what the panel
#: shows and well short of a payload that would need paging.
FACTOR_SUB_CAUSES_MAX = 20

_CATEGORY_VALUES: frozenset[str] = frozenset(category.value for category in ICAM_CATEGORY_ORDER)


def _text(value: Any) -> str:
    """Strip for emptiness only. The words themselves are not rewritten."""
    return value.strip() if isinstance(value, str) else ""


def _depth(value: Any) -> Optional[CausalDepth]:
    """A stored depth, or ``None`` for absent/unrecognised. Never guessed."""
    if isinstance(value, CausalDepth):
        return value
    try:
        return CausalDepth(str(value))
    except (TypeError, ValueError):
        return None


def _sub_causes(value: Any) -> list[str]:
    """Stored sub-causes as text. Blank entries are dropped, order is kept."""
    if not isinstance(value, (list, tuple)):
        return []
    return [_text(item) for item in value if _text(item)]


def factor_line(
    category: FishboneCategory,
    cause: str,
    sub_causes: Sequence[str] = (),
    depth: Optional[CausalDepth] = None,
) -> str:
    """Render one factor as the single line the legacy readers will see.

    ``Organisational factors: no refresher schedule (budget withdrawn; no owner
    named) [underlying cause]``.

    A factor with no recorded depth gets no bracket rather than a guessed one,
    and a factor with no sub-causes gets no parentheses. Deterministic, so the
    same factors always render the same paragraph — a pack regenerated twice
    cannot differ.
    """
    line = f"{CATEGORY_LABELS[category]}: {cause}"
    listed = [item for item in sub_causes if item]
    if listed:
        line += f" ({'; '.join(listed)})"
    if depth is not None:
        line += f" [{DEPTH_LABELS[depth]}]"
    return line


def join_factor_lines(lines: Sequence[str]) -> str:
    """One line per factor. An empty list renders as ``""``.

    Not numbered, unlike findings: nothing splits this string back into
    factors, so a number would be decoration that the next reader could mistake
    for the investigator's own ordering.
    """
    return "\n".join(line for line in lines if line)


class InvestigationFactor:
    """One contributing factor as this surface presents it.

    A plain object rather than a row: the store is a JSON entry inside a
    diagram, and pretending otherwise (a fake ORM row with an ``id`` the
    database never issued) is how a later reader ends up believing there is a
    table to join against.
    """

    __slots__ = ("id", "investigation_id", "category", "cause", "sub_causes", "depth", "position")

    def __init__(
        self,
        *,
        id: int,
        investigation_id: int,
        category: FishboneCategory,
        cause: str,
        sub_causes: list[str],
        depth: Optional[CausalDepth],
        position: int = -1,
    ) -> None:
        self.id = id
        self.investigation_id = investigation_id
        self.category = category
        self.cause = cause
        self.sub_causes = sub_causes
        self.depth = depth
        #: Index of this factor inside its category's stored list. Internal to
        #: the mutation path — a client addresses a factor by ``id``, because an
        #: index moves under it the moment anybody else deletes something.
        self.position = position

    def as_payload(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "investigation_id": self.investigation_id,
            "category": self.category.value,
            "cause": self.cause,
            "sub_causes": list(self.sub_causes),
            "depth": self.depth.value if self.depth is not None else None,
        }

    def line(self) -> str:
        return factor_line(self.category, self.cause, self.sub_causes, self.depth)


class FactorSnapshot:
    """Everything the list payload needs, read once."""

    __slots__ = ("diagram_id", "factors", "unmapped_categories", "unreadable_total", "next_id")

    def __init__(
        self,
        *,
        diagram_id: Optional[int],
        factors: list[InvestigationFactor],
        unmapped_categories: list[str],
        unreadable_total: int,
        next_id: int = 1,
    ) -> None:
        self.diagram_id = diagram_id
        self.factors = factors
        self.unmapped_categories = unmapped_categories
        self.unreadable_total = unreadable_total
        #: The id high-water mark after any lazy assignment above. Written back
        #: by the mutation path so a deleted id is never reissued.
        self.next_id = next_id

    @property
    def text(self) -> str:
        return join_factor_lines([factor.line() for factor in self.factors])


def _next_free_id(causes: Any) -> int:
    """The first id this diagram has never issued.

    The stored high-water mark, or highest-stored-plus-one when there is none
    yet, whichever is larger — the same rule
    :meth:`FishboneDiagram.next_cause_id` applies, so the two cannot allocate
    the same id. Categories this surface does not present are included: an id
    is unique across the whole row, not per category.
    """
    highest = 0
    marked = 0
    if not isinstance(causes, dict):
        return 1
    for key, entries in causes.items():
        if key == FishboneDiagram.NEXT_FACTOR_ID_KEY:
            try:
                marked = int(entries or 0)
            except (TypeError, ValueError):
                marked = 0
            continue
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            try:
                value = int(entry.get("id") or 0)
            except (TypeError, ValueError):
                continue
            highest = max(highest, value)
    return max(marked, highest + 1)


def read_factors(causes: Any, *, investigation_id: int) -> FactorSnapshot:
    """Present a diagram's ``causes`` JSON as ordered factors.

    Ordering is ICAM category order, then stored position within a category —
    the order the investigator added them in. Ids missing from the JSON are
    assigned here, deterministically, starting above the highest id already
    stored; :meth:`InvestigationFactorsService._write` persists exactly the same
    assignment on the next mutation.

    Anything this surface cannot present is counted, never rewritten: a cause
    under a non-ICAM key (a diagram from before DEC-1), an entry that is not an
    object, an entry with no usable cause text, and a duplicate id. It stays in
    the JSON.
    """
    factors: list[InvestigationFactor] = []
    unmapped: list[str] = []
    unreadable = 0
    next_id = _next_free_id(causes)
    taken: set[int] = set()

    stored = causes if isinstance(causes, dict) else {}
    for key, entries in stored.items():
        if str(key) in _CATEGORY_VALUES or key == FishboneDiagram.NEXT_FACTOR_ID_KEY:
            continue
        count = len([entry for entry in entries if entry]) if isinstance(entries, list) else 0
        if count:
            unmapped.append(str(key))
            unreadable += count

    for category in ICAM_CATEGORY_ORDER:
        entries = stored.get(category.value)
        if not isinstance(entries, list):
            continue
        for position, entry in enumerate(entries):
            if not isinstance(entry, dict):
                unreadable += 1
                continue
            cause = _text(entry.get("cause"))
            if not cause:
                unreadable += 1
                continue
            try:
                factor_id = int(entry.get("id") or 0)
            except (TypeError, ValueError):
                factor_id = 0
            if factor_id <= 0 or factor_id in taken:
                factor_id = next_id
                next_id += 1
            taken.add(factor_id)
            factors.append(
                InvestigationFactor(
                    id=factor_id,
                    investigation_id=investigation_id,
                    category=category,
                    cause=cause,
                    sub_causes=_sub_causes(entry.get("sub_causes")),
                    depth=_depth(entry.get("depth")),
                    position=position,
                )
            )

    return FactorSnapshot(
        diagram_id=None,
        factors=factors,
        unmapped_categories=sorted(unmapped),
        unreadable_total=unreadable,
        next_id=next_id,
    )


class InvestigationFactorsService:
    """One run's ICAM contributing factors, plus the dual-write to legacy readers.

    None of these commit: the route owns the transaction, so a failed JSON sync
    and a successful factor write cannot land separately.
    """

    @staticmethod
    def _tenants_match(investigation: Any, tenant_id: int) -> bool:
        record_tenant = getattr(investigation, "tenant_id", None)
        investigation_id = getattr(investigation, "id", None)
        if investigation_id is None or record_tenant is None:
            return False
        try:
            return int(record_tenant) == int(tenant_id)
        except (TypeError, ValueError):
            return False

    @staticmethod
    async def snapshot(
        db: AsyncSession,
        *,
        investigation: InvestigationRun,
        tenant_id: int,
    ) -> FactorSnapshot:
        """The run's factors, in order. No diagram is an empty list, not a 404."""
        investigation_id = int(getattr(investigation, "id", 0) or 0)
        if not InvestigationFactorsService._tenants_match(investigation, tenant_id):
            return FactorSnapshot(diagram_id=None, factors=[], unmapped_categories=[], unreadable_total=0)
        diagram = await InvestigationFactorsService._load(
            db, investigation_id=investigation_id, tenant_id=int(tenant_id)
        )
        if diagram is None:
            return FactorSnapshot(diagram_id=None, factors=[], unmapped_categories=[], unreadable_total=0)
        snapshot = read_factors(diagram.causes, investigation_id=investigation_id)
        snapshot.diagram_id = int(diagram.id) if diagram.id is not None else None
        return snapshot

    @staticmethod
    async def create_factor(
        db: AsyncSession,
        *,
        investigation: InvestigationRun,
        tenant_id: int,
        category: FishboneCategory,
        cause: str,
        sub_causes: Sequence[str] = (),
        depth: Optional[CausalDepth] = None,
        actor_id: Optional[int] = None,
    ) -> Optional[InvestigationFactor]:
        """Add one factor under one ICAM category.

        Creates the run's diagram on first use. ``None`` when the tenant does
        not match — fail closed, no write.
        """
        text = _text(cause)
        if not text:
            # The route refuses blank text at the schema (422). Refusing again
            # here means no other caller can create a factor with no words.
            return None
        if not InvestigationFactorsService._tenants_match(investigation, tenant_id):
            return None

        diagram = await InvestigationFactorsService._ensure_diagram(
            db, investigation=investigation, tenant_id=int(tenant_id), actor_id=actor_id
        )
        # Materialise any id this surface has only ever shown from memory before
        # allocating a new one, so ``next_cause_id`` cannot hand out an id a
        # client is already holding for a pre-INV-C12 cause.
        causes, _ = InvestigationFactorsService._normalised(diagram, 0)
        diagram.causes = causes
        entry = diagram.add_cause(category, text, list(_sub_causes(sub_causes)), depth)
        diagram.updated_by_id = actor_id
        await db.flush()
        await InvestigationFactorsService._resync(
            db, investigation=investigation, tenant_id=int(tenant_id), diagram=diagram
        )
        return InvestigationFactor(
            id=int(entry["id"]),
            investigation_id=int(investigation.id),
            category=category,
            cause=text,
            sub_causes=list(entry.get("sub_causes") or []),
            depth=depth,
        )

    @staticmethod
    async def update_factor(
        db: AsyncSession,
        *,
        investigation: InvestigationRun,
        tenant_id: int,
        factor_id: int,
        category: Optional[FishboneCategory] = None,
        cause: Optional[str] = None,
        sub_causes: Optional[Sequence[str]] = None,
        depth: Optional[CausalDepth] = None,
        clear_depth: bool = False,
        actor_id: Optional[int] = None,
    ) -> Optional[InvestigationFactor]:
        """Rewrite one factor. ``None`` when it is not this run's, or not this tenant's.

        Every argument left as ``None`` is left alone, so a caller editing the
        text cannot blank a depth it never sent. ``clear_depth`` is the explicit
        way to say "no depth recorded" — distinguishable from "not mentioned",
        which is why it is a separate flag rather than an empty string.

        Changing ``category`` moves the factor between ICAM categories and keeps
        its id: it is the same factor, re-classified.
        """
        if not InvestigationFactorsService._tenants_match(investigation, tenant_id):
            return None
        if cause is not None and not _text(cause):
            return None

        diagram = await InvestigationFactorsService._locked_diagram(
            db, investigation=investigation, tenant_id=int(tenant_id)
        )
        if diagram is None:
            return None

        causes, located = InvestigationFactorsService._normalised(diagram, factor_id)
        if located is None:
            return None
        source_category, index = located
        entry = dict(causes[source_category.value][index])

        if cause is not None:
            entry["cause"] = _text(cause)
        if sub_causes is not None:
            entry["sub_causes"] = list(_sub_causes(sub_causes))
        if clear_depth:
            entry.pop("depth", None)
        elif depth is not None:
            entry["depth"] = depth.value

        target_category = category or source_category
        if target_category is source_category:
            causes[source_category.value][index] = entry
        else:
            del causes[source_category.value][index]
            causes.setdefault(target_category.value, []).append(entry)

        diagram.causes = causes
        diagram.updated_by_id = actor_id
        await db.flush()
        await InvestigationFactorsService._resync(
            db, investigation=investigation, tenant_id=int(tenant_id), diagram=diagram
        )
        return InvestigationFactor(
            id=int(entry["id"]),
            investigation_id=int(investigation.id),
            category=target_category,
            cause=_text(entry.get("cause")),
            sub_causes=_sub_causes(entry.get("sub_causes")),
            depth=_depth(entry.get("depth")),
        )

    @staticmethod
    async def delete_factor(
        db: AsyncSession,
        *,
        investigation: InvestigationRun,
        tenant_id: int,
        factor_id: int,
        actor_id: Optional[int] = None,
    ) -> bool:
        """Remove one factor. Deleting the last one leaves a valid empty list."""
        if not InvestigationFactorsService._tenants_match(investigation, tenant_id):
            return False

        diagram = await InvestigationFactorsService._locked_diagram(
            db, investigation=investigation, tenant_id=int(tenant_id)
        )
        if diagram is None:
            return False

        causes, located = InvestigationFactorsService._normalised(diagram, factor_id)
        if located is None:
            return False
        category, index = located
        del causes[category.value][index]

        diagram.causes = causes
        diagram.updated_by_id = actor_id
        await db.flush()
        await InvestigationFactorsService._resync(
            db, investigation=investigation, tenant_id=int(tenant_id), diagram=diagram
        )
        return True

    # -- internals -----------------------------------------------------------

    @staticmethod
    def _normalised(
        diagram: FishboneDiagram, factor_id: int
    ) -> tuple[dict[str, Any], Optional[tuple[FishboneCategory, int]]]:
        """A writable copy of ``causes`` with ids materialised, plus where the factor is.

        The copy carries every stored key — including categories this surface
        does not present and entries it cannot read — so a mutation never drops
        what it did not understand. Only the ICAM lists are rebuilt, and only to
        write in the ids :func:`read_factors` already showed the client.
        """
        stored = diagram.causes if isinstance(diagram.causes, dict) else {}
        causes: dict[str, Any] = {
            str(key): (list(value) if isinstance(value, list) else value) for key, value in stored.items()
        }

        snapshot = read_factors(stored, investigation_id=int(diagram.investigation_id or 0))
        located: Optional[tuple[FishboneCategory, int]] = None
        for factor in snapshot.factors:
            entries = causes.get(factor.category.value)
            if not isinstance(entries, list):
                continue
            entries[factor.position] = {**entries[factor.position], "id": factor.id}
            if factor.id == int(factor_id):
                located = (factor.category, factor.position)
        # Move the mark forward with any id assigned above, so the next add
        # cannot reissue one this read has already shown a client.
        causes[FishboneDiagram.NEXT_FACTOR_ID_KEY] = snapshot.next_id
        return causes, located

    @staticmethod
    async def _ensure_diagram(
        db: AsyncSession,
        *,
        investigation: InvestigationRun,
        tenant_id: int,
        actor_id: Optional[int],
    ) -> FishboneDiagram:
        """This run's diagram, created on first factor.

        The run row is locked first, so two concurrent first-adds cannot both
        decide there is no diagram and create one each. SQLite ignores
        ``FOR UPDATE``; there the guard is the single writer the database
        already enforces.

        ``effect_statement`` is NOT NULL, and the effect a fishbone hangs off is
        the problem the investigator already stated. It is copied from the run's
        ``problem_statement`` when there is one and left empty when there is not
        — an unstated effect reads as unstated, not as the run's title standing
        in for one nobody wrote.
        """
        investigation_id = int(investigation.id)
        await db.execute(select(InvestigationRun.id).where(InvestigationRun.id == investigation_id).with_for_update())
        existing = await InvestigationFactorsService._load(db, investigation_id=investigation_id, tenant_id=tenant_id)
        if existing is not None:
            return existing

        diagram = FishboneDiagram(
            tenant_id=tenant_id,
            investigation_id=investigation_id,
            entity_type=_entity_type(investigation),
            entity_id=getattr(investigation, "assigned_entity_id", None),
            effect_statement=_text(read_investigation_field(investigation.data, "problem_statement")),
            causes={category.value: [] for category in ICAM_CATEGORY_ORDER},
            created_by_id=actor_id,
            updated_by_id=actor_id,
        )
        db.add(diagram)
        await db.flush()
        return diagram

    @staticmethod
    async def _locked_diagram(
        db: AsyncSession,
        *,
        investigation: InvestigationRun,
        tenant_id: int,
    ) -> Optional[FishboneDiagram]:
        """This run's diagram under a row lock on the run.

        Every mutation reads the whole ``causes`` object, changes one entry and
        writes the whole object back, so two concurrent edits without this would
        be a lost update — the second write would carry the first one's stale
        copy of every other factor.
        """
        investigation_id = int(investigation.id)
        await db.execute(select(InvestigationRun.id).where(InvestigationRun.id == investigation_id).with_for_update())
        return await InvestigationFactorsService._load(db, investigation_id=investigation_id, tenant_id=tenant_id)

    @staticmethod
    async def _resync(
        db: AsyncSession,
        *,
        investigation: InvestigationRun,
        tenant_id: int,
        diagram: FishboneDiagram,
    ) -> str:
        """Rewrite the legacy contributing-factors readers from the factors.

        Two of them, both still read until C18:

        * ``five_whys_analyses.contributing_factors`` — a list of strings, one
          per factor, on this run's analysis when it has one. No analysis is
          created here: an ICAM factor is not a 5-Whys document, and inventing
          an empty one so there is somewhere to mirror to would put a blank RCA
          on every run that ever named a factor.
        * ``investigation_runs.data.contributing_factors`` — flat and nested,
          through the same C10 writer the RCA workspace uses, so the two cannot
          write the two shapes differently.

        An empty factor list clears both. "Every factor was deleted" and "there
        were never any" read the same to the gate, which is the honest answer:
        both are no recorded contributing factors.
        """
        snapshot = read_factors(diagram.causes, investigation_id=int(investigation.id))
        lines = [factor.line() for factor in snapshot.factors]
        text = join_factor_lines(lines)

        analysis = await InvestigationFactorsService._analysis(
            db, investigation_id=int(investigation.id), tenant_id=tenant_id
        )
        if analysis is not None:
            analysis.contributing_factors = lines

        blob: Any = investigation.data
        if not isinstance(blob, dict):
            if not text:
                return text
            blob = {}
        # Reassigned, never mutated in place: ``data`` is a plain JSON column
        # with no mutation tracking, so an in-place edit would not be persisted.
        investigation.data = sync_rca_workspace_fields(blob, {"contributing_factors": text})
        return text

    @staticmethod
    async def _load(
        db: AsyncSession,
        *,
        investigation_id: int,
        tenant_id: int,
    ) -> Optional[FishboneDiagram]:
        result = await db.execute(
            select(FishboneDiagram)
            .where(
                FishboneDiagram.investigation_id == investigation_id,
                FishboneDiagram.tenant_id == tenant_id,
            )
            .order_by(FishboneDiagram.id.asc())
        )
        return result.scalars().first()

    @staticmethod
    async def _analysis(
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


def _entity_type(investigation: InvestigationRun) -> Optional[str]:
    value = getattr(investigation, "assigned_entity_type", None)
    if value is None:
        return None
    return value.value if hasattr(value, "value") else str(value)


__all__ = [
    "CATEGORY_LABELS",
    "DEPTH_LABELS",
    "FACTOR_SUB_CAUSES_MAX",
    "FACTOR_TEXT_MAX_LENGTH",
    "ICAM_CATEGORY_ORDER",
    "FactorSnapshot",
    "InvestigationFactor",
    "InvestigationFactorsService",
    "factor_line",
    "join_factor_lines",
    "read_factors",
]
