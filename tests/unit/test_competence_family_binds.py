"""CB-UI-2: one published template ↔ one PAMS characteristic, per mode.

The claims under test are the ones an IT-Admin can get wrong on the bind
screen, plus the two the board would then report dishonestly:

* a characteristic accepts a *field* bind and an *induction* bind, and no
  second template in either mode;
* an unpublished template cannot be bound at all, because its questions can
  still change under the bind;
* the interval declared on the bind is the one the demonstration expires on;
* a characteristic nobody has bound is still **listed**, and removing a bind
  empties the overlay for that column rather than inventing a grey
  "not assessed" — which is CB-UI-1's cell-honesty rule seen from the server.
"""

from __future__ import annotations

import ast
import json
import subprocess
import sys
import types
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import get_args
from unittest.mock import AsyncMock

import pytest
from fastapi import Response

from src.api.routes import workforce_competence_board as board_routes
from src.core.config import settings
from src.domain.exceptions import BadRequestError, ConflictError
from src.domain.models.audit import AuditTemplate
from src.domain.models.competence_assessment_bind import BIND_MODES, CompetenceAssessmentBind
from src.domain.models.competence_demonstration import CompetenceDemonstration
from src.domain.models.engineer import CompetencyLifecycleState, Engineer
from src.domain.models.pams_cache import PamsCompetenceRow
from src.domain.services import competence_demonstration_service as bind_service
from src.domain.services.competence_demonstration_service import (
    CHARACTERISTIC_ALREADY_BOUND,
    TEMPLATE_ALREADY_BOUND,
    TEMPLATE_NOT_PUBLISHED,
    create_bind_async,
    delete_bind_async,
    governing_template_by_characteristic,
    load_demonstration_overlay_async,
    record_assessment_demonstration_async,
)

# The CB-PR4 session double already models ``scalars`` dispatch on the selected
# entity; reusing it keeps one double in the tree rather than two that drift.
from tests.unit.test_competence_assessment_overlay import _bind, _engineer, _FakeDb, _published_template

TENANT = 1
ENGINEER_ID = 9
FIELD_TEMPLATE_ID = 8
INDUCTION_TEMPLATE_ID = 12
CHARACTERISTIC = "Compressor"

REPO_ROOT = Path(__file__).resolve().parents[2]
MIGRATION_PATH = REPO_ROOT / "alembic/versions/20260903_competence_bind_mode_interval.py"


def _both_templates() -> list[AuditTemplate]:
    return [
        _published_template(template_id=FIELD_TEMPLATE_ID),
        _published_template(template_id=INDUCTION_TEMPLATE_ID),
    ]


# ------------------------------------------------------- AC-01 one per mode


@pytest.mark.asyncio
async def test_a_second_template_for_the_same_characteristic_and_mode_is_refused():
    db = _FakeDb(rows={AuditTemplate: _both_templates()})

    first, created = await create_bind_async(
        db,
        tenant_id=TENANT,
        template_id=FIELD_TEMPLATE_ID,
        characteristic_key=CHARACTERISTIC,
        mode="field",
    )
    assert created is True
    assert first.mode == "field"

    with pytest.raises(ConflictError) as exc_info:
        await create_bind_async(
            db,
            tenant_id=TENANT,
            template_id=INDUCTION_TEMPLATE_ID,
            characteristic_key=CHARACTERISTIC,
            mode="field",
        )
    assert CHARACTERISTIC_ALREADY_BOUND in str(exc_info.value)
    assert len(db.added_of(CompetenceAssessmentBind)) == 1


@pytest.mark.asyncio
async def test_field_and_induction_can_both_be_bound_to_one_characteristic():
    db = _FakeDb(rows={AuditTemplate: _both_templates()})

    field_bind, _ = await create_bind_async(
        db,
        tenant_id=TENANT,
        template_id=FIELD_TEMPLATE_ID,
        characteristic_key=CHARACTERISTIC,
        mode="field",
    )
    induction_bind, created = await create_bind_async(
        db,
        tenant_id=TENANT,
        template_id=INDUCTION_TEMPLATE_ID,
        characteristic_key=CHARACTERISTIC,
        mode="induction",
    )

    assert created is True
    assert induction_bind is not field_bind
    assert {row.mode for row in db.added_of(CompetenceAssessmentBind)} == {"field", "induction"}
    assert {row.characteristic_key for row in db.added_of(CompetenceAssessmentBind)} == {CHARACTERISTIC}


