"""Governance Library Wave W4b — dashboard and PEL dependency contracts."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.domain.exceptions import NotFoundError
from src.domain.services.library_review_service import dashboard_summary, dependency_map

NOW = datetime(2026, 7, 19, 12, 0, 0, tzinfo=timezone.utc)


def _doc(*, document_id: int, review_date, statutory: bool = False, version: str = "2.0"):
    return SimpleNamespace(
        id=document_id,
        tenant_id=7,
        title="HSEQ Fire Procedure",
        file_name="fire.pdf",
        category_id=10,
        review_date=review_date,
        is_statutory=statutory,
        pel_doc_ref="PEL-HSE-01-0001",
        version=version,
        status="published",
    )


@pytest.mark.asyncio
async def test_dashboard_summary_composes_horizon_statutory_and_open_pack_counts():
    docs = [
        _doc(document_id=1, review_date=NOW - timedelta(days=1), statutory=True),
        _doc(document_id=2, review_date=NOW + timedelta(days=30)),
    ]
    counts = iter((3, 2))

    async def execute(_stmt):
        return MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=docs))))

    async def scalar(_stmt):
        return next(counts)

    summary = await dashboard_summary(SimpleNamespace(execute=execute, scalar=scalar), tenant_id=7, now=NOW)

    assert summary == {
        "as_of": NOW.isoformat(),
        "statutory_documents": 3,
        "overdue_reviews": 1,
        "open_review_packs": 2,
    }


@pytest.mark.asyncio
async def test_dependency_map_returns_document_tip_and_only_superseded_history():
    document = _doc(document_id=42, review_date=NOW, version="3.0")
    versions = [
        SimpleNamespace(
            id=3,
            version_number="3.0",
            status="published",
            published_at=NOW,
            change_notes="Current issue",
            created_at=NOW,
        ),
        SimpleNamespace(
            id=2,
            version_number="2.0",
            status="superseded",
            published_at=NOW - timedelta(days=30),
            change_notes="Prior issue",
            created_at=NOW - timedelta(days=30),
        ),
        SimpleNamespace(
            id=1,
            version_number="1.0",
            status="superseded",
            published_at=NOW - timedelta(days=60),
            change_notes=None,
            created_at=NOW - timedelta(days=60),
        ),
    ]

    async def scalar(_stmt):
        return document

    async def execute(_stmt):
        return MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=versions))))

    result = await dependency_map(
        SimpleNamespace(scalar=scalar, execute=execute),
        tenant_id=7,
        pel_doc_ref="PEL-HSE-01-0001",
    )

    assert result["current_tip"]["version_number"] == "3.0"
    assert [row["version_number"] for row in result["superseded_history"]] == ["2.0", "1.0"]


@pytest.mark.asyncio
async def test_dependency_map_is_tenant_scoped_and_raises_for_unknown_reference():
    async def scalar(_stmt):
        return None

    with pytest.raises(NotFoundError, match="PEL-HSE-01-9999"):
        await dependency_map(
            SimpleNamespace(scalar=scalar, execute=AsyncMock()),
            tenant_id=7,
            pel_doc_ref="PEL-HSE-01-9999",
        )
