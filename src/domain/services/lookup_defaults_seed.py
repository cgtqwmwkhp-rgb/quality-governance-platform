"""Idempotent seed of UK lookup defaults for unconfigured tenants (Run021 GROUP 1).

Safe to call from Alembic migrations and application startup. Inserts defaults
only when a tenant has **zero** rows in a category — never overwrites admin
configuration and never duplicates existing codes.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.form_config import LookupOption
from src.domain.models.tenant import Tenant
from src.domain.services.lookup_defaults_seed_data import LOOKUP_DEFAULT_ROWS, SEED_CATEGORIES, rows_for_category


@dataclass
class LookupSeedResult:
    tenants_processed: int = 0
    categories_seeded: dict[str, int] = field(default_factory=dict)
    rows_inserted: int = 0
    skipped_categories: dict[str, int] = field(default_factory=dict)


async def _tenant_ids(db: AsyncSession, tenant_id: int | None) -> list[int]:
    if tenant_id is not None:
        return [tenant_id]
    result = await db.execute(select(Tenant.id).order_by(Tenant.id))
    return [row[0] for row in result.all()]


async def _category_has_rows(db: AsyncSession, *, tenant_id: int, category: str) -> bool:
    count_result = await db.execute(
        select(func.count())
        .select_from(LookupOption)
        .where(
            LookupOption.tenant_id == tenant_id,
            LookupOption.category == category,
        )
    )
    return int(count_result.scalar_one()) > 0


async def seed_lookup_defaults(
    db: AsyncSession,
    *,
    tenant_id: int | None = None,
) -> LookupSeedResult:
    """Seed UK defaults for lookup categories that are empty per tenant."""
    result = LookupSeedResult()
    tenant_ids = await _tenant_ids(db, tenant_id)
    result.tenants_processed = len(tenant_ids)

    for tid in tenant_ids:
        for category in SEED_CATEGORIES:
            if await _category_has_rows(db, tenant_id=tid, category=category):
                result.skipped_categories[category] = result.skipped_categories.get(category, 0) + 1
                continue

            inserted_for_category = 0
            for row in rows_for_category(category):
                option = LookupOption(
                    tenant_id=tid,
                    category=row.category,
                    code=row.code,
                    label=row.label,
                    is_active=True,
                    display_order=row.display_order,
                )
                db.add(option)
                inserted_for_category += 1

            if inserted_for_category:
                result.categories_seeded[category] = result.categories_seeded.get(category, 0) + 1
                result.rows_inserted += inserted_for_category

    if result.rows_inserted:
        await db.commit()

    return result


async def count_active_lookup_options(
    db: AsyncSession,
    *,
    tenant_id: int,
    category: str,
) -> int:
    """Count active lookup rows for publish validation."""
    count_result = await db.execute(
        select(func.count())
        .select_from(LookupOption)
        .where(
            LookupOption.tenant_id == tenant_id,
            LookupOption.category == category,
            LookupOption.is_active.is_(True),
        )
    )
    return int(count_result.scalar_one())
