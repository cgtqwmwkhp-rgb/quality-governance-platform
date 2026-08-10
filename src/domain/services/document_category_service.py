"""Governance Library taxonomy service (Wave W0, revised WA-2).

Two responsibilities:

1. Idempotent seed/reseed of `document_categories`, `document_functions` and
   `document_tags` from `specs/governance-library/taxonomy.json` +
   `functions.json` (via `document_category_seed_data`). Safe to call
   repeatedly — upserts by natural key (`taxonomy_id` / `code` / `slug`),
   never duplicates, and always re-applies the Wave W0 deactivation list on
   reseed.
2. Atomic PEL doc-ref allocation (`PEL-<FUNCTION>-<BAND><SEQ>`, ADR-0023 as
   amended by Northern Star v6) via a single `UPDATE ... RETURNING` on
   `pel_doc_ref_counters`, so concurrent document creates in the same
   (function, band) can never collide.

WA-2 moved the counter from the category to the function: the category
classifies, the reference identifies. NS-1 then bands the sequence by cascade
level, so the reference also *positions* the document in the cascade:
`PEL-IT-2014` is IT's 14th Policy. There is exactly one allocator — the
retired `PEL-<SECTION>-<SUB>-<SEQ>` and unbanded `PEL-<FUNCTION>-0###` forms
are not issued anywhere, and references already issued under them are kept
verbatim and never rewritten (R29: allocation is append-only, nothing is ever
renumbered).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.exceptions import NotFoundError, ValidationError
from src.domain.models.document_library import (
    CASCADE_LEVEL_MAX,
    CASCADE_LEVEL_MIN,
    CASCADE_LEVELS,
    PEL_BAND_CAPACITY,
    PEL_BAND_SEQ_WIDTH,
    DocumentCategory,
    DocumentFunction,
    DocumentTag,
    PelDocRefCounter,
)
from src.domain.services.document_category_seed_data import (
    EXPECTED_CATEGORY_COUNT,
    EXPECTED_FUNCTION_COUNT,
    TAG_SEED,
    load_library_functions,
    load_taxonomy_categories,
)
from src.domain.services.library_rules import assert_pel_identity


@dataclass
class CategorySeedResult:
    """Outcome of a `seed_document_categories` run — used by tests and the admin reseed endpoint."""

    categories_created: int
    categories_updated: int
    functions_created: int
    functions_updated: int
    tags_created: int
    tags_updated: int
    counters_created: int
    total_categories: int
    total_functions: int
    total_tags: int


def _machine_readable_retention(row: dict[str, Any]) -> dict[str, Any]:
    """The category's retention columns, as already projected by the seed loader.

    ``load_taxonomy_categories`` builds these two keys through
    ``library_steward_retention.resolve_category_retention`` — accepted steward
    decision first, CUT-1 prose grammar second — so this reads them off the row
    rather than deriving a second opinion. Deriving here as well is how the seed
    came to overwrite steward decisions in the first place.
    """
    return {
        "retention_years": row["retention_years"],
        "retention_anchor": row["retention_anchor"],
    }


async def seed_document_categories(db: AsyncSession) -> CategorySeedResult:
    """Idempotently upsert the taxonomy category tree, tag vocabulary, and PEL counters.

    Running this twice (or a hundred times) always converges on the same
    `EXPECTED_CATEGORY_COUNT` (86) category rows and never creates
    duplicates — required for CI smoke, redeploys, and the admin "reload
    seed" action to be safe to run at any time.
    """
    rows = load_taxonomy_categories()

    existing_result = await db.execute(select(DocumentCategory))
    existing_by_taxonomy_id = {c.taxonomy_id: c for c in existing_result.scalars().all()}

    categories_created = 0
    categories_updated = 0

    # Pass 1: create/update level-1 sections first so level-2 parent_id FKs resolve.
    for level in (1, 2):
        for row in rows:
            if row["level"] != level:
                continue
            existing = existing_by_taxonomy_id.get(row["taxonomy_id"])
            parent_taxonomy_id = row["parent_taxonomy_id"]
            parent = existing_by_taxonomy_id.get(parent_taxonomy_id) if parent_taxonomy_id else None

            if existing is None:
                created = DocumentCategory(
                    taxonomy_id=row["taxonomy_id"],
                    parent_id=parent.id if parent else None,
                    level=row["level"],
                    sort_order=row["sort_order"],
                    name=row["name"],
                    slug=row["slug"],
                    ref_prefix=row["ref_prefix"],
                    description=row["description"],
                    default_access=row["default_access"],
                    access_note=row["access_note"],
                    suggested_owner_role=row["suggested_owner_role"],
                    review_cycle=row["review_cycle"],
                    retention_rule=row["retention_rule"],
                    typical_contents=row["typical_contents"],
                    active=row["active"],
                    **_machine_readable_retention(row),
                )
                db.add(created)
                await db.flush()
                existing_by_taxonomy_id[row["taxonomy_id"]] = created
                categories_created += 1
            else:
                existing.parent_id = parent.id if parent else existing.parent_id
                existing.level = row["level"]
                existing.sort_order = row["sort_order"]
                existing.name = row["name"]
                existing.slug = row["slug"]
                existing.ref_prefix = row["ref_prefix"]
                existing.description = row["description"]
                existing.default_access = row["default_access"]
                existing.access_note = row["access_note"]
                existing.suggested_owner_role = row["suggested_owner_role"]
                existing.review_cycle = row["review_cycle"]
                existing.retention_rule = row["retention_rule"]
                # Reasserted from the seed on every run, exactly like `active`
                # below. Before STEWARD-14 that reassertion was destructive,
                # because the seed could only re-derive from prose and so wiped a
                # steward's resolution of a blocker on the next reseed, redeploy
                # or admin "reload seed". The decision is now part of the seed
                # (`specs/governance-library/steward_retention_decisions.json`),
                # so reasserting it restores the decision instead of erasing it —
                # and the decision file, not an untraceable database edit, is the
                # one place a category's retention override lives.
                for column, value in _machine_readable_retention(row).items():
                    setattr(existing, column, value)
                existing.typical_contents = row["typical_contents"]
                # Wave W0 deactivation list always wins on reseed, even if a
                # prior manual edit reactivated the category.
                existing.active = row["active"]
                categories_updated += 1

    await db.flush()

    # Functions (WA-2 / ADR-0023) — upsert by `code`, which is the literal
    # prefix segment of every reference the function issues, so it is never
    # rewritten by a reseed even if functions.json changes the display name.
    function_rows = load_library_functions()
    existing_functions_result = await db.execute(select(DocumentFunction))
    existing_functions_by_code = {f.code: f for f in existing_functions_result.scalars().all()}
    functions_created = 0
    functions_updated = 0
    for function_row in function_rows:
        existing_function = existing_functions_by_code.get(function_row["code"])
        if existing_function is None:
            created_function = DocumentFunction(
                code=function_row["code"],
                name=function_row["name"],
                description=function_row["description"],
                sort_order=function_row["sort_order"],
                active=function_row["active"],
            )
            db.add(created_function)
            await db.flush()
            existing_functions_by_code[function_row["code"]] = created_function
            functions_created += 1
        else:
            existing_function.name = function_row["name"]
            existing_function.description = function_row["description"]
            existing_function.sort_order = function_row["sort_order"]
            existing_function.active = function_row["active"]
            functions_updated += 1

    await db.flush()

    total_functions = len(existing_functions_by_code)
    if total_functions != EXPECTED_FUNCTION_COUNT:
        raise ValidationError(
            f"Governance Library function seed produced {total_functions} functions, "
            f"expected {EXPECTED_FUNCTION_COUNT}. Check specs/governance-library/functions.json."
        )

    # PEL counters — one per function *per cascade band* (NS-1), seeded once and
    # never reset (resetting an existing counter would re-issue a PEL ref that
    # is already printed on a document and cited in a client audit pack). All
    # five bands are seeded up front rather than lazily on first use, so
    # allocation is a plain UPDATE that never has to race to create its own row.
    counters_created = 0
    function_ids = [f.id for f in existing_functions_by_code.values()]
    if function_ids:
        existing_counters = await db.execute(
            select(PelDocRefCounter.function_id, PelDocRefCounter.level_band).where(
                PelDocRefCounter.function_id.in_(function_ids)
            )
        )
        existing_counter_keys = {(row[0], row[1]) for row in existing_counters.all()}
        for function_id in function_ids:
            for band in CASCADE_LEVELS:
                if (function_id, band) not in existing_counter_keys:
                    db.add(PelDocRefCounter(function_id=function_id, level_band=band, next_seq=1))
                    counters_created += 1

    # Tag vocabulary — upsert by slug.
    existing_tags_result = await db.execute(select(DocumentTag))
    existing_tags_by_slug = {t.slug: t for t in existing_tags_result.scalars().all()}
    tags_created = 0
    tags_updated = 0
    for tag_row in TAG_SEED:
        existing_tag = existing_tags_by_slug.get(tag_row["slug"])
        if existing_tag is None:
            db.add(DocumentTag(slug=tag_row["slug"], label=tag_row["label"], group=tag_row["group"], active=True))
            tags_created += 1
        else:
            existing_tag.label = tag_row["label"]
            existing_tag.group = tag_row["group"]
            existing_tag.active = True
            tags_updated += 1

    await db.flush()

    total_categories = len(existing_by_taxonomy_id)
    if total_categories != EXPECTED_CATEGORY_COUNT:
        raise ValidationError(
            f"Governance Library taxonomy seed produced {total_categories} categories, "
            f"expected {EXPECTED_CATEGORY_COUNT}. Check specs/governance-library/taxonomy.json."
        )

    return CategorySeedResult(
        categories_created=categories_created,
        categories_updated=categories_updated,
        functions_created=functions_created,
        functions_updated=functions_updated,
        tags_created=tags_created,
        tags_updated=tags_updated,
        counters_created=counters_created,
        total_categories=total_categories,
        total_functions=total_functions,
        total_tags=len(TAG_SEED),
    )


async def resolve_function_code(db: AsyncSession, function_code: Optional[str]) -> Optional[DocumentFunction]:
    """Look up an active `DocumentFunction` by code, or return None for no code.

    Returns None only when the caller supplied no code at all — a document may
    legitimately be filed before its function is confirmed, and no PEL
    reference is allocated in that case. An unrecognised or inactive code is a
    `ValidationError`, never a silent fall-through to "no function": guessing
    would print a wrong, immutable reference on the document (ADR-0023).
    """
    if function_code is None:
        return None
    code = function_code.strip().upper()
    if not code:
        return None

    result = await db.execute(select(DocumentFunction).where(DocumentFunction.code == code))
    function = result.scalar_one_or_none()
    if function is None:
        raise ValidationError(f"Unknown document function code '{function_code}'")
    if not function.active:
        raise ValidationError(f"Function '{function.code}' is inactive and cannot accept new documents")
    return function


def coerce_cascade_level(cascade_level: object, *, field: str = "cascade_level") -> int:
    """Coerce and range-check a caller-supplied cascade level, or raise.

    Accepts an `int`, or the digit strings that arrive from multipart form
    fields. Everything else is refused, including `None` and floats: `int(2.5)`
    is 2, and silently rounding a level would band an immutable reference one
    tier away from where the caller pointed. There is deliberately no default
    level either — guessing one prints a reference in a band nobody chose, and
    the band is the part of the reference that says where the document sits in
    the cascade.
    """
    bad = ValidationError(
        f"{field} must be a cascade level {CASCADE_LEVEL_MIN}-{CASCADE_LEVEL_MAX} "
        f"(1 Manual, 2 Policy, 3 Procedure/Standard, 4 SOP/RAMS/Assessment, "
        f"5 Form/Register/Record), got {cascade_level!r}"
    )
    if isinstance(cascade_level, bool) or cascade_level is None:
        raise bad
    if isinstance(cascade_level, int):
        level = cascade_level
    elif isinstance(cascade_level, str):
        text = cascade_level.strip()
        if not text.isdigit():
            raise bad
        level = int(text)
    else:
        raise bad
    if level not in CASCADE_LEVELS:
        raise bad
    return level


async def allocate_pel_doc_ref(db: AsyncSession, function_id: int, cascade_level: int) -> str:
    """Atomically allocate the next `PEL-<FUNCTION>-<BAND><SEQ>` in one band (NS-1).

    `cascade_level` is required, has no default, and *is* the band digit: level
    3 allocates `PEL-HSEQ-3001`, `PEL-HSEQ-3002`, ... So rule R02 ("the first
    digit of the sequence equals the cascade level") holds because there is no
    way to express a reference that breaks it — the caller cannot pass a band
    and a level separately and get them out of step.

    Single `UPDATE ... RETURNING` statement — the increment and the read of
    the pre-increment value happen in one round trip, so two concurrent
    callers allocating in the same (function, band) are guaranteed distinct
    sequence numbers even though neither takes an explicit row lock first, and
    the number always moves forward (R29: append-only, never gap-filled, never
    renumbered — a rolled-back create leaves a hole rather than handing the
    number to the next caller). Raises `NotFoundError` if the function doesn't
    exist or that band has no counter row (i.e. is not a seeded function);
    `ValidationError` if the function is inactive or the level is out of range.

    Banding also relieves the contention WA-2 concentrated. The increment is
    transactional, so the counter row stays locked for the rest of the caller's
    transaction, which in the upload paths spans the blob-storage write. Under
    WA-2 every HSEQ upload serialised behind one row — and HSEQ is expected to
    carry ~73% of the estate. That queue is now split five ways, because an
    HSEQ form and an HSEQ procedure touch different rows. If it still bites,
    the fix is to allocate after the storage write rather than before it (the
    reference may be set on an already-created row — NULL to value is
    permitted), not to weaken the atomicity here.
    """
    band = coerce_cascade_level(cascade_level)

    function = await db.get(DocumentFunction, function_id)
    if function is None:
        raise NotFoundError(f"Document function {function_id} not found")
    if not function.active:
        raise ValidationError(f"Function '{function.code}' is inactive and cannot accept new documents")

    stmt = (
        update(PelDocRefCounter)
        .where(PelDocRefCounter.function_id == function_id, PelDocRefCounter.level_band == band)
        .values(next_seq=PelDocRefCounter.next_seq + 1)
        .returning(PelDocRefCounter.next_seq)
    )
    result = await db.execute(stmt)
    row = result.first()
    if row is None:
        raise NotFoundError(f"No PEL doc-ref counter seeded for function {function_id} band {band}")

    allocated_seq = row[0] - 1
    if allocated_seq > PEL_BAND_CAPACITY:
        # A band holds 999. Widening the sequence (the pre-NS-1 behaviour) would
        # emit `PEL-HSEQ-31000`, which fails R01, and narrowing/wrapping would
        # re-issue a live reference, which fails R06. Neither is available, so
        # the only honest move is to refuse and let a human amend the scheme.
        # The counter is left advanced on purpose: every subsequent attempt in
        # this band must fail the same way rather than quietly finding a hole.
        raise ValidationError(
            f"Band {band} of function '{function.code}' is exhausted at "
            f"{PEL_BAND_CAPACITY} references (R01 fixes the sequence at "
            f"{PEL_BAND_SEQ_WIDTH} digits after the band digit). The reference "
            "scheme has to be amended before this document can be filed; "
            "numbers are never re-used or renumbered (R06/R29)."
        )
    pel_doc_ref = f"PEL-{function.code}-{band}{allocated_seq:0{PEL_BAND_SEQ_WIDTH}d}"
    # W4 / NS-RULE-A: identity hard-block — the allocator constructs the ref, so
    # this is a belt-and-braces assert that R01–R03 hold by construction.
    assert_pel_identity(pel_doc_ref, function_code=function.code, cascade_level=band)
    return pel_doc_ref
