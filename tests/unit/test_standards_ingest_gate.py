"""Unit tests for Standards ingest auto-confirm gate (Wave 3 PR-E slice 1)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src.domain.models.standards_alignment import AlignmentEdge, MatrixVersion, MatrixVersionStatus
from src.domain.services.standards_alignment_import_service import build_edges, load_payload
from src.domain.services.standards_ingest_gate import (
    STANDARDS_AUTO_CONFIRM_THRESHOLD,
    CoverBlockIndex,
    StandardsAutoConfirmContext,
    evaluate,
)
from src.domain.services.standards_trap_guard import TrapGuard


@pytest.fixture
def guard_5064() -> TrapGuard:
    edges, warnings = build_edges(load_payload())
    assert warnings == []
    stored = [
        AlignmentEdge(
            tenant_id=1,
            matrix_version_id=17,
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
    version.id = 17
    return TrapGuard(edges=stored, version=version)


def _ctx(guard: TrapGuard, *, blocked: str | None = None) -> StandardsAutoConfirmContext:
    cover = CoverBlockIndex(guard=guard)
    if blocked:
        cover.blocked_for = MagicMock(return_value=blocked)  # type: ignore[method-assign]
    else:
        cover.blocked_for = MagicMock(return_value=None)  # type: ignore[method-assign]
    return StandardsAutoConfirmContext(guard=guard, cover=cover)


def test_threshold_constant_is_098():
    assert STANDARDS_AUTO_CONFIRM_THRESHOLD == 0.98


@pytest.mark.parametrize(
    ("confidence", "expect_confirm"),
    [
        (0.979, False),
        (97.9, False),
        (0.98, True),
        (98.0, True),
        (1.0, True),
    ],
)
def test_threshold_boundary(guard_5064, confidence, expect_confirm):
    # 7.5 is EXACT across frameworks in 5064.
    annotation = guard_5064.annotate_cell(framework="9001", clause_number="7.5")
    assert annotation["row_verdict"] == "EXACT"
    decision = evaluate(
        confidence=confidence,
        doc_type="procedure",
        clause_id="9001-7.5",
        context=_ctx(guard_5064),
    )
    assert decision.auto_confirm is expect_confirm
    if not expect_confirm and confidence < 98:
        assert decision.reason == "below_threshold"


def test_matrix_not_loaded_refuses_even_at_full_confidence():
    decision = evaluate(
        confidence=1.0,
        doc_type="procedure",
        clause_id="9001-7.5",
        context=None,
    )
    assert decision.auto_confirm is False
    assert decision.reason == "matrix_not_loaded"


def test_empty_guard_refuses(guard_5064):
    empty = TrapGuard()
    decision = evaluate(
        confidence=1.0,
        doc_type="procedure",
        clause_id="9001-7.5",
        context=_ctx(empty),
    )
    assert decision.auto_confirm is False
    assert decision.reason == "matrix_not_loaded"


def test_different_row_refuses(guard_5064):
    annotation = guard_5064.annotate_cell(framework="9001", clause_number="6.1.2")
    assert annotation["row_verdict"] == "DIFFERENT"
    decision = evaluate(
        confidence=1.0,
        doc_type="procedure",
        clause_id="9001-6.1.2",
        context=_ctx(guard_5064),
    )
    assert decision.auto_confirm is False
    assert decision.reason == "alignment_different"


def test_near_row_refuses(guard_5064):
    # Find a NEAR row if present.
    for clause in ("9.1.2", "8.1", "6.1", "7.4"):
        annotation = guard_5064.annotate_cell(framework="14001", clause_number=clause)
        if annotation["row_verdict"] == "NEAR":
            decision = evaluate(
                confidence=1.0,
                doc_type="procedure",
                clause_id=f"14001-{clause}",
                context=_ctx(guard_5064),
            )
            assert decision.reason == "alignment_near_requires_addition"
            assert decision.auto_confirm is False
            return
    pytest.skip("no NEAR row found in fixture payload")


def test_open_nc_blocks_exact_cell(guard_5064):
    decision = evaluate(
        confidence=1.0,
        doc_type="procedure",
        clause_id="9001-7.5",
        context=_ctx(guard_5064, blocked="cover_blocked_open_nc"),
    )
    assert decision.auto_confirm is False
    assert decision.reason == "cover_blocked_open_nc"


def test_strict_doc_type_refuses(guard_5064):
    decision = evaluate(
        confidence=1.0,
        doc_type="rams",
        clause_id="9001-7.5",
        context=_ctx(guard_5064),
    )
    assert decision.auto_confirm is False
    assert decision.reason == "strict_doc_type"


@pytest.mark.parametrize("clause_id", ["chas-7.2", "ssip-7.2", "ce-7.2", "cep-7.2", "uvdb-7.2", "pm-7.2"])
def test_a_framework_with_no_imported_alignment_cannot_machine_confirm(guard_5064, clause_id):
    """0.99 confidence on a framework nobody has aligned is still not an alignment.

    ISO 7.2 is EXACT across the five standards, and the row verdict used to be read
    onto every column that printed the same number. CHAS, SSIP and Cyber Essentials
    then auto-confirmed with zero EXACT peers of their own — a machine confirmation
    written into the audit trail on the strength of a shared digit.
    """
    decision = evaluate(
        confidence=0.99,
        doc_type="procedure",
        clause_id=clause_id,
        context=_ctx(guard_5064),
    )
    assert decision.auto_confirm is False
    assert decision.reason == "alignment_not_exact_for_framework"


def test_a_framework_in_the_edition_but_absent_from_the_row_also_refuses(guard_5064):
    """IiP has imported edges, but none on 7.2 — coverage of the framework is not enough."""
    assert guard_5064.covers_framework("iip") is True
    decision = evaluate(
        confidence=0.99,
        doc_type="procedure",
        clause_id="iip-7.2",
        context=_ctx(guard_5064),
    )
    assert decision.auto_confirm is False
    assert decision.reason == "alignment_not_exact_for_framework"


def test_iso_exact_peers_still_confirm(guard_5064):
    """The ≥98% + EXACT path is unchanged where an EXACT peer really touches the cell."""
    for clause_id in ("9001-7.2", "14001-7.5", "45001-7.5"):
        decision = evaluate(
            confidence=0.99,
            doc_type="procedure",
            clause_id=clause_id,
            context=_ctx(guard_5064),
        )
        assert decision.auto_confirm is True, clause_id
        assert decision.reason == "auto_confirmed"
        assert decision.row_verdict == "EXACT"


def test_45001_5_4_still_refuses_auto_confirm(guard_5064):
    """45001 5.4 is UNIQUE on the ISO row; its only EXACT peer is IiP, not ISO-family.

    Either reason is a refuse. The cell must not newly auto-confirm because IiP
    lookup now finds the EXACT pair.
    """
    annotation = guard_5064.annotate_cell(framework="45001", clause_number="5.4")
    assert any(p["framework"] == "iip" and p["verdict"] == "EXACT" for p in annotation["peers"])
    decision = evaluate(
        confidence=0.99,
        doc_type="procedure",
        clause_id="45001-5.4",
        context=_ctx(guard_5064),
    )
    assert decision.auto_confirm is False
    assert decision.reason in {"alignment_unique", "alignment_not_exact_for_framework"}


def test_iip_exact_peers_do_not_machine_confirm_the_scheme_cell(guard_5064):
    decision = evaluate(
        confidence=0.99,
        doc_type="procedure",
        clause_id="iip-IIP 7",
        context=_ctx(guard_5064),
    )
    assert decision.auto_confirm is False
    assert decision.reason == "alignment_not_exact_for_framework"


def test_ce_firewalls_near_refuses_auto_confirm(guard_5064):
    decision = evaluate(
        confidence=0.99,
        doc_type="procedure",
        clause_id="ce-firewalls",
        context=_ctx(guard_5064),
    )
    assert decision.auto_confirm is False
    assert decision.reason == "alignment_near_requires_addition"


def test_resolve_link_status_fail_closed_without_gate():
    from src.domain.models.compliance_evidence import EvidenceLinkStatus
    from src.domain.services.governed_knowledge_service import resolve_link_status

    status, auto = resolve_link_status(0.99, "procedure")
    assert status == EvidenceLinkStatus.PROPOSED
    assert auto is False


def test_resolve_link_status_honours_gate_allow(guard_5064):
    from src.domain.models.compliance_evidence import EvidenceLinkStatus
    from src.domain.services.governed_knowledge_service import resolve_link_status

    decision = evaluate(
        confidence=0.99,
        doc_type="procedure",
        clause_id="9001-7.5",
        context=_ctx(guard_5064),
    )
    assert decision.auto_confirm is True
    status, auto = resolve_link_status(0.99, "procedure", gate=decision)
    assert status == EvidenceLinkStatus.CONFIRMED
    assert auto is True
