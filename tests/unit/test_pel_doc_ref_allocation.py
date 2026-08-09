"""Governance Library WA-2 — PEL doc-ref atomic allocation on the function axis.

ADR-0023 moved the counter from the category to the owning function, so a
reference is `PEL-<FUNCTION>-<SEQ>` with a four-digit sequence. Every
concurrency guarantee the Wave W0 per-category allocator had is re-asserted
here against the per-function counter, because the failure mode it protects
against is unchanged and worse: two documents claiming one immutable
reference.

The concurrency tests use a temp *file*-backed SQLite DB (not `:memory:`) so
each concurrent task opens a genuinely independent connection, exactly like
tests/integration/conftest.py's integration DB. SQLite's own file locking then
has to serialize the writes for real — this is what proves
`allocate_pel_doc_ref`'s single `UPDATE ... RETURNING` never lets two
concurrent callers observe/allocate the same sequence number, which a naive
"SELECT next_seq, then UPDATE" implementation could fail under the same
interleaving (the `await db.get(...)` before the atomic update gives the event
loop a chance to interleave tasks).
"""

from __future__ import annotations

import asyncio
import tempfile
import uuid
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.domain.exceptions import NotFoundError, ValidationError
from src.domain.models.document_library import DocumentFunction, PelDocRefCounter
from src.domain.services.document_category_service import allocate_pel_doc_ref, resolve_function_code


@pytest.fixture
async def sqlite_file_engine():
    """A real file-backed SQLite DB — required for true multi-connection concurrency."""
    db_path = Path(tempfile.gettempdir()) / f"qgp-test-pel-ref-{uuid.uuid4().hex}.db"
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{db_path}",
        connect_args={"timeout": 30},
    )
    async with engine.begin() as conn:
        await conn.run_sync(DocumentFunction.__table__.create)
        await conn.run_sync(PelDocRefCounter.__table__.create)

    yield engine

    await engine.dispose()
    db_path.unlink(missing_ok=True)


@pytest.fixture
def session_factory(sqlite_file_engine):
    return async_sessionmaker(sqlite_file_engine, expire_on_commit=False, class_=AsyncSession)


async def _seed_function(
    session_factory,
    *,
    code: str = "HSEQ",
    name: str = "Health, Safety, Environment & Quality",
    active: bool = True,
    with_counter: bool = True,
    next_seq: int = 1,
) -> int:
    async with session_factory() as session:
        function = DocumentFunction(
            code=code,
            name=name,
            description=None,
            sort_order=10,
            active=active,
        )
        session.add(function)
        await session.flush()
        if with_counter:
            session.add(PelDocRefCounter(function_id=function.id, next_seq=next_seq))
        await session.commit()
        return function.id


class TestAllocatePelDocRefSerial:
    @pytest.mark.asyncio
    async def test_first_allocation_is_seq_0001(self, session_factory):
        function_id = await _seed_function(session_factory)
        async with session_factory() as session:
            ref = await allocate_pel_doc_ref(session, function_id)
            await session.commit()
        assert ref == "PEL-HSEQ-0001"

    @pytest.mark.asyncio
    async def test_sequential_allocations_increment(self, session_factory):
        function_id = await _seed_function(session_factory)
        refs = []
        for _ in range(5):
            async with session_factory() as session:
                refs.append(await allocate_pel_doc_ref(session, function_id))
                await session.commit()
        assert refs == [f"PEL-HSEQ-{n:04d}" for n in range(1, 6)]

    @pytest.mark.asyncio
    async def test_sequence_is_four_digits_not_three(self, session_factory):
        """ADR-0023: HSEQ holds 226 documents on day one; three digits would overflow."""
        function_id = await _seed_function(session_factory, next_seq=227)
        async with session_factory() as session:
            ref = await allocate_pel_doc_ref(session, function_id)
            await session.commit()
        assert ref == "PEL-HSEQ-0227"

    @pytest.mark.asyncio
    async def test_sequence_widens_rather_than_wrapping_past_9999(self, session_factory):
        """Padding is a floor, not a ceiling — a five-digit sequence must not re-issue 0001."""
        function_id = await _seed_function(session_factory, next_seq=10_000)
        async with session_factory() as session:
            ref = await allocate_pel_doc_ref(session, function_id)
            await session.commit()
        assert ref == "PEL-HSEQ-10000"

    @pytest.mark.asyncio
    async def test_reference_carries_the_function_code_not_the_category_path(self, session_factory):
        """The whole point of ADR-0023: an IT policy filed in 01.01 reads PEL-IT-####."""
        function_id = await _seed_function(session_factory, code="IT", name="IT & Information Security")
        async with session_factory() as session:
            ref = await allocate_pel_doc_ref(session, function_id)
            await session.commit()
        assert ref == "PEL-IT-0001"

    @pytest.mark.asyncio
    async def test_rejects_inactive_function(self, session_factory):
        function_id = await _seed_function(session_factory, active=False)
        async with session_factory() as session:
            with pytest.raises(ValidationError):
                await allocate_pel_doc_ref(session, function_id)

    @pytest.mark.asyncio
    async def test_inactive_function_counter_is_not_advanced_by_the_refusal(self, session_factory):
        function_id = await _seed_function(session_factory, active=False)
        async with session_factory() as session:
            with pytest.raises(ValidationError):
                await allocate_pel_doc_ref(session, function_id)
            await session.rollback()

        async with session_factory() as session:
            assert (await session.get(PelDocRefCounter, function_id)).next_seq == 1

    @pytest.mark.asyncio
    async def test_missing_function_raises_not_found(self, session_factory):
        async with session_factory() as session:
            with pytest.raises(NotFoundError):
                await allocate_pel_doc_ref(session, 999999)

    @pytest.mark.asyncio
    async def test_function_without_counter_raises_not_found(self, session_factory):
        function_id = await _seed_function(session_factory, with_counter=False)
        async with session_factory() as session:
            with pytest.raises(NotFoundError):
                await allocate_pel_doc_ref(session, function_id)