@pytest.mark.asyncio
async def test_one_template_still_cannot_serve_two_characteristics():
    """Mode does not loosen the template side of the 1:1."""
    db = _FakeDb(rows={AuditTemplate: _both_templates()})

    await create_bind_async(
        db,
        tenant_id=TENANT,
        template_id=FIELD_TEMPLATE_ID,
        characteristic_key=CHARACTERISTIC,
        mode="field",
    )

    with pytest.raises(ConflictError) as exc_info:
        await create_bind_async(
            db,
            tenant_id=TENANT,
            template_id=FIELD_TEMPLATE_ID,
            characteristic_key="Trailer",
            mode="induction",
        )
    assert TEMPLATE_ALREADY_BOUND in str(exc_info.value)


@pytest.mark.asyncio
async def test_reposting_the_same_pair_reconciles_the_interval_without_a_second_row():
    db = _FakeDb(rows={AuditTemplate: _both_templates()})

    first, created = await create_bind_async(
        db,
        tenant_id=TENANT,
        template_id=FIELD_TEMPLATE_ID,
        characteristic_key=CHARACTERISTIC,
        mode="field",
        interval_days=365,
    )
    assert created is True
    assert first.interval_days == 365

    again, created_again = await create_bind_async(
        db,
        tenant_id=TENANT,
        template_id=FIELD_TEMPLATE_ID,
        characteristic_key=CHARACTERISTIC,
        mode="field",
        interval_days=730,
    )
    assert created_again is False
    assert again is first
    assert again.interval_days == 730
    assert len(db.added_of(CompetenceAssessmentBind)) == 1


@pytest.mark.asyncio
async def test_an_unknown_mode_is_refused_rather_than_defaulted():
    db = _FakeDb(rows={AuditTemplate: _both_templates()})

    with pytest.raises(BadRequestError):
        await create_bind_async(
            db,
            tenant_id=TENANT,
            template_id=FIELD_TEMPLATE_ID,
            characteristic_key=CHARACTERISTIC,
            mode="oem",
        )
    assert db.added_of(CompetenceAssessmentBind) == []


def test_the_wire_mode_literal_matches_the_column_constant():
    """A Literal cannot be built from the tuple, so assert they agree."""
    assert set(get_args(board_routes.BindMode)) == set(BIND_MODES)


# ------------------------------------------------------ AC-02 published only


@pytest.mark.asyncio
async def test_a_draft_template_cannot_be_bound():
    draft = AuditTemplate(id=FIELD_TEMPLATE_ID, tenant_id=TENANT, is_published=False, is_active=True)
    db = _FakeDb(rows={AuditTemplate: [draft]})

    with pytest.raises(BadRequestError) as exc_info:
        await create_bind_async(
            db,
            tenant_id=TENANT,
            template_id=FIELD_TEMPLATE_ID,
            characteristic_key=CHARACTERISTIC,
            mode="field",
        )
    assert TEMPLATE_NOT_PUBLISHED in str(exc_info.value)
    assert db.added_of(CompetenceAssessmentBind) == []


@pytest.mark.asyncio
async def test_an_archived_template_cannot_be_bound():
    archived = AuditTemplate(id=FIELD_TEMPLATE_ID, tenant_id=TENANT, is_published=True, is_active=False)
    db = _FakeDb(rows={AuditTemplate: [archived]})

    with pytest.raises(BadRequestError):
        await create_bind_async(
            db,
            tenant_id=TENANT,
            template_id=FIELD_TEMPLATE_ID,
            characteristic_key=CHARACTERISTIC,
            mode="field",
        )


# ------------------------------------------------------- AC-03 bind interval


@pytest.mark.asyncio
async def test_the_bind_interval_is_what_the_demonstration_expires_on(monkeypatch):
    monkeypatch.setattr(
        bind_service,
        "resolve_reassessment_interval_days",
        AsyncMock(side_effect=AssertionError("the bind declares an interval; do not fall back")),
    )
    db = _FakeDb(
        rows={
            CompetenceAssessmentBind: [_bind(interval_days=90)],
            Engineer: [_engineer()],
        }
    )

    result = await record_assessment_demonstration_async(
        db,
        tenant_id=TENANT,
        engineer_id=ENGINEER_ID,
        template_id=FIELD_TEMPLATE_ID,
        source_run_id="asm-run-bind-interval",
        outcome="pass",
    )

    assert result is not None
    expected = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=90)
    assert abs((result.demonstration.expires_at - expected).total_seconds()) < 60


