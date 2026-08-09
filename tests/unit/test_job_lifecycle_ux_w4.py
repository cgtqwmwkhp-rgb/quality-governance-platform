"""JL-UX-W4: interaction map, audit trail, mandatory evidence, clone, concurrency.

Five claims worth pinning, one per scope item:

1. **The map is a view.** Every edge is one ``job_cycle`` cell link. Nothing
   about the graph is stored, two cells nesting the same pack draw two edges,
   and the walk is bounded so a wide pack cannot cost an unbounded number of
   queries.
2. **Map and trail share one edge model.** A ``nests`` edge means the same
   thing in both, so the two views cannot drift into two shapes.
3. **Readiness is derived, never stored.** ``requires_evidence`` is the only
   new column; whether the requirement is *met* is classified on read, and with
   assure on a withdrawn document stops counting as evidence.
4. **Clone copies axes only.** No cell, no link, no document — a copied
   reference would assert evidence the new pack has not earned.
5. **A stale edit is refused, not silently applied.** ``If-Match`` is opt-in,
   so a client that does not send it is unaffected; one that does gets 409
   rather than losing someone else's rename.
"""

from __future__ import annotations

import ast
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.api.schemas.job_lifecycle import (
    JobAuditTrailResponse,
    JobCellResponse,
    JobCycleGraphResponse,
    JobEvidenceReadinessResponse,
    JobTypeCloneResponse,
)
from src.domain.models.document import Document
from src.domain.models.document_control import ControlledDocument
from src.domain.models.job_lifecycle import JobCell, JobCellDocument, JobCellLink, JobLane, JobStep, JobType
from src.domain.services.job_lifecycle_concurrency import if_match_matches, job_lifecycle_etag, parse_if_match
from src.domain.services.job_lifecycle_graph import (
    CELL_READINESS_STATES,
    DEFAULT_AUDIT_TRAIL_PATHS,
    DEFAULT_CYCLE_GRAPH_DEPTH,
    MAX_AUDIT_TRAIL_PATHS,
    MAX_CYCLE_GRAPH_DEPTH,
    JobGraphBuilder,
    JobGraphEdge,
    JobGraphNode,
    clamp_audit_trail_limit,
    clamp_cycle_graph_depth,
    classify_cell_readiness,
    edge_key,
    node_key,
    select_trail_cells,
    summarise_readiness,
)
from src.domain.services.job_lifecycle_service import JobLifecycleService

TENANT_ID = 1
OTHER_TENANT_ID = 2
NOW = datetime(2026, 8, 8, 12, 0, tzinfo=timezone.utc)

REPO_ROOT = Path(__file__).resolve().parents[2]
ALEMBIC_VERSIONS = REPO_ROOT / "alembic/versions"
MIGRATION_PATH = ALEMBIC_VERSIONS / "20261022_job_cell_requires_evidence.py"
MIGRATION_SOURCE = MIGRATION_PATH.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Migration wiring — serial, one revision after the W2/W3 head
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
# alembic must be imported before the repository joins sys.path: the repo's own
# alembic/ directory would otherwise shadow the installed distribution.
from alembic.config import Config
from alembic.script import ScriptDirectory

repo = sys.argv[1]
sys.path.append(repo)
cfg = Config(repo + "/alembic.ini")
cfg.set_main_option("script_location", repo + "/alembic")
script = ScriptDirectory.from_config(cfg)
print(json.dumps({
    "heads": sorted(script.get_heads()),
    "on_top_of_w3": sorted(
        rev.revision
        for rev in script.walk_revisions()
        if "20261021_job_nest_pdca" in (rev._all_down_revisions or ())
    ),
    "on_top_of_w4": sorted(
        rev.revision
        for rev in script.walk_revisions()
        if "20261022_job_cell_req_ev" in (rev._all_down_revisions or ())
    ),
}))
"""


def _alembic_revision_map(tmp_path: Path) -> dict:
    """Ask Alembic itself, rather than re-implementing its parser in a regex."""
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


def test_migration_chains_serially_from_the_w3_head():
    assert _module_constant("revision") == "20261022_job_cell_req_ev"
    assert _module_constant("down_revision") == "20261021_job_nest_pdca"


def test_the_w4_revision_is_the_only_revision_on_the_w3_head(tmp_path):
    """Serial wave: W4 alone sits on the W2/W3 head (W5 sits on W4, not W3)."""
    mapping = _alembic_revision_map(tmp_path)
    assert mapping["on_top_of_w3"] == ["20261022_job_cell_req_ev"]
    # Tip head advances with later migrations; W4 remains the only successor of W3.
    assert mapping["heads"] == [
        "20261026_lib_wc1_control_holds"
    ], f"expected WC-1 as the single head, found {mapping['heads']}"
    assert mapping["on_top_of_w4"] == ["20261023_job_type_baselines"]


def test_only_the_w4_revision_sits_on_the_w3_head(tmp_path):
    """Kept name: W4 is still the sole direct child of the W2/W3 head."""
    assert _alembic_revision_map(tmp_path)["on_top_of_w3"] == ["20261022_job_cell_req_ev"]


def test_the_cell_table_gains_the_requirement_and_nothing_derived():
    """The flag is authored state; readiness is not, so it must not be a column."""
    columns = {c.name for c in JobCell.__table__.columns}
    assert "requires_evidence" in columns
    for derived in ("readiness", "readiness_state", "evidence_count", "is_ready", "last_checked_at"):
        assert derived not in columns, f"JobCell stores derived readiness in {derived}"


def test_requires_evidence_defaults_to_false_in_the_orm():
    """Marking every existing cell mandatory would invent a governance claim."""
    column = JobCell.__table__.columns["requires_evidence"]
    assert column.nullable is False
    assert "false" in str(column.server_default.arg).lower()


# ---------------------------------------------------------------------------
# Migration behaviour on a real (SQLite) schema
# ---------------------------------------------------------------------------

_RUNNER = r"""
import importlib.util, json, sys
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

job = json.loads(sys.argv[1])
spec = importlib.util.spec_from_file_location("_mig", job["migration"])
mig = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mig)

engine = sa.create_engine("sqlite:///" + job["db"])
with engine.begin() as conn:
    if job["create_table"]:
        conn.execute(sa.text(
            "CREATE TABLE job_cells (id INTEGER PRIMARY KEY, tenant_id INTEGER NOT NULL, "
            "job_type_id INTEGER NOT NULL, lane_id INTEGER NOT NULL, step_id INTEGER NOT NULL)"
        ))
    for stmt in job["seed"]:
        conn.execute(sa.text(stmt))

