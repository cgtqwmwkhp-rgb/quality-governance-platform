"""TrapGuard: the shared clause number that is not a shared requirement.

PEL-HSEQ-5064 sheet 07 names the failure this guards against. Clause 6.1.2 is one
number and five different requirements — an environmental aspects register, a
hazard identification, an information security risk assessment, a business impact
analysis. Clause 9.1.2 is worse, because two of the five *are* near identical
(ISO 14001 and ISO 45001 evaluation of compliance) while ISO 9001 9.1.2 is
customer satisfaction and shares nothing but the digits.

So the tests below are not "does the guard return a value". They are:

* does it refuse the crossings the source says are traps, and
* does it still permit the two crossings the source says are real, and
* does it leave everything else exactly as PR-B had it?

The last one matters most. This guard narrows an existing tolerant match, and a
guard that over-refuses would blank a working matrix — which is why the no-matrix
case must permit, and why a bare clause token must never be blocked.
"""

from __future__ import annotations

import pytest

from src.domain.models.standards_alignment import (
    AlignmentEdge,
    AlignmentVerdict,
    MatrixVersion,
    MatrixVersionStatus,
    canonical_alignment_pair,
)
from src.domain.services.standards_alignment_import_service import build_edges, load_payload
from src.domain.services.standards_cell_aggregate_service import FRAMEWORK_ALIASES
from src.domain.services.standards_tech_gap_guard import CYBER_ESSENTIALS_ID, CYBER_ESSENTIALS_PLUS_ID
from src.domain.services.standards_tech_gap_guard import requirement_for as tech_gap_requirement_for
from src.domain.services.standards_trap_guard import (
    ALIGNMENT_FRAMEWORK_IDS,
    TrapGuard,
    alignment_clause_key,
    clause_key,
    clause_number_from_token,
    framework_from_clause_token,
)


def _edge(
    *,
    src_framework: str,
    src_clause: str,
    dst_framework: str | None,
    dst_clause: str | None,
    verdict: AlignmentVerdict,
    clause_ref: str,
    addition_text: str | None = None,
) -> AlignmentEdge:
    """An unsaved edge in canonical order, as the import service would store it."""
    src_fw, src_key, dst_fw, dst_key = canonical_alignment_pair(
        src_framework,
        f"{src_framework}-{src_clause}",
        dst_framework,
        f"{dst_framework}-{dst_clause}" if dst_framework else None,
    )
    return AlignmentEdge(
        tenant_id=1,
        matrix_version_id=1,
        row_key=f"annexsl-{clause_ref}",
        clause_ref=clause_ref,
        title=clause_ref,
        src_framework=src_fw,
        src_clause_key=src_key,
        dst_framework=dst_fw,
        dst_clause_key=dst_key,
        verdict=verdict,
        row_verdict=verdict,
        is_pair_override=False,
        addition_text=addition_text,
    )


@pytest.fixture
def guard_5064() -> TrapGuard:
    """A guard loaded from the checked-in 5064 payload, not from hand-written rows.

    Using the real payload means these tests fail if the extraction ever stops
    producing the verdicts the source prints — which is the failure that would
    matter, and which hand-written fixtures could not detect.
    """
    edges, warnings = build_edges(load_payload())
    assert warnings == [], f"payload built with warnings: {warnings}"
    stored = [
        AlignmentEdge(
            tenant_id=1,
            matrix_version_id=1,
            row_key=edge.row_key,
            clause_ref=edge.clause_ref,
            title=edge.title,
            src_framework=edge.key.src_framework,
            src_clause_key=edge.key.src_clause_key,
            src_clause_label=edge.src_clause_label,
            dst_framework=edge.key.dst_framework,
            dst_clause_key=edge.key.dst_clause_key,
            dst_clause_label=edge.dst_clause_label,
            verdict=edge.verdict,
            row_verdict=edge.row_verdict,
            is_pair_override=edge.is_pair_override,
            addition_text=edge.addition_text,
            rationale=edge.rationale,
        )
        for edge in edges
    ]
    version = MatrixVersion(
        tenant_id=1,
        source_ref="PEL-HSEQ-5064",
        version_label="1.0",
        title="Standards Alignment Matrix",
        source_checksum="test",
        status=MatrixVersionStatus.ACTIVE,
    )
    return TrapGuard(edges=stored, version=version)


