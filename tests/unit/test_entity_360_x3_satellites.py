"""X-3: Entity360 satellite Connections — CEL + CAPA producers, flag default off."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.api.schemas.entity_360 import Entity360Hop
from src.core.config import settings
from src.domain.features.catalogue import CLIENT_FEATURES_BY_KEY
from src.domain.models.capa import CAPASource
from src.domain.services.entity_360.permissions import HOP_READ_PERMISSIONS
from src.domain.services.entity_360.producers.case_link import CaseLinkProducer
from src.domain.services.entity_360.producers.compliance_evidence import ComplianceEvidenceProducer
from src.domain.services.entity_360.registry import all_producers, ensure_default_producers, reset_producers
from src.domain.services.href_registry import clause_evidence_href, registered_entity_types


def test_entity_360_satellites_flag_pre_registered_default_off():
    feature = CLIENT_FEATURES_BY_KEY["entity_360_satellites"]
    assert feature.settings_attr == "entity_360_satellites_enabled"
    assert settings.entity_360_satellites_enabled is False


def test_cel_producer_registered_and_excludes_document():
    reset_producers()
    ensure_default_producers()
    producers = list(all_producers())
    origins = {p.origin for p in producers}
    assert "cel" in origins
    cel = next(p for p in producers if p.origin == "cel")
    assert isinstance(cel, ComplianceEvidenceProducer)
    assert cel.supports("incident")
    assert cel.supports("audit_finding")
    assert cel.supports("risk")
    assert not cel.supports("document")
    assert not cel.supports("capa")


def test_evidence_link_hop_permission_mapped():
    assert "evidence_link" in HOP_READ_PERMISSIONS
    assert HOP_READ_PERMISSIONS["evidence_link"] is None


def test_clause_evidence_href_and_dead_clause_int_builder_removed():
    assert clause_evidence_href("9001-7.2") == "/compliance/evidence?clause=9001-7.2"
    assert "clause=" in clause_evidence_href("a&b")
    assert "clause" not in registered_entity_types()
    assert "evidence_link" in registered_entity_types()


@pytest.mark.asyncio
async def test_cel_producer_skipped_when_flag_off(monkeypatch):
    monkeypatch.setattr(settings, "entity_360_satellites_enabled", False)
    producer = ComplianceEvidenceProducer()
    db = SimpleNamespace(execute=AsyncMock())
    result = await producer.produce(
        db=db,
        tenant_id=1,
        entity_type="incident",
        entity_id=9,
        user=SimpleNamespace(is_superuser=True),
    )
    assert result.status == "skipped"
    assert result.reason == "entity_360_satellites disabled"
    db.execute.assert_not_called()


@pytest.mark.asyncio
async def test_cel_producer_emits_evidence_link_hop(monkeypatch):
    monkeypatch.setattr(settings, "entity_360_satellites_enabled", True)
    producer = ComplianceEvidenceProducer()

    link = SimpleNamespace(
        id=44,
        clause_id="9001-7.2",
        title=None,
        signal_type="nonconformity",
        confidence=4.2,  # out of range — must be dropped
        document_version_id=None,
        effective_status=SimpleNamespace(value="confirmed"),
    )

    class _Scalars:
        def all(self):
            return [link]

    class _Result:
        def scalars(self):
            return _Scalars()

    db = SimpleNamespace(execute=AsyncMock(return_value=_Result()))
    result = await producer.produce(
        db=db,
        tenant_id=1,
        entity_type="incident",
        entity_id=9,
        user=SimpleNamespace(is_superuser=True),
    )
    assert result.status == "ok"
    assert result.upstream == []
    assert len(result.downstream) == 1
    hop = result.downstream[0]
    assert hop["source_type"] == "evidence_link"
    assert hop["source_id"] == 44
    assert hop["reference"] == "9001-7.2"
    assert hop["href"] == clause_evidence_href("9001-7.2")
    assert hop["origin"] == "cel"
    assert hop["relation"] == "clause_nonconformity"
    assert hop["confidence"] is None
    assert hop["direction"] == "downstream"
    Entity360Hop.model_validate({k: hop[k] for k in hop if not k.startswith("_")})
    assert hop["source_type"] in HOP_READ_PERMISSIONS


@pytest.mark.asyncio
async def test_case_link_audit_finding_skipped_when_flag_off(monkeypatch):
    monkeypatch.setattr(settings, "entity_360_satellites_enabled", False)
    producer = CaseLinkProducer()
    db = SimpleNamespace(execute=AsyncMock())
    result = await producer.produce(
        db=db,
        tenant_id=1,
        entity_type="audit_finding",
        entity_id=88,
        user=SimpleNamespace(is_superuser=True),
    )
    assert result.status == "skipped"
    db.execute.assert_not_called()


@pytest.mark.asyncio
async def test_case_link_risk_downstream_empty_when_flag_off(monkeypatch):
    monkeypatch.setattr(settings, "entity_360_satellites_enabled", False)
    producer = CaseLinkProducer()

    class _Scalars:
        def all(self):
            return []

    class _Result:
        def scalars(self):
            return _Scalars()

        def all(self):
            return []

    async def _list_links(*_a, **_k):
        return []

    db = SimpleNamespace(execute=AsyncMock(return_value=_Result()))
    monkeypatch.setattr(
        "src.domain.services.entity_360.producers.case_link.list_case_links_for_risk",
        _list_links,
    )
    result = await producer.produce(
        db=db,
        tenant_id=1,
        entity_type="risk",
        entity_id=3,
        user=SimpleNamespace(is_superuser=True),
    )
    assert result.status == "ok"
    assert result.downstream == []


@pytest.mark.asyncio
async def test_case_link_risk_treatment_capa_when_flag_on(monkeypatch):
    monkeypatch.setattr(settings, "entity_360_satellites_enabled", True)
    producer = CaseLinkProducer()

    capa = SimpleNamespace(
        id=12,
        title="Treat spill",
        reference_number="CAPA-12",
        status=SimpleNamespace(value="open"),
    )

    class _EmptyScalars:
        def all(self):
            return []

    class _CapaScalars:
        def all(self):
            return [capa]

    call_n = {"n": 0}

    class _Result:
        def scalars(self):
            call_n["n"] += 1
            # finding join then capa query
            if call_n["n"] == 1:
                return _EmptyScalars()
            return _CapaScalars()

        def all(self):
            return []

    async def _list_links(*_a, **_k):
        return []

    db = SimpleNamespace(execute=AsyncMock(return_value=_Result()))
    monkeypatch.setattr(
        "src.domain.services.entity_360.producers.case_link.list_case_links_for_risk",
        _list_links,
    )
    result = await producer.produce(
        db=db,
        tenant_id=1,
        entity_type="risk",
        entity_id=3,
        user=SimpleNamespace(is_superuser=True),
    )
    assert result.status == "ok"
    assert len(result.downstream) == 1
    hop = result.downstream[0]
    assert hop["source_type"] == "capa"
    assert hop["source_id"] == 12
    assert hop["relation"] == "risk_treatment"
    assert hop["href"] == "/actions/12"
    assert hop["origin"] == "case_link"
    Entity360Hop.model_validate(hop)
    assert hop["source_type"] in HOP_READ_PERMISSIONS


@pytest.mark.asyncio
async def test_case_link_capa_upstream_from_incident(monkeypatch):
    monkeypatch.setattr(settings, "entity_360_satellites_enabled", True)
    producer = CaseLinkProducer()

    capa = SimpleNamespace(
        id=5,
        title="Fix",
        reference_number="CAPA-5",
        source_type=CAPASource.INCIDENT,
        source_id=9,
        status=SimpleNamespace(value="open"),
    )
    incident = SimpleNamespace(id=9, title="Spill", reference_number="INC-9")

    class _CapaResult:
        def scalar_one_or_none(self):
            return capa

    class _IncidentResult:
        def scalar_one_or_none(self):
            return incident

    results = [_CapaResult(), _IncidentResult()]

    db = SimpleNamespace(execute=AsyncMock(side_effect=results))
    result = await producer.produce(
        db=db,
        tenant_id=1,
        entity_type="capa",
        entity_id=5,
        user=SimpleNamespace(is_superuser=True),
    )
    assert result.status == "ok"
    assert result.downstream == []
    assert len(result.upstream) == 1
    hop = result.upstream[0]
    assert hop["source_type"] == "incident"
    assert hop["source_id"] == 9
    assert hop["relation"] == "capa_source"
    assert hop["href"] == "/incidents/9"
    Entity360Hop.model_validate(hop)


@pytest.mark.asyncio
async def test_case_link_capa_empty_upstream_when_source_unmapped(monkeypatch):
    monkeypatch.setattr(settings, "entity_360_satellites_enabled", True)
    producer = CaseLinkProducer()
    capa = SimpleNamespace(
        id=5,
        title="Fix",
        reference_number="CAPA-5",
        source_type=CAPASource.INDUCTION,
        source_id=None,
        status=SimpleNamespace(value="open"),
    )

    class _CapaResult:
        def scalar_one_or_none(self):
            return capa

    db = SimpleNamespace(execute=AsyncMock(return_value=_CapaResult()))
    result = await producer.produce(
        db=db,
        tenant_id=1,
        entity_type="capa",
        entity_id=5,
        user=SimpleNamespace(is_superuser=True),
    )
    assert result.status == "ok"
    assert result.upstream == []
    assert result.downstream == []


@pytest.mark.asyncio
async def test_case_link_audit_finding_downstream_risks_and_capas(monkeypatch):
    monkeypatch.setattr(settings, "entity_360_satellites_enabled", True)
    producer = CaseLinkProducer()

    risk = SimpleNamespace(id=7, title="Fire", reference="R-7")
    capa = SimpleNamespace(
        id=12,
        title="Close NC",
        reference_number="CAPA-12",
        status=SimpleNamespace(value="open"),
    )

    class _RiskScalars:
        def all(self):
            return [risk]

    class _CapaScalars:
        def all(self):
            return [capa]

    class _RiskResult:
        def scalars(self):
            return _RiskScalars()

    class _CapaResult:
        def scalars(self):
            return _CapaScalars()

    db = SimpleNamespace(execute=AsyncMock(side_effect=[_RiskResult(), _CapaResult()]))
    result = await producer.produce(
        db=db,
        tenant_id=1,
        entity_type="audit_finding",
        entity_id=88,
        user=SimpleNamespace(is_superuser=True),
    )
    assert result.status == "ok"
    assert result.upstream == []
    assert len(result.downstream) == 2
    types = {h["source_type"] for h in result.downstream}
    assert types == {"risk", "capa"}
    for hop in result.downstream:
        Entity360Hop.model_validate(hop)
        assert hop["source_type"] in HOP_READ_PERMISSIONS
