"""Unit tests for Standards cell aggregate cover gate + matching (PR-B).

Wave 4 adds the cases where tolerant matching was inventing coverage: a clause
number is not a claim about a framework the imported matrix has never carried, and
an undifferentiated certificate register is not proof of anything in particular.
"""

from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional

import pytest

from src.domain.models.audit import AuditFinding
from src.domain.models.capa import CAPAAction
from src.domain.models.compliance_evidence import ComplianceEvidenceLink
from src.domain.models.external_audit_record import ExternalAuditRecord
from src.domain.models.risk import Risk
from src.domain.models.risk_register import EnterpriseRiskControl
from src.domain.models.standards_alignment import (
    AlignmentEdge,
    AlignmentVerdict,
    MatrixVersion,
    MatrixVersionStatus,
    canonical_alignment_pair,
)
from src.domain.services.standards_cell_aggregate_service import (
    FRAMEWORK_ALIASES,
    SOURCE_SCAN_LIMIT,
    StandardsCellAggregateService,
    any_token_matches_cell,
    classify_audit_kind,
    clause_match_keys,
    compute_cell_verdict,
    count_proof_certs,
    detect_recurrence,
    framework_for_certificate,
    normalize_clause_token,
    requires_framed_tokens,
    roll_framework_countdown,
    token_matches_clause,
)
from src.domain.services.standards_trap_guard import TrapGuard


def test_normalize_and_match_keys():
    keys = clause_match_keys("9001", "7.5")
    assert normalize_clause_token("7.5") in keys
    assert normalize_clause_token("9001-7.5") in keys
    assert token_matches_clause("9001-7.5", keys, "7.5")
    assert token_matches_clause("7.5", keys, "7.5")
    assert token_matches_clause("7.5.1", keys, "7.5")
    assert not token_matches_clause("8.1", keys, "7.5")


def test_classify_audit_kind_mock_imported_internal():
    assert classify_audit_kind(assessment_mode="mock", source_origin=None, template_tags=None) == "mock"
    assert classify_audit_kind(assessment_mode=None, source_origin=None, template_tags=["mock"]) == "mock"
    assert (
        classify_audit_kind(
            assessment_mode=None,
            source_origin="external_import",
            template_tags=None,
        )
        == "imported"
    )
    assert (
        classify_audit_kind(
            assessment_mode="field",
            source_origin=None,
            template_tags=["internal"],
            is_external_import=True,
        )
        == "imported"
    )
    assert classify_audit_kind(assessment_mode="field", source_origin=None, template_tags=None) == "internal"


def test_open_nc_or_action_never_covered():
    blocked = compute_cell_verdict(
        open_nc_count=1,
        open_action_count=0,
        recurrence=False,
        conformance_evidence_count=5,
        mock_gap_count=0,
        closed_nc_count=0,
    )
    assert blocked["verdict"] == "gap"
    assert blocked["cover_blocked"] is True

    action_only = compute_cell_verdict(
        open_nc_count=0,
        open_action_count=2,
        recurrence=False,
        conformance_evidence_count=5,
        mock_gap_count=0,
        closed_nc_count=0,
    )
    assert action_only["verdict"] == "partial"
    assert action_only["cover_blocked"] is True
    assert action_only["verdict"] != "covered"


def test_covered_when_evidence_and_no_open_issues():
    ok = compute_cell_verdict(
        open_nc_count=0,
        open_action_count=0,
        recurrence=False,
        conformance_evidence_count=2,
        mock_gap_count=0,
        closed_nc_count=0,
    )
    assert ok["verdict"] == "covered"
    assert ok["cover_blocked"] is False


def test_mock_gaps_paint_honestly():
    mock = compute_cell_verdict(
        open_nc_count=0,
        open_action_count=0,
        recurrence=False,
        conformance_evidence_count=0,
        mock_gap_count=1,
        closed_nc_count=0,
    )
    assert mock["verdict"] == "gap"
    assert "mock_gap" in mock["reasons"]


def test_recurrence_red_flag_after_close():
    now = datetime.now(timezone.utc)
    events = [
        {"status": "closed", "created_at": now - timedelta(days=30), "closed_at": now - timedelta(days=20)},
        {"status": "open", "created_at": now - timedelta(days=2), "closed_at": None},
    ]
    assert detect_recurrence(events) is True
    assert detect_recurrence([{"status": "open", "created_at": now}]) is False

    with_recurrence = compute_cell_verdict(
        open_nc_count=1,
        open_action_count=0,
        recurrence=True,
        conformance_evidence_count=1,
        mock_gap_count=0,
        closed_nc_count=1,
    )
    assert with_recurrence["recurrence_red_flag"] is True
    assert with_recurrence["verdict"] == "gap"


