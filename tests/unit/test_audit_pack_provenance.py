"""GKB WL1: server-side audit pack provenance + signal_type honesty."""

from __future__ import annotations

from datetime import datetime, timezone

from src.domain.services.iso_compliance_service import (
    EvidenceLink,
    ISOComplianceService,
    ISOStandard,
    audit_pack_signal_label,
    serialize_audit_pack_link,
)


def _level2_clause_id(standard: ISOStandard = ISOStandard.ISO_9001) -> str:
    svc = ISOComplianceService()
    clause = next(c for c in svc.get_all_clauses(standard) if c.level == 2)
    return clause.id


def _link(
    *,
    clause_id: str,
    signal_type: str | None,
    entity_type: str = "document",
    entity_id: str = "1",
    link_id: str = "1",
    rationale: str | None = "Mapped because procedure covers clause scope",
    scheme: str | None = "iso9001",
    status: str | None = "confirmed",
    created_by: str | None = "auditor@example.com",
    confirmed_by: str | None = "auditor@example.com",
) -> EvidenceLink:
    now = datetime(2026, 7, 13, 12, 0, tzinfo=timezone.utc)
    return EvidenceLink(
        id=link_id,
        entity_type=entity_type,
        entity_id=entity_id,
        clause_id=clause_id,
        linked_by="ai",
        confidence=0.91,
        created_at=now,
        created_by=created_by,
        title="Evidence row",
        notes="note",
        signal_type=signal_type,
        rationale=rationale,
        scheme=scheme,
        status=status,
        confirmed_at=now,
        confirmed_by=confirmed_by,
        auto_applied=False,
    )


class TestAuditPackSignalLabels:
    def test_evidence_labelled_as_conformance(self) -> None:
        assert audit_pack_signal_label("evidence") == "conformance_evidence"

    def test_nonconformity_labelled_honestly(self) -> None:
        assert audit_pack_signal_label("nonconformity") == "operational_nonconformity"

    def test_legacy_null_labelled(self) -> None:
        assert audit_pack_signal_label(None) == "legacy_untyped_evidence"


class TestSerializeAuditPackLink:
    def test_includes_full_provenance_fields(self) -> None:
        clause_id = _level2_clause_id()
        row = serialize_audit_pack_link(
            _link(clause_id=clause_id, signal_type="evidence"),
            scheme_or_standard="iso9001",
        )
        for field in (
            "created_at",
            "created_by",
            "actor",
            "rationale",
            "confidence",
            "signal_type",
            "scheme",
            "standard",
            "clause_id",
            "entity_type",
            "entity_id",
            "status",
            "confirmed_at",
            "confirmed_by",
        ):
            assert field in row
            assert row[field] is not None
        assert row["conformance_eligible"] is True
        assert row["signal_label"] == "conformance_evidence"


class TestBuildAuditPackNonconformityHonesty:
    def test_nonconformity_excluded_from_conformance_evidence_by_default(self) -> None:
        svc = ISOComplianceService()
        clause_id = _level2_clause_id()
        links = [
            _link(clause_id=clause_id, signal_type="evidence", link_id="e1"),
            _link(
                clause_id=clause_id,
                signal_type="nonconformity",
                entity_type="incident",
                entity_id="99",
                link_id="nc1",
                rationale="Incident indicates clause breach",
            ),
        ]

        pack = svc.build_audit_pack(links, include_nonconformity=False)

        assert pack["provenance_policy"]["nonconformity_mode"] == "excluded_from_conformance_evidence"
        assert pack["counts"]["conformance_evidence_links"] == 1
        assert pack["counts"]["operational_signal_links"] == 1
        assert pack["counts"]["exported_evidence_links"] == 1
        assert [row["id"] for row in pack["evidence_links"]] == ["e1"]
        assert pack["operational_signals"][0]["id"] == "nc1"
        assert pack["operational_signals"][0]["signal_type"] == "nonconformity"
        assert pack["operational_signals"][0]["conformance_eligible"] is False
        assert pack["operational_signals"][0]["signal_label"] == "operational_nonconformity"
        assert "nonconformity" not in {row["signal_type"] for row in pack["evidence_links"]}

    def test_nonconformity_included_but_labelled_when_requested(self) -> None:
        svc = ISOComplianceService()
        clause_id = _level2_clause_id()
        links = [
            _link(clause_id=clause_id, signal_type="evidence", link_id="e1"),
            _link(
                clause_id=clause_id,
                signal_type="nonconformity",
                entity_type="incident",
                entity_id="99",
                link_id="nc1",
            ),
        ]

        pack = svc.build_audit_pack(links, include_nonconformity=True)

        assert pack["provenance_policy"]["nonconformity_mode"] == "labelled_in_pack"
        assert pack["counts"]["exported_evidence_links"] == 2
        by_id = {row["id"]: row for row in pack["evidence_links"]}
        assert by_id["e1"]["conformance_eligible"] is True
        assert by_id["nc1"]["conformance_eligible"] is False
        assert by_id["nc1"]["signal_label"] == "operational_nonconformity"
        assert by_id["nc1"]["signal_type"] == "nonconformity"

    def test_gap_and_opportunity_also_excluded_by_default(self) -> None:
        svc = ISOComplianceService()
        clause_id = _level2_clause_id()
        links = [
            _link(clause_id=clause_id, signal_type="gap", link_id="g1", entity_type="near_miss"),
            _link(
                clause_id=clause_id,
                signal_type="opportunity",
                link_id="o1",
                entity_type="complaint",
            ),
        ]
        pack = svc.build_audit_pack(links, include_nonconformity=False)
        assert pack["evidence_links"] == []
        assert pack["counts"]["operational_signal_links"] == 2
        labels = {row["signal_label"] for row in pack["operational_signals"]}
        assert labels == {"operational_gap", "operational_opportunity"}