result = {"error": None, "error_type": None, "steps_run": []}
try:
    for step in job["steps"]:
        with engine.begin() as conn:
            with Operations.context(MigrationContext.configure(conn)):
                getattr(mig, step)()
        result["steps_run"].append(step)
except Exception as exc:
    result["error"] = str(exc)
    result["error_type"] = type(exc).__name__

inspector = sa.inspect(engine)
tables = set(inspector.get_table_names())
result["tables"] = sorted(tables)
result["columns"] = (
    [c["name"] for c in inspector.get_columns("job_cells")] if "job_cells" in tables else []
)
result["indexes"] = (
    sorted(i["name"] for i in inspector.get_indexes("job_cells")) if "job_cells" in tables else []
)
result["rows"] = []
if "job_cells" in tables and job["read_rows"]:
    with engine.connect() as conn:
        result["rows"] = [list(r) for r in conn.execute(sa.text(job["read_rows"])).all()]
print(json.dumps(result))
"""


def _run_migration(
    tmp_path: Path,
    *,
    steps: list[str],
    create_table: bool = True,
    seed=None,
    read_rows="",
    name: str = "w4",
):
    """Drive the revision in a subprocess against a fresh database.

    Outside the repository root, because the repo's own ``alembic/`` directory
    shadows the installed alembic distribution when it is on ``sys.path``.
    ``name`` keeps two runs in one test from colliding on the same file.
    """
    tmp_path.mkdir(parents=True, exist_ok=True)
    job = {
        "migration": str(MIGRATION_PATH),
        "db": str(tmp_path / f"{name}.db"),
        "create_table": create_table,
        "seed": seed or [],
        "steps": steps,
        "read_rows": read_rows,
    }
    completed = subprocess.run(
        [sys.executable, "-c", _RUNNER, json.dumps(job)],
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        timeout=120,
    )
    if completed.returncode != 0:
        pytest.fail(f"migration runner failed:\nstdout={completed.stdout}\nstderr={completed.stderr}")
    return json.loads(completed.stdout)


def test_upgrade_adds_the_column_and_its_index(tmp_path):
    result = _run_migration(tmp_path, steps=["upgrade"])
    assert result["error"] is None, result["error"]
    assert "requires_evidence" in result["columns"]
    assert "ix_job_cells_tenant_requires_evidence" in result["indexes"]


def test_existing_cells_come_back_not_required(tmp_path):
    """Backfilling ``true`` would silently make every legacy cell a finding."""
    result = _run_migration(
        tmp_path,
        steps=["upgrade"],
        seed=["INSERT INTO job_cells (id, tenant_id, job_type_id, lane_id, step_id) VALUES (1, 1, 1, 1, 1)"],
        read_rows="SELECT requires_evidence FROM job_cells",
    )
    assert result["error"] is None, result["error"]
    assert result["rows"] == [[0]]


def test_upgrade_is_idempotent(tmp_path):
    result = _run_migration(tmp_path, steps=["upgrade", "upgrade"])
    assert result["error"] is None, result["error"]
    assert result["steps_run"] == ["upgrade", "upgrade"]


def test_downgrade_removes_the_column_and_upgrade_reapplies(tmp_path):
    result = _run_migration(tmp_path, steps=["upgrade", "downgrade"])
    assert result["error"] is None, result["error"]
    assert "requires_evidence" not in result["columns"]
    again = _run_migration(tmp_path, steps=["upgrade", "downgrade", "upgrade"], name="reapply")
    assert again["error"] is None, again["error"]
    assert "requires_evidence" in again["columns"]


def test_downgrade_preserves_the_cells_themselves(tmp_path):
    result = _run_migration(
        tmp_path,
        steps=["upgrade", "downgrade"],
        seed=["INSERT INTO job_cells (id, tenant_id, job_type_id, lane_id, step_id) VALUES (5, 1, 1, 1, 1)"],
        read_rows="SELECT id FROM job_cells",
    )
    assert result["rows"] == [[5]]


def test_a_missing_table_is_skipped_not_fatal(tmp_path):
    result = _run_migration(tmp_path, steps=["upgrade"], create_table=False)
    assert result["error"] is None, result["error"]
    assert "job_cells" not in result["tables"]


# ---------------------------------------------------------------------------
# Readiness classification (pure)
# ---------------------------------------------------------------------------


def test_a_cell_that_requires_nothing_is_not_a_gap():
    verdict = classify_cell_readiness(requires_evidence=False, document_ids=[])
    assert verdict.state == "not_required"
    assert verdict.is_ready is True


def test_a_mandatory_cell_with_no_evidence_is_a_gap():
    verdict = classify_cell_readiness(requires_evidence=True, document_ids=[])
    assert verdict.state == "missing_evidence"
    assert verdict.reason == "no_evidence_attached"
    assert verdict.is_ready is False


def test_without_assure_readiness_is_presence_only():
    """Claiming more than a presence check would be claiming unread data."""
    verdict = classify_cell_readiness(
        requires_evidence=True,
        document_ids=[1],
        obsolete_ids=[1],
        assure=False,
    )
    assert verdict.state == "ready"
    assert verdict.reason == "evidence_attached"
    assert verdict.obsolete_count == 0


def test_with_assure_a_withdrawn_document_is_not_evidence():
    verdict = classify_cell_readiness(
        requires_evidence=True,
        document_ids=[1, 2],
        obsolete_ids=[2],
        assure=True,
    )
    assert verdict.state == "obsolete_evidence"
    assert verdict.obsolete_count == 1
    assert verdict.is_ready is False


def test_with_assure_unreadable_evidence_is_unknown_not_ready():
    verdict = classify_cell_readiness(
        requires_evidence=True,
        document_ids=[9],
        unresolved_ids=[9],
        assure=True,
    )
    assert verdict.state == "unknown"
    assert verdict.reason == "evidence_status_unreadable"
    assert verdict.is_ready is False


def test_obsolete_outranks_unreadable():
    verdict = classify_cell_readiness(
        requires_evidence=True,
        document_ids=[1, 2],
        obsolete_ids=[1],
        unresolved_ids=[2],
        assure=True,
    )
    assert verdict.state == "obsolete_evidence"


def test_status_of_documents_on_other_cells_does_not_leak_in():
    """The sets are pack-wide; a verdict must only reflect this cell's refs."""
    verdict = classify_cell_readiness(
        requires_evidence=True,
        document_ids=[1],
        obsolete_ids=[99],
        unresolved_ids=[98],
        assure=True,
    )
    assert verdict.state == "ready"
    assert verdict.reason == "evidence_current"


