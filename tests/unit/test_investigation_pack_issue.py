"""INV-C17: issuing a customer pack is gated, and the issued bytes are kept.

Two decisions are under test.

**DEC-4.** An external pack may not be issued unless the investigation is
complete *and* a human has cleared the redaction review on that pack. Neither
is inferred and neither is created on the caller's behalf — an unreviewed pack
is refused with 422, not quietly reviewed. Internal packs are not gated,
because reading your own record is not a disclosure.

**DEC-5.** Issue renders the PDF once, retains those bytes with their SHA-256,
and logs who received them. Every later download of that pack serves the
retained copy, so a renderer that has changed since cannot rewrite what a
customer was given. The renderer is patched to return different bytes on the
second call, which is the only way to tell a retained document from a
convincing re-render.

The route functions are driven directly against a SQLite session — the idiom
INV-C7 findings, INV-C10 RCA and INV-C12 factors tests use — with the tenancy
helper patched. The tenancy check itself is ``_assert_investigation_tenant``
in ``investigations.py`` and is exercised here rather than patched away.
"""

from __future__ import annotations

import ast
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from src.api.routes import investigations as routes
from src.api.schemas.investigation import (
    InvestigationPackIssuedResponse,
    InvestigationPackIssueRequest,
    InvestigationPackRedactionReviewRequest,
    InvestigationPackRedactionReviewResponse,
    InvestigationPacksResponse,
)
from src.domain.exceptions import ConflictError, NotFoundError, TenantAccessError, ValidationError
from src.domain.models.evidence_asset import EvidenceAsset, EvidenceSourceModule, EvidenceVisibility
from src.domain.models.investigation import (
    CustomerPackAudience,
    InvestigationCustomerPack,
    InvestigationPackDisclosure,
    InvestigationRevisionEvent,
    InvestigationRun,
    InvestigationStatus,
)
from src.domain.models.tenant import Tenant
from src.domain.services import investigation_pack_issue as issue_service
from src.domain.services.investigation_pack_docx import InvestigationPackDocxService
from src.domain.services.investigation_pack_issue import (
    BLOCKER_NOT_COMPLETE,
    BLOCKER_REDACTION_REVIEW_NOT_CLEARED,
    PACK_ISSUE_BLOCKED,
    external_issue_blockers,
    pack_evidence_assets_query,
    retained_docx_storage_key,
)
from src.domain.services.investigation_pack_pdf import InvestigationPackPdfService
from src.infrastructure.storage import StorageError

REPO_ROOT = Path(__file__).resolve().parents[2]
MIGRATION_PATH = REPO_ROOT / "alembic/versions/20261122_inv_c17_pack_issue_retain.py"
REVISION = "20261122_inv_c17_issue"
PARENT_REVISION = "20261121_inv_c11_capa_why"
NEW_PACK_COLUMNS = {
    "redaction_review_cleared_at",
    "redaction_review_by_id",
    "redaction_review_at",
    "redaction_review_note",
    "issued_at",
    "issued_by_id",
    "issued_pdf_asset_id",
    "issued_pdf_storage_key",
    "issued_pdf_sha256",
    "issued_pdf_size_bytes",
}

TENANT = 7
OTHER_TENANT = 8
INVESTIGATION_ID = 21
USER = SimpleNamespace(id=11, tenant_id=TENANT, is_superuser=False)
OTHER_USER = SimpleNamespace(id=12, tenant_id=OTHER_TENANT, is_superuser=False)

FIRST_RENDER = b"%PDF-1.4 first render"
SECOND_RENDER = b"%PDF-1.4 renderer has changed since"
FIRST_DOCX = b"PK\x03\x04 first word"
SECOND_DOCX = b"PK\x03\x04 renderer has changed since"


# ---------------------------------------------------------------------------
# The migration
# ---------------------------------------------------------------------------

_HEADS_RUNNER = r"""
import json, sys
from alembic.config import Config
from alembic.script import ScriptDirectory

repo = sys.argv[1]
sys.path.append(repo)
cfg = Config(repo + "/alembic.ini")
cfg.set_main_option("script_location", repo + "/alembic")
script = ScriptDirectory.from_config(cfg)
print(json.dumps({
    "heads": sorted(script.get_heads()),
    "parents": sorted(script.get_revision(sys.argv[2])._all_down_revisions or ()),
}))
"""

