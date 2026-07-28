"""Document-control routes must use naive UTC, because their columns are naive.

Every ``DateTime`` column in ``src/domain/models/document_control.py`` is declared
without ``timezone=True``. Postgres therefore stores them as ``timestamp without
time zone``, and asyncpg refuses to adapt a timezone-aware ``datetime`` for such a
column — it raises ``DataError: can't subtract offset-naive and offset-aware
datetimes`` rather than coercing. Every one of those becomes a 500.

This was invisible for two reasons, and both are worth stating because they are
why a guard is needed rather than care:

* **SQLite does not reproduce it.** Verified directly: inserting an aware datetime
  into a naive column and comparing a naive column against an aware value are both
  accepted silently by ``sqlite+aiosqlite``. The whole local development loop runs
  on SQLite, so nothing a developer runs will show this.
* **``GET /document-control/summary`` was unreachable.** It was shadowed by
  ``GET /{document_id}`` and answered 422, which masked the 500 behind it. Fixing
  the route order is what surfaced this.

The convention is per model family, not repo-wide — ``evidence_assets`` and
``policy_acknowledgments`` declare ``DateTime(timezone=True)`` and correctly use
aware datetimes. ``document_version_service`` deliberately mixes: it writes naive
values to the controlled-document tables and an aware value to
``document_versions.published_at``. So this guard is scoped to the one module
whose columns are uniformly naive, rather than being applied blindly everywhere.
"""

from __future__ import annotations

import ast
import pathlib

import pytest
import sqlalchemy as sa

import src.domain.models  # noqa: F401  (register every mapper before reading metadata)
from src.infrastructure.database import Base, engine

ROUTE_MODULE = pathlib.Path("src/api/routes/document_control.py")

# Tables owned by the document-control module, all of which must be naive for the
# convention this file enforces to be the correct one.
DOCUMENT_CONTROL_TABLES = (
    "controlled_documents",
    "controlled_document_versions",
    "document_approval_workflows",
    "document_approval_instances",
    "document_approval_actions",
    "document_distributions",
    "document_training_links",
    "document_access_logs",
    "obsolete_document_records",
)


def _is_now_call(node: ast.AST) -> bool:
    """True for ``datetime.now(...)`` / ``datetime.utcnow()`` and bare ``utcnow()``."""
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    if isinstance(func, ast.Attribute):
        return func.attr in {"now", "utcnow"}
    if isinstance(func, ast.Name):
        return func.id == "utcnow"
    return False


def _replace_tzinfo_none_targets(tree: ast.AST) -> set[int]:
    """ids of the Call nodes that are immediately ``.replace(tzinfo=None)``-wrapped."""
    wrapped: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not (isinstance(func, ast.Attribute) and func.attr == "replace"):
            continue
        makes_naive = any(
            kw.arg == "tzinfo" and isinstance(kw.value, ast.Constant) and kw.value.value is None for kw in node.keywords
        )
        if makes_naive:
            wrapped.add(id(func.value))
    return wrapped


class TestNaiveDatetimeConvention:
    """Static half — dialect-independent, so it fails on a developer's SQLite too."""

    def test_document_control_columns_really_are_all_naive(self) -> None:
        """The premise of this whole file. If it stops holding, the rule changes."""
        aware: dict[str, list[str]] = {}
        for table_name in DOCUMENT_CONTROL_TABLES:
            table = Base.metadata.tables.get(table_name)
            assert table is not None, f"{table_name} is no longer in the ORM metadata; update this test"
            offenders = [
                column.name
                for column in table.columns
                if isinstance(column.type, sa.DateTime) and getattr(column.type, "timezone", False)
            ]
            if offenders:
                aware[table_name] = offenders
        assert not aware, (
            "These document-control columns are now timezone-aware, so the naive-UTC convention "
            f"this module enforces is no longer correct for them: {aware}. Either the model change "
            "was wrong, or this guard and src/api/routes/document_control.py need updating together."
        )

    def test_routes_never_build_an_aware_datetime(self) -> None:
        """No ``datetime.now(...)`` here may escape without ``.replace(tzinfo=None)``."""
        source = ROUTE_MODULE.read_text()
        tree = ast.parse(source, filename=str(ROUTE_MODULE))
        wrapped = _replace_tzinfo_none_targets(tree)
        lines = source.splitlines()

        violations = [
            f"  line {node.lineno}: {lines[node.lineno - 1].strip()}"
            for node in ast.walk(tree)
            if _is_now_call(node) and id(node) not in wrapped
        ]
        assert not violations, (
            f"{ROUTE_MODULE} builds timezone-aware datetimes, but every DateTime column it writes "
            "to and compares against is 'timestamp without time zone'. asyncpg raises DataError "
            "for these and the endpoint returns 500 — and SQLite will not reproduce it, so this "
            "will only show up in CI or production.\n"
            + "\n".join(violations)
            + "\n\nUse the module's _utcnow() helper instead."
        )

    def test_the_helper_actually_returns_naive(self) -> None:
        """Guard the guard: everything above is worthless if _utcnow drifts."""
        from src.api.routes.document_control import _utcnow

        assert _utcnow().tzinfo is None, "_utcnow() must return a naive datetime"