@pytest.mark.parametrize("state", CELL_READINESS_STATES)
def test_every_declared_state_is_reachable(state):
    reachable = {
        classify_cell_readiness(requires_evidence=False, document_ids=[]).state,
        classify_cell_readiness(requires_evidence=True, document_ids=[]).state,
        classify_cell_readiness(requires_evidence=True, document_ids=[1]).state,
        classify_cell_readiness(requires_evidence=True, document_ids=[1], obsolete_ids=[1], assure=True).state,
        classify_cell_readiness(requires_evidence=True, document_ids=[1], unresolved_ids=[1], assure=True).state,
    }
    assert state in reachable


def test_summary_counts_states_and_excludes_optional_cells_from_the_denominator():
    verdicts = [
        classify_cell_readiness(requires_evidence=True, document_ids=[1]),
        classify_cell_readiness(requires_evidence=True, document_ids=[]),
        classify_cell_readiness(requires_evidence=False, document_ids=[]),
    ]
    summary = summarise_readiness(verdicts)
    assert summary["ready"] == 1
    assert summary["missing_evidence"] == 1
    assert summary["not_required"] == 1
    assert summary["required"] == 2


def test_summary_of_nothing_is_zeroes_not_an_empty_dict():
    summary = summarise_readiness([])
    assert summary["required"] == 0
    assert all(summary[state] == 0 for state in CELL_READINESS_STATES)


# ---------------------------------------------------------------------------
# Graph model (pure) — shared by map and trail
# ---------------------------------------------------------------------------


def test_node_keys_are_namespaced_by_kind():
    """Ids collide across tables; a bare id would merge a cell with a document."""
    assert node_key("cell", 1) != node_key("document", 1)


def test_two_cells_nesting_the_same_pack_are_two_edges():
    """Delete one link and one line should go — so they cannot share a key."""
    a = edge_key("nests", "job_type:1", "job_type:2", via=10)
    b = edge_key("nests", "job_type:1", "job_type:2", via=11)
    assert a != b


def test_the_builder_keeps_the_first_label_a_node_was_given():
    builder = JobGraphBuilder()
    builder.add_node(JobGraphNode(key="job_type:1", kind="job_type", ref_id=1, label="First"))
    builder.add_node(JobGraphNode(key="job_type:1", kind="job_type", ref_id=1, label="Second"))
    assert [n.label for n in builder.nodes] == ["First"]


def test_the_builder_dedupes_edges_by_key():
    builder = JobGraphBuilder()
    for _ in range(2):
        builder.add_edge(JobGraphEdge(key="e1", kind="nests", source="job_type:1", target="job_type:2", label="x"))
    assert len(builder.edges) == 1


def test_builder_serialises_to_the_wire_shape():
    builder = JobGraphBuilder()
    builder.add_node(JobGraphNode(key="job_type:1", kind="job_type", ref_id=1, label="Pack"))
    builder.add_edge(JobGraphEdge(key="e", kind="contains", source="job_type:1", target="cell:2", label="lane × step"))
    payload = builder.as_dict()
    assert payload["nodes"][0]["kind"] == "job_type"
    assert payload["edges"][0]["cell_id"] is None


@pytest.mark.parametrize(
    ("given", "expected"),
    [(None, DEFAULT_CYCLE_GRAPH_DEPTH), (0, 1), (-4, 1), (3, 3), (99, MAX_CYCLE_GRAPH_DEPTH)],
)
def test_depth_is_clamped_into_range(given, expected):
    assert clamp_cycle_graph_depth(given) == expected


@pytest.mark.parametrize(
    ("given", "expected"),
    [(None, DEFAULT_AUDIT_TRAIL_PATHS), (0, 1), (7, 7), (1000, MAX_AUDIT_TRAIL_PATHS)],
)
def test_trail_limit_is_clamped_into_range(given, expected):
    assert clamp_audit_trail_limit(given) == expected


def _candidate(cell_id, *, requires_evidence=False, has_content=False):
    return {"cell_id": cell_id, "requires_evidence": requires_evidence, "has_content": has_content}


def test_an_empty_optional_cell_is_not_a_path():
    selected, total = select_trail_cells([_candidate(1)], limit=10)
    assert selected == []
    assert total == 0


def test_mandatory_cells_are_walked_before_optional_ones():
    """Truncation must not drop the cells where empty is a finding."""
    candidates = [_candidate(1, has_content=True), _candidate(2, requires_evidence=True)]
    selected, _ = select_trail_cells(candidates, limit=10)
    assert [c["cell_id"] for c in selected] == [2, 1]


def test_an_empty_mandatory_cell_is_still_a_path():
    selected, total = select_trail_cells([_candidate(3, requires_evidence=True)], limit=10)
    assert [c["cell_id"] for c in selected] == [3]
    assert total == 1


def test_pack_order_is_kept_within_each_group():
    candidates = [
        _candidate(1, requires_evidence=True),
        _candidate(2, has_content=True),
        _candidate(3, requires_evidence=True),
        _candidate(4, has_content=True),
    ]
    selected, _ = select_trail_cells(candidates, limit=10)
    assert [c["cell_id"] for c in selected] == [1, 3, 2, 4]


def test_the_candidate_total_is_reported_even_when_the_sample_is_cut():
    candidates = [_candidate(i, has_content=True) for i in range(1, 6)]
    selected, total = select_trail_cells(candidates, limit=2)
    assert len(selected) == 2
    assert total == 5


# ---------------------------------------------------------------------------
# Concurrency token (pure)
# ---------------------------------------------------------------------------


def test_no_if_match_header_is_not_a_precondition():
    """Opt-in: clients that never heard of the header must keep working."""
    assert if_match_matches(if_match=None, updated_at=NOW) is True


def test_the_wildcard_only_asks_that_the_row_exist():
    assert if_match_matches(if_match="*", updated_at=NOW) is True


@pytest.mark.parametrize(
    "raw",
    [
        "2026-08-08T12:00:00+00:00",
        '"2026-08-08T12:00:00+00:00"',
        'W/"2026-08-08T12:00:00+00:00"',
        "2026-08-08T12:00:00Z",
        "  2026-08-08T12:00:00+00:00  ",
    ],
)
def test_every_shape_a_client_might_echo_back_parses(raw):
    assert parse_if_match(raw) == NOW


def test_a_stale_token_does_not_match():
    assert if_match_matches(if_match=job_lifecycle_etag(NOW - timedelta(seconds=1)), updated_at=NOW) is False


def test_a_naive_stored_timestamp_is_compared_as_utc():
    """SQLite hands back naive datetimes; a TypeError here would be a 500."""
    assert if_match_matches(if_match=job_lifecycle_etag(NOW), updated_at=NOW.replace(tzinfo=None)) is True


