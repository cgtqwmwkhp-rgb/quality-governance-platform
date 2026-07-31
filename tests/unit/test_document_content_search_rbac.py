"""Fail-closed RBAC for document chunk FTS in Global Search."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.dialects import postgresql

from src.domain.services.document_library_rbac import (
    PERM_DOCUMENT_READ,
    PERM_DOCUMENT_UPDATE,
    RESTRICTED_TAXONOMY_PERMISSIONS,
)
from src.domain.services.search_service import SearchService


def _sql_with_params(statement) -> tuple[str, dict]:
    # Avoid literal_binds: Postgres REGCONFIG literals for plainto_tsquery fail to render.
    compiled = statement.compile(dialect=postgresql.dialect())
    params = {str(k).lower(): v for k, v in compiled.params.items()}
    return str(compiled).lower(), params


def _user(*, tenant_id: int = 17, perms: set[str] | None = None, is_superuser: bool = False):
    allowed = set(perms or ())
    return SimpleNamespace(
        id=1,
        tenant_id=tenant_id,
        is_superuser=is_superuser,
        has_permission=lambda p: p in allowed,
    )


def _pg_db(execute_side_effect=None):
    bind = SimpleNamespace(dialect=SimpleNamespace(name="postgresql"))
    db = SimpleNamespace(
        get_bind=lambda: bind,
        bind=bind,
        execute=AsyncMock(side_effect=execute_side_effect) if execute_side_effect else AsyncMock(),
    )
    return db


def _doc(
    *,
    doc_id: int = 10,
    access_level: str = "all_staff",
    taxonomy_id: str | None = "02.08",
    sensitivity: str = "internal",
    title: str = "Safety Policy",
    tenant_id: int = 17,
):
    return SimpleNamespace(
        id=doc_id,
        tenant_id=tenant_id,
        title=title,
        reference_number=f"DOC-{doc_id}",
        access_level=access_level,
        category_id=1 if taxonomy_id is not None else None,
        status="Available",
        created_at="2026-01-01",
        sensitivity=sensitivity,
        description=None,
        ai_summary=None,
    )


def _chunk(*, chunk_id: int = 99, page_number: int = 2, content: str = "fire extinguisher drill"):
    return SimpleNamespace(id=chunk_id, page_number=page_number, content=content)


class _Rows:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return list(self._rows)


@pytest.mark.asyncio
async def test_no_document_read_skips_content_search_entirely():
    statements = []

    async def execute(statement):
        statements.append(statement)
        return _Rows([])

    db = _pg_db(execute)
    service = SearchService(db)
    user = _user(perms=set())  # authenticated but no document:read

    hits = await service._search_document_content("fire", user, request_id="r1")

    assert hits == []
    assert statements == []
    db.execute.assert_not_called()


@pytest.mark.asyncio
async def test_missing_tenant_id_skips_content_search():
    db = _pg_db()
    service = SearchService(db)
    user = _user(tenant_id=None, perms={PERM_DOCUMENT_READ})  # type: ignore[arg-type]

    hits = await service._search_document_content("fire", user, request_id="r1")

    assert hits == []
    db.execute.assert_not_called()


@pytest.mark.asyncio
async def test_non_postgres_dialect_skips_fts():
    bind = SimpleNamespace(dialect=SimpleNamespace(name="sqlite"))
    db = SimpleNamespace(get_bind=lambda: bind, bind=bind, execute=AsyncMock())
    service = SearchService(db)
    user = _user(perms={PERM_DOCUMENT_READ})

    hits = await service._search_document_content("fire", user, request_id="r1")

    assert hits == []
    db.execute.assert_not_called()


@pytest.mark.asyncio
async def test_content_sql_scopes_both_tenant_columns_and_uses_plainto_tsquery():
    statements = []

    async def execute(statement):
        statements.append(statement)
        return _Rows([])

    db = _pg_db(execute)
    service = SearchService(db)
    user = _user(tenant_id=17, perms={PERM_DOCUMENT_READ})

    await service._search_document_content("fire drill", user, request_id="r1")

    assert len(statements) == 1
    sql, params = _sql_with_params(statements[0])
    # Both chunk and document tenant predicates (exact equality; no IS NULL broaden).
    assert sql.count("tenant_id") >= 2
    assert "tenant_id is null" not in sql.replace(" is not null", "")
    assert 17 in params.values() or list(params.values()).count(17) >= 1
    # Count exact tenant bind occurrences — both chunk + document should bind 17.
    tenant_binds = [v for v in params.values() if v == 17]
    assert len(tenant_binds) >= 2
    assert "plainto_tsquery" in sql
    # Substring trap: "to_tsquery" is inside "plainto_tsquery".
    assert "to_tsquery(" not in sql.replace("plainto_tsquery(", "")
    assert "document_chunks" in sql
    assert "documents" in sql
    assert "is_active" in sql
    assert "search_vector" in sql
    assert "fire drill" in params.values()


@pytest.mark.asyncio
async def test_python_gate_drops_acl_denied_and_cross_tenant_style_hits():
    """SQL may over-include; Python re-check must drop (404-style omission)."""
    doc = _doc(access_level="managers", taxonomy_id=None)
    chunk = _chunk()
    rows = _Rows([(chunk, doc, None, "extinguisher", 0.9)])

    db = _pg_db(AsyncMock(return_value=rows))
    service = SearchService(db)
    # Staff: document:read only — managers ACL should fail Python gate.
    user = _user(perms={PERM_DOCUMENT_READ})

    with patch("src.domain.services.search_service.track_metric"):
        hits = await service._search_document_content("extinguisher", user, request_id="r1")

    assert hits == []


@pytest.mark.asyncio
async def test_managers_only_hidden_from_staff_visible_with_update():
    doc = _doc(access_level="managers", taxonomy_id=None)
    chunk = _chunk(content="manager briefing pack")
    rows = _Rows([(chunk, doc, None, "briefing", 0.8)])

    staff_db = _pg_db(AsyncMock(return_value=rows))
    staff = _user(perms={PERM_DOCUMENT_READ})
    staff_hits = await SearchService(staff_db)._search_document_content("briefing", staff, None)
    assert staff_hits == []

    mgr_db = _pg_db(AsyncMock(return_value=rows))
    manager = _user(perms={PERM_DOCUMENT_READ, PERM_DOCUMENT_UPDATE})
    mgr_hits = await SearchService(mgr_db)._search_document_content("briefing", manager, None)
    assert len(mgr_hits) == 1
    assert mgr_hits[0].type == "document_content"
    assert mgr_hits[0].entity_id == doc.id
    assert mgr_hits[0].module == "Document Content"


@pytest.mark.parametrize(
    ("taxonomy_id", "token"),
    list(RESTRICTED_TAXONOMY_PERMISSIONS.items()),
)
@pytest.mark.asyncio
async def test_restricted_taxonomy_requires_exact_token(taxonomy_id: str, token: str):
    doc = _doc(access_level="restricted", taxonomy_id=taxonomy_id)
    chunk = _chunk(content="restricted body text")
    rows = _Rows([(chunk, doc, taxonomy_id, "restricted", 0.7)])

    # Wrong / missing restricted token → deny
    denied_db = _pg_db(AsyncMock(return_value=rows))
    denied_user = _user(perms={PERM_DOCUMENT_READ})
    denied = await SearchService(denied_db)._search_document_content("restricted", denied_user, None)
    assert denied == []

    # Exact token → allow
    allowed_db = _pg_db(AsyncMock(return_value=rows))
    allowed_user = _user(perms={PERM_DOCUMENT_READ, token})
    allowed = await SearchService(allowed_db)._search_document_content("restricted", allowed_user, None)
    assert len(allowed) == 1
    assert allowed[0].entity_id == doc.id


@pytest.mark.asyncio
async def test_restricted_without_taxonomy_mapping_is_denied():
    doc = _doc(access_level="restricted", taxonomy_id=None)
    chunk = _chunk()
    # taxonomy_id column from join is None — fail closed
    rows = _Rows([(chunk, doc, None, "secret", 0.5)])

    db = _pg_db(AsyncMock(return_value=rows))
    # Has an OH token but no taxonomy on the hit → still deny
    user = _user(perms={PERM_DOCUMENT_READ, "document:restricted:oh"})

    hits = await SearchService(db)._search_document_content("secret", user, None)
    assert hits == []


@pytest.mark.asyncio
async def test_facets_and_totals_exclude_denied_content_hits():
    denied_doc = _doc(doc_id=1, access_level="managers", taxonomy_id=None)
    allowed_doc = _doc(doc_id=2, access_level="all_staff", taxonomy_id=None)
    rows = _Rows(
        [
            (_chunk(chunk_id=1), denied_doc, None, "alpha", 0.9),
            (_chunk(chunk_id=2), allowed_doc, None, "alpha", 0.8),
        ]
    )
    db = _pg_db(AsyncMock(return_value=rows))
    service = SearchService(db)
    user = _user(perms={PERM_DOCUMENT_READ})

    for method in (
        "_search_incidents",
        "_search_near_misses",
        "_search_rtas",
        "_search_complaints",
        "_search_risks",
        "_search_audits",
        "_search_actions",
        "_search_documents",
    ):
        setattr(service, method, AsyncMock(return_value=[]))

    with patch("src.domain.services.search_service.track_metric"):
        result = await service.search(query="alpha", tenant_id=17, user=user)

    assert result["total"] == 1
    assert result["facets"]["modules"].get("Document Content") == 1
    assert all(r["entity_id"] == 2 for r in result["results"])


@pytest.mark.asyncio
async def test_metadata_document_hits_also_apply_library_acl():
    """Security fix: metadata ILIKE hits must not leak managers/restricted docs."""
    managers_doc = _doc(doc_id=5, access_level="managers", taxonomy_id=None, title="Managers Handbook")

    class _ScalarResult:
        def scalars(self):
            return self

        def all(self):
            return [managers_doc]

    db = SimpleNamespace(execute=AsyncMock(return_value=_ScalarResult()))
    service = SearchService(db)
    staff = _user(perms={PERM_DOCUMENT_READ})

    hits = await service._search_documents("Handbook", tenant_id=17, request_id=None, user=staff)
    assert hits == []

    manager = _user(perms={PERM_DOCUMENT_READ, PERM_DOCUMENT_UPDATE})
    db2 = SimpleNamespace(execute=AsyncMock(return_value=_ScalarResult()))
    hits2 = await SearchService(db2)._search_documents("Handbook", tenant_id=17, request_id=None, user=manager)
    assert len(hits2) == 1


def test_ts_query_helper_is_plainto_not_to_tsquery():
    expr = SearchService._ts_query("fire drill")
    sql = str(expr.compile(dialect=postgresql.dialect())).lower()
    assert "plainto_tsquery" in sql
    # Substring "to_tsquery" appears inside "plainto_tsquery"; assert bare form absent.
    assert "to_tsquery(" not in sql.replace("plainto_tsquery(", "")


def test_library_acl_sql_excludes_managers_for_staff():
    from sqlalchemy import select

    from src.domain.models.document import Document
    from src.domain.models.document_library import DocumentCategory

    staff = _user(perms={PERM_DOCUMENT_READ})
    predicate = SearchService._library_acl_sql_predicate(staff, Document, DocumentCategory)
    _sql_text, params = _sql_with_params(select(Document.id).where(predicate))
    assert "all_staff" in params.values()
    assert "managers" not in params.values()


def test_library_acl_sql_includes_managers_when_user_can_update():
    from sqlalchemy import select

    from src.domain.models.document import Document
    from src.domain.models.document_library import DocumentCategory

    manager = _user(perms={PERM_DOCUMENT_READ, PERM_DOCUMENT_UPDATE})
    predicate = SearchService._library_acl_sql_predicate(manager, Document, DocumentCategory)
    _sql_text, params = _sql_with_params(select(Document.id).where(predicate))
    assert "managers" in params.values()


@pytest.mark.asyncio
async def test_sensitive_docs_suppress_snippets():
    doc = _doc(access_level="all_staff", sensitivity="confidential", taxonomy_id=None)
    chunk = _chunk(content="confidential salary bands")
    rows = _Rows([(chunk, doc, None, "<b>salary</b> bands", 0.9)])
    db = _pg_db(AsyncMock(return_value=rows))
    user = _user(perms={PERM_DOCUMENT_READ})

    hits = await SearchService(db)._search_document_content("salary", user, None)
    assert len(hits) == 1
    assert hits[0].description == ""
    assert "snippet_suppressed" in hits[0].highlights