# ------------------------------------------------------------------ Wave 4 (W4)


def _guard(*, loaded: bool = True) -> TrapGuard:
    """A two-framework edition: ISO 9001 and 14001 7.2 are EXACT, nothing else exists.

    Deliberately smaller than the real 5064 payload, because the point under test is
    what happens to the columns an edition does *not* carry — here, every column
    except those two.
    """
    if not loaded:
        return TrapGuard()
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
        version_label="1.0",
        title="Standards Alignment Matrix",
        source_checksum="test",
        status=MatrixVersionStatus.ACTIVE,
    )
    return TrapGuard(edges=[edge], version=version)


def test_only_framed_tokens_match_a_framework_the_edition_does_not_carry():
    """A bare ``7.2`` is not a CHAS claim, and neither is ``9001-7.2``."""
    guard = _guard()
    assert requires_framed_tokens(guard, "chas") is True
    assert requires_framed_tokens(guard, "9001") is False

    keys = clause_match_keys("chas", "7.2")
    assert any_token_matches_cell(["7.2"], keys, "7.2", framework="chas", guard=guard) is False
    assert any_token_matches_cell(["9001-7.2"], keys, "7.2", framework="chas", guard=guard) is False
    assert any_token_matches_cell(["chas-7.2"], keys, "7.2", framework="chas", guard=guard) is True


def test_scheme_columns_still_require_framed_tokens_after_ce_edges_load():
    """CE↔CE+ NEAR must not reopen W4 paint on a bare ``7.2``."""
    from src.domain.models.standards_alignment import AlignmentEdge, MatrixVersion, MatrixVersionStatus
    from src.domain.services.standards_alignment_import_service import build_edges, load_payload
    from src.domain.services.standards_trap_guard import TrapGuard

    edges, warnings = build_edges(load_payload())
    assert warnings == []
    stored = [
        AlignmentEdge(
            tenant_id=1,
            matrix_version_id=1,
            row_key=edge.row_key,
            clause_ref=edge.clause_ref,
            title=edge.title,
            src_framework=edge.key.src_framework,
            src_clause_key=edge.key.src_clause_key,
            dst_framework=edge.key.dst_framework,
            dst_clause_key=edge.key.dst_clause_key,
            verdict=edge.verdict,
            row_verdict=edge.row_verdict,
            is_pair_override=False,
        )
        for edge in edges
    ]
    version = MatrixVersion(
        tenant_id=1,
        source_ref="PEL-HSEQ-5064",
        version_label="1.1",
        title="t",
        source_checksum="c",
        status=MatrixVersionStatus.ACTIVE,
    )
    guard = TrapGuard(edges=stored, version=version)
    assert guard.covers_framework("ce") is True
    assert requires_framed_tokens(guard, "ce") is True
    assert requires_framed_tokens(guard, "chas") is True
    assert requires_framed_tokens(guard, "9001") is False
    chas_keys = clause_match_keys("chas", "7.2")
    assert any_token_matches_cell(["7.2"], chas_keys, "7.2", framework="chas", guard=guard) is False
    assert any_token_matches_cell(["9001-7.2"], chas_keys, "7.2", framework="chas", guard=guard) is False
    ce_keys = clause_match_keys("ce", "7.2")
    assert any_token_matches_cell(["7.2"], ce_keys, "7.2", framework="ce", guard=guard) is False
    assert any_token_matches_cell(["ce-7.2"], ce_keys, "7.2", framework="ce", guard=guard) is True


def test_matching_is_unchanged_for_carried_frameworks_and_for_an_empty_guard():
    """The gate must not narrow the columns the edition does carry, or an un-imported tenant."""
    keys = clause_match_keys("9001", "7.2")
    for guard in (_guard(), _guard(loaded=False), None):
        assert any_token_matches_cell(["7.2"], keys, "7.2", framework="9001", guard=guard) is True

    chas_keys = clause_match_keys("chas", "7.2")
    assert requires_framed_tokens(_guard(loaded=False), "chas") is False
    assert any_token_matches_cell(["7.2"], chas_keys, "7.2", framework="chas", guard=None) is True


def test_the_register_proves_nothing_on_its_own():
    """``register`` is a storage location, not a scheme, so it names no framework."""
    for alias in FRAMEWORK_ALIASES.values():
        assert "register" not in alias["cert_schemes"]