def test_an_offset_timestamp_is_normalised_before_comparing():
    other_zone = NOW.astimezone(timezone(timedelta(hours=5)))
    assert if_match_matches(if_match=other_zone.isoformat(), updated_at=NOW) is True


def test_a_row_with_no_timestamp_cannot_satisfy_a_timestamp_precondition():
    assert if_match_matches(if_match=job_lifecycle_etag(NOW), updated_at=None) is False


@pytest.mark.parametrize("raw", ["not-a-date", '""', "W/", '"   "'])
def test_a_malformed_precondition_raises_rather_than_passing(raw):
    with pytest.raises(ValueError):
        parse_if_match(raw)


def test_the_etag_round_trips_through_the_parser():
    assert parse_if_match(job_lifecycle_etag(NOW)) == NOW


def test_the_etag_of_nothing_is_nothing():
    assert job_lifecycle_etag(None) is None


# ---------------------------------------------------------------------------
# Service tests over a real (SQLite) schema
# ---------------------------------------------------------------------------


@pytest.fixture
async def session_factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        for model in (
            JobType,
            JobLane,
            JobStep,
            JobCell,
            JobCellDocument,
            JobCellLink,
            Document,
            ControlledDocument,
        ):
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


async def _document(db: AsyncSession, doc_id: int, *, title="Method statement", status="approved"):
    doc = Document(
        id=doc_id,
        tenant_id=TENANT_ID,
        title=title,
        reference_number=f"PEL-{doc_id}",
        status=status,
        file_name=f"{doc_id}.pdf",
        file_type="pdf",
        file_size=1024,
        file_path=f"/library/{doc_id}.pdf",
    )
    db.add(doc)
    await db.commit()
    return doc


# --- clone ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_clone_copies_lanes_and_steps(session_factory):
    async with session_factory() as db:
        service = JobLifecycleService(db)
        source, _, steps = await _pack(
            db, code="commissioning", name="Commissioning", lanes=("build", "verify"), steps=("plan", "do")
        )
        await service.update_step(tenant_id=TENANT_ID, step_id=steps[0].id, pdca_phase="plan")

        payload = await service.clone_job_type(
            tenant_id=TENANT_ID, source_job_type_id=source.id, code="commissioning_v2", name="Commissioning v2"
        )

        assert payload["cloned_lane_count"] == 2
        assert payload["cloned_step_count"] == 2
        clone_id = payload["job_type"].id
        cloned_lanes = await service.list_lanes(tenant_id=TENANT_ID, job_type_id=clone_id)
        cloned_steps = await service.list_steps(tenant_id=TENANT_ID, job_type_id=clone_id)
        assert [lane.name for lane in cloned_lanes] == ["build", "verify"]
        assert [step.pdca_phase for step in cloned_steps] == ["plan", None]


@pytest.mark.asyncio
async def test_clone_leaves_the_new_pack_with_no_cells_links_or_documents(session_factory):
    """The point of the feature: a template, not a copy of someone's evidence."""
    async with session_factory() as db:
        service = JobLifecycleService(db)
        source, lanes, steps = await _pack(db, code="src", name="Source")
        await _document(db, 41)
        await service.set_cell_documents(
            tenant_id=TENANT_ID,
            job_type_id=source.id,
            lane_id=lanes[0].id,
            step_id=steps[0].id,
            library_document_ids=[41],
        )
        await service.create_cell_link(
            tenant_id=TENANT_ID,
            job_type_id=source.id,
            lane_id=lanes[0].id,
            step_id=steps[0].id,
            kind="external",
            label="Spec",
            external_url="https://example.test/spec",
        )

        payload = await service.clone_job_type(
            tenant_id=TENANT_ID, source_job_type_id=source.id, code="dst", name="Destination"
        )
        clone_id = payload["job_type"].id

        assert payload["cloned_cell_count"] == 0
        assert payload["cloned_document_count"] == 0
        assert await service.list_cells(tenant_id=TENANT_ID, job_type_id=clone_id, include_links=True) == []
        # And the source keeps everything it had.
        source_cells = await service.list_cells(tenant_id=TENANT_ID, job_type_id=source.id, include_links=True)
        assert source_cells[0]["library_document_ids"] == [41]
        assert len(source_cells[0]["links"]) == 1


@pytest.mark.asyncio
async def test_clone_reuses_the_source_axis_codes(session_factory):
    """Codes are unique per job type, so the vocabulary travels with the pack."""
    async with session_factory() as db:
        service = JobLifecycleService(db)
        source, lanes, _ = await _pack(db, code="src", name="Source")
        payload = await service.clone_job_type(
            tenant_id=TENANT_ID, source_job_type_id=source.id, code="dst", name="Destination"
        )
        cloned = await service.list_lanes(tenant_id=TENANT_ID, job_type_id=payload["job_type"].id)
        assert [lane.code for lane in cloned] == [lanes[0].code]


@pytest.mark.asyncio
async def test_clone_refuses_a_code_already_in_use(session_factory):
    async with session_factory() as db:
        service = JobLifecycleService(db)
        source, _, _ = await _pack(db, code="src", name="Source")
        with pytest.raises(HTTPException) as exc_info:
            await service.clone_job_type(
                tenant_id=TENANT_ID, source_job_type_id=source.id, code="src", name="Duplicate"
            )
        assert exc_info.value.status_code == 409


@pytest.mark.asyncio
async def test_clone_of_a_pack_in_another_tenant_is_a_404(session_factory):
    async with session_factory() as db:
        service = JobLifecycleService(db)
        source, _, _ = await _pack(db, code="src", name="Source")
        with pytest.raises(HTTPException) as exc_info:
            await service.clone_job_type(
                tenant_id=OTHER_TENANT_ID, source_job_type_id=source.id, code="dst", name="Destination"
            )
        assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_clone_can_leave_retired_axes_behind_when_asked(session_factory):
    async with session_factory() as db:
        service = JobLifecycleService(db)
        source, lanes, _ = await _pack(db, code="src", name="Source", lanes=("build", "retired"))
        await service.update_lane(tenant_id=TENANT_ID, lane_id=lanes[1].id, is_active=False)

        payload = await service.clone_job_type(
            tenant_id=TENANT_ID,
            source_job_type_id=source.id,
            code="dst",
            name="Destination",
            include_inactive=False,
        )
        assert payload["cloned_lane_count"] == 1