# Runs upgrade() and downgrade() for real against SQLite and reports what the
# schema looked like at each step. In a subprocess with the repo *appended* to
# sys.path because the repository root holds a directory called ``alembic``,
# which would otherwise shadow the installed library the migration imports.
#
# The foreign keys are deliberately not exercised here: SQLite cannot ALTER a
# table to add one, so the migration's existence guards skip those branches when
# ``users`` and ``evidence_assets`` are absent. Postgres covers them — CI runs
# `alembic upgrade head` and a downgrade against a real database.
_UPDOWN_RUNNER = r"""
import importlib.util, json, sys
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

repo, migration_path, db_path = sys.argv[1], sys.argv[2], sys.argv[3]
sys.path.append(repo)

engine = sa.create_engine("sqlite+pysqlite:///" + db_path)
with engine.begin() as conn:
    conn.exec_driver_sql(
        "CREATE TABLE investigation_customer_packs ("
        " id INTEGER PRIMARY KEY, tenant_id INTEGER NOT NULL,"
        " investigation_id INTEGER NOT NULL, pack_uuid VARCHAR(36),"
        " checksum_sha256 VARCHAR(64))"
    )
    conn.exec_driver_sql(
        "INSERT INTO investigation_customer_packs"
        " (id, tenant_id, investigation_id, pack_uuid, checksum_sha256)"
        " VALUES (1, 7, 21, 'pack-uuid', 'abc')"
    )

spec = importlib.util.spec_from_file_location("inv_c17_migration", migration_path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def snapshot(conn):
    inspector = sa.inspect(conn)
    tables = set(inspector.get_table_names())
    return {
        "tables": sorted(tables),
        "pack_columns": sorted(c["name"] for c in inspector.get_columns("investigation_customer_packs")),
        "pack_indexes": sorted(i["name"] for i in inspector.get_indexes("investigation_customer_packs")),
        "disclosure_columns": sorted(
            c["name"] for c in inspector.get_columns("investigation_pack_disclosures")
        ) if "investigation_pack_disclosures" in tables else [],
        "pack_rows": conn.exec_driver_sql(
            "SELECT COUNT(*) FROM investigation_customer_packs"
        ).scalar(),
    }


result = {}
with engine.begin() as conn:
    ctx = MigrationContext.configure(conn)
    with Operations.context(ctx):
        module.upgrade()
        # Re-running an already-applied upgrade must converge, not raise.
        module.upgrade()
    result["after_upgrade"] = snapshot(conn)

with engine.begin() as conn:
    ctx = MigrationContext.configure(conn)
    with Operations.context(ctx):
        module.downgrade()
    result["after_downgrade"] = snapshot(conn)

print(json.dumps(result))
"""


def _run_probe(script: str, args: list[str], tmp_path: Path) -> dict:
    tmp_path.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run(
        [sys.executable, "-c", script, *args],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        timeout=180,
    )
    if completed.returncode != 0:
        pytest.fail(f"probe failed:\nstdout={completed.stdout}\nstderr={completed.stderr}")
    return json.loads(completed.stdout)


def test_the_new_revision_is_the_only_head(tmp_path) -> None:
    chain = _run_probe(_HEADS_RUNNER, [str(REPO_ROOT), REVISION], tmp_path)
    assert chain["heads"] == [REVISION], f"expected a single head, found {chain['heads']}"
    assert chain["parents"] == [PARENT_REVISION]


