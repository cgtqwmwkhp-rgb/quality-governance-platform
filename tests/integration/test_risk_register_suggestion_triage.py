"""Integration tests: enterprise risk import suggestion triage API."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from src.domain.models.risk_register import EnterpriseRisk
from src.infrastructure.database import async_session_maker


async def _insert_pending_risk(*, reference_suffix: str) -> int:
    async with async_session_maker() as session:
        risk = EnterpriseRisk(
            tenant_id=1,
            reference=f"RSK-TRIAGE-{reference_suffix}"[:50],
            title="Import triage test risk",
            description="Created for suggestion-triage integration tests.",
            category="compliance",
            subcategory="audit_finding",
            source="audit_finding",
            context="test",
            inherent_likelihood=2,
            inherent_impact=3,
            inherent_score=6,
            residual_likelihood=2,
            residual_impact=3,
            residual_score=6,
            risk_appetite="cautious",
            appetite_threshold=12,
            is_within_appetite=True,
            treatment_strategy="treat",
            status="identified",
            review_frequency_days=30,
            is_escalated=False,
            linked_audits=["AUD-TEST-1", "FIND-TEST-1"],
            suggestion_triage_status="pending",
            created_by=1,
        )
        session.add(risk)
        await session.commit()
        await session.refresh(risk)
        return int(risk.id)


@pytest.mark.asyncio
async def test_suggestion_triage_accept(admin_client: AsyncClient) -> None:
    suffix = uuid.uuid4().hex[:8]
    risk_id = await _insert_pending_risk(reference_suffix=suffix)

    res = await admin_client.post(
        f"/api/v1/risk-register/{risk_id}/suggestion-triage",
        json={"decision": "accept", "notes": " OK to track "},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["id"] == risk_id
    assert body["suggestion_triage_status"] == "accepted"
    assert body["status"] == "identified"

    async with async_session_maker() as session:
        row = (await session.execute(select(EnterpriseRisk).where(EnterpriseRisk.id == risk_id))).scalar_one()
        assert row.suggestion_triage_status == "accepted"
        assert row.is_escalated is True
        assert row.escalation_reason and "Accepted from import triage" in row.escalation_reason


@pytest.mark.asyncio
async def test_suggestion_triage_reject_with_notes(admin_client: AsyncClient) -> None:
    suffix = uuid.uuid4().hex[:8]
    risk_id = await _insert_pending_risk(reference_suffix=suffix)

    res = await admin_client.post(
        f"/api/v1/risk-register/{risk_id}/suggestion-triage",
        json={"decision": "reject", "notes": "Duplicate of existing control."},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["suggestion_triage_status"] == "rejected"
    assert body["status"] == "closed"

    async with async_session_maker() as session:
        row = (await session.execute(select(EnterpriseRisk).where(EnterpriseRisk.id == risk_id))).scalar_one()
        assert row.suggestion_triage_status == "rejected"
        assert row.status == "closed"
        assert row.review_notes and "Import triage rejected" in row.review_notes
        assert "Duplicate" in (row.review_notes or "")


@pytest.mark.asyncio
async def test_suggestion_triage_rejects_when_not_pending(admin_client: AsyncClient) -> None:
    suffix = uuid.uuid4().hex[:8]
    risk_id = await _insert_pending_risk(reference_suffix=suffix)
    await admin_client.post(
        f"/api/v1/risk-register/{risk_id}/suggestion-triage",
        json={"decision": "accept"},
    )
    res = await admin_client.post(
        f"/api/v1/risk-register/{risk_id}/suggestion-triage",
        json={"decision": "reject"},
    )
    assert res.status_code == 400
    payload = res.json()
    msg = payload.get("detail") or (payload.get("error") or {}).get("message", "")
    assert "not awaiting" in str(msg).lower()


@pytest.mark.asyncio
async def test_suggestion_triage_list_pending_filter(admin_client: AsyncClient) -> None:
    suffix = uuid.uuid4().hex[:8]
    risk_id = await _insert_pending_risk(reference_suffix=suffix)

    pending = await admin_client.get("/api/v1/risk-register/?suggestion_triage=pending&limit=100")
    assert pending.status_code == 200
    ids = {r["id"] for r in pending.json().get("items", [])}
    assert risk_id in ids

    await admin_client.post(
        f"/api/v1/risk-register/{risk_id}/suggestion-triage",
        json={"decision": "accept"},
    )

    pending_after = await admin_client.get("/api/v1/risk-register/?suggestion_triage=pending&limit=100")
    assert pending_after.status_code == 200
    ids_after = {r["id"] for r in pending_after.json().get("items", [])}
    assert risk_id not in ids_after
