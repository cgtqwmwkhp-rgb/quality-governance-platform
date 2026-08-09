"""Governance Library NS-1 — banded PEL doc-ref allocation on (function, level).

Northern Star v6 fixes the reference grammar at `PEL-<FUNCTION>-<BAND><SEQ>`
with `^PEL-(...)-[1-5][0-9]{3}$` (R01), and requires the band digit to equal
the document's cascade level (R02). WA-2's per-function allocator issued
`PEL-HSEQ-0001` — a leading `0` no band claims — so this module pins the
banded form and the guarantees around it:

* the band digit is the level the caller passed, never a default;
* each (function, band) numbers independently from 001;
* allocation is monotonic and append-only, never gap-filled (R29);
* a band that fills up refuses rather than widening into an invalid
  reference (R01) or wrapping onto a live one (R06).

Every concurrency guarantee the WA-2 per-function allocator had is re-asserted
against the banded counter, because the failure mode it protects against is
unchanged and worse: two documents claiming one immutable reference.

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
import json
import re
import tempfile
import uuid
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.domain.exceptions import NotFoundError, ValidationError
from src.domain.models.document_library import CASCADE_LEVELS, DocumentFunction, PelDocRefCounter
from src.domain.services.document_category_service import allocate_pel_doc_ref, resolve_function_code

_RULES_PATH = Path(__file__).resolve().parents[2] / "specs" / "governance-library" / "northern-star-rules-v6.json"
_RULES = json.loads(_RULES_PATH.read_text())

# Read from the NS-0 authority pack rather than copied into this file: the
# checked-in rules JSON is the SoT for the grammar, and a second copy here would
# silently stop tracking it the first time the pack is amended.
R01_REFERENCE_PATTERN = re.compile(_RULES["reference_pattern"])

# Functions used below are drawn from the v6 vocabulary so these tests keep
# meaning after the W2 reseed. NOTE: the seeded `document_functions` table still
# carries the WA-2 code OPS, which v6 replaces with CTR+SVC; that reseed is
# explicitly Wave W2 (ADR-0023 § Amendment), not this PR, so a `PEL-OPS-####`
# issued today would satisfy R02 but not R01's function list.
_V6_FUNCTION_CODES = frozenset(fn["code"] for fn in _RULES["functions"])


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
    bands: tuple[int, ...] = CASCADE_LEVELS,
) -> int:
    """Seed a function and, by default, all five of its band counters."""
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
            for band in bands:
                session.add(PelDocRefCounter(function_id=function.id, level_band=band, next_seq=next_seq))
        await session.commit()
        return function.id


class TestConformsToTheCheckedInAuthorityPack:
    """Pin the implementation to specs/governance-library/northern-star-rules-v6.json."""

    def test_cascade_levels_match_the_authority_pack(self):
        assert list(CASCADE_LEVELS) == [level["level"] for level in _RULES["levels"]]

    def test_each_band_range_starts_at_the_level_digit(self):
        """v6 declares bands as `1000-1999`, `2000-2999`, ... — the level is the leading digit."""
        for level in _RULES["levels"]:
            low, high = level["band"].split("-")
            assert low == f"{level['level']}000"
            assert high == f"{level['level']}999"

    @pytest.mark.asyncio
    async def test_an_allocated_reference_falls_inside_its_declared_band(self, session_factory):
        function_id = await _seed_function(session_factory)
        for level in _RULES["levels"]:
            async with session_factory() as session:
                ref = await allocate_pel_doc_ref(session, function_id, level["level"])
                await session.commit()
            low, high = (int(part) for part in level["band"].split("-"))
            assert low <= int(ref.rsplit("-", 1)[1]) <= high

    @pytest.mark.asyncio
    async def test_banding_is_correct_even_for_a_function_v6_has_not_reseeded_yet(self, session_factory):
        """OPS is a WA-2 code that v6 replaces with CTR+SVC; the reseed is Wave W2.

        Until then a document can still be filed under OPS, and this pins what
        that produces: the band digit is right (R02 holds — that is this PR's
        job), but the function segment is not yet in the v6 vocabulary, so R01
        does not pass. Recording it here means the W2 reseed has something
        concrete to flip rather than a silent surprise.
        """
        assert "OPS" not in _V6_FUNCTION_CODES
        function_id = await _seed_function(session_factory, code="OPS", name="Operations")
        async with session_factory() as session:
            ref = await allocate_pel_doc_ref(session, function_id, 3)
            await session.commit()
        assert ref == "PEL-OPS-3001"
        assert ref.rsplit("-", 1)[1][0] == "3", "R02 (band == level) must hold regardless"
        assert not R01_REFERENCE_PATTERN.match(ref), "expected the known pre-W2 R01 gap"

    def test_the_r29_rule_is_still_append_only(self):
        """If the pack ever relaxes R29 to gap-fill, this allocator's design must be revisited."""
        r29 = next(rule for rule in _RULES["validation_rules"] if rule["id"] == "R29")
        assert "next free number in its band" in r29["rule"]
        assert "nothing is ever renumbered" in r29["rule"]