@pytest.mark.asyncio
async def test_a_bind_without_an_interval_falls_back_rather_than_never_expiring(monkeypatch):
    monkeypatch.setattr(bind_service, "resolve_reassessment_interval_days", AsyncMock(return_value=180))
    db = _FakeDb(rows={CompetenceAssessmentBind: [_bind(interval_days=None)], Engineer: [_engineer()]})

    result = await record_assessment_demonstration_async(
        db,
        tenant_id=TENANT,
        engineer_id=ENGINEER_ID,
        template_id=FIELD_TEMPLATE_ID,
        source_run_id="asm-run-no-interval",
        outcome="pass",
    )

    assert result is not None
    expected = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=180)
    assert abs((result.demonstration.expires_at - expected).total_seconds()) < 60


# ------------------------------------- AC-04 unbound is listed, never a fail


def _snapshot(completed_at: datetime | None = None):
    return types.SimpleNamespace(
        id=7,
        status="ready",
        source_name="vw_plantex_engineercompetence",
        row_count=2,
        completed_at=completed_at or datetime.now(timezone.utc).replace(tzinfo=None),
    )


def _snapshot_row(characteristic: str):
    return PamsCompetenceRow(
        snapshot_id=7,
        engineer_id=ENGINEER_ID,
        pams_technician_id=158,
        characteristic_key=characteristic,
        thorough_exam=True,
    )


@pytest.mark.asyncio
async def test_unbound_characteristics_are_listed_beside_the_binds(monkeypatch):
    monkeypatch.setattr(settings, "competence_board_enabled", True)
    monkeypatch.setattr(
        "src.api.routes.workforce_competence_board.load_current_snapshot_async",
        AsyncMock(return_value=(_snapshot(), [_snapshot_row(CHARACTERISTIC), _snapshot_row("Trailer")])),
    )
    db = _FakeDb(rows={CompetenceAssessmentBind: [_bind(characteristic=CHARACTERISTIC)]})

    listed = await board_routes.list_competence_assessment_binds(
        db=db, current_user=types.SimpleNamespace(tenant_id=TENANT)
    )

    assert [item.characteristic_key for item in listed.items] == [CHARACTERISTIC]
    # "Trailer" has no bind and is still on the page. Filtering it out is what
    # would make an unmapped characteristic look like a measured gap.
    assert [entry.key for entry in listed.characteristics] == [CHARACTERISTIC, "Trailer"]
    assert listed.banner is None


@pytest.mark.asyncio
async def test_no_snapshot_says_so_rather_than_offering_an_empty_list(monkeypatch):
    monkeypatch.setattr(settings, "competence_board_enabled", True)
    monkeypatch.setattr(
        "src.api.routes.workforce_competence_board.load_current_snapshot_async",
        AsyncMock(return_value=(None, [])),
    )
    db = _FakeDb(rows={CompetenceAssessmentBind: []})

    listed = await board_routes.list_competence_assessment_binds(
        db=db, current_user=types.SimpleNamespace(tenant_id=TENANT)
    )

    assert listed.characteristics == []
    assert listed.banner is not None
    assert "No PAMS competence snapshot" in listed.banner


@pytest.mark.asyncio
async def test_a_stale_snapshot_keeps_its_own_warning(monkeypatch):
    monkeypatch.setattr(settings, "competence_board_enabled", True)
    stale = _snapshot(completed_at=datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=3))
    monkeypatch.setattr(
        "src.api.routes.workforce_competence_board.load_current_snapshot_async",
        AsyncMock(return_value=(stale, [_snapshot_row(CHARACTERISTIC)])),
    )
    db = _FakeDb(rows={CompetenceAssessmentBind: []})

    listed = await board_routes.list_competence_assessment_binds(
        db=db, current_user=types.SimpleNamespace(tenant_id=TENANT)
    )

    assert [entry.key for entry in listed.characteristics] == [CHARACTERISTIC]
    assert listed.banner is not None
    assert "stale" in listed.banner.lower()


