"""JL-UX-W2: generic job cycle nesting, acyclic guard, PDCA phase.

The three claims worth pinning here:

1. Nesting is **generic**. Any JobType may nest any other, so no test may
   depend on a privileged pair of packs (Operational↔Engineer or otherwise).
2. Nesting has exactly **one SSOT** — the ``job_cycle`` cell link. There is no
   nesting column on ``job_lanes``, and the lane chip is derived.
3. The ``job_type`` hop is reachable. Entity360 fails *closed* on unmapped
   source types, so a producer that emits ``job_type`` without a permission
   entry would silently emit hops nobody can see.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from src.api.schemas.job_lifecycle import JobCellLinkCreate, JobStepUpdate
from src.core.config import settings
from src.domain.models.job_lifecycle import (
    JOB_CELL_LINK_KINDS,
    JOB_STEP_PDCA_PHASES,
    JobCellLink,
    JobLane,
    JobStep,
)
from src.domain.services.entity_360.permissions import HOP_READ_PERMISSIONS, can_view_hop
from src.domain.services.entity_360.producers.job_lifecycle import JobLifecycleProducer
from src.domain.services.href_registry import href_for, job_type_href, registered_entity_types
from src.domain.services.job_lifecycle_service import (
    JobLifecycleService,
    list_link_entity_types,
    resolve_cell_link_href,
    serialize_cell_link,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
MIGRATION = REPO_ROOT / "alembic/versions/20261021_job_nesting_pdca.py"


# ---------------------------------------------------------------------------
# Migration + model shape
# ---------------------------------------------------------------------------


def test_migration_revises_the_job_lifecycle_chain_tip():
    """One JL chain, no parallel head: W2 must revise JL-3's revision exactly."""
    source = MIGRATION.read_text(encoding="utf-8")
    assert 'revision: str = "20261021_job_nest_pdca"' in source
    assert 'down_revision: Union[str, Sequence[str], None] = "20261020_job_cell_links"' in source


def test_migration_widens_kind_and_adds_nesting_and_pdca():
    source = MIGRATION.read_text(encoding="utf-8")
    assert "'app', 'external', 'audit_outcome', 'job_cycle'" in source
    assert "target_job_type_id" in source
    assert "pdca_phase" in source
    # CASCADE, not SET NULL: a nest link with no target cannot resolve an href.
    assert 'ondelete="CASCADE"' in source


def test_link_kinds_include_job_cycle_and_check_constraint_matches():
    assert "job_cycle" in JOB_CELL_LINK_KINDS
    constraints = {
        c.name: str(c.sqltext)
        for c in JobCellLink.__table__.constraints
        if c.name == "ck_job_cell_links_kind"
    }
    assert "ck_job_cell_links_kind" in constraints
    assert "job_cycle" in constraints["ck_job_cell_links_kind"]


def test_nesting_has_no_second_ssot_on_lanes():
    """The lane nest chip is derived. A lane FK would be a second truth."""
    lane_columns = {c.name for c in JobLane.__table__.columns}
    assert "target_job_type_id" not in lane_columns
    assert "nested_job_type_id" not in lane_columns
    assert "target_job_type_id" in {c.name for c in JobCellLink.__table__.columns}


def test_job_step_carries_nullable_pdca_phase_with_constraint():
    column = JobStep.__table__.columns["pdca_phase"]
    assert column.nullable is True
    constraint = next(
        c for c in JobStep.__table__.constraints if c.name == "ck_job_steps_pdca_phase"
    )
    rendered = str(constraint.sqltext)
    assert "IS NULL" in rendered
    for phase in JOB_STEP_PDCA_PHASES:
        assert phase in rendered


# ---------------------------------------------------------------------------
# href registry
# ---------------------------------------------------------------------------


def test_job_type_is_registered_in_href_registry():
    assert "job_type" in registered_entity_types()
    assert job_type_href(7) == "/job-lifecycle/cycles/7"
    assert href_for("job_type", 7) == job_type_href(7)


