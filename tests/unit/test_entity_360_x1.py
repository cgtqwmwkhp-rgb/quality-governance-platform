"""Entity360 X-1: hop contract, risk upstream freeze, publish block, flag-off 404."""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from src.api.routes import entity_360 as entity_360_routes
from src.api.schemas.entity_360 import Entity360Hop
from src.api.schemas.risk_register import RiskUpstreamItem
from src.core.config import settings
from src.domain.services.entity_360 import (
    HOP_REQUIRED_FIELDS,
    Entity360Service,
    build_impact_bundle,
    make_hop,
    narrow_risk_upstream_item,
    publish_blocked_detail,
    reset_producers,
)
from src.domain.services.entity_360.producers.document_graph import DocumentGraphProducer
from src.domain.services.entity_360.registry import all_producers, ensure_default_producers
from src.domain.services.href_registry import (
    case_type_href,
    document_href,
    href_for,
    risk_href,
)
from src.domain.services.risk_service import RiskService

RISK_UPSTREAM_WIRE_FIELDS = frozenset({"source_type", "source_id", "title", "reference", "href", "audit_run_id"})


# ---------------------------------------------------------------------------
# href registry
# ---------------------------------------------------------------------------


def test_href_registry_centralises_paths():
    assert document_href(42) == "/documents/42"
    assert risk_href(7) == "/risk-register/7"
    assert case_type_href("incident", 3) == "/incidents/3"
    assert case_type_href("near_miss", 3) == "/near-misses/3"
    assert href_for("complaint", 9) == "/complaints/9"


def test_hop_contract_fields_frozen():
    hop = make_hop(
        source_type="document",
        source_id=1,
        href=document_href(1),
        direction="upstream",
        relation="implements",
        origin="graph",
        title="Policy",
        reference="POL-1",
        status="confirmed",
        confidence=0.9,
        edge_id=10,
        version_pin=5,
    )
    for field in HOP_REQUIRED_FIELDS:
        assert field in hop
    Entity360Hop.model_validate(hop)


# ---------------------------------------------------------------------------
# Bidirectional producer registration
# ---------------------------------------------------------------------------


def test_document_graph_producer_registers_both_directions():
    reset_producers()
    ensure_default_producers()
    producers = list(all_producers())
    origins = {p.origin for p in producers}
    assert "graph" in origins
    assert "case_link" in origins
    graph = next(p for p in producers if p.origin == "graph")
    assert graph.supports("document")
    assert isinstance(graph, DocumentGraphProducer)


@pytest.mark.asyncio
async def test_document_graph_producer_emits_upstream_and_downstream_lists():
    """Bidirectional contract: both keys always present even when empty."""
    producer = DocumentGraphProducer()

    class _Scalars:
        def all(self):
            return []

    class _Result:
        def scalars(self):
            return _Scalars()

    db = SimpleNamespace(execute=AsyncMock(return_value=_Result()))
    result = await producer.produce(
        db=db,
        tenant_id=1,
        entity_type="document",
        entity_id=10,
        user=SimpleNamespace(is_superuser=True, has_permission=lambda _p: True),
    )
    assert result.status == "ok"
    assert isinstance(result.upstream, list)
    assert isinstance(result.downstream, list)


# ---------------------------------------------------------------------------
# Risk upstream wire freeze
# ---------------------------------------------------------------------------


def test_risk_upstream_narrowing_preserves_wire_shape():
    hop = make_hop(
        source_type="incident",
        source_id=7,
        href="/incidents/7",
        direction="upstream",
        relation="linked_risk",
        origin="case_link",
        title="Spill",
        reference="INC-7",
        status="confirmed",
    )
    hop["_audit_run_id"] = 99  # should not appear unless audit_finding
    item = narrow_risk_upstream_item(hop)
    assert set(item.keys()) <= RISK_UPSTREAM_WIRE_FIELDS
    validated = RiskUpstreamItem(**item)
    assert validated.href == "/incidents/7"
    assert validated.source_type == "incident"


@pytest.mark.asyncio
async def test_list_upstream_for_risk_builds_hrefs_via_entity360():
    link = SimpleNamespace(case_type="incident", case_id=7, created_at=datetime(2026, 7, 1), id=1)
    incident = SimpleNamespace(id=7, title="Spill", reference_number="INC-7")
    finding = SimpleNamespace(id=501, title="Missing control", reference_number="AF-501", run_id=41)

    class _FakeScalars:
        def __init__(self, items):
            self._items = items

        def all(self):
            return self._items

    class _FakeResult:
        def __init__(self, items=None):
            self._items = items or []

        def scalars(self):
            return _FakeScalars(self._items)

    db = SimpleNamespace(execute=AsyncMock())
    db.execute.side_effect = [
        _FakeResult(items=[link]),
        _FakeResult(items=[incident]),
        _FakeResult(items=[finding]),
    ]
    service = RiskService(db)  # type: ignore[arg-type]
    items = await service.list_upstream_for_risk(tenant_id=1, risk_id=42)
    assert len(items) == 2
    assert items[0]["href"] == "/incidents/7"
    assert items[1]["href"] == "/audits/41/execute"
    for item in items:
        RiskUpstreamItem(**item)


