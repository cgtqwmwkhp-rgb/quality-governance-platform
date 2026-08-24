"""WI-2 / L-32 — occurrence file homes → Register ``documents.id``.

Pins three things:

1. **Schema.** The link is nullable, indexed and ``ON DELETE SET NULL`` on both
   occurrence tables, and the migration's DDL is in lockstep with the ORM.
   The occurrence blob columns survive — WI-2 links files, it does not move them.
2. **The two link paths.** A steward naming a Register id, or a proven content
   match. Nothing else, and neither path may insert into ``documents``.
3. **The UVDB projection.** ``documents_presented`` elements become
   ``{document_id, label}``, and an element only carries an id the caller's
   tenant can actually see.

The link tests run against a real in-memory SQLite session rather than mocks.
The property under test is that a query is *tenant-scoped*, and a mock returns
whatever it was told to return regardless of the WHERE clause handed to it —
which is precisely the bug these tests exist to catch.
"""

from __future__ import annotations

import ast
import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any, Optional
from unittest.mock import AsyncMock

import pytest
import sqlalchemy as sa
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from src.api.routes import evidence_assets as evidence_assets_routes
from src.api.routes import planet_mark as planet_mark_routes
from src.domain.models.document import Document, DocumentType
from src.domain.models.document_control import ControlledDocument
from src.domain.models.evidence_asset import EvidenceAsset, EvidenceSourceModule
from src.domain.models.planet_mark import CarbonEvidence
from src.domain.services.library_file_home_link import (
    LinkMethod,
    LinkStatus,
    link_carbon_evidence,
    link_evidence_asset,
    normalise_documents_presented,
    presented_element_parts,
    promote_carbon_evidence,
    promote_evidence_asset,
    register_document_exists,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
MIGRATION_PATH = REPO_ROOT / "alembic" / "versions" / "20261031_lib_wi2_file_homes_documents_id.py"
SERVICE_PATH = REPO_ROOT / "src" / "domain" / "services" / "library_file_home_link.py"
VERSIONS = REPO_ROOT / "alembic" / "versions"

REVISION = "20261031_lib_wi2_homes"
DOWN_REVISION = "20261030_lib_wi1_cel"

#: model, table, FK name, index name — the same tuple the migration walks.
LINKED_HOMES = (
    (CarbonEvidence, "carbon_evidence", "fk_carbon_evidence_document_id", "ix_carbon_evidence_document_id"),
    (EvidenceAsset, "evidence_assets", "fk_evidence_assets_document_id", "ix_evidence_assets_document_id"),
)


def _load_migration() -> ModuleType:
    import alembic

    if not hasattr(alembic, "op"):
        alembic.op = SimpleNamespace(get_bind=lambda: None)  # type: ignore[attr-defined]

    spec = importlib.util.spec_from_file_location("qgp_lib_wi2_homes_migration", MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


migration = _load_migration()


# ---------------------------------------------------------------------------
# Migration chain and shape
# ---------------------------------------------------------------------------


def test_migration_chains_from_the_wi1_head() -> None:
    assert migration.revision == REVISION
    assert len(REVISION) <= 32, "alembic version_num column is 32 chars"
    assert migration.down_revision == DOWN_REVISION


def test_no_sibling_revision_also_sits_on_the_wi1_head() -> None:
    """WI-2 owns the next revision. A second child of WI-1 is a dual head."""
    siblings = []
    for path in sorted(VERSIONS.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        if f'down_revision: Union[str, Sequence[str], None] = "{DOWN_REVISION}"' in text:
            siblings.append(path.name)
        elif f'down_revision = "{DOWN_REVISION}"' in text:
            siblings.append(path.name)
    assert siblings == [MIGRATION_PATH.name], f"expected WI-2 alone on the WI-1 head, found {siblings}"


def test_migration_links_exactly_the_two_blob_homes() -> None:
    assert migration.LINKED_HOMES == tuple((table, fk, index) for _, table, fk, index in LINKED_HOMES)


def test_migration_performs_no_backfill() -> None:
    """A link is a claim. The migration may only add structure, never assert one.

    Enforced structurally rather than by reading the docstring: any ``op.execute``
    / ``op.bulk_insert`` would be a data write, and the whole L-32 position is
    that no legacy row's Register identity is knowable from the database alone.
    """
    allowed = {
        "get_bind",
        "add_column",
        "create_foreign_key",
        "create_index",
        "drop_index",
        "drop_constraint",
        "drop_column",
    }
    tree = ast.parse(MIGRATION_PATH.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name) and func.value.id == "op":
            assert func.attr in allowed, f"migration may not call op.{func.attr} — that is a data write"


def test_migration_downgrade_removes_every_artefact_it_added() -> None:
    source = MIGRATION_PATH.read_text(encoding="utf-8")
    downgrade = source[source.index("def downgrade()") :]
    for call in ("drop_index", "drop_constraint", "drop_column"):
        assert f"op.{call}(" in downgrade, f"downgrade never calls {call}"
    assert "reversed(LINKED_HOMES)" in downgrade, "downgrade must unwind in reverse order"


# ---------------------------------------------------------------------------
# ORM ↔ migration lockstep
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(("model", "table", "fk_name", "index_name"), LINKED_HOMES, ids=[h[1] for h in LINKED_HOMES])
def test_document_id_is_a_nullable_indexed_set_null_link(model: Any, table: str, fk_name: str, index_name: str) -> None:
    column = model.__table__.columns["document_id"]
    assert column.nullable is True, "legacy rows have no provable Register identity"
    assert isinstance(column.type, sa.Integer)

    foreign_keys = list(column.foreign_keys)
    assert len(foreign_keys) == 1
    fk = foreign_keys[0]
    assert fk.column is Document.__table__.c.id, "the only library file home is documents.id"
    assert fk.name == fk_name, "ORM constraint name must match the migration's"
    assert fk.ondelete == "SET NULL", "deleting a Register document must not delete the occurrence row"

    index_names = {index.name for index in model.__table__.indexes}
    assert index_name in index_names, f"{table}.document_id must be indexed as {index_name}"


@pytest.mark.parametrize(
    ("model", "columns"),
    [
        (CarbonEvidence, ("storage_key", "file_path", "file_hash")),
        (EvidenceAsset, ("storage_key", "checksum_sha256")),
    ],
    ids=["carbon_evidence", "evidence_assets"],
)
def test_occurrence_blob_columns_are_retained(model: Any, columns: tuple[str, ...]) -> None:
    """WI-2 links; the F-3 allowlist shrink that drops these is a later cut."""
    present = set(model.__table__.columns.keys())
    for name in columns:
        assert name in present, f"{name} must survive WI-2 — dropping it is out of scope"


def test_link_service_may_only_read_the_database() -> None:
    """The 'no silent Register create' rule, enforced on the AST.

    A ``db.add`` here would be how a library quietly fills with documents nobody
    filed, so the service is restricted to reads and in-session attribute writes;
    the route owns the commit.
    """
    tree = ast.parse(SERVICE_PATH.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name) and func.value.id == "db":
            assert func.attr in {"scalar", "execute"}, f"link service may only read, found db.{func.attr}"
        if isinstance(func, ast.Name) and func.id == "Document":
            raise AssertionError("link service must never construct a Register Document")


# ---------------------------------------------------------------------------
# Fixtures — a real session, because tenant scoping is the thing under test
# ---------------------------------------------------------------------------


@pytest.fixture
async def db_session():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        for model in (Document, ControlledDocument, CarbonEvidence, EvidenceAsset):
            await conn.run_sync(model.__table__.create)

    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        yield session

    await engine.dispose()


_REFERENCE = iter(range(1, 10_000))


def _document(*, tenant_id: int, title: str = "Fuel Card July", file_path: str = "blob/fuel-july.pdf") -> Document:
    number = next(_REFERENCE)
    return Document(
        tenant_id=tenant_id,
        title=title,
        file_name=f"{title}.pdf",
        file_type=DocumentType.POLICY,
        file_size=2048,
        file_path=file_path,
        reference_number=f"PEL-DOC-{number:05d}",
    )


def _control_record(*, tenant_id: int, document: Document, checksum: str) -> ControlledDocument:
    return ControlledDocument(
        tenant_id=tenant_id,
        document_number=f"CD-{document.reference_number}",
        title=document.title,
        document_type="policy",
        category="hse",
        library_document_id=document.id,
        checksum=checksum,
    )


def _carbon_evidence(
    *,
    tenant_id: Optional[int],
    storage_key: Optional[str] = None,
    file_path: Optional[str] = None,
    file_hash: Optional[str] = None,
) -> CarbonEvidence:
    return CarbonEvidence(
        tenant_id=tenant_id,
        reporting_year_id=1,
        document_name="Fuel Card July",
        document_type="invoice",
        evidence_category="fuel",
        storage_key=storage_key,
        file_path=file_path,
        file_hash=file_hash,
    )


def _evidence_asset(
    *,
    tenant_id: Optional[int],
    storage_key: str = "cases/1/photo.jpg",
    checksum: Optional[str] = None,
) -> EvidenceAsset:
    return EvidenceAsset(
        tenant_id=tenant_id,
        storage_key=storage_key,
        content_type="application/pdf",
        source_module=EvidenceSourceModule.INVESTIGATION,
        source_id="1",
        checksum_sha256=checksum,
    )


async def _seed(session: AsyncSession, *rows: Any) -> None:
    for row in rows:
        session.add(row)
    await session.flush()


# ---------------------------------------------------------------------------
# Steward path — an explicitly named Register id
# ---------------------------------------------------------------------------


async def test_register_document_exists_is_tenant_scoped(db_session: AsyncSession) -> None:
    document = _document(tenant_id=1)
    await _seed(db_session, document)

    assert await register_document_exists(db_session, tenant_id=1, document_id=document.id) is True
    assert await register_document_exists(db_session, tenant_id=2, document_id=document.id) is False
    assert await register_document_exists(db_session, tenant_id=None, document_id=document.id) is False


async def test_steward_links_carbon_evidence_to_a_document_in_its_tenant(db_session: AsyncSession) -> None:
    document = _document(tenant_id=1)
    evidence = _carbon_evidence(tenant_id=1)
    await _seed(db_session, document, evidence)

    outcome = await link_carbon_evidence(db_session, evidence, tenant_id=1, document_id=document.id)

    assert outcome.status is LinkStatus.LINKED
    assert outcome.method is LinkMethod.STEWARD
    assert outcome.written is True
    assert evidence.document_id == document.id


async def test_steward_cannot_link_carbon_evidence_across_tenants(db_session: AsyncSession) -> None:
    """The whole point of the tenant check: an id alone is not authority."""
    other_tenants_document = _document(tenant_id=2)
    evidence = _carbon_evidence(tenant_id=1)
    await _seed(db_session, other_tenants_document, evidence)

    outcome = await link_carbon_evidence(db_session, evidence, tenant_id=1, document_id=other_tenants_document.id)

    assert outcome.status is LinkStatus.DOCUMENT_NOT_FOUND
    assert outcome.is_error is True
    assert outcome.written is False
    assert evidence.document_id is None, "a rejected link must leave the row untouched"


async def test_steward_link_to_an_unknown_id_is_rejected(db_session: AsyncSession) -> None:
    evidence = _carbon_evidence(tenant_id=1)
    await _seed(db_session, evidence)

    outcome = await link_carbon_evidence(db_session, evidence, tenant_id=1, document_id=999_999)

    assert outcome.status is LinkStatus.DOCUMENT_NOT_FOUND
    assert evidence.document_id is None


async def test_steward_link_without_a_tenant_is_rejected(db_session: AsyncSession) -> None:
    document = _document(tenant_id=1)
    evidence = _carbon_evidence(tenant_id=None)
    await _seed(db_session, document, evidence)

    outcome = await link_carbon_evidence(db_session, evidence, tenant_id=None, document_id=document.id)

    assert outcome.status is LinkStatus.DOCUMENT_NOT_FOUND
    assert evidence.document_id is None


async def test_steward_clears_a_wrong_link_without_touching_the_row(db_session: AsyncSession) -> None:
    document = _document(tenant_id=1)
    evidence = _carbon_evidence(tenant_id=1, storage_key="pm/fuel.pdf")
    await _seed(db_session, document, evidence)
    evidence.document_id = document.id

    outcome = await link_carbon_evidence(db_session, evidence, tenant_id=1, document_id=None)

    assert outcome.status is LinkStatus.CLEARED
    assert outcome.document_id == document.id, "the cleared id is reported so it can be audited"
    assert outcome.written is True
    assert evidence.document_id is None
    assert evidence.storage_key == "pm/fuel.pdf", "clearing a link must not touch the occurrence blob"


async def test_clearing_an_absent_link_writes_nothing(db_session: AsyncSession) -> None:
    evidence = _carbon_evidence(tenant_id=1)
    await _seed(db_session, evidence)

    outcome = await link_carbon_evidence(db_session, evidence, tenant_id=1, document_id=None)

    assert outcome.status is LinkStatus.UNMATCHED
    assert outcome.written is False


async def test_relinking_the_same_document_is_a_no_op(db_session: AsyncSession) -> None:
    document = _document(tenant_id=1)
    evidence = _carbon_evidence(tenant_id=1)
    await _seed(db_session, document, evidence)
    evidence.document_id = document.id

    outcome = await link_carbon_evidence(db_session, evidence, tenant_id=1, document_id=document.id)

    assert outcome.status is LinkStatus.ALREADY_LINKED
    assert outcome.written is False


async def test_steward_links_and_cannot_cross_tenants_on_evidence_assets(db_session: AsyncSession) -> None:
    mine = _document(tenant_id=1)
    theirs = _document(tenant_id=2)
    asset = _evidence_asset(tenant_id=1)
    await _seed(db_session, mine, theirs, asset)

    rejected = await link_evidence_asset(db_session, asset, tenant_id=1, document_id=theirs.id)
    assert rejected.status is LinkStatus.DOCUMENT_NOT_FOUND
    assert asset.document_id is None

    accepted = await link_evidence_asset(db_session, asset, tenant_id=1, document_id=mine.id)
    assert accepted.status is LinkStatus.LINKED
    assert asset.document_id == mine.id


@pytest.mark.parametrize(
    ("route_module", "route", "route_kwargs", "expected_details"),
    [
        (
            evidence_assets_routes,
            evidence_assets_routes.update_evidence_asset,
            {
                "asset_id": 17,
                "asset_data": SimpleNamespace(model_dump=lambda **_: {"document_id": 29}),
            },
            {"asset_id": 17, "document_id": 29},
        ),
        (
            planet_mark_routes,
            planet_mark_routes.patch_evidence,
            {
                "year_id": 11,
                "evidence_id": 17,
                "patch": SimpleNamespace(
                    is_verified=None,
                    verified_by=None,
                    notes=None,
                    model_fields_set={"document_id"},
                    document_id=29,
                ),
            },
            {"year_id": 11, "evidence_id": 17, "document_id": 29},
        ),
    ],
)
async def test_steward_link_rejections_share_the_422_document_not_found_contract(
    monkeypatch: pytest.MonkeyPatch,
    route_module: ModuleType,
    route: Any,
    route_kwargs: dict[str, Any],
    expected_details: dict[str, int],
) -> None:
    """Both occurrence PATCH surfaces expose the same tenant-safe error."""
    occurrence = SimpleNamespace(id=17, tenant_id=1, document_id=None)
    result = SimpleNamespace(scalar_one_or_none=lambda: occurrence)
    db = SimpleNamespace(
        execute=AsyncMock(return_value=result),
        commit=AsyncMock(),
        refresh=AsyncMock(),
    )
    current_user = SimpleNamespace(id=7, tenant_id=1)
    rejected = SimpleNamespace(
        is_error=True,
        status=LinkStatus.DOCUMENT_NOT_FOUND,
        detail="Register document was not found",
    )
    link_name = "link_evidence_asset" if route_module is evidence_assets_routes else "link_carbon_evidence"
    monkeypatch.setattr(route_module, link_name, AsyncMock(return_value=rejected))

    with pytest.raises(HTTPException) as exc_info:
        await route(db=db, current_user=current_user, **route_kwargs)

    assert exc_info.value.status_code == 422
    assert exc_info.value.detail == {
        "code": "DOCUMENT_NOT_FOUND",
        "message": "Register document was not found",
        "details": expected_details,
    }
    db.commit.assert_not_awaited()


# ---------------------------------------------------------------------------
# Promote path — a proven match, or nothing
# ---------------------------------------------------------------------------


async def test_promote_matches_on_content_hash_through_the_control_anchor(db_session: AsyncSession) -> None:
    document = _document(tenant_id=1)
    await _seed(db_session, document)
    await _seed(db_session, _control_record(tenant_id=1, document=document, checksum="ABC123"))
    evidence = _carbon_evidence(tenant_id=1, file_hash="abc123")
    await _seed(db_session, evidence)

    outcome = await promote_carbon_evidence(db_session, evidence, tenant_id=1)

    assert outcome.status is LinkStatus.LINKED
    assert outcome.method is LinkMethod.CONTENT_HASH, "a digest is stronger evidence than a path"
    assert evidence.document_id == document.id


async def test_promote_matches_on_an_identical_blob_path(db_session: AsyncSession) -> None:
    document = _document(tenant_id=1, file_path="blob/tenant1/fuel.pdf")
    evidence = _carbon_evidence(tenant_id=1, storage_key="blob/tenant1/fuel.pdf")
    await _seed(db_session, document, evidence)

    outcome = await promote_carbon_evidence(db_session, evidence, tenant_id=1)

    assert outcome.status is LinkStatus.LINKED
    assert outcome.method is LinkMethod.STORAGE_PATH
    assert evidence.document_id == document.id


async def test_promote_will_not_match_another_tenants_identical_path(db_session: AsyncSession) -> None:
    theirs = _document(tenant_id=2, file_path="blob/shared/fuel.pdf")
    evidence = _carbon_evidence(tenant_id=1, storage_key="blob/shared/fuel.pdf")
    await _seed(db_session, theirs, evidence)

    outcome = await promote_carbon_evidence(db_session, evidence, tenant_id=1)

    assert outcome.status is LinkStatus.UNMATCHED
    assert evidence.document_id is None


async def test_promote_reports_ambiguity_rather_than_picking_one(db_session: AsyncSession) -> None:
    first = _document(tenant_id=1, title="Fuel A", file_path="blob/a.pdf")
    second = _document(tenant_id=1, title="Fuel B", file_path="blob/b.pdf")
    await _seed(db_session, first, second)
    await _seed(
        db_session,
        _control_record(tenant_id=1, document=first, checksum="dup"),
        _control_record(tenant_id=1, document=second, checksum="dup"),
    )
    evidence = _carbon_evidence(tenant_id=1, file_hash="dup")
    await _seed(db_session, evidence)

    outcome = await promote_carbon_evidence(db_session, evidence, tenant_id=1)

    assert outcome.status is LinkStatus.AMBIGUOUS
    assert outcome.is_error is True
    assert evidence.document_id is None, "two candidates means a steward decides, not the matcher"


async def test_promote_creates_no_register_document_when_unmatched(db_session: AsyncSession) -> None:
    """A promote is not an upload. The Register must be exactly as it was."""
    evidence = _carbon_evidence(tenant_id=1, storage_key="pm/never-filed.pdf", file_hash="nope")
    await _seed(db_session, evidence)
    before = await db_session.scalar(select(sa.func.count()).select_from(Document))

    outcome = await promote_carbon_evidence(db_session, evidence, tenant_id=1)

    assert outcome.status is LinkStatus.UNMATCHED
    assert evidence.document_id is None
    after = await db_session.scalar(select(sa.func.count()).select_from(Document))
    assert after == before == 0


async def test_promote_leaves_an_already_linked_row_alone(db_session: AsyncSession) -> None:
    linked = _document(tenant_id=1, file_path="blob/linked.pdf")
    tempting = _document(tenant_id=1, title="Other", file_path="blob/tempting.pdf")
    evidence = _carbon_evidence(tenant_id=1, storage_key="blob/tempting.pdf")
    await _seed(db_session, linked, tempting, evidence)
    evidence.document_id = linked.id

    outcome = await promote_carbon_evidence(db_session, evidence, tenant_id=1)

    assert outcome.status is LinkStatus.ALREADY_LINKED
    assert evidence.document_id == linked.id, "a steward's link outranks a later path match"


async def test_a_blank_hash_matches_nothing(db_session: AsyncSession) -> None:
    """An uncomputed checksum is not evidence, and must not match every blank."""
    document = _document(tenant_id=1, file_path="blob/other.pdf")
    await _seed(db_session, document)
    await _seed(db_session, _control_record(tenant_id=1, document=document, checksum=""))
    evidence = _carbon_evidence(tenant_id=1, file_hash="   ")
    await _seed(db_session, evidence)

    outcome = await promote_carbon_evidence(db_session, evidence, tenant_id=1)

    assert outcome.status is LinkStatus.UNMATCHED
    assert evidence.document_id is None


async def test_promote_evidence_asset_matches_on_checksum(db_session: AsyncSession) -> None:
    document = _document(tenant_id=1)
    await _seed(db_session, document)
    await _seed(db_session, _control_record(tenant_id=1, document=document, checksum="feed01"))
    asset = _evidence_asset(tenant_id=1, checksum="FEED01")
    await _seed(db_session, asset)

    outcome = await promote_evidence_asset(db_session, asset, tenant_id=1)

    assert outcome.status is LinkStatus.LINKED
    assert asset.document_id == document.id


async def test_promote_evidence_asset_without_a_tenant_matches_nothing(db_session: AsyncSession) -> None:
    document = _document(tenant_id=1, file_path="cases/1/photo.jpg")
    asset = _evidence_asset(tenant_id=None, storage_key="cases/1/photo.jpg")
    await _seed(db_session, document, asset)

    outcome = await promote_evidence_asset(db_session, asset, tenant_id=None)

    assert outcome.status is LinkStatus.UNMATCHED
    assert asset.document_id is None


# ---------------------------------------------------------------------------
# UVDB documents_presented → {document_id, label}
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("element", "expected"),
    [
        ("Site Induction.pdf", (None, "Site Induction.pdf")),
        (42, (42, None)),
        ("42", (42, "42")),
        ({"document_id": 7, "label": "Policy"}, (7, "Policy")),
        ({"id": 7, "title": "Policy"}, (7, "Policy")),
        ({"name": "Policy"}, (None, "Policy")),
        (None, (None, None)),
        ("", (None, None)),
        ("   ", (None, None)),
        (0, (None, None)),
        (-3, (None, None)),
        (True, (None, "True")),
    ],
)
def test_presented_element_parts_reads_every_legacy_shape(element: Any, expected: tuple) -> None:
    assert presented_element_parts(element) == expected


async def test_presented_list_keeps_labels_and_only_verified_ids(db_session: AsyncSession) -> None:
    document = _document(tenant_id=1, title="Site Induction")
    await _seed(db_session, document)

    projected = await normalise_documents_presented(
        db_session,
        tenant_id=1,
        elements=[document.id, "Site Induction", "Nothing On File.pdf"],
    )

    assert projected == [
        {"document_id": document.id, "label": None},
        {"document_id": document.id, "label": "Site Induction"},
        {"document_id": None, "label": "Nothing On File.pdf"},
    ]


async def test_a_cross_tenant_id_is_demoted_to_a_label_not_stored(db_session: AsyncSession) -> None:
    theirs = _document(tenant_id=2, title="Their Policy")
    await _seed(db_session, theirs)

    projected = await normalise_documents_presented(db_session, tenant_id=1, elements=[theirs.id])

    assert projected == [{"document_id": None, "label": str(theirs.id)}]


async def test_an_ambiguous_label_resolves_to_no_id(db_session: AsyncSession) -> None:
    first = _document(tenant_id=1, title="Fuel Card July", file_path="blob/one.pdf")
    second = _document(tenant_id=1, title="Fuel Card July", file_path="blob/two.pdf")
    await _seed(db_session, first, second)

    projected = await normalise_documents_presented(db_session, tenant_id=1, elements=["Fuel Card July"])

    assert projected == [{"document_id": None, "label": "Fuel Card July"}]


async def test_normalising_without_a_tenant_keeps_labels_and_no_ids(db_session: AsyncSession) -> None:
    document = _document(tenant_id=1, title="Site Induction")
    await _seed(db_session, document)

    projected = await normalise_documents_presented(
        db_session, tenant_id=None, elements=["Site Induction", document.id]
    )

    assert projected == [
        {"document_id": None, "label": "Site Induction"},
        {"document_id": None, "label": str(document.id)},
    ]


async def test_normalisation_is_stable_when_reapplied(db_session: AsyncSession) -> None:
    document = _document(tenant_id=1, title="Site Induction")
    await _seed(db_session, document)

    once = await normalise_documents_presented(db_session, tenant_id=1, elements=["Site Induction"])
    twice = await normalise_documents_presented(db_session, tenant_id=1, elements=once)

    assert once == twice == [{"document_id": document.id, "label": "Site Induction"}]


async def test_empty_and_non_list_values_pass_through_untouched(db_session: AsyncSession) -> None:
    assert await normalise_documents_presented(db_session, tenant_id=1, elements=[]) == []
    assert await normalise_documents_presented(db_session, tenant_id=1, elements=None) is None
    # A legacy scalar is the only copy of whatever it says; rewriting it destroys it.
    assert await normalise_documents_presented(db_session, tenant_id=1, elements="legacy blob") == "legacy blob"


async def test_normalisation_never_creates_a_register_document(db_session: AsyncSession) -> None:
    before = await db_session.scalar(select(sa.func.count()).select_from(Document))

    await normalise_documents_presented(db_session, tenant_id=1, elements=["Unfiled A.pdf", "Unfiled B.pdf", 12345])

    after = await db_session.scalar(select(sa.func.count()).select_from(Document))
    assert after == before == 0
