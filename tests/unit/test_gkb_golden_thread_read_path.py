"""Controlled-document GKB evidence-chain read path."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.api.routes.document_control import get_document_golden_thread


class _Result:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value

    def scalars(self):
        return self

    def all(self):
        return self.value if isinstance(self.value, list) else []


class _Db:
    def __init__(self, values):
        self.values = list(values)

    async def execute(self, _statement):
        return _Result(self.values.pop(0))


@pytest.mark.asyncio
async def test_golden_thread_exposes_unverified_candidate_evidence_with_honesty():
    controlled = SimpleNamespace(
        id=11,
        document_number="PROC-11",
        title="PPE Inspection Procedure",
        current_version="2.1",
        status="published",
    )
    library = SimpleNamespace(
        id=44,
        reference_number="PROC-11",
        title="PPE Inspection Procedure",
        version="2.1",
        status="approved",
    )
    link = SimpleNamespace(
        id=99,
        clause_id="ISO9001:7.5",
        effective_status=SimpleNamespace(value="confirmed"),
        signal_type=None,
        scheme="iso9001",
        confidence=0.95,
        linked_by=SimpleNamespace(value="manual"),
        title="PPE inspection record",
        rationale="Controlled procedure supports documented information.",
        created_at=None,
    )
    response = await get_document_golden_thread(
        11,
        current_user=SimpleNamespace(tenant_id=7),
        db=_Db([controlled, [library], [link]]),
    )

    assert response["library_document_candidate"]["id"] == 44
    assert response["library_document_candidate"]["matching_fields"] == ["title", "reference_number"]
    assert response["evidence_links"][0]["clause_id"] == "ISO9001:7.5"
    assert response["integrity"]["relationship_state"] == "unverified_candidate"
    assert response["integrity"]["hard_fk_present"] is False
    assert response["publish_plan"]["deny_reason"] == "hard_fk_absent"


@pytest.mark.asyncio
async def test_golden_thread_hides_ambiguous_library_candidates():
    controlled = SimpleNamespace(
        id=11,
        document_number="PROC-11",
        title="PPE Inspection Procedure",
        current_version="2.1",
        status="published",
    )
    candidates = [
        SimpleNamespace(id=44, title="PPE Inspection Procedure"),
        SimpleNamespace(id=45, title="PPE Inspection Procedure"),
    ]

    response = await get_document_golden_thread(
        11,
        current_user=SimpleNamespace(tenant_id=7),
        db=_Db([controlled, candidates]),
    )

    assert response["library_document_candidate"] is None
    assert response["evidence_links"] == []
    assert response["integrity"]["relationship_state"] == "ambiguous"
    assert response["publish_plan"]["documents_hard_fk_gap"] is True
