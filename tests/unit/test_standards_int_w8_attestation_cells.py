"""Int-W8: TechGapGuard mapping, cell aggregate, isolation. Existing tests unedited."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any, Optional

import pytest

from src.domain.models.compliance_evidence import ComplianceEvidenceLink
from src.domain.services.standards_cell_aggregate_service import StandardsCellAggregateService
from src.domain.services.standards_entra_attestation import AttestationPosture
from src.domain.services.standards_tech_gap_guard import (
    TECHNICAL_ATTESTATION_ENTITY_TYPES,
    assess,
)
from src.domain.services.standards_trap_guard import TrapGuard

ROOT = Path(__file__).resolve().parents[2]
PASS = AttestationPosture(
    status="pass",
    kinds=("entra_mfa",),
    source="conditional_access",
    observed_at="2026-08-13T05:00:00+00:00",
)
FAIL = AttestationPosture(status="fail", reason="not_enforced", observed_at="2026-08-13T05:00:00+00:00")
UNAVAILABLE = AttestationPosture(status="unavailable", reason="http_403")


class _FakeResult:
    def __init__(self, rows: list[Any]):
        self._rows = rows

    def scalars(self) -> "_FakeResult":
        return self

    def all(self) -> list[Any]:
        return self._rows


class _FakeSession:
    def __init__(self, rows: Optional[dict[str, list[Any]]] = None):
        self._rows = rows or {}
        self.reads: dict[str, int] = {}

    async def execute(self, query: Any) -> _FakeResult:
        entity = query.column_descriptions[0]["entity"]
        self.reads[entity.__name__] = self.reads.get(entity.__name__, 0) + 1
        return _FakeResult(list(self._rows.get(entity.__name__, [])))


def _cel(clause_id: str, *, entity_type: str = "document") -> ComplianceEvidenceLink:
    return ComplianceEvidenceLink(
        id=1,
        tenant_id=1,
        entity_type=entity_type,
        entity_id="doc-1",
        clause_id=clause_id,
        title="Access control procedure",
        signal_type="evidence",
    )


def _service(rows: Optional[dict[str, list[Any]]] = None, *, posture: Optional[AttestationPosture] = None):
    service = StandardsCellAggregateService(_FakeSession(rows), trap_guard=TrapGuard())  # type: ignore[arg-type]
    service._shelf_cache[1] = []
    if posture is not None:
        service._attestation_cache[1] = posture
    return service


def _imports_any(path: Path, needles: tuple[str, ...]) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: list[str] = []
    for node in ast.walk(tree):
        names: list[str] = []
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            names = [node.module or ""]
        for name in names:
            for needle in needles:
                if needle in name:
                    found.append(name)
    return found


def test_entra_mfa_covers_27001_a_8_5() -> None:
    decision = assess(framework="27001", clause_number="a.8.5", attestations=("entra_mfa",))
    assert decision.covered is True
    assert decision.stub is False
    assert decision.attestation_status == "pass"


def test_entra_mfa_does_not_cover_ce_user_access_control_and_names_unattested_elements() -> None:
    decision = assess(framework="ce", clause_number="user_access_control", attestations=("entra_mfa",))
    assert decision.covered is False
    assert decision.stub is True
    assert decision.attestation_status == "partial"
    assert "individually assigned accounts" in decision.unattested_elements
    assert "separated administrative accounts" in decision.unattested_elements
    assert "individually assigned accounts" in decision.reason


def test_entra_mfa_does_not_cover_ce_a_8_5_via_suffix_fallback() -> None:
    decision = assess(framework="ce", clause_number="a.8.5", attestations=("entra_mfa",))
    assert decision.covered is False
    assert decision.attestation_status != "pass"


def test_no_attestation_kind_ever_covers_cep() -> None:
    decision = assess(framework="cep", clause_number="user_access_control", attestations=("entra_mfa",))
    assert decision.covered is False
    assert decision.stub is True
    assert decision.reason == "cyber_essentials_plus_requires_witnessed_test"


def test_unknown_attestation_kind_is_ignored() -> None:
    decision = assess(framework="27001", clause_number="a.8.5", attestations=("not_a_kind",))
    assert decision.covered is False
    assert decision.stub is True
    assert decision.attestation_status is None


def test_technical_attestation_entity_types_stays_empty() -> None:
    assert TECHNICAL_ATTESTATION_ENTITY_TYPES == frozenset()


def test_cel_entity_type_named_after_an_attestation_kind_does_not_cover() -> None:
    decision = assess(
        framework="27001",
        clause_number="a.8.5",
        entity_types=("entra_mfa", "entra_mfa_attestation"),
    )
    assert decision.covered is False
    assert decision.stub is True


@pytest.mark.asyncio
async def test_cell_upgrades_from_partial_to_covered_on_pass() -> None:
    rows = {"ComplianceEvidenceLink": [_cel("27001-a.8.5")]}
    before = await _service(rows).get_cell(tenant_id=1, framework="27001", clause_number="a.8.5")
    assert before.verdict == "partial"
    assert "tech_gap_attestation_missing" in before.reasons
    assert before.tech_gap["stub"] is True
    assert before.attestation["status"] == "disabled"

    after = await _service(rows, posture=PASS).get_cell(tenant_id=1, framework="27001", clause_number="a.8.5")
    assert after.verdict == "covered"
    assert "tech_gap_attestation_missing" not in after.reasons
    assert after.tech_gap["covered"] is True
    assert after.tech_gap["stub"] is False
    assert after.attestation["status"] == "pass"


@pytest.mark.asyncio
async def test_cell_stays_partial_on_fail() -> None:
    rows = {"ComplianceEvidenceLink": [_cel("27001-a.8.5")]}
    cell = await _service(rows, posture=FAIL).get_cell(tenant_id=1, framework="27001", clause_number="a.8.5")
    assert cell.verdict == "partial"
    assert "tech_gap_attestation_missing" in cell.reasons
    assert cell.attestation["status"] == "fail"


@pytest.mark.asyncio
async def test_cell_stays_partial_on_unavailable() -> None:
    rows = {"ComplianceEvidenceLink": [_cel("27001-a.8.5")]}
    cell = await _service(rows, posture=UNAVAILABLE).get_cell(
        tenant_id=1, framework="27001", clause_number="a.8.5"
    )
    assert cell.verdict == "partial"
    assert "tech_gap_attestation_missing" in cell.reasons
    assert cell.attestation["status"] == "unavailable"


@pytest.mark.asyncio
async def test_matrix_summary_resolves_attestation_once_for_many_cells(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"n": 0}

    async def fake_resolve(**kwargs: Any) -> AttestationPosture:
        calls["n"] += 1
        return PASS

    monkeypatch.setattr(
        "src.domain.services.standards_cell_aggregate_service.resolve_attestation",
        fake_resolve,
    )
    rows = {"ComplianceEvidenceLink": [_cel("27001-a.8.5")]}
    summary = await _service(rows).get_matrix_summary(
        tenant_id=1,
        frameworks=["27001"],
        clause_numbers=["a.8.5", "user_access_control", "7.5"],
    )
    assert calls["n"] == 1
    by_clause = {cell["clause_number"]: cell for cell in summary["cells"]}
    assert "attestation" in by_clause["a.8.5"]
    assert "attestation" not in by_clause["7.5"]


def test_exact_share_still_warns_tech_gap_when_attestation_passes() -> None:
    without = assess(framework="27001", clause_number="a.8.5", entity_types=("document",))
    assert without.covered is False
    with_kind = assess(
        framework="27001",
        clause_number="a.8.5",
        entity_types=("document",),
        attestations=("entra_mfa",),
    )
    assert with_kind.covered is True
    tree = ast.parse((ROOT / "src/domain/services/standards_exact_share_service.py").read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            for keyword in node.keywords:
                assert keyword.arg != "attestations"


def test_tech_gap_guard_imports_no_http_client_or_config() -> None:
    found = _imports_any(
        ROOT / "src/domain/services/standards_tech_gap_guard.py",
        ("httpx", "entra_graph_client", "src.core.config", "standards_entra_attestation"),
    )
    assert found == []


def test_trap_guard_and_ingest_gate_do_not_import_attestation_reader() -> None:
    needles = ("standards_entra_attestation", "entra_graph_client", "standards_requirement_axis")
    for rel in (
        "src/domain/services/standards_trap_guard.py",
        "src/domain/services/standards_ingest_gate.py",
    ):
        found = _imports_any(ROOT / rel, needles)
        assert found == [], rel