# --------------------------------- AC-05 removing a bind empties the overlay


def _demonstration(*, template_id=FIELD_TEMPLATE_ID, characteristic=CHARACTERISTIC):
    return CompetenceDemonstration(
        id=5,
        tenant_id=TENANT,
        engineer_id=ENGINEER_ID,
        characteristic_key=characteristic,
        template_id=template_id,
        source_run_id="asm-run-history",
        outcome="pass",
        state=CompetencyLifecycleState.ACTIVE.value,
        assessed_at=datetime(2026, 8, 20, 9, 0),
    )


@pytest.mark.asyncio
async def test_deleting_the_bind_empties_the_overlay_but_keeps_the_history():
    bind = _bind(characteristic=CHARACTERISTIC, template_id=FIELD_TEMPLATE_ID)
    demonstration = _demonstration()
    db = _FakeDb(rows={CompetenceAssessmentBind: [bind], CompetenceDemonstration: [demonstration]})

    before = await load_demonstration_overlay_async(db, tenant_id=TENANT, engineer_ids={ENGINEER_ID})
    assert before[(ENGINEER_ID, CHARACTERISTIC)] is demonstration

    await delete_bind_async(db, tenant_id=TENANT, bind_id=bind.id)

    after = await load_demonstration_overlay_async(db, tenant_id=TENANT, engineer_ids={ENGINEER_ID})
    assert after == {}
    # The row is history, not a claim. It stays in the table.
    assert db.bucket(CompetenceDemonstration) == [demonstration]


@pytest.mark.asyncio
async def test_the_board_cell_falls_back_to_issued_after_the_bind_is_removed(monkeypatch):
    """Not "not assessed", not grey — PAMS still issued it, QGP just no longer claims a demonstration."""
    monkeypatch.setattr(settings, "competence_board_enabled", True)
    monkeypatch.setattr(
        "src.api.routes.workforce_competence_board.load_current_snapshot_async",
        AsyncMock(
            return_value=(
                _snapshot(),
                [
                    types.SimpleNamespace(
                        engineer_id=ENGINEER_ID,
                        pams_technician_id=158,
                        engineer_name="Cameron",
                        email=None,
                        depot="SS11",
                        characteristic_key=CHARACTERISTIC,
                        thorough_exam=True,
                    )
                ],
            )
        ),
    )
    db = _FakeDb(
        rows={
            Engineer: [_engineer()],
            CompetenceAssessmentBind: [],
            CompetenceDemonstration: [_demonstration()],
        }
    )

    response = await board_routes.get_competence_board(
        db=db,
        current_user=types.SimpleNamespace(tenant_id=TENANT),
        family="pams",
    )

    cell = response.people[0].cells[CHARACTERISTIC]
    assert cell.issued is True
    assert cell.demonstrated is None
    assert cell.assessed_at is None


@pytest.mark.asyncio
async def test_a_demonstration_from_a_rebound_template_does_not_reappear_on_the_old_column():
    """The bind moved to another characteristic; the old column is not its evidence."""
    moved = _bind(characteristic="Trailer", template_id=FIELD_TEMPLATE_ID)
    db = _FakeDb(rows={CompetenceAssessmentBind: [moved], CompetenceDemonstration: [_demonstration()]})

    overlay = await load_demonstration_overlay_async(db, tenant_id=TENANT, engineer_ids={ENGINEER_ID})

    assert overlay == {}


# ------------- AC-07 two modes, one square: the field assessment governs it


def _induction_bind():
    return _bind(
        characteristic=CHARACTERISTIC,
        template_id=INDUCTION_TEMPLATE_ID,
        bind_id=4,
        mode="induction",
    )


def _failed_induction_demonstration():
    return CompetenceDemonstration(
        id=6,
        tenant_id=TENANT,
        engineer_id=ENGINEER_ID,
        characteristic_key=CHARACTERISTIC,
        template_id=INDUCTION_TEMPLATE_ID,
        source_run_id="asm-run-induction",
        outcome="fail",
        state=CompetencyLifecycleState.FAILED.value,
        # Later than the field pass, so recency alone would let it win.
        assessed_at=datetime(2026, 8, 25, 9, 0),
    )