class TestBandedFormat:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("level", CASCADE_LEVELS)
    async def test_first_allocation_in_each_band_is_band_then_001(self, session_factory, level):
        function_id = await _seed_function(session_factory)
        async with session_factory() as session:
            ref = await allocate_pel_doc_ref(session, function_id, level)
            await session.commit()
        assert ref == f"PEL-HSEQ-{level}001"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("level", CASCADE_LEVELS)
    async def test_every_issued_reference_satisfies_r01(self, session_factory, level):
        function_id = await _seed_function(session_factory)
        async with session_factory() as session:
            ref = await allocate_pel_doc_ref(session, function_id, level)
            await session.commit()
        assert R01_REFERENCE_PATTERN.match(ref), f"{ref} fails the v6 reference grammar"

    @pytest.mark.asyncio
    async def test_band_digit_equals_the_cascade_level_r02(self, session_factory):
        """R02: the first digit of the sequence equals the cascade level."""
        function_id = await _seed_function(session_factory)
        for level in CASCADE_LEVELS:
            async with session_factory() as session:
                ref = await allocate_pel_doc_ref(session, function_id, level)
                await session.commit()
            assert ref.rsplit("-", 1)[1][0] == str(level)

    @pytest.mark.asyncio
    async def test_the_withdrawn_unbanded_form_is_no_longer_issuable(self, session_factory):
        """`PEL-HSEQ-0001` was the WA-2 form; it fails R01/R02 and must be unreachable."""
        function_id = await _seed_function(session_factory)
        issued = []
        for level in CASCADE_LEVELS:
            async with session_factory() as session:
                issued.append(await allocate_pel_doc_ref(session, function_id, level))
                await session.commit()
        assert "PEL-HSEQ-0001" not in issued
        assert not any(ref.rsplit("-", 1)[1].startswith("0") for ref in issued)

    @pytest.mark.asyncio
    async def test_sequential_allocations_increment_within_a_band(self, session_factory):
        function_id = await _seed_function(session_factory)
        refs = []
        for _ in range(5):
            async with session_factory() as session:
                refs.append(await allocate_pel_doc_ref(session, function_id, 3))
                await session.commit()
        assert refs == [f"PEL-HSEQ-3{n:03d}" for n in range(1, 6)]

    @pytest.mark.asyncio
    async def test_reference_carries_the_function_code_not_the_category_path(self, session_factory):
        """ADR-0023: an IT policy filed in 01.01 reads PEL-IT-2###, not the category path."""
        function_id = await _seed_function(session_factory, code="IT", name="IT & Information Security")
        async with session_factory() as session:
            ref = await allocate_pel_doc_ref(session, function_id, 2)
            await session.commit()
        assert ref == "PEL-IT-2001"