def test_the_migration_only_adds_and_never_rewrites() -> None:
    tree = ast.parse(MIGRATION_PATH.read_text(encoding="utf-8"))
    upgrade = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "upgrade")
    called = {
        node.func.attr
        for node in ast.walk(upgrade)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert "add_column" in called
    assert "create_table" in called
    for forbidden in ("alter_column", "drop_column", "drop_table", "bulk_insert", "execute"):
        assert forbidden not in called, f"upgrade() calls op.{forbidden} — this revision is additive only"


def test_upgrade_and_downgrade_round_trip(tmp_path) -> None:
    result = _run_probe(
        _UPDOWN_RUNNER,
        [str(REPO_ROOT), str(MIGRATION_PATH), str(tmp_path / "c17.db")],
        tmp_path,
    )

    after_upgrade = result["after_upgrade"]
    assert "investigation_pack_disclosures" in after_upgrade["tables"]
    assert NEW_PACK_COLUMNS <= set(after_upgrade["pack_columns"])
    assert {"tenant_id", "pack_id", "recipient", "issued_at", "pdf_sha256", "actor_id"} <= set(
        after_upgrade["disclosure_columns"]
    )
    assert "ix_investigation_customer_packs_issued_pdf_asset_id" in after_upgrade["pack_indexes"]
    # The pack that already existed is still there, unrewritten.
    assert after_upgrade["pack_rows"] == 1

    after_downgrade = result["after_downgrade"]
    assert "investigation_pack_disclosures" not in after_downgrade["tables"]
    assert NEW_PACK_COLUMNS.isdisjoint(set(after_downgrade["pack_columns"]))
    assert after_downgrade["pack_rows"] == 1


def test_the_model_declares_every_migrated_column() -> None:
    names = {column.name for column in InvestigationCustomerPack.__table__.columns}
    assert NEW_PACK_COLUMNS <= names
    for column in NEW_PACK_COLUMNS:
        assert InvestigationCustomerPack.__table__.c[column].nullable is True


def test_the_disclosure_table_cannot_hold_an_unattributed_row() -> None:
    table = InvestigationPackDisclosure.__table__
    assert table.c.tenant_id.nullable is False
    assert table.c.pack_id.nullable is False
    assert table.c.recipient.nullable is False
    assert table.c.issued_at.nullable is False
    assert table.c.pdf_sha256.nullable is False
    assert table.c.actor_id.nullable is False


# ---------------------------------------------------------------------------
# The gate, as pure logic (DEC-4)
# ---------------------------------------------------------------------------


def _pack_stub(*, audience=CustomerPackAudience.EXTERNAL_CUSTOMER, cleared_at=None):
    return SimpleNamespace(
        id=1,
        investigation_id=INVESTIGATION_ID,
        audience=audience,
        redaction_review_cleared_at=cleared_at,
    )


def _run_stub(status=InvestigationStatus.COMPLETED):
    return SimpleNamespace(id=INVESTIGATION_ID, status=status)


def test_an_internal_pack_is_not_gated() -> None:
    """Reading your own record is not a disclosure to a customer."""
    blockers = external_issue_blockers(
        _run_stub(InvestigationStatus.IN_PROGRESS),
        _pack_stub(audience=CustomerPackAudience.INTERNAL_CUSTOMER),
    )
    assert blockers == []


def test_an_incomplete_investigation_blocks_an_external_pack() -> None:
    blockers = external_issue_blockers(
        _run_stub(InvestigationStatus.IN_PROGRESS),
        _pack_stub(cleared_at=datetime(2026, 9, 1, tzinfo=timezone.utc)),
    )
    assert blockers == [BLOCKER_NOT_COMPLETE]


def test_an_uncleared_redaction_review_blocks_an_external_pack() -> None:
    blockers = external_issue_blockers(_run_stub(), _pack_stub(cleared_at=None))
    assert blockers == [BLOCKER_REDACTION_REVIEW_NOT_CLEARED]


def test_both_blockers_are_named_not_only_the_first() -> None:
    """An operator fixing one and being refused again learns nothing new."""
    blockers = external_issue_blockers(_run_stub(InvestigationStatus.DRAFT), _pack_stub())
    assert blockers == [BLOCKER_NOT_COMPLETE, BLOCKER_REDACTION_REVIEW_NOT_CLEARED]


def test_a_closed_investigation_counts_as_complete() -> None:
    blockers = external_issue_blockers(
        _run_stub(InvestigationStatus.CLOSED),
        _pack_stub(cleared_at=datetime(2026, 9, 1, tzinfo=timezone.utc)),
    )
    assert blockers == []


def test_an_unreadable_status_fails_closed() -> None:
    blockers = external_issue_blockers(
        SimpleNamespace(id=INVESTIGATION_ID, status=None),
        _pack_stub(cleared_at=datetime(2026, 9, 1, tzinfo=timezone.utc)),
    )
    assert blockers == [BLOCKER_NOT_COMPLETE]


def test_the_issue_request_rejects_a_field_it_cannot_echo() -> None:
    """Guard 4: nothing is advertised on the request that the response drops."""
    with pytest.raises(ValueError):
        InvestigationPackIssueRequest(recipient="Bedford BC", invented="no")  # type: ignore[call-arg]
    with pytest.raises(ValueError):
        InvestigationPackRedactionReviewRequest(cleared=True, invented="no")  # type: ignore[call-arg]


def test_the_issue_request_will_not_accept_an_unnamed_recipient() -> None:
    """A disclosure log whose recipient is blank records nothing worth having."""
    with pytest.raises(ValueError):
        InvestigationPackIssueRequest(recipient="")


# ---------------------------------------------------------------------------
# Route-level: storage and session harness
# ---------------------------------------------------------------------------


class _FakeStorage:
    """In-memory stand-in for blob storage, with the same failure type."""

    def __init__(self) -> None:
        self.blobs: dict[str, bytes] = {}
        self.uploads = 0

    async def upload(self, *, storage_key: str, content: bytes, content_type: str, metadata=None) -> str:
        self.uploads += 1
        self.blobs[storage_key] = bytes(content)
        return storage_key

    async def download(self, storage_key: str) -> bytes:
        if storage_key not in self.blobs:
            raise StorageError(f"File not found: {storage_key}")
        return self.blobs[storage_key]


class _CountingRenderer:
    """Returns different bytes on each call, so a re-render is unmistakable.

    Patched over ``InvestigationPackPdfService.build_pdf_bytes``. A plain object
    is not a descriptor, so it is invoked without ``self`` — the payload is the
    only positional argument it sees.
    """

    def __init__(self, *renders: bytes) -> None:
        self.renders = list(renders)
        self.calls = 0

    def __call__(self, _payload, **_kwargs) -> bytes:
        index = min(self.calls, len(self.renders) - 1)
        self.calls += 1
        return self.renders[index]


@pytest.fixture
async def session_factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Tenant.__table__.create)
        await conn.run_sync(InvestigationRun.__table__.create)
        await conn.run_sync(EvidenceAsset.__table__.create)
        await conn.run_sync(InvestigationCustomerPack.__table__.create)
        await conn.run_sync(InvestigationPackDisclosure.__table__.create)
        await conn.run_sync(InvestigationRevisionEvent.__table__.create)
    yield async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    await engine.dispose()


