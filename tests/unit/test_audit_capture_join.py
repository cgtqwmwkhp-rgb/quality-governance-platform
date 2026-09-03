"""AUD-F5: the capture write, and what it does not become.

Four things are pinned here.

1. **One transaction.** The evidence asset, the ``audit_responses`` row and the
   join row are written together. AUD-2026-0087 is the failure this closes:
   Jamie's photos were in Azure with ``source_module=audit`` and
   ``source_id=<run id>`` while the run held zero answer rows, because the save
   that would have carried ``response_json.evidence_asset_ids`` never landed.
   If any of the three can be committed without the others, the run can still
   hold evidence nobody can attribute to a question.

2. **The join does not soften AUD-F4.** A join row is not a licence to believe
   an id: completion still resolves what a response claims against the live
   ``evidence_assets`` rows for the run, so an invented id is refused whether or
   not a link row exists for something else.

3. **No circular import.** The capture endpoint lives on the audits router
   precisely so the generic evidence router never has to learn about runs,
   questions or assignees. Asserted statically over both modules' source,
   including function-level imports, because the whole point is a dependency
   direction rather than a runtime behaviour.

4. **The role vocabulary is the database's.** The model's enum and the CHECK
   constraint the migration writes cannot drift apart, or a legal role becomes
   an ``IntegrityError`` on a field upload.

The database here is an isolated in-memory SQLite schema, same shape as
``test_audit_complete_integrity.py``: SQLite does not enforce FK targets, so
tenants/users rows are not needed for these paths.
"""

from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.api.routes.audits import _evidence_role_for, _projected_evidence_ids
from src.domain.exceptions import ValidationError
from src.domain.models.audit import (
    AuditFinding,
    AuditQuestion,
    AuditResponse,
    AuditRun,
    AuditSection,
    AuditStatus,
    AuditTemplate,
)
from src.domain.models.audit_response_evidence import ROLE_VALUES, AuditEvidenceRole, AuditResponseEvidence
from src.domain.models.evidence_asset import EvidenceAsset, EvidenceAssetType, EvidenceSourceModule
from src.domain.services.audit_service import COMPLETE_EVIDENCE_NOT_RESOLVED, AuditService

REPO_ROOT = Path(__file__).resolve().parents[2]
TENANT_ID = 1


@pytest.fixture
async def session_factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        for table in (
            EvidenceAsset.__table__,
            AuditTemplate.__table__,
            AuditSection.__table__,
            AuditQuestion.__table__,
            AuditRun.__table__,
            AuditResponse.__table__,
            AuditFinding.__table__,
            AuditResponseEvidence.__table__,
        ):
            await conn.run_sync(table.create)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    yield factory
    await engine.dispose()


async def _seed_photo_run(db: AsyncSession) -> tuple[AuditRun, AuditQuestion]:
    template = AuditTemplate(
        name="Capture join",
        category="Safety",
        audit_type="inspection",
        auto_create_findings=False,
        is_published=True,
        tenant_id=TENANT_ID,
        created_by_id=1,
        reference_number="TPL-F5",
    )
    db.add(template)
    await db.flush()

    section = AuditSection(template_id=template.id, title="Evidence", sort_order=1)
    db.add(section)
    await db.flush()

    question = AuditQuestion(
        template_id=template.id,
        section_id=section.id,
        question_text="Photograph the guarding",
        question_type="photo",
        positive_answer="yes",
        is_required=True,
        sort_order=1,
    )
    db.add(question)
    await db.flush()

    run = AuditRun(
        template_id=template.id,
        title="Capture join run",
        status=AuditStatus.IN_PROGRESS,
        tenant_id=TENANT_ID,
        assigned_to_id=1,
        created_by_id=1,
        reference_number="AUD-F5",
    )
    db.add(run)
    await db.commit()
    return run, question


