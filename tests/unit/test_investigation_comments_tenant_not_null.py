"""Unit tests for investigation_comments tenant_id fail-safe backfill (WCS-TEN2)."""

from __future__ import annotations

import ast
from pathlib import Path

from src.domain.models.investigation import InvestigationComment

REPO_ROOT = Path(__file__).resolve().parents[2]
MIGRATION_PATH = REPO_ROOT / "alembic/versions/20260710_investigation_comments_tenant_not_null.py"


def _load_should_enforce_not_null():
    """Extract the pure helper without importing Alembic migration modules."""
    tree = ast.parse(MIGRATION_PATH.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "should_enforce_not_null":
            module = ast.Module(body=[node], type_ignores=[])
            ast.fix_missing_locations(module)
            namespace: dict = {}
            exec(compile(module, str(MIGRATION_PATH), "exec"), namespace)
            return namespace["should_enforce_not_null"]
    raise AssertionError("should_enforce_not_null not found in migration")


def test_investigation_comment_orm_tenant_id_is_required():
    column = InvestigationComment.__table__.c.tenant_id
    assert column.nullable is False
    assert column.index is True


def test_migration_enforces_only_when_all_comments_are_attributed():
    should_enforce_not_null = _load_should_enforce_not_null()
    assert should_enforce_not_null(0) is True
    assert should_enforce_not_null(1) is False


def test_migration_chains_from_investigation_actions_and_never_invents_tenant():
    body = MIGRATION_PATH.read_text(encoding="utf-8")
    assert 'revision: str = "20260710_inv_cmt_nn"' in body
    assert 'down_revision: Union[str, Sequence[str], None] = "20260710_inv_act_nn"' in body
    assert 'TABLE = "investigation_comments"' in body
    assert 'PARENT = "investigation_runs"' in body
    assert 'PARENT_KEY = "investigation_id"' in body
    assert "FAIL-SAFE" in body
    assert "tenant_id = 1" not in body
    assert "SET tenant_id = 1" not in body.upper()
    assert (REPO_ROOT / "docs/data/investigation-comments-tenant-backfill.md").is_file()


def _add_comment_snippet(source: str) -> str:
    start = source.index("async def add_comment")
    markers = (
        "\n    @classmethod\n    async def ",
        "\n    @classmethod\n    def ",
        "\n@router.",
        "\nasync def ",
    )
    next_def = -1
    for marker in markers:
        idx = source.find(marker, start + 1)
        if idx != -1 and (next_def == -1 or idx < next_def):
            next_def = idx
    return source[start:] if next_def == -1 else source[start:next_def]


def test_add_comment_service_stamps_tenant_from_investigation_and_never_invents():
    """Write path must inherit tenant_id from the parent investigation run."""
    body = (REPO_ROOT / "src/domain/services/investigation_service.py").read_text(encoding="utf-8")
    snippet = _add_comment_snippet(body)
    assert "tenant_id=investigation.tenant_id" in snippet
    assert "tenant_id is required to create an investigation comment" in snippet
    assert "tenant_id=1" not in snippet
    assert "SET tenant_id = 1" not in snippet.upper()


def test_add_comment_route_stamps_tenant_from_investigation_and_never_invents():
    """Route POST .../comments must stamp tenant_id (NOT NULL after WCS-TEN2)."""
    body = (REPO_ROOT / "src/api/routes/investigations.py").read_text(encoding="utf-8")
    snippet = _add_comment_snippet(body)
    assert "tenant_id=investigation.tenant_id" in snippet
    assert "InvestigationComment(" in snippet
    assert "tenant_id=1" not in snippet
    assert "SET tenant_id = 1" not in snippet.upper()

