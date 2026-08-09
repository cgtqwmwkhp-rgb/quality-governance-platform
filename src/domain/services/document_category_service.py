"""Governance Library taxonomy service (Wave W0, revised WA-2).

Two responsibilities:

1. Idempotent seed/reseed of `document_categories`, `document_functions` and
   `document_tags` from `specs/governance-library/taxonomy.json` +
   `functions.json` (via `document_category_seed_data`). Safe to call
   repeatedly — upserts by natural key (`taxonomy_id` / `code` / `slug`),
   never duplicates, and always re-applies the Wave W0 deactivation list on
   reseed.
2. Atomic PEL doc-ref allocation (`PEL-<FUNCTION>-<SEQ>`, ADR-0023) via a
   single `UPDATE ... RETURNING` on `pel_doc_ref_counters`, so concurrent
   document creates under the same function can never collide.

WA-2 moved the counter from the category to the function: the category
classifies, the reference identifies. There is exactly one allocator — the
retired `PEL-<SECTION>-<SUB>-<SEQ>` form is not issued anywhere, and
references already issued under it are kept verbatim and never rewritten.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.exceptions import NotFoundError, ValidationError
from src.domain.models.document_library import DocumentCategory, DocumentFunction, DocumentTag, PelDocRefCounter
from src.domain.services.document_category_seed_data import (
    EXPECTED_CATEGORY_COUNT,
    EXPECTED_FUNCTION_COUNT,
    TAG_SEED,
    load_library_functions,
    load_taxonomy_categories,
)

# Four digits because HSEQ holds 226 documents on day one (ADR-0023). The width
# is a floor, not a ceiling: allocation 10_000 formats as `PEL-HSEQ-10000`
# rather than truncating or wrapping, so the sequence never re-issues a
# reference just because it outgrew its padding.
PEL_SEQ_WIDTH = 4


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

    # PEL counters — one per function, seeded once and never reset (resetting
    # an existing counter would re-issue a PEL ref that is already printed on a
    # document and cited in a client audit pack).
    counters_created = 0
    function_ids = [f.id for f in existing_functions_by_code.values()]
    if function_ids:
        existing_counters = await db.execute(
            select(PelDocRefCounter.function_id).where(PelDocRefCounter.function_id.in_(function_ids))
        )
        existing_counter_ids = {row[0] for row in existing_counters.all()}
        for function_id in function_ids:
            if function_id not in existing_counter_ids:
                db.add(PelDocRefCounter(function_id=function_id, next_seq=1))
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


async def allocate_pel_doc_ref(db: AsyncSession, function_id: int) -> str:
    """Atomically allocate the next `PEL-<FUNCTION>-<SEQ>` for a function (ADR-0023).

    Single `UPDATE ... RETURNING` statement — the increment and the read of
    the pre-increment value happen in one round trip, so two concurrent
    callers allocating for the same function are guaranteed distinct sequence
    numbers even though neither takes an explicit row lock first. Raises
    `NotFoundError` if the function doesn't exist or has no counter row (i.e.
    is not a seeded function); `ValidationError` if it is inactive.

    The increment is transactional, so a rolled-back create releases the
    number rather than burning it. The flip side is that the counter row stays
    locked for the rest of the caller's transaction, which in the upload paths
    spans the blob-storage write: concurrent allocations for the *same*
    function serialise behind it. That was equally true of the Wave W0
    per-category counter, but WA-2 concentrates it, because HSEQ is expected to
    carry ~73% of the estate where the old scheme spread the same traffic over
    73 category counters. If that contention ever bites, the fix is to allocate
    after the storage write rather than before it (the reference may be set on
    an already-created row — NULL to value is permitted), not to weaken the
    atomicity here.
    """
    function = await db.get(DocumentFunction, function_id)
    if function is None:
        raise NotFoundError(f"Document function {function_id} not found")
    if not function.active:
        raise ValidationError(f"Function '{function.code}' is inactive and cannot accept new documents")

    stmt = (
        update(PelDocRefCounter)
        .where(PelDocRefCounter.function_id == function_id)
        .values(next_seq=PelDocRefCounter.next_seq + 1)
        .returning(PelDocRefCounter.next_seq)
    )
    result = await db.execute(stmt)
    row = result.first()
    if row is None:
        raise NotFoundError(f"No PEL doc-ref counter seeded for function {function_id}")

    allocated_seq = row[0] - 1
    return f"PEL-{function.code}-{allocated_seq:0{PEL_SEQ_WIDTH}d}"