@pytest.mark.asyncio
async def test_a_later_induction_fail_does_not_overwrite_the_field_pass_on_the_cell():
    """The defect the mode split would otherwise introduce.

    CB-PR4 could key the overlay on (engineer, characteristic) because one
    characteristic had one bind. Two binds means two templates writing onto one
    square, and last-write-wins would show a passed engineer as failed.
    """
    field_pass = _demonstration()
    induction_fail = _failed_induction_demonstration()
    db = _FakeDb(
        rows={
            CompetenceAssessmentBind: [_bind(), _induction_bind()],
            CompetenceDemonstration: [field_pass, induction_fail],
        }
    )

    overlay = await load_demonstration_overlay_async(db, tenant_id=TENANT, engineer_ids={ENGINEER_ID})

    assert overlay[(ENGINEER_ID, CHARACTERISTIC)] is field_pass
    assert overlay[(ENGINEER_ID, CHARACTERISTIC)].outcome == "pass"


@pytest.mark.asyncio
async def test_the_governing_bind_does_not_depend_on_the_order_rows_come_back():
    """Deterministic: field wins whichever way the query happens to sort."""
    field, induction = _bind(), _induction_bind()

    assert governing_template_by_characteristic([field, induction]) == {CHARACTERISTIC: FIELD_TEMPLATE_ID}
    assert governing_template_by_characteristic([induction, field]) == {CHARACTERISTIC: FIELD_TEMPLATE_ID}


@pytest.mark.asyncio
async def test_an_induction_only_characteristic_is_governed_by_its_induction():
    """No field bind means the induction is the only claim there is — show it."""
    induction_fail = _failed_induction_demonstration()
    db = _FakeDb(
        rows={
            CompetenceAssessmentBind: [_induction_bind()],
            CompetenceDemonstration: [induction_fail],
        }
    )

    overlay = await load_demonstration_overlay_async(db, tenant_id=TENANT, engineer_ids={ENGINEER_ID})

    assert overlay[(ENGINEER_ID, CHARACTERISTIC)] is induction_fail


@pytest.mark.asyncio
async def test_removing_the_field_bind_hands_the_cell_to_the_remaining_induction():
    """One rule, applied consistently — not a special case for deletion."""
    field, induction = _bind(), _induction_bind()
    field_pass, induction_fail = _demonstration(), _failed_induction_demonstration()
    db = _FakeDb(
        rows={
            CompetenceAssessmentBind: [field, induction],
            CompetenceDemonstration: [field_pass, induction_fail],
        }
    )

    await delete_bind_async(db, tenant_id=TENANT, bind_id=field.id)
    overlay = await load_demonstration_overlay_async(db, tenant_id=TENANT, engineer_ids={ENGINEER_ID})

    assert overlay[(ENGINEER_ID, CHARACTERISTIC)] is induction_fail


@pytest.mark.asyncio
async def test_binds_on_different_characteristics_do_not_compete():
    """The rule is per characteristic, not one governing template per tenant."""
    other = _bind(characteristic="Trailer", template_id=INDUCTION_TEMPLATE_ID, bind_id=5)

    assert governing_template_by_characteristic([_bind(), other]) == {
        CHARACTERISTIC: FIELD_TEMPLATE_ID,
        "Trailer": INDUCTION_TEMPLATE_ID,
    }


@pytest.mark.asyncio
async def test_a_failed_induction_names_its_mode_in_the_change_request():
    """ "Failed Compressor" alone would not tell the reviewer which assessment."""
    db = _FakeDb(rows={CompetenceAssessmentBind: [_induction_bind()], Engineer: [_engineer()]})

    result = await record_assessment_demonstration_async(
        db,
        tenant_id=TENANT,
        engineer_id=ENGINEER_ID,
        template_id=INDUCTION_TEMPLATE_ID,
        source_run_id="asm-run-induction-fail",
        outcome="fail",
    )

    assert result is not None
    assert result.change_request is not None
    assert "induction" in result.change_request.notes
    # Still a review item, never a PAMS write.
    assert "does not write PAMS" in result.change_request.notes