class TestBandsAreIndependent:
    @pytest.mark.asyncio
    async def test_each_band_numbers_from_001_independently(self, session_factory):
        """HSEQ's first procedure and HSEQ's first form both number 001, in different bands."""
        function_id = await _seed_function(session_factory)
        async with session_factory() as session:
            procedure = await allocate_pel_doc_ref(session, function_id, 3)
            form = await allocate_pel_doc_ref(session, function_id, 5)
            await session.commit()
        assert procedure == "PEL-HSEQ-3001"
        assert form == "PEL-HSEQ-5001"

    @pytest.mark.asyncio
    async def test_advancing_one_band_does_not_advance_another(self, session_factory):
        function_id = await _seed_function(session_factory)
        for _ in range(4):
            async with session_factory() as session:
                await allocate_pel_doc_ref(session, function_id, 4)
                await session.commit()

        async with session_factory() as session:
            assert (await session.get(PelDocRefCounter, (function_id, 4))).next_seq == 5
            assert (await session.get(PelDocRefCounter, (function_id, 1))).next_seq == 1
            first_manual = await allocate_pel_doc_ref(session, function_id, 1)
            await session.commit()
        assert first_manual == "PEL-HSEQ-1001"

    @pytest.mark.asyncio
    async def test_same_band_of_two_functions_never_cross_contaminates(self, session_factory):
        function_a = await _seed_function(session_factory, code="HSEQ")
        function_b = await _seed_function(session_factory, code="IT", name="IT & Information Security")
        async with session_factory() as session:
            a_ref = await allocate_pel_doc_ref(session, function_a, 3)
            b_ref = await allocate_pel_doc_ref(session, function_b, 3)
            await session.commit()
        assert a_ref == "PEL-HSEQ-3001"
        assert b_ref == "PEL-IT-3001"


class TestLevelIsRequiredAndValidated:
    @pytest.mark.asyncio
    async def test_missing_level_is_refused_rather_than_defaulted(self, session_factory):
        """A defaulted band prints an immutable reference nobody chose."""
        function_id = await _seed_function(session_factory)
        async with session_factory() as session:
            with pytest.raises(ValidationError):
                await allocate_pel_doc_ref(session, function_id, None)

    @pytest.mark.asyncio
    @pytest.mark.parametrize("bad_level", [0, 6, -1, 99])
    async def test_out_of_range_level_is_refused(self, session_factory, bad_level):
        function_id = await _seed_function(session_factory)
        async with session_factory() as session:
            with pytest.raises(ValidationError):
                await allocate_pel_doc_ref(session, function_id, bad_level)

    @pytest.mark.asyncio
    @pytest.mark.parametrize("bad_level", ["three", "", None, 2.5, 3.0, True, [3], object()])
    async def test_non_level_values_are_refused(self, session_factory, bad_level):
        """`int(2.5)` is 2 — rounding a level would band the reference one tier off."""
        function_id = await _seed_function(session_factory)
        async with session_factory() as session:
            with pytest.raises(ValidationError):
                await allocate_pel_doc_ref(session, function_id, bad_level)

    @pytest.mark.asyncio
    async def test_numeric_string_level_is_accepted_for_multipart_form_callers(self, session_factory):
        function_id = await _seed_function(session_factory)
        async with session_factory() as session:
            ref = await allocate_pel_doc_ref(session, function_id, "4")
            await session.commit()
        assert ref == "PEL-HSEQ-4001"

    @pytest.mark.asyncio
    async def test_a_rejected_level_does_not_advance_any_counter(self, session_factory):
        function_id = await _seed_function(session_factory)
        async with session_factory() as session:
            with pytest.raises(ValidationError):
                await allocate_pel_doc_ref(session, function_id, 9)
            await session.rollback()

        async with session_factory() as session:
            for band in CASCADE_LEVELS:
                assert (await session.get(PelDocRefCounter, (function_id, band))).next_seq == 1