async def _capture(
    db: AsyncSession,
    run: AuditRun,
    question: AuditQuestion,
    *,
    key: str,
    fail_before_commit: bool = False,
) -> tuple[int, int]:
    """Write asset + answer + join the way the endpoint does, in one transaction.

    Mirrors the handler's write block rather than calling it: the handler also
    reads a multipart body and talks to blob storage, and neither is what these
    assertions are about. The ordering under test — asset, then answer, then the
    link, one commit — is the part that has to hold.
    """
    asset = EvidenceAsset(
        tenant_id=TENANT_ID,
        storage_key=key,
        content_type="image/jpeg",
        asset_type=EvidenceAssetType.PHOTO,
        source_module=EvidenceSourceModule.AUDIT,
        source_id=str(run.id),
        description=f"audit_question:{question.id}",
    )
    db.add(asset)
    await db.flush()
    asset_id = asset.id

    from src.api.routes.audits import _answer_row, _upsert_answer_row

    existing = await _answer_row(db, run.id, question.id)
    next_json, _ = _projected_evidence_ids(existing, asset_id)
    row, _outcome = await _upsert_answer_row(
        db,
        run,
        question,
        {"response_json": next_json},
        tenant_id=TENANT_ID,
    )
    response_id = row.id

    db.add(
        AuditResponseEvidence(
            response_id=response_id,
            evidence_asset_id=asset_id,
            role=AuditEvidenceRole.PHOTO.value,
            created_by_id=1,
        )
    )
    if fail_before_commit:
        await db.rollback()
        return asset_id, response_id
    await db.commit()
    return asset_id, response_id


# ---------------------------------------------------------------------------
# 1 — one transaction
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_capture_writes_the_asset_the_answer_and_the_join_together(session_factory):
    async with session_factory() as db:
        run, question = await _seed_photo_run(db)
        asset_id, response_id = await _capture(db, run, question, key="run/photo-1.jpg")

        # Snapshot ids before expire_all(): it drops loaded columns including the
        # PK, so the next attribute access would lazy-load (MissingGreenlet on
        # asyncpg). AUD-F4 taught this suite that the hard way.
        run_id = run.id
        question_id = question.id
        db.expire_all()

        stored_answer = await db.get(AuditResponse, response_id)
        assert stored_answer is not None
        assert stored_answer.run_id == run_id
        assert stored_answer.question_id == question_id
        assert stored_answer.tenant_id == TENANT_ID

        links = (
            (await db.execute(select(AuditResponseEvidence).where(AuditResponseEvidence.response_id == response_id)))
            .scalars()
            .all()
        )
        assert [(link.evidence_asset_id, link.role) for link in links] == [(asset_id, "photo")]

        # And the projection AUD-F4 reads is in step with the join.
        assert stored_answer.response_json == {"evidence_asset_ids": [asset_id]}


@pytest.mark.asyncio
async def test_a_failed_capture_leaves_no_asset_no_answer_and_no_join(session_factory):
    """The whole point of one transaction: no orphan half of the link."""
    async with session_factory() as db:
        run, question = await _seed_photo_run(db)
        run_id = run.id
        await _capture(db, run, question, key="run/photo-doomed.jpg", fail_before_commit=True)

        db.expire_all()
        assets = (await db.execute(select(EvidenceAsset).where(EvidenceAsset.source_id == str(run_id)))).scalars().all()
        answers = (await db.execute(select(AuditResponse).where(AuditResponse.run_id == run_id))).scalars().all()
        links = (await db.execute(select(AuditResponseEvidence))).scalars().all()

        assert assets == []
        assert answers == []
        assert links == []


@pytest.mark.asyncio
async def test_a_second_capture_for_the_same_question_adds_a_link_not_a_second_answer(session_factory):
    """One answer row per question (AUD-F3's unique constraint), many links."""
    async with session_factory() as db:
        run, question = await _seed_photo_run(db)
        first_asset, first_response = await _capture(db, run, question, key="run/photo-1.jpg")
        second_asset, second_response = await _capture(db, run, question, key="run/photo-2.jpg")

        assert second_response == first_response

        run_id = run.id
        db.expire_all()
        answers = (await db.execute(select(AuditResponse).where(AuditResponse.run_id == run_id))).scalars().all()
        assert len(answers) == 1
        assert answers[0].response_json == {"evidence_asset_ids": [first_asset, second_asset]}

        linked = (
            (
                await db.execute(
                    select(AuditResponseEvidence.evidence_asset_id).where(
                        AuditResponseEvidence.response_id == first_response
                    )
                )
            )
            .scalars()
            .all()
        )
        assert sorted(linked) == sorted([first_asset, second_asset])


@pytest.mark.asyncio
async def test_a_capture_does_not_invent_an_answer_value(session_factory):
    """Attaching a photo is evidence, not a verdict on the question."""
    async with session_factory() as db:
        run, question = await _seed_photo_run(db)
        _asset_id, response_id = await _capture(db, run, question, key="run/photo-1.jpg")

        db.expire_all()
        stored = await db.get(AuditResponse, response_id)
        assert stored is not None
        assert stored.response_value is None
        assert stored.response_text is None
        assert stored.response_bool is None
        assert stored.is_na is False