@pytest.mark.asyncio
async def test_clone_inherits_the_source_description_unless_one_is_given(session_factory):
    async with session_factory() as db:
        service = JobLifecycleService(db)
        source, _, _ = await _pack(db, code="src", name="Source")
        await service.update_job_type(tenant_id=TENANT_ID, job_type_id=source.id, description="How we commission")
        inherited = await service.clone_job_type(
            tenant_id=TENANT_ID, source_job_type_id=source.id, code="dst1", name="A"
        )
        overridden = await service.clone_job_type(
            tenant_id=TENANT_ID, source_job_type_id=source.id, code="dst2", name="B", description="Fresh"
        )
        assert inherited["job_type"].description == "How we commission"
        assert overridden["job_type"].description == "Fresh"


def test_the_clone_response_states_that_nothing_deep_was_copied():
    model = JobTypeCloneResponse(
        job_type={
            "id": 1,
            "tenant_id": 1,
            "code": "c",
            "name": "n",
            "sort_order": 0,
            "is_active": True,
            "created_at": NOW,
            "updated_at": NOW,
        },
        source_job_type_id=2,
        cloned_lane_count=3,
        cloned_step_count=4,
    )
    assert model.cloned_cell_count == 0
    assert model.cloned_document_count == 0


# --- concurrency over the service ------------------------------------------


@pytest.mark.asyncio
async def test_a_matching_if_match_lets_the_rename_through(session_factory):
    async with session_factory() as db:
        service = JobLifecycleService(db)
        job_type, _, _ = await _pack(db, code="src", name="Source")
        token = job_lifecycle_etag(job_type.updated_at)
        updated = await service.update_job_type(
            tenant_id=TENANT_ID, job_type_id=job_type.id, name="Renamed", if_match=token
        )
        assert updated.name == "Renamed"


@pytest.mark.asyncio
async def test_a_stale_if_match_is_refused_with_409_and_writes_nothing(session_factory):
    async with session_factory() as db:
        service = JobLifecycleService(db)
        job_type, _, _ = await _pack(db, code="src", name="Source")
        stale = job_lifecycle_etag(job_type.updated_at - timedelta(minutes=5))

        with pytest.raises(HTTPException) as exc_info:
            await service.update_job_type(tenant_id=TENANT_ID, job_type_id=job_type.id, name="Loser", if_match=stale)
        assert exc_info.value.status_code == 409
        assert "Reload" in exc_info.value.detail

        still = await service.get_job_type(tenant_id=TENANT_ID, job_type_id=job_type.id)
        assert still.name == "Source"


@pytest.mark.asyncio
async def test_the_conflict_names_the_timestamp_the_server_is_holding(session_factory):
    async with session_factory() as db:
        service = JobLifecycleService(db)
        job_type, _, _ = await _pack(db, code="src", name="Source")
        with pytest.raises(HTTPException) as exc_info:
            await service.update_job_type(
                tenant_id=TENANT_ID,
                job_type_id=job_type.id,
                name="Loser",
                if_match="2000-01-01T00:00:00+00:00",
            )
        assert str(job_lifecycle_etag(job_type.updated_at)) in exc_info.value.detail


@pytest.mark.asyncio
async def test_the_second_writer_of_two_loses_rather_than_overwriting(session_factory):
    """The whole point: last-write-wins is what W4 removes."""
    async with session_factory() as db:
        service = JobLifecycleService(db)
        _, lanes, _ = await _pack(db, code="src", name="Source")
        lane_id = lanes[0].id
        token_both_read = job_lifecycle_etag(lanes[0].updated_at)

        await service.update_lane(tenant_id=TENANT_ID, lane_id=lane_id, name="First writer wins")
        with pytest.raises(HTTPException) as exc_info:
            await service.update_lane(
                tenant_id=TENANT_ID, lane_id=lane_id, name="Second writer", if_match=token_both_read
            )
        assert exc_info.value.status_code == 409


@pytest.mark.asyncio
async def test_a_step_edit_is_guarded_too(session_factory):
    async with session_factory() as db:
        service = JobLifecycleService(db)
        _, _, steps = await _pack(db, code="src", name="Source")
        with pytest.raises(HTTPException) as exc_info:
            await service.update_step(
                tenant_id=TENANT_ID,
                step_id=steps[0].id,
                pdca_phase="do",
                if_match="1999-01-01T00:00:00+00:00",
            )
        assert exc_info.value.status_code == 409


@pytest.mark.asyncio
async def test_an_unparsable_precondition_is_a_400_not_a_silent_pass(session_factory):
    async with session_factory() as db:
        service = JobLifecycleService(db)
        job_type, _, _ = await _pack(db, code="src", name="Source")
        with pytest.raises(HTTPException) as exc_info:
            await service.update_job_type(tenant_id=TENANT_ID, job_type_id=job_type.id, name="X", if_match="yesterday")
        assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_a_client_that_sends_no_header_is_unaffected(session_factory):
    async with session_factory() as db:
        service = JobLifecycleService(db)
        job_type, _, _ = await _pack(db, code="src", name="Source")
        updated = await service.update_job_type(tenant_id=TENANT_ID, job_type_id=job_type.id, name="Renamed")
        assert updated.name == "Renamed"


def test_the_guard_is_skipped_entirely_without_a_header():
    """No header must not even look at the row, let alone raise."""
    JobLifecycleService(db=SimpleNamespace())._assert_if_match(object(), None, label="Job cycle")


# --- mandatory evidence + readiness -----------------------------------------


@pytest.mark.asyncio
async def test_marking_an_empty_cell_mandatory_creates_it(session_factory):
    """An empty cell that should hold evidence is the gap worth showing."""
    async with session_factory() as db:
        service = JobLifecycleService(db)
        job_type, lanes, steps = await _pack(db, code="src", name="Source")
        payload = await service.set_cell_requirement(
            tenant_id=TENANT_ID,
            job_type_id=job_type.id,
            lane_id=lanes[0].id,
            step_id=steps[0].id,
            requires_evidence=True,
        )
        assert payload["requires_evidence"] is True
        assert payload["library_document_ids"] == []
        JobCellResponse.model_validate(payload)


@pytest.mark.asyncio
async def test_the_requirement_can_be_lifted_again(session_factory):
    async with session_factory() as db:
        service = JobLifecycleService(db)
        job_type, lanes, steps = await _pack(db, code="src", name="Source")
        for value in (True, False):
            payload = await service.set_cell_requirement(
                tenant_id=TENANT_ID,
                job_type_id=job_type.id,
                lane_id=lanes[0].id,
                step_id=steps[0].id,
                requires_evidence=value,
            )
        assert payload["requires_evidence"] is False