@pytest.fixture
async def db_session(session_factory):
    async with session_factory() as session:
        session.add(
            Tenant(
                id=TENANT,
                name="Plantexpand",
                slug="plantexpand",
                admin_email="admin@plantexpand.test",
                primary_color="#123456",
            )
        )
        await session.commit()
        yield session


@pytest.fixture
def storage():
    fake = _FakeStorage()
    with patch.object(issue_service, "storage_service", lambda: fake):
        yield fake


@pytest.fixture
def renderer():
    pdf = _CountingRenderer(FIRST_RENDER, SECOND_RENDER)
    docx = _CountingRenderer(FIRST_DOCX, SECOND_DOCX)
    with (
        patch.object(InvestigationPackPdfService, "build_pdf_bytes", pdf),
        patch.object(InvestigationPackDocxService, "build_docx_bytes", docx),
    ):
        pdf.docx = docx
        yield pdf


async def _seed_run(db: AsyncSession, *, status=InvestigationStatus.COMPLETED, tenant_id: int = TENANT):
    run = InvestigationRun(
        id=INVESTIGATION_ID,
        tenant_id=tenant_id,
        template_id=1,
        assigned_entity_type="incident",
        assigned_entity_id=42,
        status=status,
        title="Fork lift near miss",
        reference_number="INV-2026-0021",
        data={},
        version=1,
    )
    db.add(run)
    await db.flush()
    return run


async def _seed_pack(
    db: AsyncSession,
    *,
    pack_id: int = 1,
    audience=CustomerPackAudience.EXTERNAL_CUSTOMER,
    tenant_id: int = TENANT,
    cleared: bool = True,
):
    pack = InvestigationCustomerPack(
        id=pack_id,
        tenant_id=tenant_id,
        investigation_id=INVESTIGATION_ID,
        pack_uuid=f"pack-uuid-{pack_id}",
        audience=audience,
        content={"sections": {}, "title": "Fork lift near miss"},
        redaction_log=[],
        included_assets=[],
        checksum_sha256="0" * 64,
        generated_by_id=USER.id,
        redaction_review_cleared_at=datetime(2026, 9, 2, tzinfo=timezone.utc) if cleared else None,
        redaction_review_at=datetime(2026, 9, 2, tzinfo=timezone.utc) if cleared else None,
        redaction_review_by_id=USER.id if cleared else None,
    )
    db.add(pack)
    await db.commit()
    return pack


def _authorised(run):
    return patch.object(routes, "_get_investigation_or_404", new=AsyncMock(return_value=run))


def _issue_body(recipient: str = "Bedford Borough Council", **kwargs) -> InvestigationPackIssueRequest:
    return InvestigationPackIssueRequest(recipient=recipient, **kwargs)


# ---------------------------------------------------------------------------
# Issuing (DEC-4 refusals)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_an_incomplete_investigation_cannot_issue_an_external_pack(db_session, storage, renderer):
    run = await _seed_run(db_session, status=InvestigationStatus.IN_PROGRESS)
    await _seed_pack(db_session, cleared=True)

    with _authorised(run), pytest.raises(ValidationError) as exc:
        await routes.issue_customer_pack(INVESTIGATION_ID, 1, _issue_body(), db_session, USER)

    assert exc.value.http_status == 422
    assert exc.value.code == PACK_ISSUE_BLOCKED
    assert exc.value.details["blockers"] == [BLOCKER_NOT_COMPLETE]
    assert renderer.calls == 0
    assert storage.uploads == 0
    assert await db_session.scalar(select(func.count(InvestigationPackDisclosure.id))) == 0


