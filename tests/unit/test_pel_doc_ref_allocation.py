"""Governance Library Wave W0 — PEL doc-ref atomic allocation.

The concurrency test uses a temp *file*-backed SQLite DB (not `:memory:`)
so each concurrent task opens a genuinely independent connection, exactly
like tests/integration/conftest.py's integration DB. SQLite's own file
locking then has to serialize the writes for real — this is what proves
`allocate_pel_doc_ref`'s single `UPDATE ... RETURNING` never lets two
concurrent callers observe/allocate the same sequence number, which a
naive "SELECT next_seq, then UPDATE" implementation could fail under the
same interleaving (the `await db.get(...)` before the atomic update gives
the event loop a chance to interleave tasks).
"""

from __future__ import annotations

import asyncio
import tempfile
import uuid
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.domain.exceptions import NotFoundError, ValidationError
from src.domain.models.document_library import DocumentCategory, PelDocRefCounter
from src.domain.services.document_category_service import allocate_pel_doc_ref


@pytest.fixture
async def sqlite_file_engine():
    """A real file-backed SQLite DB — required for true multi-connection concurrency."""
    db_path = Path(tempfile.gettempdir()) / f"qgp-test-pel-ref-{uuid.uuid4().hex}.db"
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{db_path}",
        connect_args={"timeout": 30},
    )
    async with engine.begin() as conn:
        await conn.run_sync(DocumentCategory.__table__.create)
        await conn.run_sync(PelDocRefCounter.__table__.create)

    yield engine

    await engine.dispose()
    db_path.unlink(missing_ok=True)


@pytest.fixture
def session_factory(sqlite_file_engine):
    return async_sessionmaker(sqlite_file_engine, expire_on_commit=False, class_=AsyncSession)


async def _seed_category(
    session_factory,
    *,
    taxonomy_id: str = "04.04",
    ref_prefix: str = "PEL-FIR-01",
    level: int = 2,
    active: bool = True,
    with_counter: bool = True,
) -> int:
    async with session_factory() as session:
        category = DocumentCategory(
            taxonomy_id=taxonomy_id,
            parent_id=None,
            level=level,
            sort_order=1,
            name="Fire Risk Assessments",
            slug="fire-risk-assessments",
            ref_prefix=ref_prefix,
            active=active,
        )
        session.add(category)
        await session.flush()
        if with_counter:
            session.add(PelDocRefCounter(category_id=category.id, next_seq=1))
        await session.commit()
        return category.id


class TestAllocatePelDocRefSerial:
    @pytest.mark.asyncio
    async def test_first_allocation_is_seq_001(self, session_factory):
        category_id = await _seed_category(session_factory)
        async with session_factory() as session:
            ref = await allocate_pel_doc_ref(session, category_id)
            await session.commit()
        assert ref == "PEL-FIR-01-001"

    @pytest.mark.asyncio
    async def test_sequential_allocations_increment(self, session_factory):
        category_id = await _seed_category(session_factory)
        refs = []
        for _ in range(5):
            async with session_factory() as session:
                refs.append(await allocate_pel_doc_ref(session, category_id))
                await session.commit()
        assert refs == [f"PEL-FIR-01-{n:03d}" for n in range(1, 6)]

    @pytest.mark.asyncio
    async def test_rejects_level1_category(self, session_factory):
        category_id = await _seed_category(session_factory, level=1, ref_prefix="PEL-FIR", with_counter=False)
        async with session_factory() as session:
            with pytest.raises(ValidationError):
                await allocate_pel_doc_ref(session, category_id)

    @pytest.mark.asyncio
    async def test_rejects_inactive_category(self, session_factory):
        category_id = await _seed_category(session_factory, active=False)
        async with session_factory() as session:
            with pytest.raises(ValidationError):
                await allocate_pel_doc_ref(session, category_id)

    @pytest.mark.asyncio
    async def test_missing_category_raises_not_found(self, session_factory):
        async with session_factory() as session:
            with pytest.raises(NotFoundError):
                await allocate_pel_doc_ref(session, 999999)

    @pytest.mark.asyncio
    async def test_category_without_counter_raises_not_found(self, session_factory):
        category_id = await _seed_category(session_factory, with_counter=False)
        async with session_factory() as session:
            with pytest.raises(NotFoundError):
                await allocate_pel_doc_ref(session, category_id)


class TestAllocatePelDocRefConcurrency:
    @pytest.mark.asyncio
    async def test_concurrent_allocations_are_unique_and_gapless(self, session_factory):
        category_id = await _seed_category(session_factory)
        concurrency = 25

        async def _allocate_and_commit() -> str:
            async with session_factory() as session:
                ref = await allocate_pel_doc_ref(session, category_id)
                await session.commit()
                return ref

        results = await asyncio.gather(*[_allocate_and_commit() for _ in range(concurrency)])

        assert len(results) == concurrency
        assert len(set(results)) == concurrency, f"duplicate PEL refs allocated: {results}"
        expected = {f"PEL-FIR-01-{n:03d}" for n in range(1, concurrency + 1)}
        assert set(results) == expected

    @pytest.mark.asyncio
    async def test_concurrent_allocations_across_two_categories_never_cross_contaminate(self, session_factory):
        category_a = await _seed_category(session_factory, taxonomy_id="04.04", ref_prefix="PEL-FIR-01")
        category_b = await _seed_category(session_factory, taxonomy_id="03.02", ref_prefix="PEL-HSE-02")

        async def _allocate_and_commit(category_id: int) -> str:
            async with session_factory() as session:
                ref = await allocate_pel_doc_ref(session, category_id)
                await session.commit()
                return ref

        tasks = [_allocate_and_commit(category_a) for _ in range(10)] + [
            _allocate_and_commit(category_b) for _ in range(10)
        ]
        results = await asyncio.gather(*tasks)

        a_refs = {r for r in results if r.startswith("PEL-FIR-01")}
        b_refs = {r for r in results if r.startswith("PEL-HSE-02")}
        assert len(a_refs) == 10
        assert len(b_refs) == 10
        assert a_refs == {f"PEL-FIR-01-{n:03d}" for n in range(1, 11)}
        assert b_refs == {f"PEL-HSE-02-{n:03d}" for n in range(1, 11)}

    @pytest.mark.asyncio
    async def test_counter_row_reflects_total_allocations_after_concurrency(self, session_factory):
        category_id = await _seed_category(session_factory)
        concurrency = 15

        async def _allocate_and_commit() -> str:
            async with session_factory() as session:
                ref = await allocate_pel_doc_ref(session, category_id)
                await session.commit()
                return ref

        await asyncio.gather(*[_allocate_and_commit() for _ in range(concurrency)])

        async with session_factory() as session:
            counter = await session.get(PelDocRefCounter, category_id)
            assert counter.next_seq == concurrency + 1