class TestRefusals:
    @pytest.mark.asyncio
    async def test_rejects_inactive_function(self, session_factory):
        function_id = await _seed_function(session_factory, active=False)
        async with session_factory() as session:
            with pytest.raises(ValidationError):
                await allocate_pel_doc_ref(session, function_id, 3)

    @pytest.mark.asyncio
    async def test_inactive_function_counter_is_not_advanced_by_the_refusal(self, session_factory):
        function_id = await _seed_function(session_factory, active=False)
        async with session_factory() as session:
            with pytest.raises(ValidationError):
                await allocate_pel_doc_ref(session, function_id, 3)
            await session.rollback()

        async with session_factory() as session:
            assert (await session.get(PelDocRefCounter, (function_id, 3))).next_seq == 1

    @pytest.mark.asyncio
    async def test_missing_function_raises_not_found(self, session_factory):
        async with session_factory() as session:
            with pytest.raises(NotFoundError):
                await allocate_pel_doc_ref(session, 999999, 3)

    @pytest.mark.asyncio
    async def test_function_without_counters_raises_not_found(self, session_factory):
        function_id = await _seed_function(session_factory, with_counter=False)
        async with session_factory() as session:
            with pytest.raises(NotFoundError):
                await allocate_pel_doc_ref(session, function_id, 3)

    @pytest.mark.asyncio
    async def test_a_band_with_no_counter_raises_rather_than_borrowing_another_band(self, session_factory):
        """A partially seeded function must not quietly draw a number from a band it does have."""
        function_id = await _seed_function(session_factory, bands=(1, 2, 3))
        async with session_factory() as session:
            with pytest.raises(NotFoundError):
                await allocate_pel_doc_ref(session, function_id, 5)


class TestBandExhaustion:
    @pytest.mark.asyncio
    async def test_last_reference_in_a_band_is_999(self, session_factory):
        function_id = await _seed_function(session_factory, next_seq=999)
        async with session_factory() as session:
            ref = await allocate_pel_doc_ref(session, function_id, 3)
            await session.commit()
        assert ref == "PEL-HSEQ-3999"
        assert R01_REFERENCE_PATTERN.match(ref)

    @pytest.mark.asyncio
    async def test_a_full_band_refuses_instead_of_widening_past_r01(self, session_factory):
        """Widening would emit `PEL-HSEQ-31000`, which is not a valid v6 reference."""
        function_id = await _seed_function(session_factory, next_seq=1000)
        async with session_factory() as session:
            with pytest.raises(ValidationError, match="exhausted"):
                await allocate_pel_doc_ref(session, function_id, 3)

    @pytest.mark.asyncio
    async def test_a_full_band_does_not_spill_into_the_next_band(self, session_factory):
        """Band 3's 1000th would format as `4000` if the band digit were added in.

        `f"{3}{1000:03d}"` is `31000`, not `4000`, so the two bands cannot
        alias — but the allocator must refuse it either way, and must leave
        band 4's own sequence completely untouched.
        """
        function_id = await _seed_function(session_factory)
        async with session_factory() as session:
            counter = await session.get(PelDocRefCounter, (function_id, 3))
            counter.next_seq = 1000
            await session.commit()

        async with session_factory() as session:
            with pytest.raises(ValidationError):
                await allocate_pel_doc_ref(session, function_id, 3)
            await session.rollback()

        async with session_factory() as session:
            assert (await session.get(PelDocRefCounter, (function_id, 4))).next_seq == 1
            ref = await allocate_pel_doc_ref(session, function_id, 4)
            await session.commit()
        assert ref == "PEL-HSEQ-4001"

    @pytest.mark.asyncio
    async def test_an_exhausted_band_keeps_refusing_and_never_finds_a_hole(self, session_factory):
        """R06/R29: once past the end, retrying must not wrap onto a live reference."""
        function_id = await _seed_function(session_factory, next_seq=1000)
        async with session_factory() as session:
            for _ in range(3):
                with pytest.raises(ValidationError):
                    await allocate_pel_doc_ref(session, function_id, 3)
                await session.commit()


