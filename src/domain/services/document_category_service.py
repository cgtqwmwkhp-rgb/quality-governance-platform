"""Governance Library taxonomy service (Wave W0).

Two responsibilities:

1. Idempotent seed/reseed of `document_categories` + `document_tags` from
   `specs/governance-library/taxonomy.json` (via
   `document_category_seed_data`). Safe to call repeatedly — upserts by
   natural key (`taxonomy_id` / `slug`), never duplicates, and always
   re-applies the Wave W0 deactivation list on reseed.
2. Atomic PEL doc-ref allocation (`PEL-<SECTION>-<SUB>-<SEQ>`) via a single
   `UPDATE ... RETURNING` on `pel_doc_ref_counters`, so concurrent document
   creates under the same category can never collide.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.exceptions import NotFoundError, ValidationError
from src.domain.models.document_library import DocumentCategory, DocumentTag, PelDocRefCounter
from src.domain.services.document_category_seed_data import (
    EXPECTED_CATEGORY_COUNT,
    TAG_SEED,
    load_taxonomy_categories,
)


@dataclass
class CategorySeedResult:
    """Outcome of a `seed_document_categories` run — used by tests and the admin reseed endpoint."""

    categories_created: int
    categories_updated: int
    tags_created: int
    tags_updated: int
    counters_created: int
    total_categories: int
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

    # PEL counters — one per level-2 category, seeded once and never reset
    # (resetting an existing counter would risk re-issuing a PEL ref).
    counters_created = 0
    level2_ids = [c.id for c in existing_by_taxonomy_id.values() if c.level == 2]
    if level2_ids:
        existing_counters = await db.execute(
            select(PelDocRefCounter.category_id).where(PelDocRefCounter.category_id.in_(level2_ids))
        )
        existing_counter_ids = {row[0] for row in existing_counters.all()}
        for category_id in level2_ids:
            if category_id not in existing_counter_ids:
                db.add(PelDocRefCounter(category_id=category_id, next_seq=1))
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
        tags_created=tags_created,
        tags_updated=tags_updated,
        counters_created=counters_created,
        total_categories=total_categories,
        total_tags=len(TAG_SEED),
    )


async def allocate_pel_doc_ref(db: AsyncSession, category_id: int) -> str:
    """Atomically allocate the next `PEL-<SECTION>-<SUB>-<SEQ>` for a level-2 category.

    Single `UPDATE ... RETURNING` statement — the increment and the read of
    the pre-increment value happen in one round trip, so two concurrent
    callers allocating for the same category are guaranteed distinct,
    gapless-from-each-caller's-perspective sequence numbers even though
    neither takes an explicit row lock first. Raises `NotFoundError` if the
    category doesn't exist or has no counter row (i.e. is not a seeded
    level-2 category); `ValidationError` if it is not level 2 or is
    inactive (matches access-policy.md's create-time category_id rule).
    """
    category = await db.get(DocumentCategory, category_id)
    if category is None:
        raise NotFoundError(f"Document category {category_id} not found")
    if category.level != 2:
        raise ValidationError("PEL doc-ref allocation requires a level-2 (subcategory) category")
    if not category.active:
        raise ValidationError(f"Category '{category.name}' is inactive and cannot accept new documents")

    stmt = (
        update(PelDocRefCounter)
        .where(PelDocRefCounter.category_id == category_id)
        .values(next_seq=PelDocRefCounter.next_seq + 1)
        .returning(PelDocRefCounter.next_seq)
    )
    result = await db.execute(stmt)
    row = result.first()
    if row is None:
        raise NotFoundError(f"No PEL doc-ref counter seeded for category {category_id}")

    allocated_seq = row[0] - 1
    return f"{category.ref_prefix}-{allocated_seq:03d}"