@pytest.mark.asyncio
async def test_attaching_documents_does_not_clear_the_requirement(session_factory):
    async with session_factory() as db:
        service = JobLifecycleService(db)
        job_type, lanes, steps = await _pack(db, code="src", name="Source")
        await _document(db, 7)
        await service.set_cell_requirement(
            tenant_id=TENANT_ID,
            job_type_id=job_type.id,
            lane_id=lanes[0].id,
            step_id=steps[0].id,
            requires_evidence=True,
        )
        payload = await service.set_cell_documents(
            tenant_id=TENANT_ID,
            job_type_id=job_type.id,
            lane_id=lanes[0].id,
            step_id=steps[0].id,
            library_document_ids=[7],
        )
        assert payload["requires_evidence"] is True


@pytest.mark.asyncio
async def test_readiness_lists_only_the_mandatory_cells(session_factory):
    async with session_factory() as db:
        service = JobLifecycleService(db)
        job_type, lanes, steps = await _pack(db, code="src", name="Source", steps=("plan", "do"))
        await _document(db, 7)
        await service.set_cell_documents(
            tenant_id=TENANT_ID,
            job_type_id=job_type.id,
            lane_id=lanes[0].id,
            step_id=steps[1].id,
            library_document_ids=[7],
        )
        await service.set_cell_requirement(
            tenant_id=TENANT_ID,
            job_type_id=job_type.id,
            lane_id=lanes[0].id,
            step_id=steps[0].id,
            requires_evidence=True,
        )

        payload = await service.evidence_readiness(tenant_id=TENANT_ID, job_type_id=job_type.id)
        assert payload["total"] == 1
        assert payload["items"][0]["step_id"] == steps[0].id
        assert payload["items"][0]["state"] == "missing_evidence"
        assert payload["summary"]["required"] == 1
        JobEvidenceReadinessResponse.model_validate(
            {
                "items": payload["items"],
                "total": payload["total"],
                "job_type_id": payload["job_type_id"],
                "assure": payload["assure"],
                "summary": payload["summary"],
            }
        )


@pytest.mark.asyncio
async def test_readiness_names_the_lane_and_step_so_the_gap_is_findable(session_factory):
    async with session_factory() as db:
        service = JobLifecycleService(db)
        job_type, lanes, steps = await _pack(db, code="src", name="Source")
        await service.set_cell_requirement(
            tenant_id=TENANT_ID,
            job_type_id=job_type.id,
            lane_id=lanes[0].id,
            step_id=steps[0].id,
            requires_evidence=True,
        )
        item = (await service.evidence_readiness(tenant_id=TENANT_ID, job_type_id=job_type.id))["items"][0]
        assert item["lane_name"] == "build"
        assert item["step_name"] == "plan"


@pytest.mark.asyncio
async def test_assure_turns_a_withdrawn_attachment_into_a_gap(session_factory):
    async with session_factory() as db:
        service = JobLifecycleService(db)
        job_type, lanes, steps = await _pack(db, code="src", name="Source")
        await _document(db, 8, status="obsolete")
        # Attach directly: the W3 guard rightly refuses to *add* an obsolete
        # document, and this is the case where it went obsolete afterwards.
        cell = await service._get_or_create_cell(
            tenant_id=TENANT_ID, job_type_id=job_type.id, lane_id=lanes[0].id, step_id=steps[0].id
        )
        cell.requires_evidence = True
        db.add(JobCellDocument(tenant_id=TENANT_ID, cell_id=cell.id, library_document_id=8, sort_order=0))
        await db.commit()

        lenient = await service.evidence_readiness(tenant_id=TENANT_ID, job_type_id=job_type.id, assure=False)
        assured = await service.evidence_readiness(tenant_id=TENANT_ID, job_type_id=job_type.id, assure=True)
        assert lenient["items"][0]["state"] == "ready"
        assert assured["items"][0]["state"] == "obsolete_evidence"
        assert assured["assure"] is True


@pytest.mark.asyncio
async def test_assure_reports_unknown_for_evidence_it_cannot_read(session_factory):
    async with session_factory() as db:
        service = JobLifecycleService(db)
        job_type, lanes, steps = await _pack(db, code="src", name="Source")
        cell = await service._get_or_create_cell(
            tenant_id=TENANT_ID, job_type_id=job_type.id, lane_id=lanes[0].id, step_id=steps[0].id
        )
        cell.requires_evidence = True
        db.add(JobCellDocument(tenant_id=TENANT_ID, cell_id=cell.id, library_document_id=404, sort_order=0))
        await db.commit()

        assured = await service.evidence_readiness(tenant_id=TENANT_ID, job_type_id=job_type.id, assure=True)
        assert assured["items"][0]["state"] == "unknown"
        assert assured["items"][0]["is_ready"] is False


@pytest.mark.asyncio
async def test_readiness_of_a_pack_with_no_mandatory_cells_is_empty_not_an_error(session_factory):
    async with session_factory() as db:
        service = JobLifecycleService(db)
        job_type, _, _ = await _pack(db, code="src", name="Source")
        payload = await service.evidence_readiness(tenant_id=TENANT_ID, job_type_id=job_type.id, assure=True)
        assert payload["items"] == []
        assert payload["summary"]["required"] == 0


# --- process interaction map -------------------------------------------------


async def _nest(service: JobLifecycleService, *, source, lane, step, target, label="Nested"):
    return await service.create_cell_link(
        tenant_id=TENANT_ID,
        job_type_id=source.id,
        lane_id=lane.id,
        step_id=step.id,
        kind="job_cycle",
        label=label,
        target_job_type_id=target.id,
    )


@pytest.mark.asyncio
async def test_a_pack_that_nests_nothing_is_a_single_node(session_factory):
    async with session_factory() as db:
        service = JobLifecycleService(db)
        job_type, _, _ = await _pack(db, code="src", name="Source")
        graph = await service.cycle_graph(tenant_id=TENANT_ID, job_type_id=job_type.id)
        assert [n["ref_id"] for n in graph["nodes"]] == [job_type.id]
        assert graph["edges"] == []
        assert graph["truncated"] is False
        JobCycleGraphResponse.model_validate(graph)


@pytest.mark.asyncio
async def test_each_nest_link_draws_one_edge(session_factory):
    async with session_factory() as db:
        service = JobLifecycleService(db)
        parent, lanes, steps = await _pack(db, code="parent", name="Parent", steps=("plan", "do"))
        child, _, _ = await _pack(db, code="child", name="Child")
        await _nest(service, source=parent, lane=lanes[0], step=steps[0], target=child)
        await _nest(service, source=parent, lane=lanes[0], step=steps[1], target=child)

        graph = await service.cycle_graph(tenant_id=TENANT_ID, job_type_id=parent.id)
        assert len(graph["edges"]) == 2, "two cells nesting the same pack are two links"
        assert {e["kind"] for e in graph["edges"]} == {"nests"}
        assert len([n for n in graph["nodes"] if n["ref_id"] == child.id]) == 1