# ---------------------------------------------------------------------------
# Runtime half
#
# Only Postgres reproduces the defect, so these skip on SQLite rather than
# passing and implying cover they do not provide. CI's Integration Tests job
# runs against Postgres, which is where this actually bites.
# ---------------------------------------------------------------------------

_IS_POSTGRES = engine.url.get_backend_name() == "postgresql"

postgres_only = pytest.mark.skipif(
    not _IS_POSTGRES,
    reason=(
        "naive/aware datetime mismatches are only rejected by asyncpg; SQLite accepts them "
        "silently (verified), so this assertion would pass vacuously"
    ),
)


@postgres_only
class TestDocumentControlDatetimePathsOnPostgres:
    """Drive the endpoints that bind a datetime, and require they not 500."""

    async def _create_document(self, admin_client) -> int:
        response = await admin_client.post(
            "/api/v1/document-control/",
            json={
                "title": "Naive datetime regression document",
                "document_type": "procedure",
                "category": "quality",
                "description": "created by test_document_control_naive_datetimes",
            },
        )
        assert response.status_code == 201, response.text
        return response.json()["id"]

    async def test_summary_binds_a_naive_comparison(self, admin_client) -> None:
        """``next_review_date < now`` is the comparison CI caught."""
        response = await admin_client.get("/api/v1/document-control/summary")
        assert response.status_code == 200, (
            f"GET /api/v1/document-control/summary returned {response.status_code}. "
            f"An aware datetime bound against a naive column is the usual cause. Body: {response.text}"
        )

    async def test_update_writes_a_naive_updated_at(self, admin_client) -> None:
        document_id = await self._create_document(admin_client)
        response = await admin_client.put(f"/api/v1/document-control/{document_id}", json={"department": "Quality"})
        assert response.status_code == 200, f"PUT sets document.updated_at; got {response.status_code}: {response.text}"

    async def test_distribute_writes_a_naive_notified_date(self, admin_client) -> None:
        document_id = await self._create_document(admin_client)
        response = await admin_client.post(
            f"/api/v1/document-control/{document_id}/distribute",
            json={"recipient_type": "user", "recipient_name": "Recipient"},
        )
        assert (
            response.status_code == 201
        ), f"distribute sets notified_date; got {response.status_code}: {response.text}"

    async def test_obsolete_writes_naive_obsolete_and_retention_dates(self, admin_client) -> None:
        document_id = await self._create_document(admin_client)
        response = await admin_client.post(
            f"/api/v1/document-control/{document_id}/obsolete",
            json={"obsolete_reason": "superseded by a newer controlled procedure"},
        )
        assert (
            response.status_code == 200
        ), f"obsolete sets obsolete_date and retention_end_date; got {response.status_code}: {response.text}"

    async def test_list_compares_next_review_date_in_python(self, admin_client) -> None:
        """``is_overdue`` compares a loaded column against now, in Python.

        A naive value from Postgres against an aware ``now`` raises TypeError, so
        this only bites once a document actually has a ``next_review_date``.
        """
        document_id = await self._create_document(admin_client)
        from datetime import datetime

        from src.domain.models.document_control import ControlledDocument
        from src.infrastructure.database import async_session_maker

        async with async_session_maker() as session:
            await session.execute(
                sa.update(ControlledDocument)
                .where(ControlledDocument.id == document_id)
                .values(next_review_date=datetime(2020, 1, 1))
            )
            await session.commit()

        response = await admin_client.get("/api/v1/document-control/")
        assert (
            response.status_code == 200
        ), f"listing computes is_overdue from next_review_date; got {response.status_code}: {response.text}"
        listed = [d for d in response.json()["documents"] if d["id"] == document_id]
        assert (
            listed and listed[0]["is_overdue"] is True
        ), f"a document whose next_review_date is in 2020 must read as overdue: {listed}"