# --------------------------------------------------------------------- parsing


@pytest.mark.parametrize(
    ("token", "expected_framework", "expected_clause"),
    [
        ("14001-9.1.2", "14001", "9.1.2"),
        ("iso9001:7.5", "9001", "7.5"),
        ("iso_45001-6.1.2", "45001", "6.1.2"),
        ("ce-a.8.5", "ce", "a.8.5"),
        # A bare clause number commits to no framework, so it can never be a
        # cross-framework claim and must never be blocked.
        ("7.5", None, "7.5"),
        ("", None, ""),
        (None, None, ""),
    ],
)
def test_token_framework_and_clause_are_parsed(token, expected_framework, expected_clause):
    assert framework_from_clause_token(token) == expected_framework
    assert clause_number_from_token(token) == expected_clause


def test_alignment_framework_ids_agree_with_the_matrix_column_registry():
    """Every alignment id has a matrix column; there are no alignment-only ids."""
    assert set(ALIGNMENT_FRAMEWORK_IDS) == set(FRAMEWORK_ALIASES)


def test_cyber_essentials_is_keyed_to_its_own_matrix_column():
    """`ce` is Cyber Essentials, not a carbon scheme."""
    assert CYBER_ESSENTIALS_ID == "ce"
    assert CYBER_ESSENTIALS_PLUS_ID == "cep"
    assert FRAMEWORK_ALIASES[CYBER_ESSENTIALS_ID]["cert_schemes"][0] == "cyber_essentials"
    requirement = tech_gap_requirement_for("ce", "user_access_control")
    assert requirement is not None
    assert "27001" in requirement.frameworks


# ------------------------------------------------------------ the 6.1.2 traps


@pytest.mark.parametrize(
    ("framework_a", "framework_b"),
    [
        ("9001", "14001"),
        ("9001", "45001"),
        ("9001", "27001"),
        ("9001", "22301"),
        ("14001", "45001"),
        ("14001", "27001"),
        ("14001", "22301"),
        ("45001", "27001"),
        ("45001", "22301"),
        ("27001", "22301"),
    ],
)
def test_clause_6_1_2_never_crosses_between_any_two_standards(guard_5064, framework_a, framework_b):
    """The most dangerous row in the matrix: five standards, five requirements.

    Every one of the ten pairs must refuse. An aspects and impacts register does
    not identify hazards, and a hazard identification does not perform a business
    impact analysis.
    """
    decision = guard_5064.may_share_evidence(
        src_framework=framework_a,
        src_clause="6.1.2",
        dst_framework=framework_b,
        dst_clause="6.1.2",
    )
    assert decision.allowed is False
    assert decision.verdict is AlignmentVerdict.DIFFERENT
    assert "6.1.2" in (decision.clause_ref or "")


def test_clause_9_1_2_refuses_iso_9001_but_permits_the_14001_45001_pair(guard_5064):
    """The subset the source names explicitly must survive the row's DIFFERENT verdict.

    ISO 9001 9.1.2 is customer satisfaction. ISO 14001 and ISO 45001 9.1.2 are both
    evaluation of compliance and one register genuinely serves both — the largest
    single evidence saving on this row. A row-level verdict alone would lose it.
    """
    for other in ("14001", "45001"):
        refused = guard_5064.may_share_evidence(
            src_framework="9001", src_clause="9.1.2", dst_framework=other, dst_clause="9.1.2"
        )
        assert refused.allowed is False
        assert refused.verdict is AlignmentVerdict.DIFFERENT

    permitted = guard_5064.may_share_evidence(
        src_framework="14001", src_clause="9.1.2", dst_framework="45001", dst_clause="9.1.2"
    )
    assert permitted.allowed is True
    assert permitted.verdict is AlignmentVerdict.NEAR
    assert permitted.addition_text, "a NEAR verdict must name what the deliverable carries"