@pytest.mark.asyncio
async def test_the_map_carries_the_cell_each_edge_came_from(session_factory):
    """So the map can send an operator to the link they would have to delete."""
    async with session_factory() as db:
        service = JobLifecycleService(db)
        parent, lanes, steps = await _pack(db, code="parent", name="Parent")
        child, _, _ = await _pack(db, code="child", name="Child")
        await _nest(service, source=parent, lane=lanes[0], step=steps[0], target=child)
        edge = (await service.cycle_graph(tenant_id=TENANT_ID, job_type_id=parent.id))["edges"][0]
        assert edge["lane_id"] == lanes[0].id
        assert edge["step_id"] == steps[0].id
        assert edge["href"].endswith(f"/{child.id}")


@pytest.mark.asyncio
async def test_the_walk_stops_at_the_requested_depth_and_says_so(session_factory):
    async with session_factory() as db:
        service = JobLifecycleService(db)
        a, a_lanes, a_steps = await _pack(db, code="a", name="A")
        b, b_lanes, b_steps = await _pack(db, code="b", name="B")
        c, _, _ = await _pack(db, code="c", name="C")
        await _nest(service, source=a, lane=a_lanes[0], step=a_steps[0], target=b)
        await _nest(service, source=b, lane=b_lanes[0], step=b_steps[0], target=c)

        shallow = await service.cycle_graph(tenant_id=TENANT_ID, job_type_id=a.id, depth=1)
        deep = await service.cycle_graph(tenant_id=TENANT_ID, job_type_id=a.id, depth=2)
        assert {n["ref_id"] for n in shallow["nodes"]} == {a.id, b.id}
        assert shallow["truncated"] is True
        assert {n["ref_id"] for n in deep["nodes"]} == {a.id, b.id, c.id}
        assert deep["truncated"] is False


@pytest.mark.asyncio
async def test_the_root_is_labelled_as_the_root(session_factory):
    async with session_factory() as db:
        service = JobLifecycleService(db)
        job_type, _, _ = await _pack(db, code="src", name="Source")
        graph = await service.cycle_graph(tenant_id=TENANT_ID, job_type_id=job_type.id)
        assert graph["nodes"][0]["detail"] == "root"
        assert graph["root_job_type_id"] == job_type.id


@pytest.mark.asyncio
async def test_a_deleted_nest_target_is_shown_as_unavailable_not_hidden(session_factory):
    """The link is still in a cell; pretending it is not would be worse."""
    async with session_factory() as db:
        service = JobLifecycleService(db)
        parent, lanes, steps = await _pack(db, code="parent", name="Parent")
        child, _, _ = await _pack(db, code="child", name="Child")
        await _nest(service, source=parent, lane=lanes[0], step=steps[0], target=child)
        await service.soft_delete_job_type(tenant_id=TENANT_ID, job_type_id=child.id)

        graph = await service.cycle_graph(tenant_id=TENANT_ID, job_type_id=parent.id)
        child_node = next(n for n in graph["nodes"] if n["ref_id"] == child.id)
        assert child_node["detail"] == "unavailable"
        assert len(graph["edges"]) == 1


@pytest.mark.asyncio
async def test_the_map_of_another_tenants_pack_is_a_404(session_factory):
    async with session_factory() as db:
        service = JobLifecycleService(db)
        job_type, _, _ = await _pack(db, code="src", name="Source")
        with pytest.raises(HTTPException) as exc_info:
            await service.cycle_graph(tenant_id=OTHER_TENANT_ID, job_type_id=job_type.id)
        assert exc_info.value.status_code == 404


# --- audit trail -------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_trail_path_walks_pack_to_cell_to_document(session_factory):
    async with session_factory() as db:
        service = JobLifecycleService(db)
        job_type, lanes, steps = await _pack(db, code="src", name="Source")
        await _document(db, 21, title="Commissioning checklist")
        await service.set_cell_documents(
            tenant_id=TENANT_ID,
            job_type_id=job_type.id,
            lane_id=lanes[0].id,
            step_id=steps[0].id,
            library_document_ids=[21],
        )

        trail = await service.audit_trail(tenant_id=TENANT_ID, job_type_id=job_type.id)
        assert len(trail["paths"]) == 1
        assert [e["kind"] for e in trail["edges"]] == ["contains", "evidences"]
        assert {n["kind"] for n in trail["nodes"]} == {"job_type", "cell", "document"}
        JobAuditTrailResponse.model_validate(trail)


@pytest.mark.asyncio
async def test_the_document_node_carries_its_library_reference(session_factory):
    async with session_factory() as db:
        service = JobLifecycleService(db)
        job_type, lanes, steps = await _pack(db, code="src", name="Source")
        await _document(db, 22, title="Checklist")
        await service.set_cell_documents(
            tenant_id=TENANT_ID,
            job_type_id=job_type.id,
            lane_id=lanes[0].id,
            step_id=steps[0].id,
            library_document_ids=[22],
        )
        trail = await service.audit_trail(tenant_id=TENANT_ID, job_type_id=job_type.id)
        document_node = next(n for n in trail["nodes"] if n["kind"] == "document")
        assert document_node["label"] == "PEL-22 · Checklist"
        assert document_node["href"] == "/documents/22"


@pytest.mark.asyncio
async def test_a_reference_the_library_cannot_resolve_still_gets_a_node(session_factory):
    """Dropping it would hide a dangling reference, which is the finding."""
    async with session_factory() as db:
        service = JobLifecycleService(db)
        job_type, lanes, steps = await _pack(db, code="src", name="Source")
        cell = await service._get_or_create_cell(
            tenant_id=TENANT_ID, job_type_id=job_type.id, lane_id=lanes[0].id, step_id=steps[0].id
        )
        db.add(JobCellDocument(tenant_id=TENANT_ID, cell_id=cell.id, library_document_id=999, sort_order=0))
        await db.commit()

        trail = await service.audit_trail(tenant_id=TENANT_ID, job_type_id=job_type.id)
        document_node = next(n for n in trail["nodes"] if n["kind"] == "document")
        assert document_node["label"] == "Document #999"


