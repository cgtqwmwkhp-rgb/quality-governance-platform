"""Unit tests for Assessor Follow-up A lifecycle auto-assess hooks."""

from __future__ import annotations

from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@asynccontextmanager
async def _nested_ok():
    yield


def _db_with_nested() -> MagicMock:
    db = MagicMock()
    db.begin_nested = lambda: _nested_ok()
    return db


@pytest.mark.asyncio
async def test_complaint_assess_hook_invokes_service() -> None:
    from src.api.routes.complaints import _trigger_operational_standards_assess

    complaint = SimpleNamespace(id=11, title="Late delivery", description="Missed SLA", tenant_id=7)
    user = SimpleNamespace(id=1)
    db = _db_with_nested()
    assess = AsyncMock()

    with patch(
        "src.domain.services.governed_knowledge_service.governed_knowledge_service.assess_operational_entity",
        assess,
    ):
        await _trigger_operational_standards_assess(db, complaint, user)

    assess.assert_awaited_once()
    kwargs = assess.await_args.kwargs
    assert kwargs["entity_type"] == "complaint"
    assert kwargs["entity_id"] == "11"
    assert "Late delivery" in kwargs["content"]
    assert kwargs["tenant_id"] == 7


@pytest.mark.asyncio
async def test_complaint_assess_hook_swallows_errors() -> None:
    from src.api.routes.complaints import _trigger_operational_standards_assess

    complaint = SimpleNamespace(id=11, title="x", description="y", tenant_id=7)
    with patch(
        "src.domain.services.governed_knowledge_service.governed_knowledge_service.assess_operational_entity",
        AsyncMock(side_effect=RuntimeError("boom")),
    ):
        await _trigger_operational_standards_assess(_db_with_nested(), complaint, SimpleNamespace(id=1))


@pytest.mark.asyncio
async def test_near_miss_assess_hook_invokes_service() -> None:
    from src.api.routes.near_miss import _trigger_operational_standards_assess

    near_miss = SimpleNamespace(
        id=22,
        description="Almost hit by forklift",
        potential_consequences="Injury",
        preventive_action_suggested="Barriers",
        location="Yard A",
        tenant_id=3,
    )
    assess = AsyncMock()
    with patch(
        "src.domain.services.governed_knowledge_service.governed_knowledge_service.assess_operational_entity",
        assess,
    ):
        await _trigger_operational_standards_assess(AsyncMock(), near_miss, SimpleNamespace(id=1))

    kwargs = assess.await_args.kwargs
    assert kwargs["entity_type"] == "near_miss"
    assert kwargs["entity_id"] == "22"
    assert "Almost hit" in kwargs["content"]
    assert "Yard A" in kwargs["content"]


@pytest.mark.asyncio
async def test_rta_assess_hook_invokes_service() -> None:
    from src.api.routes.rtas import _trigger_operational_standards_assess

    rta = SimpleNamespace(id=33, title="Junction collision", description="Low speed", tenant_id=9)
    assess = AsyncMock()
    with patch(
        "src.domain.services.governed_knowledge_service.governed_knowledge_service.assess_operational_entity",
        assess,
    ):
        await _trigger_operational_standards_assess(AsyncMock(), rta, SimpleNamespace(id=1))

    kwargs = assess.await_args.kwargs
    assert kwargs["entity_type"] == "rta"
    assert kwargs["entity_id"] == "33"


@pytest.mark.asyncio
async def test_audit_finding_assess_hook_passes_finding_type() -> None:
    from src.api.routes.audits import _trigger_operational_standards_assess

    finding = SimpleNamespace(
        id=44,
        title="Doc control gap",
        description="Uncontrolled copies",
        tenant_id=5,
        finding_type="opportunity",
    )
    assess = AsyncMock()
    with patch(
        "src.domain.services.governed_knowledge_service.governed_knowledge_service.assess_operational_entity",
        assess,
    ):
        await _trigger_operational_standards_assess(AsyncMock(), finding, SimpleNamespace(id=1))

    kwargs = assess.await_args.kwargs
    assert kwargs["entity_type"] == "audit_finding"
    assert kwargs["entity_id"] == "44"
    assert kwargs["finding_type"] == "opportunity"


@pytest.mark.asyncio
async def test_audit_finding_assess_hook_swallows_errors() -> None:
    from src.api.routes.audits import _trigger_operational_standards_assess

    finding = SimpleNamespace(
        id=44,
        title="x",
        description="y",
        tenant_id=5,
        finding_type="nonconformity",
    )
    with patch(
        "src.domain.services.governed_knowledge_service.governed_knowledge_service.assess_operational_entity",
        AsyncMock(side_effect=RuntimeError("boom")),
    ):
        await _trigger_operational_standards_assess(AsyncMock(), finding, SimpleNamespace(id=1))