def test_the_uvdb_column_recognises_the_shelf_stamp_for_achilles():
    """The shelf stamps ``uvdb_achilles``; the column listed only ``uvdb``/``achilles``."""
    assert "uvdb_achilles" in FRAMEWORK_ALIASES["uvdb"]["cert_schemes"]


@pytest.mark.parametrize(
    ("certificate_type", "name", "expected"),
    [
        ("iso9001", "Quality certificate", "9001"),
        ("certification", "ISO 14001:2015 Certificate", "14001"),
        ("chas", "CHAS Premium Plus", "chas"),
        ("cyber_essentials_plus", "Annual assessment", "cep"),
        ("cyber_essentials", "Annual assessment", "ce"),
        ("ce", "Annual assessment", "ce"),
        ("CE+", "Annual assessment", "cep"),
        ("Cyber Essentials+", "Shelf stamp", "cep"),
        ("achilles", "UVDB B2 verification", "uvdb"),
        # The ones that must stay unattributed: real certificates that prove
        # something real, and no framework column at all.
        ("pat_testing", "PAT test 2026", None),
        ("insurance", "Employers liability", None),
        ("training", "Fire marshal training", None),
    ],
)
def test_register_certificates_are_attributed_by_type(certificate_type, name, expected):
    assert framework_for_certificate(certificate_type, name) == expected


def test_unmatched_shelf_items_are_never_counted_as_proof():
    certificates = [
        {"proof_scope": "framework"},
        {"proof_scope": "clause"},
        {"proof_scope": "unmatched"},
    ]
    assert count_proof_certs(certificates) == 2


def test_pat_does_not_drive_iso_or_chas_countdown():
    """SG-D-03: operational register items must not set matrix column days."""
    today = date(2026, 8, 13)
    rolled = roll_framework_countdown(
        [
            {
                "scheme": "register",
                "name": "PAT test 2026",
                "metadata": {"certificate_type": "pat_testing"},
                "expiry_date": date(2026, 8, 20),
            }
        ],
        frameworks=["9001", "chas"],
        today=today,
    )
    assert rolled["unmatched_on_shelf"] is True
    assert rolled["frameworks"]["9001"] == {
        "status": "none",
        "next_expiry": None,
        "days_remaining": None,
        "name": None,
    }
    assert rolled["frameworks"]["chas"]["status"] == "none"
    assert rolled["frameworks"]["chas"]["next_expiry"] is None


def test_iso_9001_register_cert_sets_countdown_and_not_chas():
    today = date(2026, 8, 13)
    rolled = roll_framework_countdown(
        [
            {
                "scheme": "register",
                "name": "ISO 9001:2015 Certificate",
                "metadata": {"certificate_type": "iso9001"},
                "expiry_date": date(2026, 9, 1),
            }
        ],
        frameworks=["9001", "chas"],
        today=today,
    )
    assert rolled["unmatched_on_shelf"] is False
    assert rolled["frameworks"]["9001"]["status"] == "due_soon"
    assert rolled["frameworks"]["9001"]["days_remaining"] == 19
    assert rolled["frameworks"]["9001"]["next_expiry"] == "2026-09-01"
    assert rolled["frameworks"]["9001"]["name"] == "ISO 9001:2015 Certificate"
    assert rolled["frameworks"]["chas"]["status"] == "none"
    assert rolled["frameworks"]["chas"]["next_expiry"] is None


def test_unmatched_register_item_does_not_set_next_expiry_on_any_column():
    today = date(2026, 8, 13)
    rolled = roll_framework_countdown(
        [
            {
                "scheme": "register",
                "name": "Employers liability",
                "metadata": {"certificate_type": "insurance"},
                "expiry_date": "2026-08-01",
            },
            {
                "scheme": "planet_mark",
                "name": "Planet Mark 2026",
                "expiry_date": date(2026, 12, 1),
            },
        ],
        frameworks=["9001", "pm"],
        today=today,
    )
    assert rolled["unmatched_on_shelf"] is True
    assert rolled["frameworks"]["9001"]["next_expiry"] is None
    assert rolled["frameworks"]["pm"]["status"] == "current"
    assert rolled["frameworks"]["pm"]["next_expiry"] == "2026-12-01"


