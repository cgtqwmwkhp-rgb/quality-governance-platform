"""Int-W9: IMS Overview meters from cell aggregate, not Control-table %."""

from __future__ import annotations

from typing import Any, Optional
from unittest.mock import AsyncMock

import pytest

from src.domain.models.standards_alignment import (
    AlignmentEdge,
    AlignmentVerdict,
    MatrixVersion,
    MatrixVersionStatus,
    canonical_alignment_pair,
)
from src.domain.services.ims_dashboard_service import IMSDashboardService
from src.domain.services.standards_cell_aggregate_service import (
    CellAggregateResult,
    StandardsCellAggregateService,
    ims_overview_axes,
    roll_ims_framework_meter,
)
from src.domain.services.standards_requirement_axis import SCHEME_AXIS_FRAMEWORKS, axis_rows
from src.domain.services.standards_trap_guard import TrapGuard


class _FakeResult:
    def __init__(self, rows: list[Any]):
        self._rows = rows

    def scalars(self):
        return self

    def all(self):
        return self._rows


class _FakeSession:
    def __init__(self, rows: Optional[dict[str, list[Any]]] = None):
        self._rows = rows or {}
        self.reads: dict[str, int] = {}

    async def execute(self, query: Any) -> _FakeResult:
        entity = query.column_descriptions[0]["entity"]
        self.reads[entity.__name__] = self.reads.get(entity.__name__, 0) + 1
        return _FakeResult(list(self._rows.get(entity.__name__, [])))


def _loaded_iso_guard() -> TrapGuard:
    src_fw, src_key, dst_fw, dst_key = canonical_alignment_pair("9001", "9001-7.2", "14001", "14001-7.2")
    edge = AlignmentEdge(
        tenant_id=1,
        matrix_version_id=1,
        row_key="annexsl-7.2",
        clause_ref="7.2",
        title="Competence",
        src_framework=src_fw,
        src_clause_key=src_key,
        dst_framework=dst_fw,
        dst_clause_key=dst_key,
        verdict=AlignmentVerdict.EXACT,
        row_verdict=AlignmentVerdict.EXACT,
        is_pair_override=False,
    )
    version = MatrixVersion(
        tenant_id=1,
        source_ref="PEL-HSEQ-5064",
        version_label="1.1",
        title="Standards Alignment Matrix",
        source_checksum="test",
        status=MatrixVersionStatus.ACTIVE,
    )
    return TrapGuard(edges=[edge], version=version)


def _service(*, guard: TrapGuard) -> StandardsCellAggregateService:
    service = StandardsCellAggregateService(_FakeSession({}), trap_guard=guard)  # type: ignore[arg-type]
    service._shelf_cache[1] = []
    return service


def test_empty_guard_tracks_scheme_catalogues_not_iso_and_not_control_table() -> None:
    axes = ims_overview_axes(TrapGuard())
    frameworks = [axis["framework"] for axis in axes]
    assert set(frameworks) == set(SCHEME_AXIS_FRAMEWORKS)
    assert "9001" not in frameworks
    assert "uvdb" in frameworks
    assert "pm" in frameworks
    chas = next(axis for axis in axes if axis["framework"] == "chas")
    assert chas["axis_source"] == "requirement_catalogue"
    assert chas["clause_numbers"] == [row["clause_number"] for row in axis_rows("chas")]
    assert "7.2" not in chas["clause_numbers"]


def test_imported_alignment_adds_covered_iso_frameworks_once() -> None:
    axes = ims_overview_axes(_loaded_iso_guard())
    by_fw = {axis["framework"]: axis for axis in axes}
    assert set(by_fw) == {"9001", "14001", *SCHEME_AXIS_FRAMEWORKS}
    assert by_fw["9001"]["axis_source"] == "alignment"
    assert by_fw["9001"]["clause_numbers"] == ["7.2"]
    assert "27001" not in by_fw
    assert by_fw["chas"]["axis_source"] == "requirement_catalogue"
    assert by_fw["uvdb"]["clause_numbers"] == [row["clause_number"] for row in axis_rows("uvdb")]


def test_roll_ims_framework_meter_is_counts_not_a_percentage() -> None:
    meter = roll_ims_framework_meter(
        framework="uvdb",
        axis_source="requirement_catalogue",
        cells=[
            {"verdict": "covered", "summary": {"cert_count": 1, "open_nc_count": 0}},
            {"verdict": "covered", "summary": {"cert_count": 2, "open_nc_count": 0}},
            {"verdict": "gap", "summary": {"cert_count": 2, "open_nc_count": 3}},
            {"verdict": "unknown", "summary": {"cert_count": 0, "open_nc_count": 0}},
        ],
    )
    assert meter["covered"] == 2
    assert meter["gap"] == 1
    assert meter["unknown"] == 1
    assert meter["cells"] == 4
    assert meter["cert_count"] == 2
    assert meter["open_nc_cells"] == 1
    assert "compliance_percentage" not in meter
    assert "%" not in str(meter.values())


@pytest.mark.asyncio
async def test_get_ims_framework_meters_empty_guard_tracks_seven_schemes() -> None:
    meters = await _service(guard=TrapGuard()).get_ims_framework_meters(1)
    frameworks = {row["framework"] for row in meters["frameworks"]}
    assert meters["tracked_count"] == len(SCHEME_AXIS_FRAMEWORKS)
    assert frameworks == set(SCHEME_AXIS_FRAMEWORKS)
    assert meters["matrix_loaded"] is False
    assert "9001" not in frameworks
    assert meters["honesty"].startswith("Counts of matrix cells")
    chas = next(row for row in meters["frameworks"] if row["framework"] == "chas")
    assert chas["cells"] == len(axis_rows("chas"))
    assert chas["unknown"] == chas["cells"]


@pytest.mark.asyncio
async def test_get_ims_framework_meters_reads_each_source_once() -> None:
    service = _service(guard=TrapGuard())
    await service.get_ims_framework_meters(1)
    reads = service.db.reads  # type: ignore[attr-defined]
    for source in ("AuditFinding", "CAPAAction", "ComplianceEvidenceLink", "Risk", "EnterpriseRiskControl"):
        assert reads.get(source, 0) == 1, f"{source} was read {reads.get(source, 0)} times"


@pytest.mark.asyncio
async def test_get_ims_framework_meters_does_not_n_plus_one_get_cell_without_cache() -> None:
    service = _service(guard=TrapGuard())
    calls: list[tuple[str, str]] = []
    original = service.get_cell

    async def wrapped(*, tenant_id: int, framework: str, clause_number: str) -> CellAggregateResult:
        calls.append((framework, clause_number))
        return await original(tenant_id=tenant_id, framework=framework, clause_number=clause_number)

    service.get_cell = wrapped  # type: ignore[method-assign]
    meters = await service.get_ims_framework_meters(1)
    expected = sum(len(axis_rows(fw)) for fw in SCHEME_AXIS_FRAMEWORKS)
    assert len(calls) == expected
    assert meters["totals"]["cells"] == expected


@pytest.mark.asyncio
async def test_get_cell_overview_requires_tenant() -> None:
    service = IMSDashboardService(AsyncMock())
    empty = await service.get_cell_overview(tenant_id=None)
    assert empty["tracked_count"] == 0
    assert empty["frameworks"] == []
    assert empty["error"] == "tenant_required"
