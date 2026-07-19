"""Governance Library Wave W5 disposal and legacy policy freeze acceptance tests."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from src.api.routes import documents, policies
from src.domain.models.enums import DocumentStatus
from src.domain.services.document_library_disposal_service import disposal_eligibility_reason


def _document(**overrides):
    values = {
        "retention_until": datetime.now(timezone.utc) - timedelta(days=1),
        "status": DocumentStatus.RETIRED,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_disposal_candidate_requires_due_retention_and_inactive_lifecycle():
    now = datetime.now(timezone.utc)
    assert disposal_eligibility_reason(_document(), now) is None
    assert disposal_eligibility_reason(_document(retention_until=None), now) == "retention_until_missing"
    assert disposal_eligibility_reason(_document(retention_until=now + timedelta(days=1)), now) == "retention_not_due"
    assert disposal_eligibility_reason(_document(status=DocumentStatus.PUBLISHED), now) == "lifecycle_not_disposable"


@pytest.mark.asyncio
async def test_disposal_preview_is_dry_run_and_exposes_execution_state(monkeypatch):
    candidate = SimpleNamespace(
        document_id=11,
        reference_number="DOC-2026-0011",
        pel_doc_ref="PEL-HSE-01-0011",
        title="Retired procedure",
        status="retired",
        retention_until=datetime.now(timezone.utc) - timedelta(days=1),
        category_retention_rule="Keep for 3 years",
    )
    monkeypatch.setattr(documents, "list_disposal_candidates", AsyncMock(return_value=[candidate]))
    monkeypatch.setattr(documents.settings, "library_disposal_execute", False)

    result = await documents.preview_disposal_queue(
        MagicMock(),
        SimpleNamespace(tenant_id=7),
        limit=25,
    )

    assert result.dry_run is True
    assert result.execute_enabled is False
    assert result.items[0].document_id == 11


@pytest.mark.asyncio
async def test_disposal_execute_is_blocked_by_default(monkeypatch):
    monkeypatch.setattr(documents.settings, "library_disposal_execute", False)

    with pytest.raises(HTTPException) as exc:
        await documents.execute_disposal_queue(
            documents.DisposalExecuteRequest(document_ids=[11]),
            MagicMock(),
            SimpleNamespace(tenant_id=7),
        )

    assert exc.value.status_code == 403
    assert "LIBRARY_DISPOSAL_EXECUTE" in str(exc.value.detail)


@pytest.mark.asyncio
async def test_disposal_execute_delegates_only_when_flag_enabled(monkeypatch):
    monkeypatch.setattr(documents.settings, "library_disposal_execute", True)
    execute = AsyncMock(return_value=[11])
    monkeypatch.setattr(documents, "execute_disposal", execute)

    result = await documents.execute_disposal_queue(
        documents.DisposalExecuteRequest(document_ids=[11]),
        MagicMock(),
        SimpleNamespace(tenant_id=7),
    )

    assert result.disposed_document_ids == [11]
    execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_legacy_policy_create_is_frozen_before_any_write():
    with pytest.raises(HTTPException) as exc:
        await policies.create_policy(
            MagicMock(),
            MagicMock(),
            MagicMock(),
            request_id="test-request",
        )

    assert exc.value.status_code == 410
    assert "Governance Library" in str(exc.value.detail)
