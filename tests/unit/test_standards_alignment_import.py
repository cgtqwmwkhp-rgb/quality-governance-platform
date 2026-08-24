"""Alignment import: dry-run, accept-each, and apply idempotency.

An alignment verdict decides whether one document can be shown to two auditors, so
an import that half-lands, double-lands, or quietly loosens a verdict is a
correctness problem rather than an inconvenience. These tests hold the three
properties the import service claims:

* **Idempotent apply.** Re-applying the same payload writes nothing and creates no
  second edition, enforced by a checksum over the *resulting* edge set plus a
  partial unique index — not by a read-then-write check.
* **Accept-each is a gate in both directions.** A declined change keeps the live
  verdict and a declined removal keeps the pair, so declining can never make the
  matrix claim more sharing than before.
* **Contradictory source data is refused, not resolved by guessing.**

The tests run against file-backed SQLite so the partial unique indexes declared on
the models are really created and really enforced, rather than being asserted only
as Python attributes.
"""

from __future__ import annotations

import tempfile
import uuid
from dataclasses import replace
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from src.domain.models.standards_alignment import AlignmentEdge, AlignmentVerdict, MatrixVersion, MatrixVersionStatus
from src.domain.services.standards_alignment_import_service import (
    AlignmentImportError,
    StandardsAlignmentImportService,
    build_edges,
    compute_checksum,
    load_payload,
)
from src.domain.services.standards_alignment_read_service import StandardsAlignmentReadService

TENANT_ID = 1


@pytest.fixture
async def session():
    """File-backed SQLite so the partial unique indexes are genuinely created."""
    db_path = Path(tempfile.gettempdir()) / f"qgp-test-alignment-{uuid.uuid4().hex}.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", connect_args={"timeout": 30})
    async with engine.begin() as conn:
        await conn.run_sync(MatrixVersion.__table__.create)
        await conn.run_sync(AlignmentEdge.__table__.create)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as db:
        yield db
    await engine.dispose()
    db_path.unlink(missing_ok=True)


@pytest.fixture
def payload() -> dict:
    return load_payload()


def _minimal_payload(verdict: str = "DIFFERENT") -> dict:
    return {
        "source_ref": "TEST-MATRIX",
        "version_label": "1.0",
        "title": "Test matrix",
        "rows": [
            {
                "row_key": "row-9.1.2",
                "clause_ref": "9.1.2",
                "title": "Evaluation of compliance, and customer satisfaction",
                "verdict": verdict,
                "frameworks": {
                    "9001": {"clause_number": "9.1.2", "label": "customer satisfaction"},
                    "14001": {"clause_number": "9.1.2", "label": "evaluation of compliance"},
                },
            }
        ],
    }


# ------------------------------------------------------------------- idempotency


async def test_applying_the_same_payload_twice_writes_nothing_the_second_time(session, payload):
    service = StandardsAlignmentImportService(session)

    first = await service.apply(tenant_id=TENANT_ID, payload=payload)
    await session.commit()
    assert first.created is True
    assert first.edges_written > 0

    second = await service.apply(tenant_id=TENANT_ID, payload=payload)
    await session.commit()
    assert second.created is False
    assert second.reactivated is False
    assert second.edges_written == 0
    assert second.matrix_version_id == first.matrix_version_id

    versions = await session.scalar(
        select(func.count()).select_from(MatrixVersion).where(MatrixVersion.tenant_id == TENANT_ID)
    )
    assert versions == 1, "a second identical apply must not create a second edition"

    edges = await session.scalar(
        select(func.count()).select_from(AlignmentEdge).where(AlignmentEdge.tenant_id == TENANT_ID)
    )
    assert edges == first.edges_written, "edges must not be duplicated by a re-apply"


