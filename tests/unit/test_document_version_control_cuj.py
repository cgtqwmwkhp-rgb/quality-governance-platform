"""CUJ — Document version control: create → revise → publish with immutability."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.api.routes.document_control import DocumentCreate, DocumentUpdate, create_document, update_document
from src.domain.exceptions import BadRequestError
from src.domain.models.document_control import ControlledDocument, ControlledDocumentVersion
from src.domain.services.document_version_service import DocumentVersionService


class _ScalarResult:
    def __init__(self, value=None):
        self._value = value

    def scalar_one_or_none(self):
        return self._value

    def scalars(self):
        return self

    def all(self):
        return list(self._value or [])


class _ScriptedSession:
    """Minimal async session that returns scripted scalar/execute results."""

    def __init__(self, scalar_queue=None, execute_queue=None):
        self.added: list = []
        self._scalar_queue = list(scalar_queue or [])
        self._execute_queue = list(execute_queue or [])

    def add(self, obj):
        self.added.append(obj)
        if getattr(obj, "id", None) is None:
            obj.id = len(self.added)

    async def flush(self):
        return None

    async def scalar(self, _statement):
        if not self._scalar_queue:
            return None
        return self._scalar_queue.pop(0)

    async def execute(self, _statement):
        if not self._execute_queue:
            return _ScalarResult([])
        return self._execute_queue.pop(0)


@pytest.mark.asyncio
async def test_create_revise_publish_freezes_prior_published():
    """Service CUJ: 1.0 draft → publish → revise 1.1 → publish supersedes 1.0."""
    service = DocumentVersionService()
    document = ControlledDocument(
        id=1,
        tenant_id=3,
        document_number="PRO-TEST01",
        title="Version CUJ Procedure",
        document_type="procedure",
        category="quality",
        current_version="1.0",
        major_version=1,
        minor_version=0,
        status="draft",
    )

    v1 = service.build_initial_controlled_version(
        tenant_id=3,
        document_id=1,
        author_name="Controller",
        created_by_id=1,
    )
    v1.id = 1

    # publish: scalar finds draft v1; execute finds no prior published
    db = _ScriptedSession(
        scalar_queue=[v1],
        execute_queue=[_ScalarResult([])],
    )
    published = await service.publish_controlled(
        db,
        document,
        tenant_id=3,
        published_by_id=1,
        published_by_name="Controller",
    )
    assert published.version_number == "1.0"
    assert published.status == "published"
    assert published.is_immutable is True
    assert document.status == "published"

    # revise after publish: scalar finds no open draft (first call), then new draft created
    db2 = _ScriptedSession(scalar_queue=[None])
    draft = await service.revise_controlled(
        db2,
        document,
        tenant_id=3,
        change_summary="Updated PPE section after near-miss review",
        is_major_version=False,
        created_by_id=1,
        created_by_name="Controller",
    )
    assert draft.version_number == "1.1"
    assert draft.status == "draft"
    assert draft.is_immutable is False
    assert document.status == "under_revision"
    assert document.current_version == "1.1"

    # publish 1.1: scalar finds draft; execute returns prior published v1
    db3 = _ScriptedSession(
        scalar_queue=[draft],
        execute_queue=[_ScalarResult([v1])],
    )
    published2 = await service.publish_controlled(
        db3,
        document,
        tenant_id=3,
        published_by_id=1,
        published_by_name="Controller",
    )
    assert published2.version_number == "1.1"
    assert published2.is_immutable is True
    assert v1.status == "superseded"
    assert v1.is_immutable is True
    assert document.current_version == "1.1"
    assert document.status == "published"


@pytest.mark.asyncio
async def test_update_published_controlled_document_is_rejected():
    document = SimpleNamespace(id=9, status="published", updated_at=None)
    db = SimpleNamespace(
        execute=AsyncMock(return_value=_ScalarResult(document)),
        commit=AsyncMock(),
        refresh=AsyncMock(),
    )
    user = SimpleNamespace(tenant_id=1, id=1)

    with pytest.raises(BadRequestError, match="read-only"):
        await update_document(
            document_id=9,
            document_data=DocumentUpdate(title="Should not apply"),
            current_user=user,
            db=db,
        )


@pytest.mark.asyncio
async def test_create_document_route_returns_honest_version_payload():
    added = []

    async def refresh(entity):
        if isinstance(entity, ControlledDocument):
            entity.id = 55

    db = SimpleNamespace(
        add=added.append,
        commit=AsyncMock(),
        refresh=AsyncMock(side_effect=refresh),
    )
    user = SimpleNamespace(tenant_id=12, id=4)
    payload = DocumentCreate(
        title="Honest version create path",
        document_type="procedure",
        category="ops",
    )
    result = await create_document(document_data=payload, current_user=user, db=db)
    assert result["current_version"] == "1.0"
    assert result["status"] == "draft"
    assert result["version"]["version_number"] == "1.0"
    assert result["version"]["status"] == "draft"
    assert result["version"]["is_immutable"] is False
    assert isinstance(added[1], ControlledDocumentVersion)
    assert added[1].version_number == "1.0"