@pytest.mark.asyncio
async def test_a_capture_preserves_the_client_revision_already_on_the_answer(session_factory):
    """Wiping it would make the auditor's next legitimate save look like a replay."""
    async with session_factory() as db:
        run, question = await _seed_photo_run(db)
        db.add(
            AuditResponse(
                run_id=run.id,
                question_id=question.id,
                tenant_id=TENANT_ID,
                response_value="yes",
                response_json={"client_revision": 9, "selected": ["a"]},
            )
        )
        await db.commit()

        asset_id, response_id = await _capture(db, run, question, key="run/photo-1.jpg")

        db.expire_all()
        stored = await db.get(AuditResponse, response_id)
        assert stored is not None
        assert stored.response_json == {
            "client_revision": 9,
            "selected": ["a"],
            "evidence_asset_ids": [asset_id],
        }
        assert stored.response_value == "yes"


# ---------------------------------------------------------------------------
# 2 — the join does not soften AUD-F4
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_an_invented_id_is_still_refused_when_the_answer_also_has_a_real_link(session_factory):
    async with session_factory() as db:
        run, question = await _seed_photo_run(db)
        await _capture(db, run, question, key="run/photo-1.jpg")

        # The client adds an id nobody issued alongside the real one.
        row = await db.get(AuditResponse, (await _first_response_id(db, run.id)))
        assert row is not None
        row.response_json = {"evidence_asset_ids": sorted({*row.response_json["evidence_asset_ids"], 4242})}
        await db.commit()

        with pytest.raises(ValidationError) as refused:
            await AuditService(db).complete_run(run.id, tenant_id=TENANT_ID, actor_user_id=1)

        assert refused.value.code == COMPLETE_EVIDENCE_NOT_RESOLVED
        assert refused.value.details["unresolved_evidence_asset_ids"] == [4242]


@pytest.mark.asyncio
async def test_a_captured_run_completes_because_the_evidence_is_real(session_factory):
    """The positive half: nothing about F5 makes completion harder than F4 did."""
    async with session_factory() as db:
        run, question = await _seed_photo_run(db)
        await _capture(db, run, question, key="run/photo-1.jpg")

        completed = await AuditService(db).complete_run(run.id, tenant_id=TENANT_ID, actor_user_id=1)
        await db.commit()

        assert completed.status == AuditStatus.COMPLETED


async def _first_response_id(db: AsyncSession, run_id: int) -> int:
    result = await db.execute(select(AuditResponse.id).where(AuditResponse.run_id == run_id))
    return int(result.scalars().one())


# ---------------------------------------------------------------------------
# 3 — no circular import between the audit route and the evidence route
# ---------------------------------------------------------------------------


def _imported_modules(path: Path) -> set[str]:
    """Every module either import form names, at any nesting depth.

    Module level is not enough: this repository routinely imports inside a
    handler to break a cycle, so a function-level
    ``from src.api.routes.evidence_assets import ...`` would be invisible to a
    top-of-file check while being exactly the thing that must not appear.
    """
    tree = ast.parse(path.read_text())
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.add(node.module)
    return names


def test_the_audits_route_does_not_import_the_evidence_route() -> None:
    imported = _imported_modules(REPO_ROOT / "src/api/routes/audits.py")
    assert "src.api.routes.evidence_assets" not in imported, (
        "the capture endpoint must not reach into the generic evidence router. "
        "That router imports the audit *model* to validate a source id, so an "
        "import back the other way closes a cycle — which is why AUD-F5 is an "
        "audit-scoped endpoint in the first place."
    )


def test_the_evidence_route_does_not_import_audit_services() -> None:
    """The other direction, so nobody 'fixes' this by moving the dependency."""
    imported = _imported_modules(REPO_ROOT / "src/api/routes/evidence_assets.py")
    audit_services = sorted(name for name in imported if name.startswith("src.domain.services.audit"))
    assert audit_services == [], (
        f"the generic evidence router now imports {audit_services}. It must stay "
        "generic: audit runs, questions, assignees and the answer upsert are the "
        "audits module's business."
    )


def test_the_capture_endpoint_reuses_infrastructure_not_the_evidence_router() -> None:
    """What the audits route is allowed to share: storage + the allowlist."""
    imported = _imported_modules(REPO_ROOT / "src/api/routes/audits.py")
    assert "src.infrastructure.storage" in imported
    assert "src.domain.services.evidence_service" in imported


# ---------------------------------------------------------------------------
# 4 — helper-level facts, no database needed
# ---------------------------------------------------------------------------