def test_nest_link_href_comes_from_the_registry():
    link = SimpleNamespace(
        kind="job_cycle",
        entity_type=None,
        entity_id=None,
        external_url=None,
        audit_run_id=None,
        audit_finding_id=None,
        target_job_type_id=12,
    )
    assert resolve_cell_link_href(link) == job_type_href(12)


def test_nest_link_without_target_is_a_server_error_not_a_broken_href():
    link = SimpleNamespace(
        kind="job_cycle",
        entity_type=None,
        entity_id=None,
        external_url=None,
        audit_run_id=None,
        audit_finding_id=None,
        target_job_type_id=None,
    )
    with pytest.raises(HTTPException) as exc_info:
        resolve_cell_link_href(link)
    assert exc_info.value.status_code == 500


def test_serialize_includes_target_job_type_id():
    row = SimpleNamespace(
        id=1,
        tenant_id=1,
        cell_id=2,
        kind="job_cycle",
        label="Engineer pack",
        entity_type=None,
        entity_id=None,
        external_url=None,
        audit_run_id=None,
        audit_finding_id=None,
        target_job_type_id=9,
        sort_order=0,
        created_at="t0",
        updated_at="t1",
    )
    payload = serialize_cell_link(row)
    assert payload["target_job_type_id"] == 9
    assert payload["href"] == job_type_href(9)


def test_app_entity_type_list_is_registry_derived_and_excludes_job_type():
    items = list_link_entity_types()
    assert items == sorted(items), "sorted so the dropdown order is stable"
    assert "document" in items
    # Nesting is the job_cycle kind with its own guard, not a free-form app link.
    assert "job_type" not in items
    assert set(items) <= registered_entity_types()


# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------


def test_job_cycle_schema_requires_target_and_forbids_other_refs():
    with pytest.raises(ValidationError):
        JobCellLinkCreate(kind="job_cycle", label="x")
    with pytest.raises(ValidationError):
        JobCellLinkCreate(kind="job_cycle", label="x", target_job_type_id=3, external_url="https://a.test")
    with pytest.raises(ValidationError):
        JobCellLinkCreate(kind="job_cycle", label="x", target_job_type_id=3, entity_type="document", entity_id=1)
    with pytest.raises(ValidationError):
        JobCellLinkCreate(kind="job_cycle", label="x", target_job_type_id=3, audit_run_id=1, audit_finding_id=2)
    ok = JobCellLinkCreate(kind="job_cycle", label="Engineer", target_job_type_id=3)
    assert ok.target_job_type_id == 3


def test_other_kinds_may_not_smuggle_a_nest_target():
    with pytest.raises(ValidationError):
        JobCellLinkCreate(kind="app", label="x", entity_type="document", entity_id=1, target_job_type_id=2)
    with pytest.raises(ValidationError):
        JobCellLinkCreate(kind="external", label="x", external_url="https://a.test", target_job_type_id=2)
    with pytest.raises(ValidationError):
        JobCellLinkCreate(
            kind="audit_outcome", label="x", audit_run_id=1, audit_finding_id=2, target_job_type_id=3
        )


def test_step_update_distinguishes_omitted_phase_from_cleared_phase():
    omitted = JobStepUpdate(name="Deliver")
    assert omitted.pdca_phase is None
    assert omitted.pdca_phase_set is False

    cleared = JobStepUpdate(pdca_phase=None, pdca_phase_set=True)
    assert cleared.pdca_phase_set is True

    with pytest.raises(ValidationError):
        JobStepUpdate(pdca_phase="review")


# ---------------------------------------------------------------------------
# Acyclic guard (BFS, same shape as document_graph)
# ---------------------------------------------------------------------------


class _FakeNestGraph:
    """Nesting edges as ``{job_type_id: [nested ids]}`` for the BFS under test."""

    def __init__(self, edges: dict[int, list[int]]):
        self.edges = edges
        self.calls = 0

    async def nested_job_type_ids(self, *, tenant_id: int, job_type_id: int) -> list[int]:
        _ = tenant_id
        self.calls += 1
        return list(self.edges.get(job_type_id, []))


def _service_with_graph(edges: dict[int, list[int]]) -> tuple[JobLifecycleService, _FakeNestGraph]:
    service = JobLifecycleService(db=SimpleNamespace())
    graph = _FakeNestGraph(edges)
    service.nested_job_type_ids = graph.nested_job_type_ids  # type: ignore[method-assign]
    return service, graph