def test_exact_rows_share_evidence(guard_5064):
    """7.5 documented information is identical in all five — the largest alignment."""
    decision = guard_5064.may_share_evidence(
        src_framework="9001", src_clause="7.5", dst_framework="27001", dst_clause="7.5"
    )
    assert decision.allowed is True
    assert decision.verdict is AlignmentVerdict.EXACT


def test_unique_clause_refuses_every_other_framework(guard_5064):
    """45001 5.4 consultation has no equivalent in 9001, 14001, 27001 or 22301."""
    assert guard_5064.unique_edge_for("45001", "5.4") is not None
    decision = guard_5064.may_share_evidence(
        src_framework="45001", src_clause="5.4", dst_framework="9001", dst_clause="5.4"
    )
    assert decision.allowed is False
    assert decision.verdict is AlignmentVerdict.UNIQUE


def test_unique_clause_still_permits_the_alignment_the_source_states(guard_5064):
    """5.4 is UNIQUE among the five standards *and* EXACT against IiP indicator 3.

    Both statements are in the source and they do not contradict: UNIQUE is a claim
    about the five management system standards, and the IiP pairing is a claim about
    a different framework. An explicit pair edge must win over the UNIQUE default.
    """
    decision = guard_5064.may_share_evidence(
        src_framework="45001", src_clause="5.4", dst_framework="iip", dst_clause="IIP 3"
    )
    assert decision.allowed is True
    assert decision.verdict is AlignmentVerdict.EXACT


# ------------------------------------------------------- aggregate integration


def test_cross_framework_token_is_dropped_on_a_trap_row(guard_5064):
    """A 14001 compliance-evaluation link must not cover the ISO 9001 9.1.2 cell.

    This is the concrete bug the guard exists for: the aggregate's suffix rule
    matches ``14001-9.1.2`` onto the 9001 9.1.2 cell because the numbers agree.
    """
    kept, blocked = guard_5064.filter_cross_framework_tokens(
        framework="9001",
        clause_number="9.1.2",
        tokens=["14001-9.1.2"],
    )
    assert kept == []
    assert len(blocked) == 1
    assert blocked[0]["verdict"] == "DIFFERENT"
    assert blocked[0]["token_framework"] == "14001"


def test_same_framework_and_bare_tokens_are_never_dropped(guard_5064):
    """The guard must only ever remove a cross-framework claim on a trap row."""
    kept, blocked = guard_5064.filter_cross_framework_tokens(
        framework="9001",
        clause_number="9.1.2",
        tokens=["9001-9.1.2", "9.1.2", "iso9001:9.1.2"],
    )
    assert blocked == []
    assert len(kept) == 3


def test_cross_framework_token_survives_where_the_matrix_permits_sharing(guard_5064):
    """14001 evidence on the 45001 9.1.2 cell is a real saving, not a trap."""
    kept, blocked = guard_5064.filter_cross_framework_tokens(
        framework="45001",
        clause_number="9.1.2",
        tokens=["14001-9.1.2"],
    )
    assert blocked == []
    assert kept == ["14001-9.1.2"]


def test_an_unloaded_guard_permits_everything_and_says_so():
    """No imported matrix must mean no opinion — never a silently emptied matrix."""
    guard = TrapGuard()
    assert guard.is_loaded is False
    assert guard.version_label is None

    decision = guard.may_share_evidence(
        src_framework="9001", src_clause="6.1.2", dst_framework="45001", dst_clause="6.1.2"
    )
    assert decision.allowed is True
    assert "no alignment matrix imported" in decision.reason

    kept, blocked = guard.filter_cross_framework_tokens(framework="9001", clause_number="6.1.2", tokens=["45001-6.1.2"])
    assert kept == ["45001-6.1.2"]
    assert blocked == []


def test_a_pair_the_matrix_says_nothing_about_is_not_treated_as_a_trap(guard_5064):
    """Absence of a verdict is absence of a verdict, not a refusal.

    Sheet 03's 93 Annex A controls are not imported by this edition. A cell inside
    them must behave exactly as it did in PR-B rather than turning into a trap.
    """
    decision = guard_5064.may_share_evidence(
        src_framework="27001", src_clause="A.8.24", dst_framework="9001", dst_clause="A.8.24"
    )
    assert decision.allowed is True
    assert decision.verdict is None