@pytest.mark.asyncio
async def test_the_trail_reuses_the_maps_nest_edge(session_factory):
    """One vocabulary: a nest edge must not be spelled differently per view."""
    async with session_factory() as db:
        service = JobLifecycleService(db)
        parent, lanes, steps = await _pack(db, code="parent", name="Parent")
        child, _, _ = await _pack(db, code="child", name="Child")
        await _nest(service, source=parent, lane=lanes[0], step=steps[0], target=child)

        trail = await service.audit_trail(tenant_id=TENANT_ID, job_type_id=parent.id, include_links=True)
        graph = await service.cycle_graph(tenant_id=TENANT_ID, job_type_id=parent.id)
        trail_nest = next(e for e in trail["edges"] if e["kind"] == "nests")
        graph_nest = graph["edges"][0]
        assert trail_nest["target"] == graph_nest["target"]
        assert trail_nest["cell_id"] == graph_nest["cell_id"]


@pytest.mark.asyncio
async def test_an_external_link_is_a_reference_edge(session_factory):
    async with session_factory() as db:
        service = JobLifecycleService(db)
        job_type, lanes, steps = await _pack(db, code="src", name="Source")
        await service.create_cell_link(
            tenant_id=TENANT_ID,
            job_type_id=job_type.id,
            lane_id=lanes[0].id,
            step_id=steps[0].id,
            kind="external",
            label="Vendor manual",
            external_url="https://example.test/manual",
        )
        trail = await service.audit_trail(tenant_id=TENANT_ID, job_type_id=job_type.id, include_links=True)
        edge = next(e for e in trail["edges"] if e["kind"] == "references")
        assert edge["href"] == "https://example.test/manual"


@pytest.mark.asyncio
async def test_links_stay_hidden_when_the_links_flag_is_closed(session_factory):
    """The trail must not surface what the composer is gating away."""
    async with session_factory() as db:
        service = JobLifecycleService(db)
        job_type, lanes, steps = await _pack(db, code="src", name="Source")
        await service.create_cell_link(
            tenant_id=TENANT_ID,
            job_type_id=job_type.id,
            lane_id=lanes[0].id,
            step_id=steps[0].id,
            kind="external",
            label="Vendor manual",
            external_url="https://example.test/manual",
        )
        trail = await service.audit_trail(tenant_id=TENANT_ID, job_type_id=job_type.id, include_links=False)
        assert trail["paths"] == []
        assert [e["kind"] for e in trail["edges"]] == []


@pytest.mark.asyncio
async def test_an_empty_optional_cell_is_not_walked_but_an_empty_mandatory_one_is(session_factory):
    async with session_factory() as db:
        service = JobLifecycleService(db)
        job_type, lanes, steps = await _pack(db, code="src", name="Source", steps=("plan", "do"))
        await service.set_cell_requirement(
            tenant_id=TENANT_ID,
            job_type_id=job_type.id,
            lane_id=lanes[0].id,
            step_id=steps[0].id,
            requires_evidence=True,
        )
        await service._get_or_create_cell(
            tenant_id=TENANT_ID, job_type_id=job_type.id, lane_id=lanes[0].id, step_id=steps[1].id
        )
        await db.commit()

        trail = await service.audit_trail(tenant_id=TENANT_ID, job_type_id=job_type.id)
        assert [p["step_id"] for p in trail["paths"]] == [steps[0].id]
        assert trail["paths"][0]["readiness"]["state"] == "missing_evidence"


@pytest.mark.asyncio
async def test_a_truncated_sample_never_reads_as_a_complete_export(session_factory):
    async with session_factory() as db:
        service = JobLifecycleService(db)
        job_type, lanes, steps = await _pack(db, code="src", name="Source", steps=("a", "b", "c"))
        for step in steps:
            await service.set_cell_requirement(
                tenant_id=TENANT_ID,
                job_type_id=job_type.id,
                lane_id=lanes[0].id,
                step_id=step.id,
                requires_evidence=True,
            )
        trail = await service.audit_trail(tenant_id=TENANT_ID, job_type_id=job_type.id, limit=2)
        assert len(trail["paths"]) == 2
        assert trail["total_candidates"] == 3
        assert trail["truncated"] is True


@pytest.mark.asyncio
async def test_the_trail_summarises_the_readiness_of_what_it_walked(session_factory):
    async with session_factory() as db:
        service = JobLifecycleService(db)
        job_type, lanes, steps = await _pack(db, code="src", name="Source")
        await service.set_cell_requirement(
            tenant_id=TENANT_ID,
            job_type_id=job_type.id,
            lane_id=lanes[0].id,
            step_id=steps[0].id,
            requires_evidence=True,
        )
        trail = await service.audit_trail(tenant_id=TENANT_ID, job_type_id=job_type.id)
        assert trail["summary"]["missing_evidence"] == 1
        assert trail["summary"]["required"] == 1


@pytest.mark.asyncio
async def test_assure_marks_withdrawn_evidence_on_the_walked_path(session_factory):
    async with session_factory() as db:
        service = JobLifecycleService(db)
        job_type, lanes, steps = await _pack(db, code="src", name="Source")
        await _document(db, 31, status="obsolete")
        cell = await service._get_or_create_cell(
            tenant_id=TENANT_ID, job_type_id=job_type.id, lane_id=lanes[0].id, step_id=steps[0].id
        )
        cell.requires_evidence = True
        db.add(JobCellDocument(tenant_id=TENANT_ID, cell_id=cell.id, library_document_id=31, sort_order=0))
        await db.commit()

        trail = await service.audit_trail(tenant_id=TENANT_ID, job_type_id=job_type.id, assure=True)
        assert trail["paths"][0]["readiness"]["state"] == "obsolete_evidence"
        document_node = next(n for n in trail["nodes"] if n["kind"] == "document")
        assert document_node["detail"] == "obsolete"


@pytest.mark.asyncio
async def test_the_trail_of_an_empty_pack_is_empty_not_an_error(session_factory):
    async with session_factory() as db:
        service = JobLifecycleService(db)
        job_type, _, _ = await _pack(db, code="src", name="Source")
        trail = await service.audit_trail(tenant_id=TENANT_ID, job_type_id=job_type.id)
        assert trail["paths"] == []
        assert trail["total_candidates"] == 0
        assert trail["truncated"] is False
        assert [n["kind"] for n in trail["nodes"]] == ["job_type"]


# ---------------------------------------------------------------------------
# Wire contract
# ---------------------------------------------------------------------------


def test_a_cell_payload_written_before_w4_still_validates():
    model = JobCellResponse.model_validate(
        {
            "id": 1,
            "tenant_id": 1,
            "job_type_id": 1,
            "lane_id": 2,
            "step_id": 3,
            "created_at": NOW,
            "updated_at": NOW,
        }
    )
    assert model.requires_evidence is False