@pytest.mark.asyncio
async def test_self_nesting_is_a_cycle():
    service, graph = _service_with_graph({})
    assert await service.would_create_job_cycle_nest_cycle(
        tenant_id=1, source_job_type_id=5, target_job_type_id=5
    )
    assert graph.calls == 0, "self-nesting is rejected without touching the graph"


@pytest.mark.asyncio
async def test_direct_back_edge_is_a_cycle():
    # 2 already nests 1, so nesting 2 inside 1 closes the loop.
    service, _ = _service_with_graph({2: [1]})
    assert await service.would_create_job_cycle_nest_cycle(
        tenant_id=1, source_job_type_id=1, target_job_type_id=2
    )


@pytest.mark.asyncio
async def test_transitive_back_edge_is_a_cycle():
    # 2 → 3 → 4 → 1, so nesting 2 inside 1 closes a four-hop loop.
    service, _ = _service_with_graph({2: [3], 3: [4], 4: [1]})
    assert await service.would_create_job_cycle_nest_cycle(
        tenant_id=1, source_job_type_id=1, target_job_type_id=2
    )


@pytest.mark.asyncio
async def test_diamond_nesting_is_allowed():
    """Shared descendants are not cycles — the guard rejects loops, not reuse."""
    service, _ = _service_with_graph({2: [4], 3: [4]})
    assert not await service.would_create_job_cycle_nest_cycle(
        tenant_id=1, source_job_type_id=1, target_job_type_id=2
    )
    assert not await service.would_create_job_cycle_nest_cycle(
        tenant_id=1, source_job_type_id=1, target_job_type_id=3
    )


@pytest.mark.asyncio
async def test_guard_terminates_on_a_graph_that_already_contains_a_cycle():
    """A pre-existing loop must not spin the BFS forever."""
    service, _ = _service_with_graph({2: [3], 3: [2]})
    assert not await service.would_create_job_cycle_nest_cycle(
        tenant_id=1, source_job_type_id=1, target_job_type_id=2
    )


@pytest.mark.asyncio
async def test_nesting_is_generic_in_both_directions():
    """No pack is privileged: A→B and B→A are each fine on an empty graph."""
    service, _ = _service_with_graph({})
    assert not await service.would_create_job_cycle_nest_cycle(
        tenant_id=1, source_job_type_id=101, target_job_type_id=202
    )
    assert not await service.would_create_job_cycle_nest_cycle(
        tenant_id=1, source_job_type_id=202, target_job_type_id=101
    )


@pytest.mark.asyncio
async def test_assert_nestable_rejects_missing_target_id():
    service, _ = _service_with_graph({})
    with pytest.raises(HTTPException) as exc_info:
        await service._assert_nestable_job_cycle(
            tenant_id=1, source_job_type_id=1, target_job_type_id=None
        )
    assert exc_info.value.status_code == 422


@pytest.mark.asyncio
async def test_assert_nestable_404s_on_a_target_outside_the_tenant():
    service, _ = _service_with_graph({})
    service._get_live = AsyncMock(return_value=None)  # type: ignore[method-assign]
    with pytest.raises(HTTPException) as exc_info:
        await service._assert_nestable_job_cycle(
            tenant_id=1, source_job_type_id=1, target_job_type_id=99
        )
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_assert_nestable_conflicts_when_a_cycle_would_form():
    service, _ = _service_with_graph({2: [1]})
    service._get_live = AsyncMock(return_value=SimpleNamespace(id=2))  # type: ignore[method-assign]
    with pytest.raises(HTTPException) as exc_info:
        await service._assert_nestable_job_cycle(
            tenant_id=1, source_job_type_id=1, target_job_type_id=2
        )
    assert exc_info.value.status_code == 409


@pytest.mark.asyncio
async def test_assert_nestable_allows_a_clean_nest():
    service, _ = _service_with_graph({})
    service._get_live = AsyncMock(return_value=SimpleNamespace(id=2))  # type: ignore[method-assign]
    await service._assert_nestable_job_cycle(
        tenant_id=1, source_job_type_id=1, target_job_type_id=2
    )


