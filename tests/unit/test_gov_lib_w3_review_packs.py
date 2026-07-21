"""Governance Library Wave W3 — review packs + horizon stubs."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.domain.exceptions import BadRequestError, ConflictError, StateTransitionError
from src.domain.models.library_review import (
    FindingDisposition,
    LibraryRegulatoryFinding,
    LibraryReviewPack,
    ReviewPackStatus,
)
from src.domain.services.library_horizon_adapter import StubHorizonProvider, get_horizon_provider
from src.domain.services.library_review_service import (
    close_pack,
    confirm_finding,
    horizons,
    open_pack,
    reject_finding,
    review_window_allows_open,
    run_horizon_scan,
    stub_internal_inputs,
)
from src.infrastructure.tasks.library_review_tasks import classify_review_reminder_band

NOW = datetime(2026, 7, 19, 12, 0, 0, tzinfo=timezone.utc)


def _doc(*, review_date, document_id: int = 1, tenant_id: int = 1, title: str = "Fire Policy"):
    return SimpleNamespace(
        id=document_id,
        tenant_id=tenant_id,
        title=title,
        file_name="fire.pdf",
        review_date=review_date,
        category_id=10,
        pel_doc_ref="PEL-HSE-01-0001",
    )


def test_review_window_gate_within_90_and_overdue():
    assert review_window_allows_open(NOW + timedelta(days=45), now=NOW) is True
    assert review_window_allows_open(NOW + timedelta(days=90), now=NOW) is True
    assert review_window_allows_open(NOW - timedelta(days=1), now=NOW) is True
    assert review_window_allows_open(NOW + timedelta(days=91), now=NOW) is False
    assert review_window_allows_open(None, now=NOW) is False


@pytest.mark.asyncio
async def test_open_pack_rejects_outside_window():
    document = _doc(review_date=NOW + timedelta(days=120))

    async def scalar(_stmt):
        return document

    db = SimpleNamespace(scalar=scalar, add=MagicMock(), flush=AsyncMock())
    with pytest.raises(BadRequestError, match="outside"):
        await open_pack(db, tenant_id=1, document_id=1, opened_by_id=5, now=NOW)


@pytest.mark.asyncio
async def test_open_pack_rejects_duplicate_open():
    document = _doc(review_date=NOW + timedelta(days=30))
    existing = LibraryReviewPack(
        id=9,
        tenant_id=1,
        document_id=1,
        status=ReviewPackStatus.OPEN,
        window_days=90,
        opened_at=NOW,
        opened_by_id=1,
    )
    calls = {"n": 0}

    async def scalar(_stmt):
        calls["n"] += 1
        if calls["n"] == 1:
            return document
        return existing

    db = SimpleNamespace(scalar=scalar, add=MagicMock(), flush=AsyncMock())
    with pytest.raises(ConflictError, match="already has an open"):
        await open_pack(db, tenant_id=1, document_id=1, opened_by_id=5, now=NOW)


@pytest.mark.asyncio
async def test_close_pack_blocked_while_pending():
    pack = LibraryReviewPack(
        id=1,
        tenant_id=1,
        document_id=1,
        status=ReviewPackStatus.OPEN,
        window_days=90,
        opened_at=NOW,
        opened_by_id=1,
        findings=[
            LibraryRegulatoryFinding(
                id=1,
                tenant_id=1,
                pack_id=1,
                provider="stub",
                title="Pending finding",
                disposition=FindingDisposition.PENDING,
            )
        ],
    )

    async def scalar(_stmt):
        return pack

    db = SimpleNamespace(scalar=scalar, flush=AsyncMock())
    with pytest.raises(StateTransitionError, match="pending"):
        await close_pack(db, tenant_id=1, pack_id=1, closed_by_id=2)


@pytest.mark.asyncio
async def test_close_pack_ok_when_all_dispositioned():
    pack = LibraryReviewPack(
        id=1,
        tenant_id=1,
        document_id=1,
        status=ReviewPackStatus.OPEN,
        window_days=90,
        opened_at=NOW,
        opened_by_id=1,
        findings=[
            LibraryRegulatoryFinding(
                id=1,
                tenant_id=1,
                pack_id=1,
                provider="stub",
                title="Confirmed",
                disposition=FindingDisposition.CONFIRMED,
            ),
            LibraryRegulatoryFinding(
                id=2,
                tenant_id=1,
                pack_id=1,
                provider="stub",
                title="Rejected",
                disposition=FindingDisposition.REJECTED,
            ),
        ],
    )

    async def scalar(_stmt):
        return pack

    db = SimpleNamespace(scalar=scalar, flush=AsyncMock())
    closed = await close_pack(db, tenant_id=1, pack_id=1, closed_by_id=2)
    assert closed.status == ReviewPackStatus.CLOSED
    assert closed.closed_by_id == 2
    assert closed.closed_at is not None


@pytest.mark.parametrize(
    "days,expected",
    [
        (-1, "overdue"),
        (0, "due_7"),
        (7, "due_7"),
        (8, "due_30"),
        (30, "due_30"),
        (31, "due_60"),
        (60, "due_60"),
        (61, "due_90"),
        (90, "due_90"),
        (91, None),
    ],
)
def test_classify_review_reminder_band(days, expected):
    due = NOW + timedelta(days=days)
    assert classify_review_reminder_band(due, now=NOW) == expected


def test_stub_horizon_provider_returns_deterministic_findings():
    provider = StubHorizonProvider()
    findings = provider.scan(document_id=42, document_title="Fire Policy", tenant_id=1)
    assert 1 <= len(findings) <= 2
    assert all(f.provider == "stub" for f in findings)
    assert findings[0].external_id == "stub-loler-42"
    assert get_horizon_provider("stub").name == "stub"


@pytest.mark.asyncio
async def test_run_horizon_scan_persists_pending_stub_findings():
    pack = LibraryReviewPack(
        id=3,
        tenant_id=1,
        document_id=42,
        status=ReviewPackStatus.OPEN,
        window_days=90,
        opened_at=NOW,
        opened_by_id=1,
    )
    document = _doc(review_date=NOW + timedelta(days=20), document_id=42)
    calls = {"n": 0}
    added: list = []

    async def scalar(_stmt):
        calls["n"] += 1
        if calls["n"] == 1:
            return pack
        return document

    db = SimpleNamespace(scalar=scalar, add=added.append, flush=AsyncMock())
    created = await run_horizon_scan(db, tenant_id=1, pack_id=3, provider_name="stub")
    assert len(created) == 2
    assert all(f.disposition == FindingDisposition.PENDING for f in created)
    assert all(f.provider == "stub" for f in created)
    assert len(added) == 2


@pytest.mark.asyncio
async def test_horizons_buckets_by_review_date():
    docs = [
        _doc(review_date=NOW - timedelta(days=5), document_id=1, title="Overdue"),
        _doc(review_date=NOW + timedelta(days=20), document_id=2, title="Due"),
        _doc(review_date=NOW + timedelta(days=100), document_id=3, title="Upcoming"),
        _doc(review_date=NOW + timedelta(days=400), document_id=4, title="Out of horizon"),
    ]

    async def execute(_stmt):
        return MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=docs))))

    db = SimpleNamespace(execute=execute)
    result = await horizons(db, tenant_id=1, months=12, now=NOW)
    assert result["counts"]["overdue"] == 1
    assert result["counts"]["due"] == 1
    assert result["counts"]["upcoming"] == 1
    assert result["overdue"][0]["document_id"] == 1
    assert result["due"][0]["document_id"] == 2
    assert result["upcoming"][0]["document_id"] == 3


def test_stub_internal_inputs_shape():
    inputs = stub_internal_inputs()
    assert set(inputs) == {"new_docs", "dependencies", "incidents", "audits"}
    assert all(isinstance(v, list) for v in inputs.values())


@pytest.mark.asyncio
async def test_confirm_and_reject_finding():
    pack = LibraryReviewPack(
        id=1,
        tenant_id=1,
        document_id=1,
        status=ReviewPackStatus.OPEN,
        window_days=90,
        opened_at=NOW,
        opened_by_id=1,
    )
    finding = LibraryRegulatoryFinding(
        id=7,
        tenant_id=1,
        pack_id=1,
        provider="stub",
        title="Signal",
        disposition=FindingDisposition.PENDING,
    )
    calls = {"n": 0}

    async def scalar(_stmt):
        calls["n"] += 1
        if calls["n"] % 2 == 1:
            return pack
        return finding

    db = SimpleNamespace(scalar=scalar, flush=AsyncMock())
    confirmed = await confirm_finding(db, tenant_id=1, pack_id=1, finding_id=7, user_id=9, notes="ok")
    assert confirmed.disposition == FindingDisposition.CONFIRMED
    assert confirmed.dispositioned_by_id == 9

    finding.disposition = FindingDisposition.PENDING
    rejected = await reject_finding(db, tenant_id=1, pack_id=1, finding_id=7, user_id=9, notes="noise")
    assert rejected.disposition == FindingDisposition.REJECTED
