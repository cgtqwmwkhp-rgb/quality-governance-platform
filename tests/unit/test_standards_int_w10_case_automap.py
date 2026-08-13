"""Int-W10: case auto-map expands ISO EXACT peers; always force_proposed; no scheme EXACT."""

from __future__ import annotations

from src.domain.models.standards_alignment import (
    AlignmentEdge,
    AlignmentVerdict,
    MatrixVersion,
    MatrixVersionStatus,
    canonical_alignment_pair,
)
from src.domain.services.governed_knowledge_service import SchemeMapping, expand_iso_exact_peers
from src.domain.services.standards_trap_guard import TrapGuard


def _iso_exact_guard() -> TrapGuard:
    src_fw, src_key, dst_fw, dst_key = canonical_alignment_pair("9001", "9001-7.2", "14001", "14001-7.2")
    edge = AlignmentEdge(
        tenant_id=1,
        matrix_version_id=1,
        row_key="annexsl-7.2",
        clause_ref="7.2",
        title="Competence",
        src_framework=src_fw,
        src_clause_key=src_key,
        dst_framework=dst_fw,
        dst_clause_key=dst_key,
        verdict=AlignmentVerdict.EXACT,
        row_verdict=AlignmentVerdict.EXACT,
        is_pair_override=False,
    )
    version = MatrixVersion(
        tenant_id=1,
        source_ref="PEL-HSEQ-5064",
        version_label="1.1",
        title="Standards Alignment Matrix",
        source_checksum="test",
        status=MatrixVersionStatus.ACTIVE,
    )
    return TrapGuard(edges=[edge], version=version)


def test_expand_iso_exact_peers_adds_iso_family_peer() -> None:
    extra = expand_iso_exact_peers(
        [
            SchemeMapping(
                clause_id="9001-7.2",
                scheme="iso9001",
                confidence=90.0,
                rationale="competence gap",
            )
        ],
        _iso_exact_guard(),
    )
    assert [m.clause_id for m in extra] == ["14001-7.2"]
    assert extra[0].scheme == "iso14001"
    assert "EXACT alignment peer" in extra[0].rationale


def test_expand_iso_exact_peers_skips_unloaded_guard() -> None:
    extra = expand_iso_exact_peers(
        [SchemeMapping(clause_id="9001-7.2", scheme="iso9001", confidence=90.0, rationale="x")],
        TrapGuard(),
    )
    assert extra == []


def test_expand_iso_exact_peers_does_not_invent_scheme_exact() -> None:
    extra = expand_iso_exact_peers(
        [
            SchemeMapping(clause_id="chas-7.2", scheme="chas", confidence=99.0, rationale="x"),
            SchemeMapping(clause_id="uvdb-B2", scheme="uvdb", confidence=99.0, rationale="x"),
            SchemeMapping(clause_id="pm:scope1", scheme="planet_mark", confidence=99.0, rationale="x"),
        ],
        _iso_exact_guard(),
    )
    assert extra == []


def test_expand_iso_exact_peers_does_not_duplicate_already_mapped_peer() -> None:
    extra = expand_iso_exact_peers(
        [
            SchemeMapping(clause_id="9001-7.2", scheme="iso9001", confidence=90.0, rationale="a"),
            SchemeMapping(clause_id="14001-7.2", scheme="iso14001", confidence=80.0, rationale="b"),
        ],
        _iso_exact_guard(),
    )
    assert extra == []


def test_near_miss_ingest_gate_never_auto_confirms() -> None:
    from src.domain.services.standards_ingest_gate import evaluate

    decision = evaluate(
        confidence=99.0,
        doc_type=None,
        clause_id="9001-7.2",
        entity_type="near_miss",
    )
    assert decision.auto_confirm is False
    assert decision.reason == "operational_entity"
