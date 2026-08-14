"""Wave 3 PR-E3 — re-score machine-confirmed CEL after a 5064 matrix change."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src.domain.models.compliance_evidence import EvidenceLinkMethod, EvidenceLinkStatus
from src.domain.models.standards_alignment import AlignmentEdge, MatrixVersion, MatrixVersionStatus
from src.domain.services.standards_alignment_import_service import build_edges, load_payload
from src.domain.services.standards_ingest_gate import CoverBlockIndex, StandardsAutoConfirmContext
from src.domain.services.standards_matrix_rescore_service import (
    apply_demotion,
    classify_rescore_target,
    is_human_confirmed,
    maybe_rescore_after_apply,
    rescore_loaded_links,
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


def _link(
    *,
    clause_id: str,
    status=EvidenceLinkStatus.CONFIRMED,
    linked_by=EvidenceLinkMethod.AI,
    auto_applied: bool = True,
    confidence: float = 0.99,
    confirmed_by_id=None,
    entity_type: str = "document",
    entity_id: str = "42",
    deleted_at=None,
):
    return SimpleNamespace(
        id=1,
        tenant_id=1,
        entity_type=entity_type,
        entity_id=entity_id,
        clause_id=clause_id,
        status=status,
        linked_by=linked_by,
        auto_applied=auto_applied,
        confidence=confidence,
        confirmed_by_id=confirmed_by_id,
        deleted_at=deleted_at,
    )


def test_human_confirmer_stamp_is_preserved_even_on_near(guard_5064):
    link = _link(
        clause_id="14001-9.1.2",
        linked_by=EvidenceLinkMethod.AI,
        auto_applied=False,
        confirmed_by_id=7,
    )
    assert is_human_confirmed(link) is True
    assert classify_rescore_target(link) == "human"
    summary = rescore_loaded_links([link], context=_ctx(guard_5064))
    assert summary.preserved_human == 1
    assert summary.demoted == 0
    assert link.status == EvidenceLinkStatus.CONFIRMED
    assert link.confirmed_by_id == 7


def test_manual_link_is_preserved_without_confirmed_by_id(guard_5064):
    link = _link(
        clause_id="9001-6.1.2",
        linked_by=EvidenceLinkMethod.MANUAL,
        auto_applied=False,
        confirmed_by_id=None,
    )
    summary = rescore_loaded_links([link], context=_ctx(guard_5064))
    assert summary.preserved_human == 1
    assert link.status == EvidenceLinkStatus.CONFIRMED
    assert link.auto_applied is False


def test_near_demotes_machine_confirmed(guard_5064):
    clause = None
    for candidate in ("9.1.2", "8.1", "6.1", "7.4"):
        annotation = guard_5064.annotate_cell(framework="14001", clause_number=candidate)
        if annotation["row_verdict"] == "NEAR":
            clause = f"14001-{candidate}"
            break
    if clause is None:
        pytest.skip("no NEAR row found in fixture payload")
    link = _link(clause_id=clause)
    summary = rescore_loaded_links([link], context=_ctx(guard_5064))
    assert summary.demoted == 1
    assert link.status == EvidenceLinkStatus.PROPOSED
    assert link.auto_applied is False
    assert summary.demotions[0][1].reason == "alignment_near_requires_addition"
    assert summary.demotions[0][2] == "confirmed"


def test_different_demotes_machine_confirmed(guard_5064):
    link = _link(clause_id="9001-6.1.2")
    summary = rescore_loaded_links([link], context=_ctx(guard_5064))
    assert summary.demoted == 1
    assert link.status == EvidenceLinkStatus.PROPOSED
    assert summary.demotions[0][1].reason == "alignment_different"


def test_exact_iso_peer_keeps_machine_confirmed(guard_5064):
    link = _link(clause_id="9001-7.2")
    summary = rescore_loaded_links([link], context=_ctx(guard_5064))
    assert summary.kept == 1
    assert summary.demoted == 0
    assert link.status == EvidenceLinkStatus.CONFIRMED
    assert link.auto_applied is True


def test_cover_block_demotes_even_on_exact(guard_5064):
    link = _link(clause_id="9001-7.5")
    summary = rescore_loaded_links([link], context=_ctx(guard_5064, blocked="cover_blocked_open_nc"))
    assert summary.demoted == 1
    assert link.status == EvidenceLinkStatus.PROPOSED
    assert summary.demotions[0][1].reason == "cover_blocked_open_nc"


def test_chas_without_own_exact_peer_demotes(guard_5064):
    link = _link(clause_id="chas-7.2")
    summary = rescore_loaded_links([link], context=_ctx(guard_5064))
    assert summary.demoted == 1
    assert summary.demotions[0][1].reason == "alignment_not_exact_for_framework"


def test_proposed_exact_is_never_auto_promoted(guard_5064):
    link = _link(
        clause_id="9001-7.2",
        status=EvidenceLinkStatus.PROPOSED,
        auto_applied=False,
    )
    assert classify_rescore_target(link) == "skip"
    summary = rescore_loaded_links([link], context=_ctx(guard_5064))
    assert summary.skipped == 1
    assert summary.demoted == 0
    assert summary.kept == 0
    assert link.status == EvidenceLinkStatus.PROPOSED


def test_operational_entity_is_skipped(guard_5064):
    link = _link(clause_id="9001-7.2", entity_type="incident")
    summary = rescore_loaded_links([link], context=_ctx(guard_5064))
    assert summary.skipped == 1
    assert link.status == EvidenceLinkStatus.CONFIRMED


def test_missing_context_fail_closed_demotes_machine_confirmed():
    link = _link(clause_id="9001-7.2")
    summary = rescore_loaded_links([link], context=None)
    assert summary.demoted == 1
    assert link.status == EvidenceLinkStatus.PROPOSED
    assert summary.demotions[0][1].reason == "matrix_not_loaded"


def test_apply_demotion_does_not_clear_human_stamp():
    link = _link(clause_id="9001-7.2", confirmed_by_id=9, auto_applied=False)
    apply_demotion(link)
    assert link.status == EvidenceLinkStatus.PROPOSED
    assert link.auto_applied is False
    assert link.confirmed_by_id == 9


@pytest.mark.asyncio
async def test_idempotent_apply_does_not_rescore():
    called = {"n": 0}

    class _Boom:
        async def execute(self, *_a, **_k):
            called["n"] += 1
            raise AssertionError("rescore must not touch the session on a no-op apply")

    result = await maybe_rescore_after_apply(
        _Boom(),  # type: ignore[arg-type]
        tenant_id=1,
        created=False,
        reactivated=False,
        matrix_version_id=17,
        matrix_version_label="1.0",
    )
    assert result is None
    assert called["n"] == 0
