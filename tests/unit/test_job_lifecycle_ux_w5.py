"""JL-UX-W5: portal nested-cycle read + cycle baseline snapshot/diff.

Two claims worth pinning:

1. **Baselines are snapshots, not forks.** Creating one freezes axes + nest
   edges at time T; live tables remain the source of truth for edit; diff is
   structured added/removed/changed keyed by JL codes.
2. **Portal is read-only.** The portal job-lifecycle router mounts GET routes
   under ``job:read`` only — no PATCH/POST author surface — and the nested
   cycle DTO always reports ``read_only`` / ``can_author=False``.
"""

from __future__ import annotations

import ast
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.api.routes import portal_job_lifecycle as portal_routes
from src.api.schemas.job_lifecycle import (
    JobTypeBaselineDiffResponse,
    JobTypeBaselineResponse,
    PortalNestedCycleResponse,
)
from src.domain.authz.extraction import REQUIRED_PERMISSION_ATTR
from src.domain.models.job_lifecycle import (
    JobCell,
    JobCellDocument,
    JobCellLink,
    JobLane,
    JobStep,
    JobType,
    JobTypeBaseline,
)
from src.domain.services.job_lifecycle_baseline import (
    SNAPSHOT_VERSION,
    build_snapshot,
    diff_snapshots,
    viewing_baseline_banner,
)
from src.domain.services.job_lifecycle_service import JobLifecycleService
from src.infrastructure.middleware.tenant_context import RLS_TABLES

TENANT_ID = 1
OTHER_TENANT_ID = 2
NOW = datetime(2026, 8, 8, 12, 0, tzinfo=timezone.utc)

REPO_ROOT = Path(__file__).resolve().parents[2]
ALEMBIC_VERSIONS = REPO_ROOT / "alembic/versions"
MIGRATION_PATH = ALEMBIC_VERSIONS / "20261023_job_type_baselines.py"
MIGRATION_SOURCE = MIGRATION_PATH.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Migration wiring — serial, one revision after W4
# ---------------------------------------------------------------------------