def test_expired_attributed_cert_paints_expired_not_due_soon():
    today = date(2026, 8, 13)
    rolled = roll_framework_countdown(
        [
            {
                "scheme": "chas",
                "name": "CHAS Premium",
                "expiry_date": date(2026, 7, 1),
            }
        ],
        frameworks=["chas", "9001"],
        today=today,
    )
    assert rolled["frameworks"]["chas"]["status"] == "expired"
    assert rolled["frameworks"]["chas"]["days_remaining"] == -43
    assert rolled["frameworks"]["9001"]["status"] == "none"


# ------------------------------------------------- get_cell over a stubbed session


class _FakeResult:
    def __init__(self, rows: list[Any]):
        self._rows = rows

    def scalars(self) -> "_FakeResult":
        return self

    def all(self) -> list[Any]:
        return self._rows


class _FakeSession:
    """Returns canned rows per queried entity, so get_cell can be driven without a DB."""

    def __init__(self, rows: Optional[dict[str, list[Any]]] = None):
        self._rows = rows or {}
        self.reads: dict[str, int] = {}

    async def execute(self, query: Any) -> _FakeResult:
        entity = query.column_descriptions[0]["entity"]
        self.reads[entity.__name__] = self.reads.get(entity.__name__, 0) + 1
        return _FakeResult(list(self._rows.get(entity.__name__, [])))


def _service(rows: Optional[dict[str, list[Any]]] = None, *, shelf: Optional[list[dict]] = None):
    service = StandardsCellAggregateService(_FakeSession(rows), trap_guard=_guard())  # type: ignore[arg-type]
    service._shelf_cache[1] = list(shelf or [])
    return service


def _cel(clause_id: str, link_id: int = 1) -> ComplianceEvidenceLink:
    return ComplianceEvidenceLink(
        id=link_id,
        tenant_id=1,
        entity_type="document",
        entity_id="doc-1",
        clause_id=clause_id,
        title="Competence procedure",
        signal_type="evidence",
    )


@pytest.mark.asyncio
async def test_an_iso_evidence_link_does_not_paint_a_column_the_matrix_never_carried():
    """AC-02: one ISO CEL used to paint every column that printed the same number."""
    rows = {
        "ComplianceEvidenceLink": [_cel("9001-7.2")],
        "AuditFinding": [
            AuditFinding(
                id=1,
                tenant_id=1,
                run_id=1,
                title="Competence records incomplete",
                finding_type="nonconformity",
                status="open",
                clause_ids_json_legacy=["7.2"],
            )
        ],
        "CAPAAction": [
            CAPAAction(
                id=1,
                tenant_id=1,
                title="Refresh competence matrix",
                status="open",
                clause_reference="7.2",
                iso_standard="9001",
            )
        ],
        "Risk": [],
        "EnterpriseRiskControl": [],
        "ExternalAuditRecord": [],
    }
    chas = await _service(rows).get_cell(tenant_id=1, framework="chas", clause_number="7.2")
    assert chas.verdict == "unknown"
    assert chas.evidence == []
    assert chas.findings == []
    assert chas.actions == []
    assert chas.alignment["row_verdict"] is None
    assert chas.alignment["alignment_known"] is False

    iso = await _service(rows).get_cell(tenant_id=1, framework="9001", clause_number="7.2")
    assert len(iso.evidence) == 1
    assert len(iso.findings) == 1
    assert len(iso.actions) == 1
    assert iso.alignment["row_verdict"] == "EXACT"


@pytest.mark.asyncio
async def test_a_register_certificate_only_proves_the_framework_it_names():
    """AC-03: a PAT test on the shelf is not CHAS proof, and must not be counted."""
    shelf = [
        {
            "shelf_key": "register:1",
            "name": "PAT test 2026",
            "scheme": "register",
            "metadata": {"certificate_type": "pat_testing"},
        },
        {
            "shelf_key": "register:2",
            "name": "ISO 9001:2015 certificate",
            "scheme": "register",
            "metadata": {"certificate_type": "iso9001"},
        },
    ]
    chas = await _service(shelf=shelf).get_cell(tenant_id=1, framework="chas", clause_number="7.2")
    assert chas.summary["cert_count"] == 0
    assert [cert["proof_scope"] for cert in chas.certificates] == ["unmatched"]
    assert chas.certificates[0]["name"] == "PAT test 2026"

    iso = await _service(shelf=shelf).get_cell(tenant_id=1, framework="9001", clause_number="7.2")
    assert iso.summary["cert_count"] == 1
    assert iso.certificates[0]["name"] == "ISO 9001:2015 certificate"
    assert iso.certificates[0]["proof_scope"] == "framework"


