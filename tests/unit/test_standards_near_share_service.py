"""Unit tests for ISO NEAR proposed-share (AP-07).

NEAR is not EXACT: ExactShare stays EXACT-only. This service offers ISO-family
NEAR peers only, surfaces addition_text, and never auto-confirms.
"""

from __future__ import annotations

import inspect
from types import SimpleNamespace
from typing import Any, Optional
from unittest.mock import AsyncMock, patch

import pytest

from src.domain.exceptions import ConflictError
from src.domain.models.compliance_evidence import EvidenceCoverKind, EvidenceLinkStatus
from src.domain.models.standards_alignment import AlignmentEdge, MatrixVersion, MatrixVersionStatus
from src.domain.services.standards_alignment_import_service import build_edges, load_payload
from src.domain.services.standards_exact_share_service import ExactShareService
from src.domain.services.standards_near_share_service import NearShareService
from src.domain.services.standards_trap_guard import ISO_NUMBERING_FAMILY, TrapGuard


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
        version_label="1.1",
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


def _service_with_guard(
    guard: TrapGuard,
    cells: dict[tuple[str, str], SimpleNamespace],
    *,
    cls: type = NearShareService,
) -> NearShareService:
    aggregate = SimpleNamespace()
    aggregate.trap_guard = AsyncMock(return_value=guard)

    async def get_cell(*, tenant_id: int, framework: str, clause_number: str):
        key = (framework.strip().lower(), clause_number.strip())
        if key not in cells:
            return _cell(framework=framework, clause_number=clause_number)
        return cells[key]

    aggregate.get_cell = get_cell
    return cls(db=AsyncMock(), aggregate=aggregate)  # type: ignore[arg-type]


def _shareable(link_id: int = 1, title: str = "Context statement") -> list[dict[str, Any]]:
    return [
        {
            "link_id": link_id,
            "entity_type": "document",
            "entity_id": "9",
            "title": title,
            "cover_kind": "covers",
            "already_shared_frameworks": [],
        }
    ]


@pytest.mark.asyncio
async def test_iso_near_4_1_offers_iso_peers_and_names_the_addition(guard_5064):
    annotation = guard_5064.annotate_cell(framework="9001", clause_number="4.1")
    near_iso = [p for p in annotation["peers"] if p["verdict"] == "NEAR" and p["framework"] in ISO_NUMBERING_FAMILY]
    assert near_iso, "5064 4.1 is the ISO NEAR row"

    source = _cell(
        framework="9001",
        clause_number="4.1",
        evidence=[{"id": 1, "entity_type": "document", "entity_id": "9", "signal_type": "evidence"}],
    )
    service = _service_with_guard(guard_5064, {("9001", "4.1"): source})
    service._shareable_links = AsyncMock(return_value=_shareable())  # type: ignore[method-assign]
    plan = await service.plan(tenant_id=1, framework="9001", clause_number="4.1", source_cell=source)

    assert plan.available is True
    assert plan.unavailable_reason is None
    assert {c["framework"] for c in plan.candidates} == {p["framework"] for p in near_iso}
    assert all(c["verdict"] == "NEAR" for c in plan.candidates)
    assert all(c["framework"] in ISO_NUMBERING_FAMILY for c in plan.candidates)
    assert any(str(c.get("addition_text") or "").strip() for c in plan.candidates)


@pytest.mark.asyncio
async def test_exact_share_on_4_1_still_refuses_because_peers_are_near(guard_5064):
    source = _cell(
        framework="9001",
        clause_number="4.1",
        evidence=[{"id": 1, "entity_type": "document", "entity_id": "9", "signal_type": "evidence"}],
    )
    exact = _service_with_guard(guard_5064, {("9001", "4.1"): source}, cls=ExactShareService)
    plan = await exact.plan(tenant_id=1, framework="9001", clause_number="4.1", source_cell=source)
    assert plan.available is False
    assert plan.unavailable_reason == "no_exact_peers"
    assert plan.candidates == []


@pytest.mark.asyncio
async def test_ce_plus_near_is_not_offered_this_slice(guard_5064):
    source = _cell(
        framework="ce",
        clause_number="firewalls",
        evidence=[{"id": 3, "entity_type": "document", "entity_id": "11", "signal_type": "evidence"}],
    )
    service = _service_with_guard(guard_5064, {("ce", "firewalls"): source})
    plan = await service.plan(tenant_id=1, framework="ce", clause_number="firewalls", source_cell=source)
    assert plan.available is False
    assert plan.unavailable_reason == "no_iso_near_peers"
    assert plan.candidates == []


@pytest.mark.asyncio
async def test_chas_source_is_not_an_iso_near_share(guard_5064):
    source = _cell(
        framework="chas",
        clause_number="7.2",
        evidence=[{"id": 4, "entity_type": "document", "entity_id": "12", "signal_type": "evidence"}],
    )
    service = _service_with_guard(guard_5064, {("chas", "7.2"): source})
    plan = await service.plan(tenant_id=1, framework="chas", clause_number="7.2", source_cell=source)
    assert plan.available is False
    assert plan.unavailable_reason == "no_iso_near_peers"


