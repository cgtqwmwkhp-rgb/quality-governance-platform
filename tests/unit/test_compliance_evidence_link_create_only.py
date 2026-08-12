"""Create-only CEL writer behaviour (Wave 2 PR-D)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.exc import IntegrityError

from src.domain.models.compliance_evidence import EvidenceCoverKind, EvidenceLinkMethod
from src.domain.services.compliance_evidence_link_writer import create_evidence_links_if_absent


class _Result:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return SimpleNamespace(all=lambda: list(self._rows))


@pytest.mark.asyncio
async def test_create_if_absent_leaves_existing_row_untouched(monkeypatch):
    existing = SimpleNamespace(
        clause_id="9001-7.5",
        title="Original title",
        notes="keep me",
        confirmed_by_id=42,
        confirmed_at="stamp",
        confidence=0.9,
    )
    db = AsyncMock()
    db.execute = AsyncMock(return_value=_Result([existing]))
    db.add = MagicMock()
    db.commit = AsyncMock()

    result = await create_evidence_links_if_absent(
        db,
        tenant_id=1,
        entity_type="document",
        entity_id="9",
        clause_ids=["9001-7.5"],
        cover_kind=EvidenceCoverKind.COVERS,
        link_method=EvidenceLinkMethod.MANUAL,
        actor_id=99,
        title="Would overwrite",
        notes="Would overwrite",
        commit=True,
    )
    assert result.created == []
    assert result.existing == [existing]
    assert existing.title == "Original title"
    assert existing.notes == "keep me"
    assert existing.confirmed_by_id == 42
    db.add.assert_not_called()
    db.commit.assert_not_called()


@pytest.mark.asyncio
async def test_create_if_absent_classifies_integrity_error_as_existing(monkeypatch):
    db = AsyncMock()
    # First select: nothing live. Second select after IntegrityError: the winner.
    winner = SimpleNamespace(clause_id="14001-7.5", id=77)
    db.execute = AsyncMock(side_effect=[_Result([]), _Result([winner])])
    db.add = MagicMock()
    db.commit = AsyncMock(side_effect=IntegrityError("stmt", {}, Exception("dup")))
    db.rollback = AsyncMock()
    db.refresh = AsyncMock()

    async def fake_pin(*_args, **_kwargs):
        return None

    monkeypatch.setattr(
        "src.domain.services.cel_version_pin.pin_evidence_link_document_version",
        fake_pin,
    )

    result = await create_evidence_links_if_absent(
        db,
        tenant_id=1,
        entity_type="document",
        entity_id="9",
        clause_ids=["14001-7.5"],
        cover_kind=EvidenceCoverKind.COVERS,
        link_method=EvidenceLinkMethod.MANUAL,
        actor_id=1,
        signal_type="evidence",
        commit=True,
    )
    assert result.created == []
    assert result.existing == [winner]
    db.rollback.assert_awaited()