@pytest.mark.asyncio
async def test_an_uncleared_redaction_review_cannot_issue_an_external_pack(db_session, storage, renderer):
    run = await _seed_run(db_session)
    pack = await _seed_pack(db_session, cleared=False)

    with _authorised(run), pytest.raises(ValidationError) as exc:
        await routes.issue_customer_pack(INVESTIGATION_ID, 1, _issue_body(), db_session, USER)

    assert exc.value.details["blockers"] == [BLOCKER_REDACTION_REVIEW_NOT_CLEARED]
    # No review was invented on the way to refusing.
    await db_session.refresh(pack)
    assert pack.redaction_review_cleared_at is None
    assert pack.redaction_review_at is None
    assert pack.issued_at is None
    assert await db_session.scalar(select(func.count(InvestigationPackDisclosure.id))) == 0


@pytest.mark.asyncio
async def test_an_internal_pack_issues_without_completion_or_review(db_session, storage, renderer):
    """Internal packs are not a disclosure to a customer, so they are not gated."""
    run = await _seed_run(db_session, status=InvestigationStatus.IN_PROGRESS)
    await _seed_pack(db_session, audience=CustomerPackAudience.INTERNAL_CUSTOMER, cleared=False)

    with _authorised(run):
        payload = await routes.issue_customer_pack(INVESTIGATION_ID, 1, _issue_body("Depot manager"), db_session, USER)

    assert payload["recipient"] == "Depot manager"
    assert payload["pdf_newly_retained"] is True


# ---------------------------------------------------------------------------
# Issuing (DEC-5 retention)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_issue_retains_the_pdf_bytes_and_their_checksum(db_session, storage, renderer):
    run = await _seed_run(db_session)
    pack = await _seed_pack(db_session)

    with _authorised(run):
        payload = await routes.issue_customer_pack(
            INVESTIGATION_ID,
            1,
            _issue_body(recipient_email="foi@bedford.gov.uk", note="FOI request 2026/114"),
            db_session,
            USER,
        )

    expected_sha = hashlib.sha256(FIRST_RENDER).hexdigest()
    assert payload["pdf_sha256"] == expected_sha
    assert payload["pdf_size_bytes"] == len(FIRST_RENDER)
    assert payload["pdf_newly_retained"] is True
    # The response is the contract the client actually receives.
    assert InvestigationPackIssuedResponse.model_validate(payload).disclosure_count == 1

    await db_session.refresh(pack)
    assert pack.issued_pdf_sha256 == expected_sha
    assert pack.issued_at is not None
    assert pack.issued_by_id == USER.id
    # The bytes are in the existing evidence library, not a second blob store.
    assert storage.blobs[str(pack.issued_pdf_storage_key)] == FIRST_RENDER

    asset = await db_session.scalar(select(EvidenceAsset).where(EvidenceAsset.id == pack.issued_pdf_asset_id))
    assert asset is not None
    assert asset.tenant_id == TENANT
    assert asset.linked_investigation_id == INVESTIGATION_ID
    assert asset.source_module == EvidenceSourceModule.INVESTIGATION
    assert asset.checksum_sha256 == expected_sha
    # Never swept back into the next pack as an attachment.
    assert asset.visibility == EvidenceVisibility.INTERNAL_ONLY


@pytest.mark.asyncio
async def test_a_download_after_issue_returns_the_retained_bytes(db_session, storage, renderer):
    """The renderer would now produce something else; the customer's copy wins."""
    run = await _seed_run(db_session)
    await _seed_pack(db_session)

    with _authorised(run):
        await routes.issue_customer_pack(INVESTIGATION_ID, 1, _issue_body(), db_session, USER)
        assert renderer.calls == 1

        response = await routes.download_customer_pack_pdf(INVESTIGATION_ID, 1, db_session, USER)

    assert response.body == FIRST_RENDER
    assert response.media_type == "application/pdf"
    # Not a re-render dressed up as a retained copy.
    assert renderer.calls == 1


