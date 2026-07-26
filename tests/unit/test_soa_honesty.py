"""PX-251: SoA must not invent org names or applicability justifications."""

from src.domain.services.iso_compliance_service import EvidenceLink, ISOStandard, iso_compliance_service


def test_soa_without_org_name_does_not_print_organisation_placeholder():
    soa = iso_compliance_service.generate_soa([], organization_name=None)
    assert soa["organization"] is None
    blob = str(soa)
    assert "Organisation" not in blob
    assert soa["total_controls"] == 93


def test_soa_evidence_free_controls_have_no_justification():
    soa = iso_compliance_service.generate_soa([], organization_name="Plantexpand Limited")
    assert soa["organization"] == "Plantexpand Limited"
    for control in soa["controls"]:
        assert control["justification"] is None
        assert control["justification_source"] == "not_recorded"
        assert control["applicability_decision"] == "not_recorded"
        assert control["applicable"] is None


def test_soa_evidence_backed_control_derives_justification():
    annex = [
        c
        for c in iso_compliance_service.get_all_clauses(ISOStandard.ISO_27001)
        if c.clause_number.startswith("A.") and c.level == 2
    ]
    assert annex
    link = EvidenceLink(
        id="1",
        entity_type="document",
        entity_id="42",
        clause_id=annex[0].id,
        linked_by="manual",
        confidence=0.9,
        title="ISMS Policy",
    )
    soa = iso_compliance_service.generate_soa([link], organization_name="Plantexpand Limited")
    matched = next(c for c in soa["controls"] if c["clause_id"] == annex[0].id)
    assert matched["justification_source"] == "derived_from_evidence"
    assert matched["justification"] is not None
    assert "ISMS Policy" in matched["justification"]
    assert "applicable to" not in matched["justification"].lower()
