"""create_new_version must use Golden Thread hard FK resolve, and must NOT rematch.

ADR-0021 P0: rematch / quiz stale / quiz draft fire on publish, not revise draft.
"""

from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.api.routes.document_control import VersionCreate, create_new_version, publish_document
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
async def test_create_new_version_does_not_rematch_even_with_hard_library_fk(monkeypatch):
    """Opening a revise draft must not mark evidence needs_review / stale quizzes."""
    controlled = SimpleNamespace(
        id=11,
        title="PPE Inspection Procedure",
        document_number="PROC-11",
        library_document_id=44,
    )
    version = SimpleNamespace(id=101, version_number="3.0", status="draft")
    db = _Db(controlled)

    monkeypatch.setattr(
        "src.api.routes.document_control.document_version_service.revise_controlled",
        AsyncMock(return_value=version),
    )

    rematch = AsyncMock()
    stale = AsyncMock()
    quiz = AsyncMock()
    lifecycle = AsyncMock()
    monkeypatch.setattr(
        "src.domain.services.governed_knowledge_service.governed_knowledge_service",
        SimpleNamespace(
            rematch_evidence_on_version=rematch,
            mark_quizzes_stale_for_document=stale,
            generate_quiz_draft=quiz,
        ),
    )
    monkeypatch.setattr(
        "src.domain.services.gkb_publish_lifecycle.run_controlled_publish_lifecycle",
        lifecycle,
    )

    response = await create_new_version(
        11,
        VersionCreate(change_summary="Revision must not rematch"),
        current_user=SimpleNamespace(id=1, full_name="Tester", tenant_id=7),
        db=db,
    )

    assert response["version_number"] == "3.0"
    rematch.assert_not_awaited()
    stale.assert_not_awaited()
    quiz.assert_not_awaited()
    lifecycle.assert_not_awaited()


@pytest.mark.asyncio
async def test_publish_document_runs_controlled_publish_lifecycle(monkeypatch):
    """Controlled publish is the rematch / quiz-stale trigger (hard FK path)."""
    controlled = SimpleNamespace(
        id=11,
        title="PPE Inspection Procedure",
        current_version="3.0",
        status="published",
        library_document_id=44,
    )
    version = SimpleNamespace(
        id=101,
        version_number="3.0",
        status="published",
        change_summary=None,
        change_type="revision",
        is_immutable=True,
        created_by_name="Tester",
        created_at=None,
        approved_by_name="Tester",
        approved_date=None,
        effective_date=None,
    )
    db = _Db(controlled)

    monkeypatch.setattr(
        "src.api.routes.document_control.document_version_service.publish_controlled",
        AsyncMock(return_value=version),
    )
    monkeypatch.setattr(
        "src.api.routes.document_control.document_version_service.serialize_controlled_version",
        lambda v: {"id": v.id, "version_number": v.version_number, "status": v.status},
    )

    lifecycle = AsyncMock(
        return_value=SimpleNamespace(
            rematch_invoked=True,
            quizzes_stale_invoked=True,
            quiz_draft_invoked=True,
        )
    )
    monkeypatch.setattr(
        "src.domain.services.gkb_publish_lifecycle.run_controlled_publish_lifecycle",
        lifecycle,
    )

    await publish_document(
        11,
        current_user=SimpleNamespace(id=1, full_name="Tester", tenant_id=7),
        db=db,
    )

    lifecycle.assert_awaited_once()
    assert lifecycle.await_args.kwargs["new_version"] == "3.0"
    assert lifecycle.await_args.kwargs["tenant_id"] == 7
    assert db.commit.await_count >= 2


@pytest.mark.asyncio
async def test_create_new_version_source_still_resolves_library_only_on_publish_path():
    """Regression: revise path must not OR-match library title/reference inline."""
    tree = ast.parse(Path("src/api/routes/document_control.py").read_text())
    fn = next(
        node for node in tree.body if isinstance(node, ast.AsyncFunctionDef) and node.name == "create_new_version"
    )
    source = ast.get_source_segment(Path("src/api/routes/document_control.py").read_text(), fn)
    assert source is not None
    assert "LibraryDocument.title" not in source
    assert "rematch_evidence_on_version" not in source
    assert "run_controlled_publish_lifecycle" not in source

    publish_fn = next(
        node for node in tree.body if isinstance(node, ast.AsyncFunctionDef) and node.name == "publish_document"
    )
    publish_source = ast.get_source_segment(Path("src/api/routes/document_control.py").read_text(), publish_fn)
    assert publish_source is not None
    assert "run_controlled_publish_lifecycle" in publish_source


@pytest.mark.asyncio
async def test_soft_library_candidate_still_skipped_on_publish(monkeypatch):
    """Publish lifecycle denies when Golden Thread is not hard-linked."""
    from src.domain.services.gkb_publish_lifecycle import PublishLifecycleDenyReason, run_controlled_publish_lifecycle

    controlled = SimpleNamespace(id=11, library_document_id=None, title="Collision")
    resolve = AsyncMock(
        return_value=(
            SimpleNamespace(id=99, title="Collision"),
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
    result = await run_controlled_publish_lifecycle(
        db=SimpleNamespace(),
        controlled_document=controlled,
        new_version="2.0",
        user=SimpleNamespace(id=1),
        tenant_id=7,
        service=SimpleNamespace(rematch_evidence_on_version=rematch),
    )
    assert result.planned.denied is True
    assert result.planned.deny_reason == PublishLifecycleDenyReason.LIBRARY_DOCUMENT_REQUIRED
    rematch.assert_not_awaited()