async def test_reapplying_a_superseded_edition_makes_it_live_again(session):
    """Re-applying an older payload must reactivate that edition, not no-op."""
    service = StandardsAlignmentImportService(session)
    first = await service.apply(tenant_id=TENANT_ID, payload=_minimal_payload("DIFFERENT"))
    await session.commit()

    loosened = _minimal_payload("NEAR")
    plan = await service.plan(tenant_id=TENANT_ID, payload=loosened)
    accept = [item.token for item in plan.items if item.change_type == "changed"]
    second = await service.apply(
        tenant_id=TENANT_ID,
        payload=loosened,
        accepted_tokens=accept,
    )
    await session.commit()
    assert second.created is True
    assert second.superseded_version_id == first.matrix_version_id

    rollback = await service.apply(tenant_id=TENANT_ID, payload=_minimal_payload("DIFFERENT"))
    await session.commit()
    assert rollback.created is False
    assert rollback.reactivated is True
    assert rollback.matrix_version_id == first.matrix_version_id
    assert rollback.superseded_version_id == second.matrix_version_id

    active = (
        (
            await session.execute(
                select(MatrixVersion).where(
                    MatrixVersion.tenant_id == TENANT_ID,
                    MatrixVersion.status == MatrixVersionStatus.ACTIVE,
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(active) == 1
    assert active[0].id == first.matrix_version_id

    superseded = await session.get(MatrixVersion, second.matrix_version_id)
    assert superseded is not None
    assert superseded.status == MatrixVersionStatus.SUPERSEDED

    edge_count = await session.scalar(
        select(func.count()).select_from(AlignmentEdge).where(AlignmentEdge.tenant_id == TENANT_ID)
    )
    assert edge_count == first.edges_written + second.edges_written

    catalogue = await StandardsAlignmentReadService(session).catalogue(tenant_id=TENANT_ID)
    assert catalogue["matrix_loaded"] is True
    assert any(row["verdict"] == "DIFFERENT" for row in catalogue["rows"])


async def test_only_one_edition_is_active_after_a_real_change(session, payload):
    service = StandardsAlignmentImportService(session)
    first = await service.apply(tenant_id=TENANT_ID, payload=payload)
    await session.commit()

    changed = {**payload, "version_label": "1.1"}
    changed["rows"] = [
        {**row, "verdict": "DIFFERENT"} if row["clause_ref"] == "7.5" else row for row in changed["rows"]
    ]
    second = await service.apply(tenant_id=TENANT_ID, payload=changed)
    await session.commit()

    assert second.created is True
    assert second.superseded_version_id == first.matrix_version_id

    active = (
        (
            await session.execute(
                select(MatrixVersion).where(
                    MatrixVersion.tenant_id == TENANT_ID,
                    MatrixVersion.status == MatrixVersionStatus.ACTIVE,
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(active) == 1
    assert active[0].id == second.matrix_version_id

    superseded = await session.get(MatrixVersion, first.matrix_version_id)
    assert superseded is not None
    assert superseded.status == MatrixVersionStatus.SUPERSEDED
    assert superseded.edge_count > 0, "the superseded edition stays readable"


def test_checksum_ignores_provenance_but_not_verdicts(payload):
    """Re-issuing the workbook with rows moved must not read as a changed verdict."""
    edges, _ = build_edges(payload)
    baseline = compute_checksum(source_ref="X", version_label="1.0", edges=edges)

    # Row order is not part of the edition's identity.
    assert compute_checksum(source_ref="X", version_label="1.0", edges=list(reversed(edges))) == baseline

    # Neither is the sheet/row the verdict was read from: a re-issued workbook with
    # rows inserted above shifts every source_row without changing a single verdict.
    moved = [replace(edge, source_row=(edge.source_row or 0) + 100, source_sheet="moved sheet") for edge in edges]
    assert compute_checksum(source_ref="X", version_label="1.0", edges=moved) == baseline

    # A verdict is part of the identity, so flipping one must change the checksum.
    flipped = list(edges)
    original = flipped[0].verdict
    flipped[0] = replace(
        flipped[0],
        verdict=(AlignmentVerdict.EXACT if original is not AlignmentVerdict.EXACT else AlignmentVerdict.DIFFERENT),
    )
    assert compute_checksum(source_ref="X", version_label="1.0", edges=flipped) != baseline

    # So is the addition a NEAR verdict requires, because that text is the condition
    # on which one deliverable is allowed to serve two standards.
    retexted = list(edges)
    retexted[0] = replace(retexted[0], addition_text="a different addition entirely")
    assert compute_checksum(source_ref="X", version_label="1.0", edges=retexted) != baseline


# ------------------------------------------------------------------ accept-each


async def test_declining_a_change_keeps_the_live_verdict(session):
    """A declined change must never loosen what the matrix already says."""
    service = StandardsAlignmentImportService(session)
    await service.apply(tenant_id=TENANT_ID, payload=_minimal_payload("DIFFERENT"))
    await session.commit()

    loosened = _minimal_payload("EXACT")
    plan = await service.plan(tenant_id=TENANT_ID, payload=loosened)
    changed = [item for item in plan.items if item.change_type == "changed"]
    assert len(changed) == 1
    assert changed[0].previous_verdict == "different"
    assert changed[0].verdict == "exact"

    # Accept nothing: the DIFFERENT verdict must survive.
    result = await service.apply(tenant_id=TENANT_ID, payload=loosened, accepted_tokens=[])
    await session.commit()

    stored = (
        (
            await session.execute(
                select(AlignmentEdge).where(
                    AlignmentEdge.tenant_id == TENANT_ID,
                    AlignmentEdge.matrix_version_id == result.matrix_version_id,
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(stored) == 1
    assert stored[0].verdict == AlignmentVerdict.DIFFERENT


async def test_accepting_a_change_applies_it(session):
    service = StandardsAlignmentImportService(session)
    await service.apply(tenant_id=TENANT_ID, payload=_minimal_payload("DIFFERENT"))
    await session.commit()

    tightened = _minimal_payload("NEAR")
    plan = await service.plan(tenant_id=TENANT_ID, payload=tightened)
    tokens = [item.token for item in plan.items if item.change_type == "changed"]
    assert tokens

    result = await service.apply(tenant_id=TENANT_ID, payload=tightened, accepted_tokens=tokens)
    await session.commit()

    stored = (
        (
            await session.execute(
                select(AlignmentEdge).where(
                    AlignmentEdge.matrix_version_id == result.matrix_version_id,
                )
            )
        )
        .scalars()
        .all()
    )
    assert [edge.verdict for edge in stored] == [AlignmentVerdict.NEAR]


async def test_declining_a_removal_keeps_the_pair(session):
    """Dropping a verdict is a decision, so it must be accepted explicitly."""
    service = StandardsAlignmentImportService(session)
    await service.apply(tenant_id=TENANT_ID, payload=_minimal_payload("DIFFERENT"))
    await session.commit()

    shrunk = _minimal_payload("DIFFERENT")
    shrunk["rows"][0]["frameworks"].pop("14001")
    shrunk["rows"][0]["verdict"] = "UNIQUE"

    plan = await service.plan(tenant_id=TENANT_ID, payload=shrunk)
    removals = [item for item in plan.items if item.change_type == "removed"]
    assert len(removals) == 1

    result = await service.apply(tenant_id=TENANT_ID, payload=shrunk, accepted_tokens=[])
    await session.commit()

    stored = (
        (
            await session.execute(
                select(AlignmentEdge).where(
                    AlignmentEdge.matrix_version_id == result.matrix_version_id,
                )
            )
        )
        .scalars()
        .all()
    )
    verdicts = sorted(edge.verdict.value for edge in stored)
    assert "different" in verdicts, "the declined removal kept the original pair"


async def test_plan_writes_nothing(session, payload):
    service = StandardsAlignmentImportService(session)
    plan = await service.plan(tenant_id=TENANT_ID, payload=payload)
    assert plan.counts["added"] > 0
    assert plan.active_version_id is None

    versions = await session.scalar(select(func.count()).select_from(MatrixVersion))
    edges = await session.scalar(select(func.count()).select_from(AlignmentEdge))
    assert versions == 0
    assert edges == 0


# ------------------------------------------------------------- refusing garbage


def test_a_unique_row_with_two_frameworks_is_refused_not_guessed():
    """UNIQUE means exactly one framework asks. Two is a contradiction in the source."""
    contradictory = {
        "source_ref": "TEST",
        "version_label": "1.0",
        "rows": [
            {
                "row_key": "row-5.4",
                "clause_ref": "5.4",
                "title": "Consultation",
                "verdict": "UNIQUE",
                "frameworks": {
                    "45001": {"clause_number": "5.4"},
                    "9001": {"clause_number": "5.4"},
                },
            }
        ],
    }
    edges, warnings = build_edges(contradictory)
    assert edges == [], "nothing may be stored from a contradictory row"
    assert any("UNIQUE" in warning for warning in warnings)


def test_an_empty_payload_builds_no_edges_rather_than_raising():
    """``build_edges`` is pure: an empty payload is empty, and refusal is apply's job."""
    edges, warnings = build_edges({"source_ref": "TEST", "rows": []})
    assert edges == []
    assert warnings == []


async def test_apply_refuses_a_payload_that_produces_no_edges(session, payload):
    """An empty import must not be able to blank a tenant's live matrix."""
    service = StandardsAlignmentImportService(session)
    first = await service.apply(tenant_id=TENANT_ID, payload=payload)
    await session.commit()

    with pytest.raises(AlignmentImportError):
        await service.apply(tenant_id=TENANT_ID, payload={"source_ref": "PEL-HSEQ-5064", "rows": []})

    active = (
        (await session.execute(select(MatrixVersion).where(MatrixVersion.status == MatrixVersionStatus.ACTIVE)))
        .scalars()
        .all()
    )
    assert len(active) == 1
    assert active[0].id == first.matrix_version_id, "the live edition survived the refused import"


async def test_apply_refuses_a_payload_with_no_source_ref(session, payload):
    service = StandardsAlignmentImportService(session)
    with pytest.raises(AlignmentImportError):
        await service.apply(tenant_id=TENANT_ID, payload={**payload, "source_ref": ""})


# ------------------------------------------------------------------ seed shape


async def test_seed_coverage_holds_annex_sl_and_the_named_traps(session, payload):
    """The imported edition must actually contain the coverage the PR claims."""
    service = StandardsAlignmentImportService(session)
    await service.apply(tenant_id=TENANT_ID, payload=payload)
    await session.commit()

    read = StandardsAlignmentReadService(session)
    catalogue = await read.catalogue(tenant_id=TENANT_ID)

    assert catalogue["matrix_loaded"] is True
    clause_refs = {row["clauseNumber"] for row in catalogue["rows"]}
    # Annex SL 4 to 10 across the five management system standards.
    for clause in ("4.1", "4.2", "5.2", "5.3", "5.4", "6.1.2", "7.2", "7.5", "9.1.2", "9.2", "10.3"):
        assert clause in clause_refs, f"clause {clause} missing from imported catalogue"

    # Constructionline is out by decision, and that decision is recorded.
    assert "constructionline" in catalogue["excluded_frameworks"]
    assert "constructionline" not in catalogue["frameworks"]

    verdicts = {row["clauseNumber"]: row["verdict"] for row in catalogue["rows"]}
    assert verdicts["6.1.2"] == "DIFFERENT", "the most dangerous row must present as DIFFERENT"
    assert verdicts["5.4"] == "UNIQUE"
    assert verdicts["7.5"] == "EXACT"

    trap_rows = {row["clauseNumber"] for row in catalogue["rows"] if row["is_trap"]}
    for clause in ("5.2", "6.1.2", "8.1", "9.1.2"):
        assert clause in trap_rows, f"clause {clause} is a trap on sheet 07 and must be flagged"


async def test_catalogue_is_honestly_empty_before_any_import(session):
    read = StandardsAlignmentReadService(session)
    catalogue = await read.catalogue(tenant_id=TENANT_ID)
    assert catalogue["matrix_loaded"] is False
    assert catalogue["rows"] == []
    assert "fallback_note" in catalogue


async def test_one_tenants_matrix_is_not_visible_to_another(session, payload):
    """RLS enforces this in PostgreSQL; the query filters must agree with it."""
    service = StandardsAlignmentImportService(session)
    await service.apply(tenant_id=TENANT_ID, payload=payload)
    await session.commit()

    read = StandardsAlignmentReadService(session)
    other = await read.catalogue(tenant_id=TENANT_ID + 1)
    assert other["matrix_loaded"] is False
    assert other["rows"] == []