def _module_constant(name: str):
    tree = ast.parse(MIGRATION_SOURCE)
    for node in tree.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Name) and target.id == name:
                    return ast.literal_eval(node.value)
    raise AssertionError(f"{name} not found in {MIGRATION_PATH.name}")


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
    "on_top_of_w4": sorted(
        rev.revision
        for rev in script.walk_revisions()
        if "20261022_job_cell_req_ev" in (rev._all_down_revisions or ())
    ),
}))
"""


def _alembic_revision_map(tmp_path: Path) -> dict:
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


def test_migration_chains_serially_from_the_w4_head():
    assert _module_constant("revision") == "20261023_job_type_baselines"
    assert _module_constant("down_revision") == "20261022_job_cell_req_ev"


def test_the_w5_revision_is_the_only_head(tmp_path):
    heads = _alembic_revision_map(tmp_path)["heads"]
    assert heads == [
        "20261112_standards_w5_axes"
    ], f"expected the Int-W5 requirement-axes revision as the single head, found {heads}"


def test_only_the_w5_revision_sits_on_the_w4_head(tmp_path):
    assert _alembic_revision_map(tmp_path)["on_top_of_w4"] == ["20261023_job_type_baselines"]


def test_baseline_table_is_registered_for_rls():
    assert "job_type_baselines" in RLS_TABLES
    assert "job_type_baselines" in _module_constant("ADOPT_TABLES")


def test_baseline_model_stores_a_snapshot_not_a_live_fork_pointer():
    columns = {c.name for c in JobTypeBaseline.__table__.columns}
    assert "snapshot" in columns
    assert "job_type_id" in columns
    for forbidden in ("forked_job_type_id", "live_revision_id", "is_fork"):
        assert forbidden not in columns


# ---------------------------------------------------------------------------
# Pure snapshot / diff
# ---------------------------------------------------------------------------


def _sample_snapshot(**overrides: Any) -> dict[str, Any]:
    base = build_snapshot(
        job_type={"code": "ops", "name": "Operational", "description": None, "is_active": True, "sort_order": 0},
        lanes=[{"code": "build", "name": "Build", "description": None, "sort_order": 0, "is_active": True}],
        steps=[
            {
                "code": "plan",
                "name": "Plan",
                "description": None,
                "sort_order": 0,
                "is_active": True,
                "pdca_phase": "plan",
            }
        ],
        cells=[{"lane_code": "build", "step_code": "plan", "requires_evidence": False}],
        nest_edges=[
            {
                "lane_code": "build",
                "step_code": "plan",
                "target_job_type_code": "eng",
                "label": "Engineer cycle",
            }
        ],
    )
    base.update(overrides)
    return base


def test_build_snapshot_records_version_and_codes():
    snap = _sample_snapshot()
    assert snap["version"] == SNAPSHOT_VERSION
    assert snap["job_type"]["code"] == "ops"
    assert snap["nest_edges"][0]["target_job_type_code"] == "eng"


def test_diff_reports_added_removed_and_changed():
    baseline = _sample_snapshot()
    live = build_snapshot(
        job_type={"code": "ops", "name": "Operational v2", "description": None, "is_active": True, "sort_order": 0},
        lanes=[
            {"code": "build", "name": "Build", "description": None, "sort_order": 0, "is_active": True},
            {"code": "verify", "name": "Verify", "description": None, "sort_order": 1, "is_active": True},
        ],
        steps=[],
        cells=[{"lane_code": "build", "step_code": "plan", "requires_evidence": True}],
        nest_edges=[],
    )
    diff = diff_snapshots(baseline, live)
    assert diff["has_changes"] is True
    assert diff["summary"]["job_type"]["changed"] == 1
    assert diff["summary"]["lanes"]["added"] == 1
    assert diff["summary"]["steps"]["removed"] == 1
    assert diff["summary"]["cells"]["changed"] == 1
    assert diff["summary"]["nest_edges"]["removed"] == 1


def test_identical_snapshots_have_no_changes():
    snap = _sample_snapshot()
    diff = diff_snapshots(snap, snap)
    assert diff["has_changes"] is False
    assert all(
        diff["summary"][section]["added"] == 0
        and diff["summary"][section]["removed"] == 0
        and diff["summary"][section]["changed"] == 0
        for section in ("job_type", "lanes", "steps", "cells", "nest_edges")
    )


def test_viewing_banner_names_the_baseline_and_keeps_edit_on_live():
    banner = viewing_baseline_banner(baseline_id=12, label="Approved Aug")
    assert "#12" in banner
    assert "Approved Aug" in banner
    assert "live tip" in banner.lower()


# ---------------------------------------------------------------------------
# Service tests
# ---------------------------------------------------------------------------


@pytest.fixture
async def session_factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        for model in (JobType, JobLane, JobStep, JobCell, JobCellDocument, JobCellLink, JobTypeBaseline):
            await conn.run_sync(model.__table__.create)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    yield factory
    await engine.dispose()


async def _pack(db: AsyncSession, *, code: str, name: str, lanes=("build",), steps=("plan",)):
    service = JobLifecycleService(db)
    job_type = await service.create_job_type(tenant_id=TENANT_ID, code=code, name=name)
    lane_rows = [
        await service.create_lane(
            tenant_id=TENANT_ID, job_type_id=job_type.id, code=f"{code}_{lane}", name=lane, sort_order=i
        )
        for i, lane in enumerate(lanes)
    ]
    step_rows = [
        await service.create_step(
            tenant_id=TENANT_ID, job_type_id=job_type.id, code=f"{code}_{step}", name=step, sort_order=i
        )
        for i, step in enumerate(steps)
    ]
    return job_type, lane_rows, step_rows


@pytest.mark.asyncio
async def test_create_baseline_freezes_axes_and_nest_edges(session_factory):
    async with session_factory() as db:
        service = JobLifecycleService(db)
        parent, lanes, steps = await _pack(db, code="ops", name="Operational")
        child, _, _ = await _pack(db, code="eng", name="Engineer")
        await service.create_cell_link(
            tenant_id=TENANT_ID,
            job_type_id=parent.id,
            lane_id=lanes[0].id,
            step_id=steps[0].id,
            kind="job_cycle",
            label="Engineer nest",
            target_job_type_id=child.id,
        )
        row = await service.create_baseline(
            tenant_id=TENANT_ID,
            job_type_id=parent.id,
            label="Approved",
            created_by_id=7,
        )
        assert row.label == "Approved"
        assert row.created_by_id == 7
        assert row.snapshot["job_type"]["code"] == "ops"
        assert row.snapshot["lanes"][0]["code"] == "ops_build"
        assert row.snapshot["nest_edges"][0]["target_job_type_code"] == "eng"


@pytest.mark.asyncio
async def test_diff_baseline_sees_live_changes_without_mutating_the_snapshot(session_factory):
    async with session_factory() as db:
        service = JobLifecycleService(db)
        job_type, lanes, _ = await _pack(db, code="ops", name="Operational", lanes=("build",))
        baseline = await service.create_baseline(tenant_id=TENANT_ID, job_type_id=job_type.id, label="T0")
        await service.create_lane(
            tenant_id=TENANT_ID, job_type_id=job_type.id, code="ops_verify", name="Verify", sort_order=1
        )
        await service.update_lane(tenant_id=TENANT_ID, lane_id=lanes[0].id, name="Build renamed")

        payload = await service.diff_baseline(tenant_id=TENANT_ID, job_type_id=job_type.id, baseline_id=baseline.id)
        assert payload["has_changes"] is True
        assert payload["edit_targets_live"] is True
        assert payload["viewing_baseline"] is True
        assert "live tip" in payload["banner"].lower()
        assert payload["summary"]["lanes"]["added"] == 1
        assert payload["summary"]["lanes"]["changed"] == 1

        # Snapshot itself is unchanged — live is SoT for edit.
        refreshed = await service.get_baseline(tenant_id=TENANT_ID, job_type_id=job_type.id, baseline_id=baseline.id)
        assert refreshed.snapshot["lanes"][0]["name"] == "build"
        assert len(refreshed.snapshot["lanes"]) == 1


@pytest.mark.asyncio
async def test_list_baselines_is_newest_first(session_factory):
    async with session_factory() as db:
        service = JobLifecycleService(db)
        job_type, _, _ = await _pack(db, code="ops", name="Operational")
        first = await service.create_baseline(tenant_id=TENANT_ID, job_type_id=job_type.id, label="A")
        second = await service.create_baseline(tenant_id=TENANT_ID, job_type_id=job_type.id, label="B")
        items = await service.list_baselines(tenant_id=TENANT_ID, job_type_id=job_type.id)
        assert [row.id for row in items] == [second.id, first.id]


@pytest.mark.asyncio
async def test_baseline_of_another_tenant_is_a_404(session_factory):
    async with session_factory() as db:
        service = JobLifecycleService(db)
        job_type, _, _ = await _pack(db, code="ops", name="Operational")
        baseline = await service.create_baseline(tenant_id=TENANT_ID, job_type_id=job_type.id)
        with pytest.raises(HTTPException) as exc_info:
            await service.get_baseline(tenant_id=OTHER_TENANT_ID, job_type_id=job_type.id, baseline_id=baseline.id)
        assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_portal_nested_cycle_is_read_only_and_nest_aware(session_factory):
    async with session_factory() as db:
        service = JobLifecycleService(db)
        parent, lanes, steps = await _pack(db, code="ops", name="Operational")
        child, _, _ = await _pack(db, code="eng", name="Engineer")
        await service.create_cell_link(
            tenant_id=TENANT_ID,
            job_type_id=parent.id,
            lane_id=lanes[0].id,
            step_id=steps[0].id,
            kind="job_cycle",
            label="Engineer nest",
            target_job_type_id=child.id,
        )
        # Also plant an app link — portal must strip non-nest kinds.
        await service.create_cell_link(
            tenant_id=TENANT_ID,
            job_type_id=parent.id,
            lane_id=lanes[0].id,
            step_id=steps[0].id,
            kind="external",
            label="Handbook",
            external_url="https://example.test/handbook",
        )

        payload = await service.portal_nested_cycle(
            tenant_id=TENANT_ID,
            job_type_id=parent.id,
            include_links=True,
            include_cycle_graph=True,
        )
        assert payload["read_only"] is True
        assert payload["can_author"] is False
        assert payload["job_type"].id == parent.id
        assert len(payload["cells"]) == 1
        nest_links = payload["cells"][0]["nest_links"]
        assert len(nest_links) == 1
        assert nest_links[0]["kind"] == "job_cycle"
        assert nest_links[0]["target_job_type_id"] == child.id
        assert payload["cycle_graph"] is not None
        assert payload["cycle_graph"]["root_job_type_id"] == parent.id


def test_baseline_response_schema_marks_edit_targets_live():
    model = JobTypeBaselineResponse(
        id=1,
        tenant_id=1,
        job_type_id=2,
        created_at=NOW,
        updated_at=NOW,
        snapshot={"version": 1},
        viewing_baseline=True,
        banner="Viewing baseline #1. Edit always targets the live tip, not this baseline.",
    )
    assert model.is_snapshot is True
    assert model.edit_targets_live is True
    assert model.viewing_baseline is True


def test_diff_response_schema_round_trips():
    model = JobTypeBaselineDiffResponse(
        baseline_id=1,
        job_type_id=2,
        banner="x",
        baseline_created_at=NOW,
        has_changes=False,
        summary={"lanes": {"added": 0, "removed": 0, "changed": 0}},
        sections={},
    )
    assert model.edit_targets_live is True
    assert model.viewing_baseline is True


def test_portal_nested_cycle_schema_forbids_author_chrome():
    model = PortalNestedCycleResponse(
        job_type={
            "id": 1,
            "tenant_id": 1,
            "code": "ops",
            "name": "Operational",
            "sort_order": 0,
            "is_active": True,
            "created_at": NOW,
            "updated_at": NOW,
        },
    )
    assert model.read_only is True
    assert model.can_author is False


# ---------------------------------------------------------------------------
# Portal router — read ok, write denied by absence
# ---------------------------------------------------------------------------


def _iter_api_routes(router):
    """Flatten nested ``include_router`` mounts.

    FastAPI >=0.140 keeps an ``_IncludedRouter`` wrapper whose child routes live
    on ``original_router`` (not ``.routes``). Older FastAPI flattens APIRoutes
    onto the parent, so both shapes must resolve to the same GET handlers.
    """
    for route in getattr(router, "routes", []) or []:
        nested_router = getattr(route, "original_router", None)
        if nested_router is not None:
            yield from _iter_api_routes(nested_router)
            continue
        nested = getattr(route, "routes", None)
        if nested is not None:
            yield from _iter_api_routes(route)
            continue
        yield route


def _route_permission(route) -> str | None:
    dependant = getattr(route, "dependant", None)
    if dependant is None:
        return None
    for dep in dependant.dependencies:
        call = getattr(dep, "call", None)
        if call is None:
            continue
        required = getattr(call, REQUIRED_PERMISSION_ATTR, None)
        if required:
            return required
    return None


def test_portal_router_exposes_only_get_routes_under_job_read():
    """Write denied on the portal path: no POST/PATCH/PUT/DELETE is mounted."""
    methods: set[str] = set()
    permissions: set[str | None] = set()
    for route in _iter_api_routes(portal_routes.router):
        path_methods = getattr(route, "methods", None) or set()
        methods |= {m.upper() for m in path_methods}
        permissions.add(_route_permission(route))
    assert methods == {"GET"}
    assert permissions == {"job:read"}
    assert "job:author" not in permissions


def test_portal_router_has_no_write_path_templates():
    paths = [getattr(route, "path", "") or "" for route in _iter_api_routes(portal_routes.router)]
    assert any("nested-cycle" in path for path in paths)
    for path in paths:
        assert "baselines" not in path  # baselines are composer/author surface
        assert not path.endswith("/documents")