def test_annotate_cell_reports_the_row_verdict_and_trap_peers(guard_5064):
    annotation = guard_5064.annotate_cell(framework="9001", clause_number="6.1.2")
    assert annotation["matrix_loaded"] is True
    assert annotation["row_verdict"] == "DIFFERENT"
    assert annotation["is_trap_row"] is True
    assert annotation["trap_peer_count"] == 4
    assert all(peer["shareable"] is False for peer in annotation["peers"])

    exact = guard_5064.annotate_cell(framework="9001", clause_number="7.5")
    assert exact["row_verdict"] == "EXACT"
    assert exact["is_trap_row"] is False
    assert exact["peers"], "7.5 aligns with the other four standards"


def test_annotate_cell_resolves_relocated_clause_row_verdicts(guard_5064):
    """Framework-local numbers that differ from the printed row still show the row verdict."""
    relocated_trap = guard_5064.annotate_cell(framework="45001", clause_number="8.1.3")
    assert relocated_trap["row_verdict"] == "DIFFERENT"
    assert relocated_trap["is_trap_row"] is True

    near_relocated = guard_5064.annotate_cell(framework="27001", clause_number="6.1")
    assert near_relocated["row_verdict"] == "NEAR"
    assert near_relocated["is_trap_row"] is False

    dual_row = guard_5064.annotate_cell(framework="14001", clause_number="8.1")
    assert dual_row["row_verdict"] == "DIFFERENT"


def test_annotate_cell_on_an_unknown_clause_is_empty_not_wrong(guard_5064):
    annotation = guard_5064.annotate_cell(framework="9001", clause_number="99.9")
    assert annotation["row_verdict"] is None
    assert annotation["is_trap_row"] is False
    assert annotation["peers"] == []


# ------------------------------------------- Wave 4: what the guard may not lend


def test_the_guard_knows_which_frameworks_the_edition_actually_carries(guard_5064):
    """5064 prints six frameworks. The matrix shows twelve. Six have no axis at all."""
    for carried in ("9001", "14001", "45001", "27001", "22301", "iip", "ce", "cep"):
        assert guard_5064.covers_framework(carried) is True
    for absent in ("chas", "ssip", "uvdb", "pm"):
        assert guard_5064.covers_framework(absent) is False
    assert TrapGuard().covers_framework("9001") is False


def test_frameworks_on_row_lists_only_the_frameworks_the_row_prints(guard_5064):
    assert guard_5064.frameworks_on_row("7.2") == frozenset({"9001", "14001", "45001", "27001", "22301"})
    assert guard_5064.frameworks_on_row("99.9") == frozenset()


@pytest.mark.parametrize("framework", ["chas", "ssip", "uvdb", "pm"])
def test_a_framework_absent_from_the_edition_never_borrows_the_iso_row_verdict(guard_5064, framework):
    """The bug this wave exists for: CHAS 7.2 read ISO 7.2's EXACT and confirmed.

    Competence is a real CHAS question, but nobody has aligned it to ISO 9001 7.2 in
    an imported edition, so the honest answer for the cell is that we do not know.
    """
    annotation = guard_5064.annotate_cell(framework=framework, clause_number="7.2")
    assert annotation["row_verdict"] is None
    assert annotation["framework_covered"] is False
    assert annotation["alignment_known"] is False
    assert annotation["peers"] == []


def test_the_iso_row_verdict_is_unchanged_for_frameworks_on_the_row(guard_5064):
    """The narrowing must cost the ISO columns nothing — they are on the row."""
    annotation = guard_5064.annotate_cell(framework="9001", clause_number="7.2")
    assert annotation["row_verdict"] == "EXACT"
    assert annotation["framework_covered"] is True
    assert annotation["alignment_known"] is True
    # Four ISO peers plus IiP indicator 7, which the source does align to 9001 7.2.
    assert {peer["framework"] for peer in annotation["peers"]} == {"14001", "45001", "27001", "22301", "iip"}