@pytest.mark.asyncio
async def test_rebinding_the_same_template_to_the_other_mode_says_what_is_actually_wrong():
    """It is not bound to a different characteristic — saying so would be false."""
    db = _FakeDb(
        rows={
            AuditTemplate: _both_templates(),
            CompetenceAssessmentBind: [_bind()],
        }
    )

    with pytest.raises(ConflictError) as raised:
        await create_bind_async(
            db,
            tenant_id=TENANT,
            template_id=FIELD_TEMPLATE_ID,
            characteristic_key=CHARACTERISTIC,
            mode="induction",
        )

    message = str(raised.value)
    assert "other mode" in message
    assert "different PAMS characteristic" not in message


# ------------------------------------------------------------- AC-06 the flag


@pytest.mark.asyncio
async def test_bind_endpoints_carry_mode_and_interval_end_to_end(monkeypatch):
    monkeypatch.setattr(settings, "competence_board_enabled", True)
    monkeypatch.setattr(
        "src.api.routes.workforce_competence_board.load_current_snapshot_async",
        AsyncMock(return_value=(_snapshot(), [_snapshot_row(CHARACTERISTIC)])),
    )
    db = _FakeDb(rows={AuditTemplate: _both_templates()})
    user = types.SimpleNamespace(id=42, tenant_id=TENANT)
    response = Response()

    field = await board_routes.create_competence_assessment_bind(
        payload=board_routes.CompetenceAssessmentBindCreate(
            template_id=FIELD_TEMPLATE_ID,
            characteristic_key=CHARACTERISTIC,
            mode="field",
            interval_days=365,
        ),
        db=db,
        current_user=user,
        response=response,
    )
    assert response.status_code == 201
    assert field.mode == "field"
    assert field.interval_days == 365

    induction = await board_routes.create_competence_assessment_bind(
        payload=board_routes.CompetenceAssessmentBindCreate(
            template_id=INDUCTION_TEMPLATE_ID,
            characteristic_key=CHARACTERISTIC,
            mode="induction",
        ),
        db=db,
        current_user=user,
        response=response,
    )
    assert induction.mode == "induction"
    assert induction.interval_days is None

    listed = await board_routes.list_competence_assessment_binds(db=db, current_user=user)
    assert {(item.characteristic_key, item.mode) for item in listed.items} == {
        (CHARACTERISTIC, "field"),
        (CHARACTERISTIC, "induction"),
    }

    await board_routes.delete_competence_assessment_bind(bind_id=field.id, db=db, current_user=user)
    remaining = await board_routes.list_competence_assessment_binds(db=db, current_user=user)
    assert [item.mode for item in remaining.items] == ["induction"]
    # The column is still on the page after the bind is gone.
    assert [entry.key for entry in remaining.characteristics] == [CHARACTERISTIC]


def test_the_bind_routes_stay_behind_the_flag_dependency():
    """Flag off is a 404 for the bind surface too, not an empty mapping screen."""
    assert any(
        getattr(dependency, "dependency", None) is board_routes.require_competence_board_enabled
        for dependency in board_routes._enabled_router.dependencies
    )


# ------------------------------------------------------------ the migration


def _module_constant(name: str):
    """Read a revision constant without importing it.

    The repository's own ``alembic/`` directory shadows the installed
    distribution whenever the cwd is the repo root, which is where pytest runs.
    """
    tree = ast.parse(MIGRATION_PATH.read_text())
    for node in tree.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Name) and target.id == name:
                    return ast.literal_eval(node.value)
    raise AssertionError(f"{name} not found in {MIGRATION_PATH.name}")


def test_the_revision_chains_off_the_real_head():
    assert _module_constant("revision") == "20260903_cb_bind_mode"
    # ``alembic heads`` at the time of writing. The filename that sorts last in
    # alembic/versions is not the head in this tree — 20260901_* chains after
    # 20261118_*, which is the trap AUD-F5 documented.
    assert _module_constant("down_revision") == "20261119_aud_f5_resp_evid"