class TestResolveFunctionCode:
    @pytest.mark.asyncio
    async def test_none_resolves_to_none_so_the_document_files_without_a_reference(self, session_factory):
        await _seed_function(session_factory)
        async with session_factory() as session:
            assert await resolve_function_code(session, None) is None

    @pytest.mark.asyncio
    async def test_blank_code_resolves_to_none(self, session_factory):
        await _seed_function(session_factory)
        async with session_factory() as session:
            assert await resolve_function_code(session, "   ") is None

    @pytest.mark.asyncio
    async def test_code_is_matched_case_insensitively(self, session_factory):
        function_id = await _seed_function(session_factory, code="IT")
        async with session_factory() as session:
            resolved = await resolve_function_code(session, " it ")
        assert resolved is not None
        assert resolved.id == function_id

    @pytest.mark.asyncio
    async def test_unknown_code_raises_rather_than_falling_back_to_no_function(self, session_factory):
        """Falling through would file the document with no reference the caller never asked for."""
        await _seed_function(session_factory)
        async with session_factory() as session:
            with pytest.raises(ValidationError, match="Unknown document function"):
                await resolve_function_code(session, "NOPE")

    @pytest.mark.asyncio
    async def test_inactive_code_raises(self, session_factory):
        await _seed_function(session_factory, code="CTR", name="Control Room", active=False)
        async with session_factory() as session:
            with pytest.raises(ValidationError, match="inactive"):
                await resolve_function_code(session, "CTR")


class TestAllocatePelDocRefConcurrency:
    @pytest.mark.asyncio
    async def test_concurrent_allocations_are_unique_and_gapless(self, session_factory):
        function_id = await _seed_function(session_factory)
        concurrency = 25

        async def _allocate_and_commit() -> str:
            async with session_factory() as session:
                ref = await allocate_pel_doc_ref(session, function_id)
                await session.commit()
                return ref

        results = await asyncio.gather(*[_allocate_and_commit() for _ in range(concurrency)])

        assert len(results) == concurrency
        assert len(set(results)) == concurrency, f"duplicate PEL refs allocated: {results}"
        expected = {f"PEL-HSEQ-{n:04d}" for n in range(1, concurrency + 1)}
        assert set(results) == expected

    @pytest.mark.asyncio
    async def test_concurrent_allocations_across_two_functions_never_cross_contaminate(self, session_factory):
        function_a = await _seed_function(session_factory, code="HSEQ")
        function_b = await _seed_function(session_factory, code="IT", name="IT & Information Security")

        async def _allocate_and_commit(function_id: int) -> str:
            async with session_factory() as session:
                ref = await allocate_pel_doc_ref(session, function_id)
                await session.commit()
                return ref

        tasks = [_allocate_and_commit(function_a) for _ in range(10)] + [
            _allocate_and_commit(function_b) for _ in range(10)
        ]
        results = await asyncio.gather(*tasks)

        a_refs = {r for r in results if r.startswith("PEL-HSEQ-")}
        b_refs = {r for r in results if r.startswith("PEL-IT-")}
        assert len(a_refs) == 10
        assert len(b_refs) == 10
        assert a_refs == {f"PEL-HSEQ-{n:04d}" for n in range(1, 11)}
        assert b_refs == {f"PEL-IT-{n:04d}" for n in range(1, 11)}

    @pytest.mark.asyncio
    async def test_counter_row_reflects_total_allocations_after_concurrency(self, session_factory):
        function_id = await _seed_function(session_factory)
        concurrency = 15

        async def _allocate_and_commit() -> str:
            async with session_factory() as session:
                ref = await allocate_pel_doc_ref(session, function_id)
                await session.commit()
                return ref

        await asyncio.gather(*[_allocate_and_commit() for _ in range(concurrency)])

        async with session_factory() as session:
            counter = await session.get(PelDocRefCounter, function_id)
            assert counter.next_seq == concurrency + 1
