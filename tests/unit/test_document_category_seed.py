"""Governance Library Wave W0 — taxonomy seed idempotency.

Uses an isolated in-memory SQLite session (StaticPool keeps the one
connection alive across sessions — required for `:memory:` databases;
without it every new session would see a fresh, empty DB) with only the
three taxonomy tables created, mirroring the pattern in
tests/integration/test_audit_version_entity_integrity.py.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from src.domain.models.document_library import DocumentCategory, DocumentTag, PelDocRefCounter
from src.domain.services.document_category_seed_data import (
    DEACTIVATED_TAXONOMY_IDS,
    EXPECTED_CATEGORY_COUNT,
    TAG_SEED,
    load_taxonomy_categories,
)
from src.domain.services.document_category_service import seed_document_categories


@pytest.fixture
async def isolated_db_session():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with engine.begin() as conn:
        await conn.run_sync(DocumentCategory.__table__.create)
        await conn.run_sync(DocumentTag.__table__.create)
        await conn.run_sync(PelDocRefCounter.__table__.create)

    async with session_factory() as session:
        yield session

    await engine.dispose()


class TestTaxonomySeedData:
    """Sanity checks on the parsed taxonomy.json shape (before any DB write)."""

    def test_taxonomy_json_has_86_categories(self):
        rows = load_taxonomy_categories()
        assert len(rows) == EXPECTED_CATEGORY_COUNT

    def test_taxonomy_json_has_13_sections_and_73_subcategories(self):
        rows = load_taxonomy_categories()
        assert sum(1 for r in rows if r["level"] == 1) == 13
        assert sum(1 for r in rows if r["level"] == 2) == 73

    def test_06_04_hgv_o_licence_forced_inactive(self):
        rows = load_taxonomy_categories()
        by_id = {r["taxonomy_id"]: r for r in rows}
        assert "06.04" in by_id
        assert by_id["06.04"]["active"] is False
        assert "O-Licence" in by_id["06.04"]["name"]

    def test_only_06_04_is_deactivated(self):
        rows = load_taxonomy_categories()
        inactive_ids = {r["taxonomy_id"] for r in rows if not r["active"]}
        assert inactive_ids == set(DEACTIVATED_TAXONOMY_IDS)

    def test_tag_seed_excludes_iso_standards_tags(self):
        slugs = {t["slug"] for t in TAG_SEED}
        for iso_tag in ("iso-9001", "iso-14001", "iso-45001", "iso-27001"):
            assert iso_tag not in slugs

    def test_tag_seed_keeps_planet_mark_and_subject_tags(self):
        slugs = {t["slug"] for t in TAG_SEED}
        assert "planet-mark" in slugs
        assert "fire" in slugs
        assert "coshh" in slugs
        assert "gdpr" in slugs


class TestSeedDocumentCategoriesIdempotency:
    @pytest.mark.asyncio
    async def test_first_run_creates_86_categories(self, isolated_db_session: AsyncSession):
        result = await seed_document_categories(isolated_db_session)
        await isolated_db_session.commit()

        assert result.total_categories == EXPECTED_CATEGORY_COUNT
        assert result.categories_created == EXPECTED_CATEGORY_COUNT
        assert result.categories_updated == 0

        all_rows = (await isolated_db_session.execute(select(DocumentCategory))).scalars().all()
        assert len(all_rows) == EXPECTED_CATEGORY_COUNT

    @pytest.mark.asyncio
    async def test_06_04_seeded_inactive_in_db(self, isolated_db_session: AsyncSession):
        await seed_document_categories(isolated_db_session)
        await isolated_db_session.commit()

        result = await isolated_db_session.execute(
            select(DocumentCategory).where(DocumentCategory.taxonomy_id == "06.04")
        )
        category = result.scalar_one()
        assert category.active is False
        assert category.ref_prefix == "PEL-FLT-04"

    @pytest.mark.asyncio
    async def test_second_run_creates_nothing_new(self, isolated_db_session: AsyncSession):
        await seed_document_categories(isolated_db_session)
        await isolated_db_session.commit()

        second_result = await seed_document_categories(isolated_db_session)
        await isolated_db_session.commit()

        assert second_result.categories_created == 0
        assert second_result.categories_updated == EXPECTED_CATEGORY_COUNT
        assert second_result.total_categories == EXPECTED_CATEGORY_COUNT

        all_rows = (await isolated_db_session.execute(select(DocumentCategory))).scalars().all()
        assert len(all_rows) == EXPECTED_CATEGORY_COUNT  # no duplicates

    @pytest.mark.asyncio
    async def test_running_five_times_never_duplicates(self, isolated_db_session: AsyncSession):
        for _ in range(5):
            await seed_document_categories(isolated_db_session)
            await isolated_db_session.commit()

        all_rows = (await isolated_db_session.execute(select(DocumentCategory))).scalars().all()
        assert len(all_rows) == EXPECTED_CATEGORY_COUNT

        counters = (await isolated_db_session.execute(select(PelDocRefCounter))).scalars().all()
        assert len(counters) == 73  # one per level-2 category, never duplicated
        assert all(c.next_seq == 1 for c in counters)  # reseeding never resets/bumps an existing counter

        tags = (await isolated_db_session.execute(select(DocumentTag))).scalars().all()
        assert len(tags) == len(TAG_SEED)

    @pytest.mark.asyncio
    async def test_reseed_reasserts_deactivation_even_if_manually_reactivated(self, isolated_db_session: AsyncSession):
        """A prior manual reactivation of 06.04 must not survive a reseed."""
        await seed_document_categories(isolated_db_session)
        await isolated_db_session.commit()

        result = await isolated_db_session.execute(
            select(DocumentCategory).where(DocumentCategory.taxonomy_id == "06.04")
        )
        category = result.scalar_one()
        category.active = True
        await isolated_db_session.commit()

        await seed_document_categories(isolated_db_session)
        await isolated_db_session.commit()

        result = await isolated_db_session.execute(
            select(DocumentCategory).where(DocumentCategory.taxonomy_id == "06.04")
        )
        assert result.scalar_one().active is False

    @pytest.mark.asyncio
    async def test_seed_creates_one_counter_per_level2_category(self, isolated_db_session: AsyncSession):
        result = await seed_document_categories(isolated_db_session)
        await isolated_db_session.commit()

        assert result.counters_created == 73
        level2_ids = (
            (await isolated_db_session.execute(select(DocumentCategory.id).where(DocumentCategory.level == 2)))
            .scalars()
            .all()
        )
        counter_ids = (await isolated_db_session.execute(select(PelDocRefCounter.category_id))).scalars().all()
        assert set(level2_ids) == set(counter_ids)

    @pytest.mark.asyncio
    async def test_seed_creates_tag_vocabulary_without_iso_tags(self, isolated_db_session: AsyncSession):
        await seed_document_categories(isolated_db_session)
        await isolated_db_session.commit()

        tags = (await isolated_db_session.execute(select(DocumentTag))).scalars().all()
        slugs = {t.slug for t in tags}
        assert len(tags) == len(TAG_SEED)
        assert "planet-mark" in slugs
        for iso_tag in ("iso-9001", "iso-14001", "iso-45001", "iso-27001"):
            assert iso_tag not in slugs