@pytest.mark.asyncio
async def test_the_uvdb_column_sees_the_achilles_shelf_and_no_one_else_does():
    """AC-06: the shelf stamp and the column alias disagreed, so UVDB showed no proof."""
    shelf = [
        {
            "shelf_key": "uvdb:1",
            "name": "UVDB AB-1234",
            "scheme": "uvdb_achilles",
            "metadata": {"audit_type": "B2"},
        }
    ]
    uvdb = await _service(shelf=shelf).get_cell(tenant_id=1, framework="uvdb", clause_number="7.2")
    assert uvdb.summary["cert_count"] == 1

    iso = await _service(shelf=shelf).get_cell(tenant_id=1, framework="9001", clause_number="7.2")
    assert iso.summary["cert_count"] == 0


@pytest.mark.asyncio
async def test_a_truncated_scan_says_so_rather_than_reporting_a_floor_as_a_total():
    """AC-05: the cap is a read budget; a cell painted from a partial read is not clean."""
    rows = {"ComplianceEvidenceLink": [_cel("9001-7.2", link_id=n) for n in range(SOURCE_SCAN_LIMIT)]}
    cell = await _service(rows).get_cell(tenant_id=1, framework="9001", clause_number="7.2")
    assert cell.scan_truncated is True
    assert cell.scan_truncated_sources == ["evidence_links"]
    assert cell.summary["scan_truncated"] is True
    assert cell.to_dict()["scan_truncated"] is True

    honest = await _service({"ComplianceEvidenceLink": [_cel("9001-7.2")]}).get_cell(
        tenant_id=1, framework="9001", clause_number="7.2"
    )
    assert honest.scan_truncated is False


@pytest.mark.asyncio
async def test_a_matrix_batch_reads_each_source_once_not_once_per_cell():
    """AC-04: the All preset is 12 columns, so a per-cell re-scan is the timeout.

    Every cell runs the identical tenant-wide query and then matches in Python, so
    the read belongs to the batch, not the cell. This also means one response paints
    every cell from the same snapshot.
    """
    service = _service({"ComplianceEvidenceLink": [_cel("9001-7.2")]})
    frameworks = ["9001", "14001", "45001", "27001", "22301", "ce", "cep", "iip", "pm", "chas", "ssip", "uvdb"]
    summary = await service.get_matrix_summary(tenant_id=1, frameworks=frameworks, clause_numbers=["7.2", "7.3", "8.1"])
    assert len(summary["cells"]) == 36
    reads = service.db.reads  # type: ignore[attr-defined]
    for source in ("AuditFinding", "CAPAAction", "ComplianceEvidenceLink", "Risk", "EnterpriseRiskControl"):
        assert reads.get(source, 0) == 1, f"{source} was read {reads.get(source, 0)} times for 36 cells"


@pytest.mark.asyncio
async def test_matrix_summary_reports_truncation_for_the_whole_grid():
    rows = {"ComplianceEvidenceLink": [_cel("9001-7.2", link_id=n) for n in range(SOURCE_SCAN_LIMIT)]}
    summary = await _service(rows).get_matrix_summary(tenant_id=1, frameworks=["9001", "chas"], clause_numbers=["7.2"])
    assert summary["scan_truncated"] is True
    assert summary["scan_truncated_sources"] == ["evidence_links"]
    assert [cell["scan_truncated"] for cell in summary["cells"]] == [True, True]


@pytest.mark.asyncio
async def test_matrix_summary_attaches_framework_countdown_without_painting_pat_onto_iso():
    shelf = [
        {
            "scheme": "register",
            "name": "PAT test 2026",
            "metadata": {"certificate_type": "pat_testing"},
            "expiry_date": date(2026, 8, 20),
        },
        {
            "scheme": "register",
            "name": "ISO 9001 Certificate",
            "metadata": {"certificate_type": "iso9001"},
            "expiry_date": date(2026, 12, 1),
        },
    ]
    summary = await _service(shelf=shelf).get_matrix_summary(
        tenant_id=1, frameworks=["9001", "chas"], clause_numbers=["7.2"]
    )
    countdown = summary["framework_countdown"]
    assert countdown["unmatched_on_shelf"] is True
    assert countdown["frameworks"]["9001"]["name"] == "ISO 9001 Certificate"
    assert countdown["frameworks"]["9001"]["next_expiry"] == "2026-12-01"
    assert countdown["frameworks"]["chas"]["status"] == "none"
    assert countdown["frameworks"]["chas"]["next_expiry"] is None
