"""Tenant-isolation tests for the advanced document-control module."""

from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from src.api.routes.document_control import DocumentCreate, create_document, get_document, list_documents
from src.domain.exceptions import NotFoundError
from src.domain.models.document_control import (
    ControlledDocument,
    ControlledDocumentVersion,
    DocumentAccessLog,
    DocumentApprovalAction,
    DocumentApprovalInstance,
    DocumentApprovalWorkflow,
    DocumentDistribution,
    DocumentTrainingLink,
    ObsoleteDocumentRecord,
)


class _Result:
    def __init__(self, value=None):
        self.value = value

    def scalar(self):
        return self.value

    def scalar_one_or_none(self):
        return self.value

    def scalars(self):
        return self

    def all(self):
        return [] if self.value is None else list(self.value)


DOCUMENT_CONTROL_MODELS = (
    ControlledDocument,
    ControlledDocumentVersion,
    DocumentApprovalWorkflow,
    DocumentApprovalInstance,
    DocumentApprovalAction,
    DocumentDistribution,
    DocumentTrainingLink,
    DocumentAccessLog,
    ObsoleteDocumentRecord,
)


def _sql(statement) -> str:
    return str(statement.compile(compile_kwargs={"literal_binds": True})).lower()


def test_all_document_control_models_expose_tenant_id():
    """WCS-TEN2: ControlledDocument(+Version) NOT NULL; siblings remain nullable until promoted."""
    required = {ControlledDocument, ControlledDocumentVersion, ObsoleteDocumentRecord}
    for model in DOCUMENT_CONTROL_MODELS:
        column = model.__table__.c.tenant_id
        assert column.index is True
        if model in required:
            assert column.nullable is False
        else:
            assert column.nullable is True


@pytest.mark.asyncio
async def test_list_documents_uses_exact_tenant_scope():
    statements = []

    async def execute(statement):
        statements.append(statement)
        return _Result(0 if len(statements) == 1 else [])

    db = SimpleNamespace(execute=AsyncMock(side_effect=execute))
    user = SimpleNamespace(tenant_id=17)

    response = await list_documents(
        current_user=user,
        db=db,
        document_type=None,
        category=None,
        department=None,
        status=None,
        search=None,
        skip=0,
        limit=50,
    )

    assert response == {"total": 0, "documents": []}
    assert len(statements) == 2
    for statement in statements:
        sql = _sql(statement)
        assert "tenant_id = 17" in sql
        assert "tenant_id is null" not in sql


@pytest.mark.asyncio
async def test_cross_tenant_document_lookup_is_indistinguishable_from_missing():
    statements = []

    async def execute(statement):
        statements.append(statement)
        return _Result(None)

    db = SimpleNamespace(execute=AsyncMock(side_effect=execute))
    user = SimpleNamespace(tenant_id=23)

    with pytest.raises(NotFoundError):
        await get_document(document_id=99, current_user=user, db=db)

    sql = _sql(statements[0])
    assert "controlled_documents.id = 99" in sql
    assert "controlled_documents.tenant_id = 23" in sql


@pytest.mark.asyncio
async def test_create_document_stamps_parent_and_initial_version():
    added = []

    async def refresh(entity):
        if isinstance(entity, ControlledDocument):
            entity.id = 101

    db = SimpleNamespace(
        add=added.append,
        commit=AsyncMock(),
        refresh=AsyncMock(side_effect=refresh),
    )
    user = SimpleNamespace(tenant_id=31)
    payload = DocumentCreate(
        title="Tenant-owned procedure",
        document_type="procedure",
        category="quality",
    )

    await create_document(document_data=payload, current_user=user, db=db)

    assert isinstance(added[0], ControlledDocument)
    assert isinstance(added[1], ControlledDocumentVersion)
    assert added[0].tenant_id == 31
    assert added[1].tenant_id == 31
    assert added[1].document_id == 101


@pytest.mark.asyncio
async def test_document_control_fails_closed_without_tenant_context():
    user = SimpleNamespace(tenant_id=None)
    db = SimpleNamespace(execute=AsyncMock())

    with pytest.raises(HTTPException) as exc:
        await list_documents(current_user=user, db=db, skip=0, limit=50)

    assert exc.value.status_code == 403
    db.execute.assert_not_awaited()


def test_phase1_migration_and_not_null_followup_docs_exist():
    mig = Path("alembic/versions/20260710_document_control_tenancy.py")
    assert mig.is_file()
    tree = ast.parse(mig.read_text())
    assert any(isinstance(n, ast.FunctionDef) and n.name == "upgrade" for n in tree.body)
    followup = Path("docs/data/document-control-tenant-backfill.md")
    assert followup.is_file()
    body = followup.read_text().lower()
    assert "not null" in body
    assert "phase 2" in body or "phase 1" in body
