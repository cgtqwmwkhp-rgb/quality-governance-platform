"""STEWARD-14 / CIT-1 — the fourteen accepted retention decisions.

Three things are load-bearing here and each has its own section below.

1. **The decisions never shorten retention.** A steward decision replaces prose
   that named two or more periods. If the accepted number is shorter than the
   longest period the prose names, the decision has quietly discarded a
   governance requirement — and disposal hard-deletes the row and the blob.
   :func:`test_no_decision_is_shorter_than_the_longest_period_its_prose_names`
   and :func:`test_no_decision_disposes_earlier_than_the_pre_cut1_parser` pin
   both directions of that.
2. **The cutover gate is actually clear.** `blockers` must be 0, which is the
   ADR-0023 / F-7 §2 precondition for retiring Citation (ATLAS) as the retention
   authority for the Register.
3. **A reseed no longer wipes a decision.** That was the defect: the seed
   re-derived both columns from prose on every run, so a resolved blocker was
   erased by the next redeploy or admin "reload seed".
"""

from __future__ import annotations

import ast
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from scripts.governance.library.citation_cutover_readiness import readiness_report
from src.domain.models.document_library import DocumentCategory, DocumentFunction, DocumentTag, PelDocRefCounter
from src.domain.services.document_category_seed_data import load_taxonomy_categories, machine_readable_retention
from src.domain.services.document_category_service import seed_document_categories
from src.domain.services.library_retention_policy import RetentionAnchor, resolve_retention_rule, retention_until_for
from src.domain.services.library_steward_retention import (
    SOURCE_STEWARD_DECISION,
    SOURCE_TAXONOMY_PROSE,
    STEWARD_DECISIONS_JSON_PATH,
    load_steward_retention_decisions,
    resolve_category_retention,
    steward_decision_for,
    steward_retention_decisions,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
TAXONOMY = REPO_ROOT / "specs" / "governance-library" / "taxonomy.json"
MIGRATION = REPO_ROOT / "alembic" / "versions" / "20261103_lib_steward14_retention_decisions.py"
STEWARD14_REVISION = "20261103_lib_steward14"
CUT1_REVISION = "20261102_lib_cut1_sor"

#: The decisions the steward accepted on 2026-08-10, restated here independently
#: of the JSON. A test that reads its expectations out of the file it is checking
#: asserts only that the file is self-consistent.
ACCEPTED_DECISIONS: dict[str, tuple[int, str]] = {
    "02.02": (40, "supersede"),
    "02.04": (6, "supersede"),
    "02.05": (3, "issue"),
    "02.06": (3, "issue"),
    "02.07": (6, "issue"),
    "02.08": (40, "issue"),
    "03.04": (3, "supersede"),
    "04.08": (40, "supersede"),
    "04.10": (40, "issue"),
    "06.02": (2, "issue"),
    "06.04": (2, "issue"),
    "07.03": (6, "supersede"),
    "08.03": (3, "issue"),
    "08.04": (6, "supersede"),
}

APPROVED_AT = datetime(2026, 1, 1, tzinfo=timezone.utc)
SUPERSEDED_AT = datetime(2040, 6, 15, tzinfo=timezone.utc)

# Exactly the expression `document_library_filing_service` used before CUT-1.
_PRE_CUT1_RE = re.compile(r"(\d+)\s*years?", re.IGNORECASE)
_DURATION_RE = re.compile(r"(\d+)\s*(year|month)s?", re.IGNORECASE)

#: Prose that says the current issue is kept as well as a period. Anchoring one
#: of these at `issue` would make the document disposable while it is still live,
#: which is the CUT-1 defect arriving by a new route.
_CURRENT_ISSUE_KEPT = "current"


def _taxonomy_by_id() -> dict[str, dict[str, object]]:
    payload = json.loads(TAXONOMY.read_text(encoding="utf-8"))
    return {row["id"]: row for row in payload["categories"]}


def _prose_for(taxonomy_id: str) -> str:
    rule = _taxonomy_by_id()[taxonomy_id].get("retention_rule")
    assert isinstance(rule, str) and rule, f"{taxonomy_id} has no retention_rule prose"
    return rule


def _months_named_in(prose: str) -> list[int]:
    """Every period the prose names, in months, so legs of different units compare."""
    return [int(amount) * (12 if unit.lower() == "year" else 1) for amount, unit in _DURATION_RE.findall(prose)]


def _pre_cut1_retention_until(rule: str) -> datetime | None:
    """The behaviour CUT-1 replaced, reproduced so the comparison is real."""
    text = rule.strip()
    if not text or text.lower() == "current":
        return None
    match = _PRE_CUT1_RE.search(text)
    if not match:
        return None
    years = int(match.group(1))
    if years <= 0:
        return None
    return APPROVED_AT + timedelta(days=years * 365)


def _earliest_disposal(taxonomy_id: str) -> datetime | None:
    """The earliest date a document in this category can become disposable."""
    policy = resolve_category_retention(taxonomy_id, _prose_for(taxonomy_id)).policy
    assert policy is not None
    return retention_until_for(policy, issued_at=APPROVED_AT) or retention_until_for(
        policy, superseded_at=SUPERSEDED_AT
    )


# ---------------------------------------------------------------------------
# The safety invariants
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("taxonomy_id", sorted(ACCEPTED_DECISIONS))
def test_no_decision_is_shorter_than_the_longest_period_its_prose_names(taxonomy_id: str) -> None:
    """The accepted number honours every leg of the prose, not the convenient one.

    Each of these rules names two or more periods (or one in months). Taking the
    shorter leg is precisely the pre-CUT-1 defect — "3 years minimum …;
    investigations 6 years" resolved to 3 and silently discarded the six-year
    investigation requirement. So the decision must be at least the *longest*
    period the prose names, and a sub-year period must round up, never down.
    """
    prose = _prose_for(taxonomy_id)
    decision = steward_decision_for(taxonomy_id)
    assert decision is not None
    named = _months_named_in(prose)
    assert named, f"{taxonomy_id}: prose names no period at all: {prose!r}"
    assert decision.years * 12 >= max(named), (
        f"{taxonomy_id}: accepted {decision.years} years but the prose names "
        f"{max(named)} months — the decision would discard a governance requirement: {prose!r}"
    )


@pytest.mark.parametrize("taxonomy_id", sorted(ACCEPTED_DECISIONS))
def test_no_decision_disposes_earlier_than_the_pre_cut1_parser(taxonomy_id: str) -> None:
    """No accepted decision brings a disposal date forward of the old behaviour.

    Converging retention onto one executable policy may keep documents longer.
    A single day earlier is a record destroyed before its governance rule allowed.
    """
    before = _pre_cut1_retention_until(_prose_for(taxonomy_id))
    after = _earliest_disposal(taxonomy_id)
    assert after is not None, f"{taxonomy_id} must now be computable"
    if before is None:
        # "15 months (longer if incident-related)" had no `\d+ years` match, so the
        # old parser produced no date at all and the document was kept forever.
        # A decision that makes it disposable is the *point* of CUT-1; the
        # longest-leg test above is what keeps it honest.
        return
    assert after >= before, f"{taxonomy_id} would be disposable at {after} but was {before} before CUT-1"


@pytest.mark.parametrize("taxonomy_id", sorted(ACCEPTED_DECISIONS))
def test_prose_naming_a_kept_current_issue_is_anchored_on_supersede(taxonomy_id: str) -> None:
    """A rule that keeps the current issue cannot start its clock at issue.

    "Current + superseded 6 years" counted from approval made a document
    disposable the day it stopped being current. Anchoring these on `supersede`
    is what stops a live document ever having a disposal date.
    """
    prose = _prose_for(taxonomy_id)
    decision = steward_decision_for(taxonomy_id)
    assert decision is not None
    if _CURRENT_ISSUE_KEPT not in prose.lower():
        return
    assert decision.anchor is RetentionAnchor.SUPERSEDE, (
        f"{taxonomy_id}: prose keeps the current issue but the decision anchors on "
        f"{decision.anchor.value}, which would date a live document: {prose!r}"
    )


def test_a_supersede_anchored_decision_gives_a_live_document_no_disposal_date() -> None:
    """02.02 COSHH: 40 years, but only once the assessment is superseded."""
    policy = resolve_category_retention("02.02", _prose_for("02.02")).policy
    assert policy is not None
    assert (policy.years, policy.anchor) == (40, RetentionAnchor.SUPERSEDE)
    assert retention_until_for(policy, issued_at=APPROVED_AT) is None
    assert retention_until_for(policy, superseded_at=SUPERSEDED_AT) == datetime(2080, 6, 15, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# The decision file is the single source of truth
# ---------------------------------------------------------------------------


def test_the_decision_file_records_exactly_the_accepted_fourteen() -> None:
    decisions = steward_retention_decisions()
    assert {
        taxonomy_id: (decision.years, decision.anchor.value) for taxonomy_id, decision in decisions.items()
    } == ACCEPTED_DECISIONS


def test_the_decision_file_records_who_accepted_it_and_when() -> None:
    """R19 wants a basis. An unattributed retention decision has none."""
    loaded = load_steward_retention_decisions()
    assert loaded.accepted_by
    assert loaded.accepted_on == "2026-08-10"
    for decision in loaded.decisions.values():
        assert decision.rationale, f"{decision.taxonomy_id} has no rationale"


def test_every_decision_names_a_filable_level_2_category() -> None:
    """A decision for an id no category carries is inert but reads as cleared."""
    by_id = _taxonomy_by_id()
    for taxonomy_id in ACCEPTED_DECISIONS:
        assert taxonomy_id in by_id, f"{taxonomy_id} is not in taxonomy.json"
        assert by_id[taxonomy_id]["level"] == 2, f"{taxonomy_id} is not a filable (level-2) category"


def test_the_decision_file_does_not_duplicate_the_taxonomy_prose() -> None:
    """F-7 §4 — one home per fact. The prose stays in taxonomy.json only."""
    raw = STEWARD_DECISIONS_JSON_PATH.read_text(encoding="utf-8")
    for taxonomy_id in ACCEPTED_DECISIONS:
        assert _prose_for(taxonomy_id) not in raw, f"{taxonomy_id}'s retention_rule prose is copied into the decisions"


def test_steward14_did_not_edit_the_taxonomy_prose() -> None:
    """Every one of the fourteen rules is still one the CUT-1 grammar refuses.

    If a rule had been reworded to make it parse, the decision would be
    decorative and the real change would be an unreviewed edit to the governance
    text.
    """
    for taxonomy_id in ACCEPTED_DECISIONS:
        assert resolve_retention_rule(_prose_for(taxonomy_id)).policy is None, (
            f"{taxonomy_id}'s prose now parses on its own — the decision file is no longer "
            "recording a steward judgement, so check whether the prose was edited"
        )


@pytest.mark.parametrize("taxonomy_id", sorted(ACCEPTED_DECISIONS))
def test_the_basis_stays_the_taxonomy_prose(taxonomy_id: str) -> None:
    """A decision is a reading of the governance text, not a replacement for it."""
    policy = resolve_category_retention(taxonomy_id, _prose_for(taxonomy_id)).policy
    assert policy is not None
    assert policy.basis == " ".join(_prose_for(taxonomy_id).split())


def test_a_category_without_a_decision_still_reads_its_prose() -> None:
    assert steward_decision_for("04.01") is None
    assert resolve_category_retention("04.01", "6 years") == resolve_retention_rule("6 years")
    assert resolve_category_retention(None, "6 years") == resolve_retention_rule("6 years")


@pytest.mark.parametrize(
    "payload",
    [
        {"accepted_by": "x", "accepted_on": "y", "decisions": []},
        {"accepted_by": "x", "accepted_on": "y", "decisions": [{"retention_years": 3, "retention_anchor": "issue"}]},
        {
            "accepted_by": "x",
            "accepted_on": "y",
            "decisions": [
                {"taxonomy_id": "01.01", "retention_years": 0, "retention_anchor": "issue", "rationale": "r"}
            ],
        },
        {
            "accepted_by": "x",
            "accepted_on": "y",
            "decisions": [
                {"taxonomy_id": "01.01", "retention_years": 3, "retention_anchor": "whenever", "rationale": "r"}
            ],
        },
        {
            "accepted_by": "x",
            "accepted_on": "y",
            "decisions": [
                # `event` and `indefinite` never yield a disposal date, so a
                # "decision" naming one clears no blocker while reading as if it did.
                {"taxonomy_id": "01.01", "retention_years": 3, "retention_anchor": "event", "rationale": "r"}
            ],
        },
        {
            "accepted_by": "x",
            "accepted_on": "y",
            "decisions": [{"taxonomy_id": "01.01", "retention_years": 3, "retention_anchor": "issue", "rationale": ""}],
        },
        {
            "accepted_by": "x",
            "accepted_on": "y",
            "decisions": [
                {"taxonomy_id": "01.01", "retention_years": 3, "retention_anchor": "issue", "rationale": "r"},
                {"taxonomy_id": "01.01", "retention_years": 6, "retention_anchor": "issue", "rationale": "r"},
            ],
        },
        {"decisions": [{"taxonomy_id": "01.01", "retention_years": 3, "retention_anchor": "issue", "rationale": "r"}]},
    ],
)
def test_a_malformed_decision_file_is_refused_not_partially_read(payload: dict, tmp_path: Path) -> None:
    """Half a decision set would be written to the database by the next reseed."""
    path = tmp_path / "steward_retention_decisions.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError):
        load_steward_retention_decisions(path)


# ---------------------------------------------------------------------------
# The cutover gate
# ---------------------------------------------------------------------------


def test_the_citation_cutover_gate_has_no_blockers_left() -> None:
    """ADR-0023 / F-7 §2 — the precondition for retiring Citation is now met."""
    summary = readiness_report()["summary"]
    assert summary["blockers"] == 0, f"expected no blockers, reasons: {summary['blocker_reasons']}"
    assert summary["blocker_reasons"] == {}
    assert summary["steward_decisions"] == len(ACCEPTED_DECISIONS)
    assert summary["steward_decisions_applied"] == len(ACCEPTED_DECISIONS)
    assert summary["orphan_steward_decisions"] == 0


def test_the_gate_still_accounts_for_every_filable_category() -> None:
    """Clearing the blockers must move them into `computable`, not out of the report."""
    report = readiness_report()
    summary = report["summary"]
    assert summary["filable_categories"] == 73
    assert summary["computable"] + summary["no_disposal_clock"] + summary["blockers"] == 73
    # CUT-1 shipped 28 computable with 14 blocked; the fourteen decisions are
    # computable by construction (`issue` / `supersede` only).
    assert summary["computable"] == 42
    assert summary["no_disposal_clock"] == 31


def test_the_gate_says_which_categories_were_decided_rather_than_derived() -> None:
    report = readiness_report()
    decided = {row["taxonomy_id"] for row in report["steward_decided"]}
    assert decided == set(ACCEPTED_DECISIONS)
    for row in report["computable"]:
        assert row["source"] in (SOURCE_STEWARD_DECISION, SOURCE_TAXONOMY_PROSE)
        if row["taxonomy_id"] in ACCEPTED_DECISIONS:
            assert row["source"] == SOURCE_STEWARD_DECISION
            assert row["steward_rationale"]
        else:
            assert row["source"] == SOURCE_TAXONOMY_PROSE
            assert row["steward_rationale"] is None


def test_fail_on_blockers_exits_zero_now_that_the_gate_is_clear() -> None:
    """CIT-1 wires this flag into CI, so a re-opened blocker must fail the build."""
    from scripts.governance.library.citation_cutover_readiness import main

    assert main(["--fail-on-blockers"]) == 0
    assert main(["--json", "--fail-on-blockers"]) == 0


# ---------------------------------------------------------------------------
# The seed prefers the decision, and a reseed no longer erases it
# ---------------------------------------------------------------------------


def test_the_seed_loader_projects_the_decision_onto_the_category_columns() -> None:
    rows = {row["taxonomy_id"]: row for row in load_taxonomy_categories()}
    for taxonomy_id, (years, anchor) in ACCEPTED_DECISIONS.items():
        assert (rows[taxonomy_id]["retention_years"], rows[taxonomy_id]["retention_anchor"]) == (years, anchor)
        # The prose is carried through untouched — it is still the R19 basis.
        assert rows[taxonomy_id]["retention_rule"] == _prose_for(taxonomy_id)


def test_the_seed_loader_still_derives_undecided_categories_from_prose() -> None:
    rows = {row["taxonomy_id"]: row for row in load_taxonomy_categories()}
    row = rows["04.01"]
    expected = resolve_retention_rule(row["retention_rule"]).policy
    assert expected is not None
    assert (row["retention_years"], row["retention_anchor"]) == (expected.years, expected.anchor.value)


def test_an_undecided_unreadable_rule_still_projects_to_null() -> None:
    """Refusal is still the default. A decision is the only way out of a blocker."""
    assert machine_readable_retention("99.99", "Tacho data 12 months; working time records 2 years") == {
        "retention_years": None,
        "retention_anchor": None,
    }


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
        await conn.run_sync(DocumentFunction.__table__.create)
        await conn.run_sync(DocumentTag.__table__.create)
        await conn.run_sync(PelDocRefCounter.__table__.create)

    async with session_factory() as session:
        yield session

    await engine.dispose()


async def _retention_by_taxonomy_id(db: AsyncSession) -> dict[str, tuple[int | None, str | None]]:
    result = await db.execute(
        select(
            DocumentCategory.taxonomy_id,
            DocumentCategory.retention_years,
            DocumentCategory.retention_anchor,
        )
    )
    return {row[0]: (row[1], row[2]) for row in result.all()}


@pytest.mark.asyncio
async def test_seed_writes_the_accepted_decisions_to_the_category_rows(isolated_db_session: AsyncSession) -> None:
    await seed_document_categories(isolated_db_session)
    await isolated_db_session.commit()

    stored = await _retention_by_taxonomy_id(isolated_db_session)
    for taxonomy_id, (years, anchor) in ACCEPTED_DECISIONS.items():
        assert stored[taxonomy_id] == (years, anchor), taxonomy_id


@pytest.mark.asyncio
async def test_reseeding_does_not_wipe_the_steward_decisions(isolated_db_session: AsyncSession) -> None:
    """The defect this closes.

    The seed re-derived both columns from prose on every run, so the fourteen
    decided categories were reset to NULL by any reseed — a redeploy, a CI smoke
    run, or an admin clicking "reload seed" — and Citation quietly stopped being
    retired for them.
    """
    await seed_document_categories(isolated_db_session)
    await isolated_db_session.commit()
    for _ in range(3):
        await seed_document_categories(isolated_db_session)
        await isolated_db_session.commit()

    stored = await _retention_by_taxonomy_id(isolated_db_session)
    for taxonomy_id, (years, anchor) in ACCEPTED_DECISIONS.items():
        assert stored[taxonomy_id] == (years, anchor), f"{taxonomy_id} lost its decision on reseed"


@pytest.mark.asyncio
async def test_reseed_restores_a_decision_someone_cleared_by_hand(isolated_db_session: AsyncSession) -> None:
    """The decision file wins on reseed, exactly as the deactivation list does."""
    await seed_document_categories(isolated_db_session)
    await isolated_db_session.commit()

    category = (
        await isolated_db_session.execute(select(DocumentCategory).where(DocumentCategory.taxonomy_id == "02.08"))
    ).scalar_one()
    category.retention_years = None
    category.retention_anchor = None
    await isolated_db_session.commit()

    await seed_document_categories(isolated_db_session)
    await isolated_db_session.commit()

    stored = await _retention_by_taxonomy_id(isolated_db_session)
    assert stored["02.08"] == ACCEPTED_DECISIONS["02.08"]


@pytest.mark.asyncio
async def test_seed_leaves_undecided_unreadable_categories_null(isolated_db_session: AsyncSession) -> None:
    """Only the fourteen were decided; nothing else gained a number."""
    await seed_document_categories(isolated_db_session)
    await isolated_db_session.commit()

    stored = await _retention_by_taxonomy_id(isolated_db_session)
    for row in load_taxonomy_categories():
        taxonomy_id = row["taxonomy_id"]
        if taxonomy_id in ACCEPTED_DECISIONS:
            continue
        expected = resolve_retention_rule(row["retention_rule"]).policy
        assert stored[taxonomy_id] == (
            (expected.years, expected.anchor.value) if expected else (None, None)
        ), taxonomy_id


# ---------------------------------------------------------------------------
# The migration snapshot must still agree with the decision file
# ---------------------------------------------------------------------------


def _migration_constant(name: str) -> object:
    """Read a literal out of the migration without importing alembic machinery."""
    tree = ast.parse(MIGRATION.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == name:
            assert node.value is not None
            return ast.literal_eval(node.value)
    raise AssertionError(f"{name} not found in {MIGRATION.name}")


def test_migration_declares_steward14_once_and_sits_on_cut1() -> None:
    text = MIGRATION.read_text(encoding="utf-8")
    assert f'revision: str = "{STEWARD14_REVISION}"' in text
    assert f'down_revision: Union[str, Sequence[str], None] = "{CUT1_REVISION}"' in text
    declarers = [
        path
        for path in (REPO_ROOT / "alembic" / "versions").rglob("*.py")
        if path.is_file() and f'revision: str = "{STEWARD14_REVISION}"' in path.read_text(encoding="utf-8")
    ]
    assert declarers == [MIGRATION], f"exactly one file may declare {STEWARD14_REVISION}, found {declarers}"


def test_migration_snapshot_still_matches_the_decision_file() -> None:
    """The frozen literal is only safe while it agrees with the accepted decisions."""
    frozen = {
        taxonomy_id: (years, anchor)
        for taxonomy_id, years, anchor in _migration_constant("STEWARD_RETENTION_DECISIONS")
    }
    assert frozen == ACCEPTED_DECISIONS


def test_migration_touches_only_category_retention_columns() -> None:
    """No schema change, no `retention_until` rewrite, no other table."""
    tree = ast.parse(MIGRATION.read_text(encoding="utf-8"))
    statements = [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and re.search(r"\b(UPDATE|ALTER TABLE|INSERT INTO|DELETE FROM|DROP)\b", node.value)
    ]
    assert statements, "expected the migration to carry its SQL as literals"
    for statement in statements:
        assert statement.startswith("UPDATE document_categories "), statement
        assert "retention_until" not in statement, statement
        assert "controlled_documents" not in statement, statement


def test_migration_downgrade_clears_only_the_fourteen() -> None:
    """Downgrade returns them to the NULL CUT-1 left, and touches nothing else."""
    source = MIGRATION.read_text(encoding="utf-8")
    downgrade = source[source.index("def downgrade()") :]
    assert "retention_years = NULL, retention_anchor = NULL" in downgrade
    assert "WHERE taxonomy_id = :taxonomy_id" in downgrade
    assert "STEWARD_RETENTION_DECISIONS" in downgrade