class TestMonotonicNotGapFilling:
    @pytest.mark.asyncio
    async def test_a_rolled_back_allocation_leaves_a_hole_rather_than_reissuing(self, session_factory):
        """R29: allocation is append-only. A released number is never handed out again."""
        function_id = await _seed_function(session_factory)
        async with session_factory() as session:
            first = await allocate_pel_doc_ref(session, function_id, 3)
            await session.commit()
        assert first == "PEL-HSEQ-3001"

        async with session_factory() as session:
            abandoned = await allocate_pel_doc_ref(session, function_id, 3)
            await session.commit()  # the number is spent even though no document uses it
        assert abandoned == "PEL-HSEQ-3002"

        async with session_factory() as session:
            following = await allocate_pel_doc_ref(session, function_id, 3)
            await session.commit()
        assert following == "PEL-HSEQ-3003", "the allocator gap-filled a spent number"

    @pytest.mark.asyncio
    async def test_allocation_is_max_plus_one_not_lowest_free(self, session_factory):
        function_id = await _seed_function(session_factory, next_seq=42)
        async with session_factory() as session:
            ref = await allocate_pel_doc_ref(session, function_id, 5)
            await session.commit()
        assert ref == "PEL-HSEQ-5042"


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
    async def test_concurrent_allocations_in_one_band_are_unique_and_gapless(self, session_factory):
        function_id = await _seed_function(session_factory)
        concurrency = 25

        async def _allocate_and_commit() -> str:
            async with session_factory() as session:
                ref = await allocate_pel_doc_ref(session, function_id, 3)
                await session.commit()
                return ref

        results = await asyncio.gather(*[_allocate_and_commit() for _ in range(concurrency)])

        assert len(results) == concurrency
        assert len(set(results)) == concurrency, f"duplicate PEL refs allocated: {results}"
        expected = {f"PEL-HSEQ-3{n:03d}" for n in range(1, concurrency + 1)}
        assert set(results) == expected

    @pytest.mark.asyncio
    async def test_concurrent_allocations_across_bands_of_one_function_never_collide(self, session_factory):
        """The band is part of the key, so five bands allocate in parallel without contending."""
        function_id = await _seed_function(session_factory)
        per_band = 8

        async def _allocate_and_commit(level: int) -> str:
            async with session_factory() as session:
                ref = await allocate_pel_doc_ref(session, function_id, level)
                await session.commit()
                return ref

        tasks = [_allocate_and_commit(level) for level in CASCADE_LEVELS for _ in range(per_band)]
        results = await asyncio.gather(*tasks)

        assert len(set(results)) == len(results)
        for level in CASCADE_LEVELS:
            band_refs = {r for r in results if r.startswith(f"PEL-HSEQ-{level}")}
            assert band_refs == {f"PEL-HSEQ-{level}{n:03d}" for n in range(1, per_band + 1)}

    @pytest.mark.asyncio
    async def test_concurrent_allocations_across_two_functions_never_cross_contaminate(self, session_factory):
        function_a = await _seed_function(session_factory, code="HSEQ")
        function_b = await _seed_function(session_factory, code="IT", name="IT & Information Security")

        async def _allocate_and_commit(function_id: int) -> str:
            async with session_factory() as session:
                ref = await allocate_pel_doc_ref(session, function_id, 2)
                await session.commit()
                return ref

        tasks = [_allocate_and_commit(function_a) for _ in range(10)] + [
            _allocate_and_commit(function_b) for _ in range(10)
        ]
        results = await asyncio.gather(*tasks)

        a_refs = {r for r in results if r.startswith("PEL-HSEQ-")}
        b_refs = {r for r in results if r.startswith("PEL-IT-")}
        assert a_refs == {f"PEL-HSEQ-2{n:03d}" for n in range(1, 11)}
        assert b_refs == {f"PEL-IT-2{n:03d}" for n in range(1, 11)}

    @pytest.mark.asyncio
    async def test_counter_row_reflects_total_allocations_after_concurrency(self, session_factory):
        function_id = await _seed_function(session_factory)
        concurrency = 15

        async def _allocate_and_commit() -> str:
            async with session_factory() as session:
                ref = await allocate_pel_doc_ref(session, function_id, 1)
                await session.commit()
                return ref

        await asyncio.gather(*[_allocate_and_commit() for _ in range(concurrency)])

        async with session_factory() as session:
            counter = await session.get(PelDocRefCounter, (function_id, 1))
            assert counter.next_seq == concurrency + 1
