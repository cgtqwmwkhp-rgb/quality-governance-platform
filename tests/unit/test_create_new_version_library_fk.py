"""create_new_version must use Golden Thread hard FK, not title fuzzy match."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.api.routes.document_control import VersionCreate, create_new_version
from src.domain.services.gkb_control_library_link import SoftLibraryMatch


class _Result:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


class _Db:
    def __init__(self, document):
        self.document = document
        self.commit = AsyncMock()
        self.refresh = AsyncMock()

    async def execute(self, _statement):
        return _Result(self.document)


@pytest.mark.asyncio
async def test_create_new_version_skips_gkb_when_only_title_candidate(monkeypatch):
    """Title/reference soft match must not drive rematch/quiz side effects."""
    controlled = SimpleNamespace(
        id=11,
        title="Shared Title Collision",
        document_number="DOC-11",
        library_document_id=None,
    )
    version = SimpleNamespace(id=101, version_number="2.0", status="draft")
    db = _Db(controlled)

    revise = AsyncMock(return_value=version)
    monkeypatch.setattr(
        "src.api.routes.document_control.document_version_service.revise_controlled",
        revise,
    )

    resolve = AsyncMock(
        return_value=(
            SimpleNamespace(
                id=99,
                title="Shared Title Collision",
                description="",
                ai_summary=None,
                ai_tags=None,
                document_type="policy",
            ),
            SoftLibraryMatch(
                library_document_id=None,
                matching_fields=("title",),
                relationship_state="unverified_candidate",
            ),
        )
    )
    monkeypatch.setattr(
        "src.domain.services.gkb_control_library_link.resolve_library_for_controlled",
        resolve,
    )

    rematch = AsyncMock()
    stale = AsyncMock()
    quiz = AsyncMock()
    gkb = SimpleNamespace(
        rematch_evidence_on_version=rematch,
        mark_quizzes_stale_for_document=stale,
        generate_quiz_draft=quiz,
    )
    monkeypatch.setattr(
        "src.domain.services.governed_knowledge_service.governed_knowledge_service",
        gkb,
    )

    response = await create_new_version(
        11,
        VersionCreate(change_summary="Revision for regression coverage"),
        current_user=SimpleNamespace(id=1, full_name="Tester", tenant_id=7),
        db=db,
    )

    assert response["version_number"] == "2.0"
    resolve.assert_awaited_once()
    rematch.assert_not_awaited()
    stale.assert_not_awaited()
    quiz.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_new_version_rematches_via_hard_library_fk(monkeypatch):
    """Hard-linked library_document_id is the only path into GKB rematch on revise."""
    controlled = SimpleNamespace(
        id=11,
        title="PPE Inspection Procedure",
        document_number="PROC-11",
        library_document_id=44,
    )
    library = SimpleNamespace(
        id=44,
        title="PPE Inspection Procedure",
        description="desc",
        ai_summary="summary",
        ai_tags=["ppe"],
        document_type="procedure",
    )
    version = SimpleNamespace(id=101, version_number="3.0", status="draft")
    db = _Db(controlled)

    monkeypatch.setattr(
        "src.api.routes.document_control.document_version_service.revise_controlled",
        AsyncMock(return_value=version),
    )
    monkeypatch.setattr(
        "src.domain.services.gkb_control_library_link.resolve_library_for_controlled",
        AsyncMock(
            return_value=(
                library,
                SoftLibraryMatch(
                    library_document_id=44,
                    matching_fields=("title", "reference_number"),
                    relationship_state="linked",
                ),
            )
        ),
    )

    rematch = AsyncMock()
    stale = AsyncMock()
    quiz = AsyncMock()
    monkeypatch.setattr(
        "src.domain.services.governed_knowledge_service.governed_knowledge_service",
        SimpleNamespace(
            rematch_evidence_on_version=rematch,
            mark_quizzes_stale_for_document=stale,
            generate_quiz_draft=quiz,
        ),
    )

    await create_new_version(
        11,
        VersionCreate(change_summary="Revision for hard-FK rematch path"),
        current_user=SimpleNamespace(id=1, full_name="Tester", tenant_id=7),
        db=db,
    )

    rematch.assert_awaited_once()
    assert rematch.await_args.args[1] == 44
    stale.assert_awaited_once()
    quiz.assert_awaited_once()
    db.commit.assert_awaited()


def test_create_new_version_source_has_no_title_fuzzy_lookup():
    """Regression: revise path must not OR-match library title/reference inline."""
    import ast
    from pathlib import Path

    tree = ast.parse(Path("src/api/routes/document_control.py").read_text())
    fn = next(
        node
        for node in tree.body
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "create_new_version"
    )
    source = ast.get_source_segment(Path("src/api/routes/document_control.py").read_text(), fn)
    assert source is not None
    assert "LibraryDocument.title" not in source
    assert "resolve_library_for_controlled" in source
