"""Unit tests for import triage accept owner gate (PX-264)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.api.routes.risk_register import SuggestionTriageResolve, resolve_suggestion_triage
from src.domain.exceptions import BadRequestError


class _FakeResult:
    def __init__(self, risk):
        self._risk = risk

    def scalar_one_or_none(self):
        return self._risk


@pytest.mark.asyncio
async def test_accept_import_triage_rejects_unassigned():
    risk = SimpleNamespace(
        id=9,
        reference="RSK-IMP-9",
        suggestion_triage_status="pending",
        risk_owner_id=None,
        risk_owner_name=None,
        status="identified",
        is_escalated=False,
        escalation_reason=None,
        review_notes=None,
        updated_at=None,
        tenant_id=1,
    )
    db = AsyncMock()
    db.execute = AsyncMock(return_value=_FakeResult(risk))
    db.commit = AsyncMock()
    user = SimpleNamespace(id=1, tenant_id=1)

    with pytest.raises(BadRequestError, match="owner"):
        await resolve_suggestion_triage(
            risk_id=9,
            body=SuggestionTriageResolve(decision="accept"),
            current_user=user,
            db=db,
        )

    db.commit.assert_not_called()
    assert risk.suggestion_triage_status == "pending"


@pytest.mark.asyncio
async def test_accept_import_triage_allows_named_owner(monkeypatch):
    risk = SimpleNamespace(
        id=10,
        reference="RSK-IMP-10",
        suggestion_triage_status="pending",
        risk_owner_id=None,
        risk_owner_name="Named Owner",
        status="identified",
        is_escalated=False,
        escalation_reason=None,
        review_notes=None,
        updated_at=None,
        tenant_id=1,
    )
    db = AsyncMock()
    db.execute = AsyncMock(return_value=_FakeResult(risk))
    db.commit = AsyncMock()
    user = SimpleNamespace(id=1, tenant_id=1)

    invalidate = MagicMock()
    monkeypatch.setattr(
        "src.api.routes.risk_register.invalidate_tenant_cache",
        AsyncMock(side_effect=invalidate),
    )

    result = await resolve_suggestion_triage(
        risk_id=10,
        body=SuggestionTriageResolve(decision="accept"),
        current_user=user,
        db=db,
    )

    assert result["suggestion_triage_status"] == "accepted"
    assert risk.is_escalated is True
    db.commit.assert_awaited()