# ---------------------------------------------------------------------------
# Entity360 producer
# ---------------------------------------------------------------------------


def test_producer_supports_job_type_and_hop_is_permissioned():
    producer = JobLifecycleProducer()
    assert producer.supports("job_type")
    # Entity360 denies unmapped source types, so this entry is what makes the
    # nest hop visible at all.
    assert HOP_READ_PERMISSIONS["job_type"] == "job:read"
    assert can_view_hop(SimpleNamespace(is_superuser=False, has_permission=lambda p: p == "job:read"), "job_type")
    assert not can_view_hop(SimpleNamespace(is_superuser=False, has_permission=lambda p: False), "job_type")


@pytest.mark.asyncio
async def test_job_type_producer_returns_both_lists_when_links_flag_off(monkeypatch):
    monkeypatch.setattr(settings, "job_cell_links_enabled", False)
    producer = JobLifecycleProducer()
    db = SimpleNamespace(execute=AsyncMock())
    result = await producer.produce(
        db=db, tenant_id=1, entity_type="job_type", entity_id=5, user=SimpleNamespace(is_superuser=True)
    )
    assert result.status == "ok"
    assert result.upstream == []
    assert result.downstream == []
    db.execute.assert_not_called()


@pytest.mark.asyncio
async def test_job_type_producer_emits_nest_hops_both_ways(monkeypatch):
    monkeypatch.setattr(settings, "job_cell_links_enabled", True)
    producer = JobLifecycleProducer()

    child = SimpleNamespace(id=7, name="Engineer pack", code="engineer", is_active=True)
    parent = SimpleNamespace(id=2, name="Operational pack", code="operational", is_active=True)

    class _Scalars:
        def __init__(self, rows):
            self._rows = rows

        def all(self):
            return self._rows

    class _Result:
        def __init__(self, rows):
            self._rows = rows

        def scalars(self):
            return _Scalars(self._rows)

    # First call is downstream (children), second is upstream (parents).
    db = SimpleNamespace(execute=AsyncMock(side_effect=[_Result([child]), _Result([parent])]))
    result = await producer.produce(
        db=db, tenant_id=1, entity_type="job_type", entity_id=5, user=SimpleNamespace(is_superuser=True)
    )

    assert result.status == "ok"
    assert [h["source_id"] for h in result.downstream] == [7]
    assert [h["source_id"] for h in result.upstream] == [2]
    for hop in result.downstream + result.upstream:
        assert hop["source_type"] == "job_type"
        assert hop["relation"] == "job_cycle_nest"
        assert hop["origin"] == "job"
        assert hop["href"] == job_type_href(hop["source_id"])


@pytest.mark.asyncio
async def test_job_step_producer_emits_nest_hop_for_job_cycle_link(monkeypatch):
    monkeypatch.setattr(settings, "job_cell_links_enabled", True)
    producer = JobLifecycleProducer()

    cell = SimpleNamespace(id=3, step_id=4, deleted_at=None)
    nest_link = SimpleNamespace(
        kind="job_cycle",
        label="Engineer pack",
        entity_type=None,
        entity_id=None,
        external_url=None,
        audit_run_id=None,
        audit_finding_id=None,
        target_job_type_id=9,
        sort_order=0,
    )

    class _Result:
        def __init__(self, rows):
            self._rows = rows

        def all(self):
            return self._rows

    # First execute: documents in the cell (none). Second: cell links.
    db = SimpleNamespace(execute=AsyncMock(side_effect=[_Result([]), _Result([(nest_link, cell)])]))
    result = await producer.produce(
        db=db, tenant_id=1, entity_type="job_step", entity_id=4, user=SimpleNamespace(is_superuser=True)
    )

    assert result.status == "ok"
    nest_hops = [h for h in result.downstream if h["source_type"] == "job_type"]
    assert len(nest_hops) == 1
    assert nest_hops[0]["source_id"] == 9
    assert nest_hops[0]["relation"] == "job_cycle_nest"
    assert nest_hops[0]["href"] == job_type_href(9)