# ---------------------------------------------------------------------------
# ImpactBundle publish block
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_impact_bundle_blocks_when_degraded():
    with patch(
        "src.domain.services.entity_360.impact.Entity360Service.compose",
        new=AsyncMock(
            return_value={
                "entity": {"source_type": "document", "source_id": 1, "href": "/documents/1"},
                "upstream": [],
                "downstream": [],
                "sources": [{"origin": "lifecycle", "status": "error"}],
                "complete": False,
                "degraded_reasons": ["campaigns unavailable"],
                "generated_at": datetime.utcnow(),
            }
        ),
    ):
        bundle = await build_impact_bundle(
            db=MagicMock(),
            tenant_id=1,
            document_id=1,
            user=SimpleNamespace(is_superuser=True, has_permission=lambda _p: True),
        )
    assert bundle["complete"] is False
    assert bundle["can_publish"] is False
    detail = publish_blocked_detail(bundle)
    assert detail["code"] == "ENTITY360_IMPACT_INCOMPLETE"
    assert "campaigns unavailable" in detail["degraded_reasons"]


@pytest.mark.asyncio
async def test_publish_route_blocks_when_entity360_degraded(monkeypatch):
    from src.api.routes import documents as documents_routes

    monkeypatch.setattr(documents_routes.settings, "entity_360_enabled", True)

    async def _fake_get_doc(*_a, **_k):
        return SimpleNamespace(id=9, tenant_id=1)

    async def _fake_impact(**_k):
        return {
            "complete": False,
            "can_publish": False,
            "degraded_reasons": ["lifecycle campaigns: boom"],
            "sources": [{"origin": "lifecycle", "status": "error"}],
        }

    monkeypatch.setattr(documents_routes, "_get_document_or_404", _fake_get_doc)

    with (
        patch(
            "src.domain.services.entity_360.build_impact_bundle",
            new=_fake_impact,
        ),
        patch(
            "src.domain.services.entity_360.publish_blocked_detail",
            wraps=publish_blocked_detail,
        ),
    ):
        with pytest.raises(HTTPException) as exc_info:
            await documents_routes.publish_document_version(
                document_id=9,
                db=MagicMock(),
                current_user=SimpleNamespace(id=1, tenant_id=1),  # type: ignore[arg-type]
                version_id=None,
            )
    assert exc_info.value.status_code == 409
    assert exc_info.value.detail["code"] == "ENTITY360_IMPACT_INCOMPLETE"


# ---------------------------------------------------------------------------
# Flag-off 404
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_entity_360_flag_off_dependency_404(monkeypatch):
    monkeypatch.setattr(settings, "entity_360_enabled", False)
    with pytest.raises(HTTPException) as exc_info:
        await entity_360_routes.require_entity_360_enabled()
    assert exc_info.value.status_code == 404
    assert "not enabled" in str(exc_info.value.detail).lower()


@pytest.mark.asyncio
async def test_composer_denied_carries_no_count():
    """When all hops are filtered, source status is denied without hop counts."""
    from src.domain.services.entity_360.types import ProducerResult

    class _DenyAll:
        is_superuser = False

        def has_permission(self, _p: str) -> bool:
            return False

    class _StubProducer:
        origin = "graph"

        def supports(self, entity_type: str) -> bool:
            return entity_type == "document"

        async def produce(self, **_kwargs):
            return ProducerResult(
                origin="graph",
                status="ok",
                upstream=[
                    make_hop(
                        source_type="document",
                        source_id=2,
                        href="/documents/2",
                        direction="upstream",
                        relation="implements",
                        origin="graph",
                    )
                ],
                downstream=[],
            )

    with patch(
        "src.domain.services.entity_360.composer.iter_producers",
        return_value=[_StubProducer()],
    ):
        service = Entity360Service(MagicMock())
        bundle = await service.compose(
            tenant_id=1,
            entity_type="document",
            entity_id=1,
            user=_DenyAll(),
        )
    assert bundle["sources"][0]["status"] == "denied"
    assert "count" not in bundle["sources"][0]
    assert bundle["upstream"] == []
    assert bundle["downstream"] == []