@pytest.mark.asyncio
async def test_word_after_issue_returns_the_frozen_bytes(db_session, storage, renderer):
    """Issue retains Word from the same payload. A later renderer must not win."""
    run = await _seed_run(db_session)
    await _seed_pack(db_session)

    with _authorised(run):
        await routes.issue_customer_pack(INVESTIGATION_ID, 1, _issue_body(), db_session, USER)
        assert renderer.calls == 1
        assert renderer.docx.calls == 1
        first = await routes.download_customer_pack_docx(INVESTIGATION_ID, 1, db_session, USER)
        second = await routes.download_customer_pack_docx(INVESTIGATION_ID, 1, db_session, USER)

    assert first.body == FIRST_DOCX
    assert second.body == FIRST_DOCX
    assert "wordprocessingml" in (first.media_type or "")
    pack = await db_session.get(InvestigationCustomerPack, 1)
    assert pack is not None
    assert pack.issued_pdf_sha256
    assert "issued_docx_sha256" not in InvestigationCustomerPack.__table__.c
    assert renderer.calls == 1
    assert renderer.docx.calls == 1
    assert storage.blobs[retained_docx_storage_key(INVESTIGATION_ID, "pack-uuid-1")] == FIRST_DOCX


@pytest.mark.asyncio
async def test_word_after_issue_refuses_when_no_frozen_blob(db_session, storage, renderer):
    """Packs issued before R10 have no Word blob. Do not live re-render one."""
    run = await _seed_run(db_session)
    await _seed_pack(db_session)

    with _authorised(run):
        await routes.issue_customer_pack(INVESTIGATION_ID, 1, _issue_body(), db_session, USER)
        del storage.blobs[retained_docx_storage_key(INVESTIGATION_ID, "pack-uuid-1")]
        with pytest.raises(ConflictError) as exc:
            await routes.download_customer_pack_docx(INVESTIGATION_ID, 1, db_session, USER)

    assert exc.value.code == "ISSUED_DOCX_UNAVAILABLE"
    assert renderer.docx.calls == 1


@pytest.mark.asyncio
async def test_word_working_copy_renders_before_issue(db_session, storage, renderer):
    run = await _seed_run(db_session)
    await _seed_pack(db_session)

    with _authorised(run):
        response = await routes.download_customer_pack_docx(INVESTIGATION_ID, 1, db_session, USER)

    assert response.body.startswith(b"PK")
    assert "wordprocessingml" in (response.media_type or "")
    assert renderer.calls == 0


@pytest.mark.asyncio
async def test_a_download_before_issue_still_renders_live(db_session, storage, renderer):
    run = await _seed_run(db_session)
    await _seed_pack(db_session)

    with _authorised(run):
        response = await routes.download_customer_pack_pdf(INVESTIGATION_ID, 1, db_session, USER)

    assert response.body == FIRST_RENDER
    assert renderer.calls == 1
    assert storage.uploads == 0


@pytest.mark.asyncio
async def test_a_second_disclosure_reuses_the_retained_bytes(db_session, storage, renderer):
    run = await _seed_run(db_session)
    pack = await _seed_pack(db_session)

    with _authorised(run):
        first = await routes.issue_customer_pack(INVESTIGATION_ID, 1, _issue_body("Bedford BC"), db_session, USER)
        second = await routes.issue_customer_pack(INVESTIGATION_ID, 1, _issue_body("HSE"), db_session, USER)

    assert renderer.calls == 1, "a re-issue must not re-render the issued record"
    assert renderer.docx.calls == 1
    assert storage.uploads == 2
    assert second["pdf_newly_retained"] is False
    assert second["pdf_sha256"] == first["pdf_sha256"]
    assert second["disclosure_count"] == 2

    await db_session.refresh(pack)
    # issued_at names the moment the retained bytes were created, and does not move.
    assert pack.issued_at is not None
    recipients = (
        (
            await db_session.execute(
                select(InvestigationPackDisclosure.recipient).order_by(InvestigationPackDisclosure.id)
            )
        )
        .scalars()
        .all()
    )
    assert list(recipients) == ["Bedford BC", "HSE"]


@pytest.mark.asyncio
async def test_a_corrupted_retained_copy_is_refused_rather_than_re_rendered(db_session, storage, renderer):
    """Serving unverified bytes under an issued pack's name would make the checksum a decoration."""
    from fastapi import HTTPException

    run = await _seed_run(db_session)
    pack = await _seed_pack(db_session)

    with _authorised(run):
        await routes.issue_customer_pack(INVESTIGATION_ID, 1, _issue_body(), db_session, USER)
        await db_session.refresh(pack)
        storage.blobs[str(pack.issued_pdf_storage_key)] = b"%PDF-1.4 tampered"

        with pytest.raises(HTTPException) as exc:
            await routes.download_customer_pack_pdf(INVESTIGATION_ID, 1, db_session, USER)

    assert exc.value.status_code == 500
    assert exc.value.detail["error_code"] == "RETAINED_PACK_CHECKSUM_MISMATCH"
    assert renderer.calls == 1