@pytest.mark.asyncio
async def test_source_cover_blocked_refuses_near_share(guard_5064):
    source = _cell(
        framework="9001",
        clause_number="4.1",
        cover_blocked=True,
        open_nc=1,
        evidence=[{"id": 1, "entity_type": "document", "entity_id": "9", "signal_type": "evidence"}],
    )
    service = _service_with_guard(guard_5064, {("9001", "4.1"): source})
    plan = await service.plan(tenant_id=1, framework="9001", clause_number="4.1", source_cell=source)
    assert plan.available is False
    assert plan.unavailable_reason == "source_cover_blocked"
    assert plan.candidates
    assert all(c["verdict"] == "NEAR" for c in plan.candidates)


@pytest.mark.asyncio
async def test_target_open_nc_is_ineligible_on_near_peers(guard_5064):
    source = _cell(
        framework="9001",
        clause_number="4.1",
        evidence=[{"id": 1, "entity_type": "document", "entity_id": "9", "signal_type": "evidence"}],
    )
    annotation = guard_5064.annotate_cell(framework="9001", clause_number="4.1")
    near = [p for p in annotation["peers"] if p["verdict"] == "NEAR" and p["framework"] in ISO_NUMBERING_FAMILY]
    blocked_fw = near[0]["framework"]
    blocked_clause = near[0]["clause_key"].split("-", 1)[-1]
    cells = {
        ("9001", "4.1"): source,
        (blocked_fw, blocked_clause): _cell(
            framework=blocked_fw, clause_number=blocked_clause, cover_blocked=True, open_nc=2
        ),
    }
    service = _service_with_guard(guard_5064, cells)
    service._shareable_links = AsyncMock(return_value=_shareable())  # type: ignore[method-assign]
    plan = await service.plan(tenant_id=1, framework="9001", clause_number="4.1", source_cell=source)
    blocked = next(c for c in plan.candidates if c["framework"] == blocked_fw)
    assert blocked["eligible"] is False
    assert "target_open_nc" in blocked["blocked_reasons"]


def test_apply_never_auto_confirms():
    source = inspect.getsource(NearShareService.apply)
    assert "EvidenceLinkStatus.PROPOSED" in source
    assert "auto_applied=True" in source
    assert "EvidenceLinkStatus.CONFIRMED" not in source
    assert NearShareService.conflict_prefix == "NEAR_SHARE"
    select_src = inspect.getsource(NearShareService._select_peers)
    assert "ISO_NUMBERING_FAMILY" in select_src


@pytest.mark.asyncio
async def test_apply_writes_proposed_notes_naming_the_addition(guard_5064):
    source = _cell(
        framework="9001",
        clause_number="4.1",
        evidence=[{"id": 1, "entity_type": "document", "entity_id": "9", "signal_type": "evidence"}],
    )
    annotation = guard_5064.annotate_cell(framework="9001", clause_number="4.1")
    near = [p for p in annotation["peers"] if p["verdict"] == "NEAR" and p["framework"] in ISO_NUMBERING_FAMILY]
    target_fw = near[0]["framework"]
    service = _service_with_guard(guard_5064, {("9001", "4.1"): source})

    source_link = SimpleNamespace(
        entity_type="document",
        entity_id="9",
        cover_kind=EvidenceCoverKind.COVERS,
        confidence=None,
        title="Context",
        notes=None,
        signal_type="evidence",
        clause_id="9001-4.1",
    )
    service._require_shareable_source_link = AsyncMock(return_value=source_link)  # type: ignore[method-assign]
    captured: dict[str, Any] = {}

    async def fake_create(*_args, **kwargs):
        captured.update(kwargs)
        clause_id = kwargs["clause_ids"][0]
        return SimpleNamespace(
            created=[SimpleNamespace(id=99, clause_id=clause_id)],
            existing=[],
        )

    with patch(
        "src.domain.services.standards_exact_share_service.create_evidence_links_if_absent",
        fake_create,
    ):
        result = await service.apply(
            tenant_id=1,
            actor_id=7,
            actor_email="auditor@example.com",
            source_link_id=1,
            source_framework="9001",
            source_clause="4.1",
            target_frameworks=[target_fw],
            matrix_version_id=17,
        )

    assert captured["status"] is EvidenceLinkStatus.PROPOSED
    assert captured["auto_applied"] is True
    assert captured["status"] is not EvidenceLinkStatus.CONFIRMED
    notes = captured["notes"] or ""
    assert "NEAR share — not EXACT" in notes
    assert result["created"][0]["verdict"] == "NEAR"


@pytest.mark.asyncio
async def test_apply_refuses_a_scheme_target_even_if_named(guard_5064):
    source = _cell(framework="9001", clause_number="4.1")
    service = _service_with_guard(guard_5064, {("9001", "4.1"): source})
    source_link = SimpleNamespace(
        entity_type="document",
        entity_id="9",
        cover_kind=EvidenceCoverKind.COVERS,
        confidence=None,
        title="Context",
        notes=None,
        signal_type="evidence",
        clause_id="9001-4.1",
    )
    service._require_shareable_source_link = AsyncMock(return_value=source_link)  # type: ignore[method-assign]
    with pytest.raises(ConflictError) as exc:
        await service.apply(
            tenant_id=1,
            actor_id=7,
            actor_email="auditor@example.com",
            source_link_id=1,
            source_framework="9001",
            source_clause="4.1",
            target_frameworks=["chas"],
            matrix_version_id=17,
        )
    assert exc.value.code == "NEAR_SHARE_TARGET_BLOCKED"
    assert exc.value.details["targets"][0]["blocked_reasons"] == ["not_iso_near_peer"]