#: Runs out of process and out of the repo directory for the same shadowing
#: reason, the way ``test_audit_capture_join.py`` probes the revision map.
_MIGRATION_RUNNER = r"""
import json, sys
import importlib.util
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, text

repo = sys.argv[1]
sys.path.append(repo)

spec = importlib.util.spec_from_file_location(
    "cb_ui2_bind_revision", repo + "/alembic/versions/20260903_competence_bind_mode_interval.py"
)
revision = importlib.util.module_from_spec(spec)
spec.loader.exec_module(revision)

TABLE = "competence_assessment_binds"
engine = create_engine("sqlite://")
with engine.begin() as conn:
    conn.execute(text("CREATE TABLE audit_templates (id INTEGER PRIMARY KEY)"))
    conn.execute(text(
        "CREATE TABLE " + TABLE + " ("
        " id INTEGER PRIMARY KEY,"
        " tenant_id INTEGER NOT NULL,"
        " template_id INTEGER NOT NULL,"
        " characteristic_key VARCHAR(80) NOT NULL,"
        " created_at DATETIME NOT NULL,"
        " CONSTRAINT uq_competence_assessment_binds_template UNIQUE (tenant_id, template_id),"
        " CONSTRAINT uq_competence_assessment_binds_characteristic UNIQUE (tenant_id, characteristic_key),"
        " FOREIGN KEY(template_id) REFERENCES audit_templates(id) ON DELETE CASCADE)"
    ))
    conn.execute(text("INSERT INTO audit_templates (id) VALUES (1)"))
    conn.execute(text(
        "INSERT INTO " + TABLE + " (tenant_id, template_id, characteristic_key, created_at)"
        " VALUES (1, 1, 'Compressor', '2026-09-01 09:00:00')"
    ))


def run(direction):
    with engine.begin() as conn:
        with Operations.context(MigrationContext.configure(conn)):
            getattr(revision, direction)()


def shape():
    inspector = inspect(engine)
    return {
        "columns": {c["name"]: bool(c["nullable"]) for c in inspector.get_columns(TABLE)},
        "uniques": {u["name"]: list(u["column_names"]) for u in inspector.get_unique_constraints(TABLE)},
    }


run("upgrade")
after_upgrade = shape()
with engine.begin() as conn:
    rows = [list(row) for row in conn.execute(text("SELECT mode, interval_days FROM " + TABLE)).all()]

run("upgrade")  # a second run must be a no-op, not a duplicate constraint
after_rerun = shape()

run("downgrade")
after_downgrade = shape()

run("upgrade")
after_reapply = shape()

print(json.dumps({
    "after_upgrade": after_upgrade,
    "rows": rows,
    "after_rerun": after_rerun,
    "after_downgrade": after_downgrade,
    "after_reapply": after_reapply,
}))
"""


@pytest.fixture(scope="module")
def migration_shape(tmp_path_factory) -> dict:
    workdir = tmp_path_factory.mktemp("cb-ui2-migration")
    completed = subprocess.run(
        [sys.executable, "-c", _MIGRATION_RUNNER, str(REPO_ROOT)],
        cwd=str(workdir),
        capture_output=True,
        text=True,
        timeout=180,
    )
    if completed.returncode != 0:
        pytest.fail(f"migration probe failed:\nstdout={completed.stdout}\nstderr={completed.stderr}")
    return json.loads(completed.stdout)


def test_the_migration_backfills_existing_binds_as_field(migration_shape):
    """A CB-PR4 row predates the split; it was a field assessment, not a null."""
    assert migration_shape["after_upgrade"]["columns"]["mode"] is False  # NOT NULL
    assert migration_shape["after_upgrade"]["columns"]["interval_days"] is True
    assert migration_shape["rows"] == [["field", None]]


def test_the_migration_swaps_the_characteristic_constraint_for_a_mode_aware_one(migration_shape):
    uniques = migration_shape["after_upgrade"]["uniques"]
    assert uniques["uq_competence_assessment_binds_characteristic_mode"] == [
        "tenant_id",
        "characteristic_key",
        "mode",
    ]
    assert "uq_competence_assessment_binds_characteristic" not in uniques
    # The template side of the 1:1 is untouched.
    assert uniques["uq_competence_assessment_binds_template"] == ["tenant_id", "template_id"]


def test_the_migration_is_re_runnable(migration_shape):
    assert migration_shape["after_rerun"] == migration_shape["after_upgrade"]


def test_the_migration_is_reversible(migration_shape):
    after = migration_shape["after_downgrade"]
    assert "mode" not in after["columns"]
    assert "interval_days" not in after["columns"]
    assert "uq_competence_assessment_binds_characteristic" in after["uniques"]
    assert migration_shape["after_reapply"] == migration_shape["after_upgrade"]