@pytest.mark.asyncio
async def test_a_missing_retained_copy_is_refused_rather_than_re_rendered(db_session, storage, renderer):
    from fastapi import HTTPException

    run = await _seed_run(db_session)
    pack = await _seed_pack(db_session)

    with _authorised(run):
        await routes.issue_customer_pack(INVESTIGATION_ID, 1, _issue_body(), db_session, USER)
        await db_session.refresh(pack)
        storage.blobs.clear()

        with pytest.raises(HTTPException) as exc:
            await routes.download_customer_pack_pdf(INVESTIGATION_ID, 1, db_session, USER)

    assert exc.value.detail["error_code"] == "RETAINED_PACK_UNREADABLE"
    assert renderer.calls == 1


# ---------------------------------------------------------------------------
# The disclosure log
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_disclosure_log_records_recipient_time_actor_and_tenant(db_session, storage, renderer):
    run = await _seed_run(db_session)
    await _seed_pack(db_session)

    before = datetime.now(timezone.utc)
    with _authorised(run):
        await routes.issue_customer_pack(
            INVESTIGATION_ID,
            1,
            _issue_body("Bedford Borough Council", recipient_email="foi@bedford.gov.uk"),
            db_session,
            USER,
        )

    row = await db_session.scalar(select(InvestigationPackDisclosure))
    assert row is not None
    assert row.recipient == "Bedford Borough Council"
    assert row.recipient_email == "foi@bedford.gov.uk"
    assert row.actor_id == USER.id
    assert row.tenant_id == TENANT
    assert row.pack_id == 1
    assert row.investigation_id == INVESTIGATION_ID
    assert row.pdf_sha256 == hashlib.sha256(FIRST_RENDER).hexdigest()
    assert row.issued_at >= before.replace(tzinfo=row.issued_at.tzinfo)


@pytest.mark.asyncio
async def test_another_tenants_disclosure_is_not_counted_into_this_ones_log(db_session, storage, renderer):
    run = await _seed_run(db_session)
    await _seed_pack(db_session)

    with _authorised(run):
        await routes.issue_customer_pack(INVESTIGATION_ID, 1, _issue_body(), db_session, USER)

    db_session.add(
        InvestigationPackDisclosure(
            tenant_id=OTHER_TENANT,
            investigation_id=INVESTIGATION_ID,
            pack_id=1,
            recipient="Somebody else's customer",
            issued_at=datetime.now(timezone.utc),
            pdf_sha256="f" * 64,
            actor_id=OTHER_USER.id,
        )
    )
    await db_session.commit()

    with _authorised(run):
        listing = await routes.get_investigation_packs(INVESTIGATION_ID, db_session, USER, page=1, page_size=20)

    assert InvestigationPacksResponse.model_validate(listing).items[0].disclosure_count == 1


@pytest.mark.asyncio
async def test_another_tenant_cannot_reach_the_pack_at_all(db_session, storage, renderer):
    """The 404/refusal happens before any disclosure could be written."""
    run = await _seed_run(db_session)
    await _seed_pack(db_session)

    with _authorised(run), pytest.raises(TenantAccessError):
        await routes.issue_customer_pack(INVESTIGATION_ID, 1, _issue_body(), db_session, OTHER_USER)

    assert await db_session.scalar(select(func.count(InvestigationPackDisclosure.id))) == 0


@pytest.mark.asyncio
async def test_a_pack_belonging_to_another_tenant_is_not_found(db_session, storage, renderer):
    run = await _seed_run(db_session)
    await _seed_pack(db_session, pack_id=2, tenant_id=OTHER_TENANT)

    with _authorised(run), pytest.raises(NotFoundError):
        await routes.issue_customer_pack(INVESTIGATION_ID, 2, _issue_body(), db_session, USER)


@pytest.mark.asyncio
async def test_download_of_another_tenants_pack_is_not_found(db_session, storage, renderer):
    """The retained-or-live PDF path is scoped the same way as issue."""
    run = await _seed_run(db_session)
    await _seed_pack(db_session, pack_id=2, tenant_id=OTHER_TENANT)

    with _authorised(run), pytest.raises(NotFoundError):
        await routes.download_customer_pack_pdf(INVESTIGATION_ID, 2, db_session, USER)