def test_the_role_check_constraint_matches_the_model_enum() -> None:
    migration = (REPO_ROOT / "alembic/versions/20261119_aud_f5_response_evidence.py").read_text()
    for value in ROLE_VALUES:
        assert f"'{value}'" in migration, f"role {value!r} is legal in the model but not in the CHECK constraint"
    assert ROLE_VALUES == ("photo", "signature", "attachment")


#: Asks Alembic for the chain rather than re-implementing its parser, the same
#: probe ``test_job_lifecycle_ux_w5.py`` uses. Run out of process and out of the
#: repo directory because the repository's own ``alembic/`` package shadows the
#: installed one on ``sys.path`` when the cwd is the repo root.
_HEADS_RUNNER = r"""
import json, sys
from alembic.config import Config
from alembic.script import ScriptDirectory

repo = sys.argv[1]
# Some revisions import ``src.*`` at module scope, which ScriptDirectory loads.
sys.path.append(repo)
cfg = Config(repo + "/alembic.ini")
cfg.set_main_option("script_location", repo + "/alembic")
script = ScriptDirectory.from_config(cfg)
print(json.dumps({
    "heads": sorted(script.get_heads()),
    "parents": sorted(script.get_revision("20261119_aud_f5_resp_evid")._all_down_revisions or ()),
}))
"""


def _alembic_chain(tmp_path: Path) -> dict:
    tmp_path.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run(
        [sys.executable, "-c", _HEADS_RUNNER, str(REPO_ROOT)],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        timeout=180,
    )
    if completed.returncode != 0:
        pytest.fail(f"alembic head probe failed:\nstdout={completed.stdout}\nstderr={completed.stderr}")
    return json.loads(completed.stdout)


def test_the_new_revision_is_the_only_head(tmp_path) -> None:
    """A second head makes ``alembic upgrade head`` refuse — on deploy, not here.

    The trap this catches is not a typo. ``20261118_engineer_roster_archived_at``
    sorts last in ``alembic/versions`` and is *not* the tip: the competence-board
    revisions are filed under ``20260901_*`` while chaining after it. Revising
    the file that looks latest forks the chain, and nothing about the diff would
    say so.
    """
    chain = _alembic_chain(tmp_path)
    assert chain["heads"] == ["20261119_aud_f5_resp_evid"], f"expected a single head, found {chain['heads']}"
    assert chain["parents"] == ["20260901_comp_cov"]


def test_the_migration_adds_a_table_and_backfills_nothing() -> None:
    """The kill condition: a join backfill would need downtime, so there isn't one."""
    migration = (REPO_ROOT / "alembic/versions/20261119_aud_f5_response_evidence.py").read_text()
    tree = ast.parse(migration)
    upgrade = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "upgrade")
    called = {
        node.func.attr
        for node in ast.walk(upgrade)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert "create_table" in called
    for forbidden in ("alter_column", "add_column", "drop_column", "bulk_insert", "execute"):
        assert forbidden not in called, f"upgrade() calls op.{forbidden}; this revision is ADD TABLE only"


@pytest.mark.parametrize(
    ("asset_type", "expected"),
    [
        (EvidenceAssetType.PHOTO, "photo"),
        (EvidenceAssetType.SIGNATURE, "signature"),
        (EvidenceAssetType.PDF, "attachment"),
        (EvidenceAssetType.DOCUMENT, "attachment"),
        (EvidenceAssetType.OTHER, "attachment"),
    ],
)
def test_the_role_describes_what_the_file_actually_is(asset_type, expected) -> None:
    assert _evidence_role_for(asset_type) == expected


def test_the_projection_ignores_junk_the_client_left_in_the_id_list() -> None:
    row = AuditResponse()
    row.__dict__["response_json"] = {"evidence_asset_ids": [7, "8", None, -1, 0, "nine", 7]}
    payload, ids = _projected_evidence_ids(row, 12)
    assert ids == [7, 8, 12]
    assert payload["evidence_asset_ids"] == [7, 8, 12]


def test_the_projection_survives_a_response_json_that_is_not_an_object() -> None:
    row = AuditResponse()
    row.__dict__["response_json"] = "captured"
    payload, ids = _projected_evidence_ids(row, 12)
    assert ids == [12]
    assert payload == {"evidence_asset_ids": [12]}


def test_the_projection_handles_a_question_with_no_answer_row_yet() -> None:
    payload, ids = _projected_evidence_ids(None, 12)
    assert ids == [12]
    assert payload == {"evidence_asset_ids": [12]}