def test_a_cross_framework_token_needs_an_imported_verdict_not_merely_no_objection(guard_5064):
    """IiP is in the edition, but not on the 6.1.2 row, so an ISO CEL cannot paint it.

    The old rule kept any pair the matrix had no verdict for, which is how one ISO
    risk assessment link painted columns that never asked the question.
    """
    kept, blocked = guard_5064.filter_cross_framework_tokens(
        framework="iip",
        clause_number="6.1.2",
        tokens=["9001-6.1.2"],
    )
    assert kept == []
    assert len(blocked) == 1
    assert blocked[0]["verdict"] is None
    assert "no imported alignment" in blocked[0]["reason"]


def test_may_share_evidence_still_answers_no_verdict_as_no_opinion(guard_5064):
    """Matching got stricter; the pair question did not change its meaning."""
    decision = guard_5064.may_share_evidence(
        src_framework="9001", src_clause="6.1.2", dst_framework="iip", dst_clause="6.1.2"
    )
    assert decision.allowed is True
    assert decision.verdict is None


def test_canonical_pair_ordering_is_stable_in_both_directions():
    """Edges are stored once per unordered pair, so both call orders must agree.

    The DB has no CHECK enforcing the ordering (``<`` on text is collation
    dependent), which makes this assertion the enforcement.
    """
    forward = canonical_alignment_pair("9001", "9001-7.5", "14001", "14001-7.5")
    reverse = canonical_alignment_pair("14001", "14001-7.5", "9001", "9001-7.5")
    assert forward == reverse
    assert forward[0] == "14001", "byte order puts 14001 before 9001"

    unique = canonical_alignment_pair("45001", "45001-5.4", None, None)
    assert unique == ("45001", "45001-5.4", None, None)


def test_row_verdict_prefers_the_most_restrictive_verdict_on_the_row():
    """A row with one DIFFERENT pair must not present itself as NEAR."""
    guard = TrapGuard(
        edges=[
            _edge(
                src_framework="14001",
                src_clause="6.1.3",
                dst_framework="45001",
                dst_clause="6.1.3",
                verdict=AlignmentVerdict.NEAR,
                clause_ref="6.1.3",
            ),
            _edge(
                src_framework="14001",
                src_clause="6.1.3",
                dst_framework="27001",
                dst_clause="6.1.3",
                verdict=AlignmentVerdict.DIFFERENT,
                clause_ref="6.1.3",
            ),
        ],
        version=MatrixVersion(
            tenant_id=1,
            source_ref="PEL-HSEQ-5064",
            version_label="1.0",
            title="t",
            source_checksum="c",
            status=MatrixVersionStatus.ACTIVE,
        ),
    )
    assert guard.row_verdict("6.1.3") is AlignmentVerdict.DIFFERENT


def test_clause_key_stays_case_preserving_for_catalogue_join():
    """W5 IiP catalogue keys are ``iip-IIP 7``; alignment lookup lowercases separately."""
    assert clause_key("iip", "IIP 7") == "iip-IIP 7"
    assert alignment_clause_key("iip", "IIP 7") == "iip-iip 7"


def test_iip_exact_peers_are_visible_when_the_clause_is_printed_uppercase(guard_5064):
    """The stored key is lowercased; the matrix asks for ``IIP 7``."""
    annotation = guard_5064.annotate_cell(framework="iip", clause_number="IIP 7")
    assert annotation["row_verdict"] == "EXACT"
    peers = {peer["framework"] for peer in annotation["peers"]}
    assert peers == {"9001", "14001", "45001", "27001", "22301"}
    assert annotation["alignment_known"] is True


def test_ce_plus_near_peers_do_not_invent_exact(guard_5064):
    annotation = guard_5064.annotate_cell(framework="ce", clause_number="firewalls")
    assert annotation["row_verdict"] == "NEAR"
    assert annotation["framework_covered"] is True
    assert len(annotation["peers"]) == 1
    assert annotation["peers"][0]["framework"] == "cep"
    assert annotation["peers"][0]["verdict"] == "NEAR"
    assert annotation["peers"][0]["shareable"] is True
    assert "independent" in (annotation["peers"][0]["addition_text"] or "").lower()


def test_ce_iso_numbered_cells_still_do_not_borrow_the_iso_row(guard_5064):
    annotation = guard_5064.annotate_cell(framework="ce", clause_number="7.2")
    assert annotation["row_verdict"] is None
    assert annotation["peers"] == []