# ---------------------------------------------------------------------------
# The redaction review itself
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_clearing_the_review_unblocks_issue(db_session, storage, renderer):
    run = await _seed_run(db_session)
    pack = await _seed_pack(db_session, cleared=False)

    with _authorised(run):
        review = await routes.review_customer_pack_redaction(
            INVESTIGATION_ID,
            1,
            InvestigationPackRedactionReviewRequest(cleared=True, note="Read every narrative field."),
            db_session,
            USER,
        )
        assert InvestigationPackRedactionReviewResponse.model_validate(review).issue_blockers == []

        issued = await routes.issue_customer_pack(INVESTIGATION_ID, 1, _issue_body(), db_session, USER)

    assert review["cleared"] is True
    assert review["note"] == "Read every narrative field."
    assert review["reviewed_by_id"] == USER.id
    assert issued["disclosure_count"] == 1

    await db_session.refresh(pack)
    assert pack.redaction_review_cleared_at is not None


@pytest.mark.asyncio
async def test_a_review_requiring_changes_withdraws_an_earlier_clearance(db_session, storage, renderer):
    run = await _seed_run(db_session)
    pack = await _seed_pack(db_session, cleared=True)

    with _authorised(run):
        review = await routes.review_customer_pack_redaction(
            INVESTIGATION_ID,
            1,
            InvestigationPackRedactionReviewRequest(cleared=False, note="Driver named in section 2."),
            db_session,
            USER,
        )
        with pytest.raises(ValidationError) as exc:
            await routes.issue_customer_pack(INVESTIGATION_ID, 1, _issue_body(), db_session, USER)

    assert review["cleared"] is False
    assert review["issue_blockers"] == [BLOCKER_REDACTION_REVIEW_NOT_CLEARED]
    assert exc.value.details["blockers"] == [BLOCKER_REDACTION_REVIEW_NOT_CLEARED]

    await db_session.refresh(pack)
    assert pack.redaction_review_cleared_at is None
    # The review still happened and is still on the record.
    assert pack.redaction_review_at is not None
    assert pack.redaction_review_note == "Driver named in section 2."


@pytest.mark.asyncio
async def test_reviewing_another_tenants_pack_is_not_found(db_session, storage, renderer):
    run = await _seed_run(db_session)
    await _seed_pack(db_session, pack_id=3, tenant_id=OTHER_TENANT, cleared=False)

    with _authorised(run), pytest.raises(NotFoundError):
        await routes.review_customer_pack_redaction(
            INVESTIGATION_ID,
            3,
            InvestigationPackRedactionReviewRequest(cleared=True),
            db_session,
            USER,
        )


@pytest.mark.asyncio
async def test_review_and_issue_are_on_the_revision_trail(db_session, storage, renderer):
    run = await _seed_run(db_session)
    await _seed_pack(db_session, cleared=False)

    with _authorised(run):
        await routes.review_customer_pack_redaction(
            INVESTIGATION_ID, 1, InvestigationPackRedactionReviewRequest(cleared=True), db_session, USER
        )
        await routes.issue_customer_pack(INVESTIGATION_ID, 1, _issue_body(), db_session, USER)

    events = (
        (
            await db_session.execute(
                select(InvestigationRevisionEvent.event_type).order_by(InvestigationRevisionEvent.id)
            )
        )
        .scalars()
        .all()
    )
    assert list(events) == ["PACK_REDACTION_REVIEWED", "PACK_ISSUED"]


# ---------------------------------------------------------------------------
# The retained pack is not evidence for the next pack
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_retained_pack_is_not_offered_as_evidence_in_the_next_pack(db_session, storage, renderer):
    run = await _seed_run(db_session)
    pack = await _seed_pack(db_session)

    exhibit = EvidenceAsset(
        tenant_id=TENANT,
        storage_key="evidence/investigation/21/photo.jpg",
        content_type="image/jpeg",
        asset_type="photo",
        source_module=EvidenceSourceModule.INVESTIGATION,
        source_id=str(INVESTIGATION_ID),
        linked_investigation_id=INVESTIGATION_ID,
        visibility=EvidenceVisibility.EXTERNAL_ALLOWED,
    )
    db_session.add(exhibit)
    await db_session.commit()

    with _authorised(run):
        await routes.issue_customer_pack(INVESTIGATION_ID, 1, _issue_body(), db_session, USER)

    await db_session.refresh(pack)
    offered = (
        (await db_session.execute(pack_evidence_assets_query(investigation_id=INVESTIGATION_ID, tenant_id=TENANT)))
        .scalars()
        .all()
    )

    offered_ids = {asset.id for asset in offered}
    assert exhibit.id in offered_ids, "a genuine exhibit must still be offered"
    assert pack.issued_pdf_asset_id not in offered_ids
