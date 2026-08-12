"""Unit tests for EXACT shared-apply planning rules (Wave 2 PR-D)."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Optional
from unittest.mock import AsyncMock

import pytest

from src.domain.models.standards_alignment import AlignmentEdge, MatrixVersion, MatrixVersionStatus
from src.domain.services.standards_alignment_import_service import build_edges, load_payload
from src.domain.services.standards_exact_share_service import ExactShareService
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


def _cell(
    *,
    framework: str,
    clause_number: str,
    cover_blocked: bool = False,
    open_nc: int = 0,
    open_action: int = 0,
    evidence: Optional[list[dict[str, Any]]] = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        framework=framework,
        clause_number=clause_number,
        cover_blocked=cover_blocked,
        evidence=evidence or [],
        summary={
            "open_nc_count": open_nc,
            "open_action_count": open_action,
        },
    )


def _service_with_guard(guard: TrapGuard, cells: dict[tuple[str, str], SimpleNamespace]) -> ExactShareService:
    aggregate = SimpleNamespace()
    aggregate.trap_guard = AsyncMock(return_value=guard)

    async def get_cell(*, tenant_id: int, framework: str, clause_number: str):
        key = (framework.strip().lower(), clause_number.strip())
        if key not in cells:
            return _cell(framework=framework, clause_number=clause_number)
        return cells[key]

    aggregate.get_cell = get_cell
    service = ExactShareService(db=AsyncMock(), aggregate=aggregate)  # type: ignore[arg-type]
    return service


@pytest.mark.asyncio
async def test_different_and_unique_peers_are_never_offered_as_targets(guard_5064):
    source = _cell(
        framework="9001",
        clause_number="6.1.2",
        evidence=[{"id": 1, "entity_type": "document", "entity_id": "9", "signal_type": "evidence"}],
    )
    service = _service_with_guard(guard_5064, {("9001", "6.1.2"): source})
    plan = await service.plan(tenant_id=1, framework="9001", clause_number="6.1.2", source_cell=source)
    assert plan.unavailable_reason == "no_exact_peers"
    assert plan.candidates == []
    assert plan.available is False


@pytest.mark.asyncio
async def test_near_peer_is_not_offered_because_the_addition_is_not_attested(guard_5064):
    annotation = guard_5064.annotate_cell(framework="9001", clause_number="7.5")
    near = [p for p in annotation["peers"] if p["verdict"] == "NEAR"]
    exact = [p for p in annotation["peers"] if p["verdict"] == "EXACT"]
    # If this row has no NEAR peers in the payload, skip — the filter is still covered
    # by comparing candidate verdicts below when EXACT peers exist.
    source = _cell(
        framework="9001",
        clause_number="7.5",
        evidence=[{"id": 1, "entity_type": "document", "entity_id": "9", "signal_type": "evidence"}],
    )
    cells = {("9001", "7.5"): source}
    service = _service_with_guard(guard_5064, cells)
    # Patch _shareable_links to avoid DB reads in plan happy-path.
    service._shareable_links = AsyncMock(  # type: ignore[method-assign]
        return_value=[
            {
                "link_id": 1,
                "entity_type": "document",
                "entity_id": "9",
                "title": "Competence matrix",
                "cover_kind": "covers",
                "already_shared_frameworks": [],
            }
        ]
    )
    plan = await service.plan(tenant_id=1, framework="9001", clause_number="7.5", source_cell=source)
    assert all(c["verdict"] == "EXACT" for c in plan.candidates)
    assert len(plan.candidates) == len(exact)
    if near:
        near_fws = {p["framework"] for p in near}
        assert near_fws.isdisjoint({c["framework"] for c in plan.candidates}) or all(
            c["verdict"] != "NEAR" for c in plan.candidates
        )


@pytest.mark.asyncio
async def test_row_verdict_different_still_offers_the_shareable_pair(guard_5064):
    """Clause 6.1.3 is DIFFERENT as a row; 14001↔27001 A.5.31 remains EXACT."""
    annotation = guard_5064.annotate_cell(framework="14001", clause_number="6.1.3")
    assert annotation["row_verdict"] == "DIFFERENT"
    exact = [p for p in annotation["peers"] if p["verdict"] == "EXACT"]
    assert any(p["framework"] == "27001" for p in exact)

    source = _cell(
        framework="14001",
        clause_number="6.1.3",
        evidence=[{"id": 2, "entity_type": "document", "entity_id": "12", "signal_type": "evidence"}],
    )
    service = _service_with_guard(guard_5064, {("14001", "6.1.3"): source})
    service._shareable_links = AsyncMock(  # type: ignore[method-assign]
        return_value=[
            {
                "link_id": 2,
                "entity_type": "document",
                "entity_id": "12",
                "title": "Legal register",
                "cover_kind": "covers",
                "already_shared_frameworks": [],
            }
        ]
    )
    plan = await service.plan(tenant_id=1, framework="14001", clause_number="6.1.3", source_cell=source)
    assert any(c["framework"] == "27001" and c["verdict"] == "EXACT" for c in plan.candidates)


@pytest.mark.asyncio
async def test_unloaded_matrix_offers_no_targets():
    service = _service_with_guard(TrapGuard(), {})
    source = _cell(framework="9001", clause_number="7.5")
    plan = await service.plan(tenant_id=1, framework="9001", clause_number="7.5", source_cell=source)
    assert plan.available is False
    assert plan.unavailable_reason == "matrix_not_loaded"


@pytest.mark.asyncio
async def test_target_with_open_nc_is_ineligible_and_names_the_reason(guard_5064):
    source = _cell(
        framework="9001",
        clause_number="7.5",
        evidence=[{"id": 1, "entity_type": "document", "entity_id": "9", "signal_type": "evidence"}],
    )
    annotation = guard_5064.annotate_cell(framework="9001", clause_number="7.5")
    exact = [p for p in annotation["peers"] if p["verdict"] == "EXACT"]
    assert exact, "expected EXACT peers on 7.5"
    blocked_fw = exact[0]["framework"]
    blocked_clause = exact[0]["clause_key"].split("-", 1)[-1]
    cells = {
        ("9001", "7.5"): source,
        (blocked_fw, blocked_clause): _cell(
            framework=blocked_fw, clause_number=blocked_clause, cover_blocked=True, open_nc=2
        ),
    }
    service = _service_with_guard(guard_5064, cells)
    service._shareable_links = AsyncMock(return_value=[])  # type: ignore[method-assign]
    plan = await service.plan(tenant_id=1, framework="9001", clause_number="7.5", source_cell=source)
    blocked = next(c for c in plan.candidates if c["framework"] == blocked_fw)
    assert blocked["eligible"] is False
    assert "target_open_nc" in blocked["blocked_reasons"]


@pytest.mark.asyncio
async def test_target_with_open_action_only_is_ineligible(guard_5064):
    source = _cell(
        framework="9001",
        clause_number="7.5",
        evidence=[{"id": 1, "entity_type": "document", "entity_id": "9", "signal_type": "evidence"}],
    )
    annotation = guard_5064.annotate_cell(framework="9001", clause_number="7.5")
    exact = [p for p in annotation["peers"] if p["verdict"] == "EXACT"]
    blocked_fw = exact[0]["framework"]
    blocked_clause = exact[0]["clause_key"].split("-", 1)[-1]
    cells = {
        ("9001", "7.5"): source,
        (blocked_fw, blocked_clause): _cell(
            framework=blocked_fw, clause_number=blocked_clause, cover_blocked=True, open_action=1
        ),
    }
    service = _service_with_guard(guard_5064, cells)
    service._shareable_links = AsyncMock(return_value=[])  # type: ignore[method-assign]
    plan = await service.plan(tenant_id=1, framework="9001", clause_number="7.5", source_cell=source)
    blocked = next(c for c in plan.candidates if c["framework"] == blocked_fw)
    assert "target_open_action" in blocked["blocked_reasons"]


@pytest.mark.asyncio
async def test_source_cover_blocked_refuses_the_whole_share(guard_5064):
    source = _cell(
        framework="9001",
        clause_number="7.5",
        cover_blocked=True,
        open_nc=1,
        evidence=[{"id": 1, "entity_type": "document", "entity_id": "9", "signal_type": "evidence"}],
    )
    service = _service_with_guard(guard_5064, {("9001", "7.5"): source})
    plan = await service.plan(tenant_id=1, framework="9001", clause_number="7.5", source_cell=source)
    assert plan.available is False
    assert plan.unavailable_reason == "source_cover_blocked"
