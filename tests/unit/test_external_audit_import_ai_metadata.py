"""Path-to-10 S1: external_audit_import AI metadata helper."""

from __future__ import annotations

from types import SimpleNamespace

from src.domain.services.external_audit_import_ai_metadata import apply_ai_metadata_to_job


def test_apply_ai_metadata_noop_when_incomplete() -> None:
    job = SimpleNamespace(
        organization_name=None,
        auditor_name=None,
        audit_type=None,
        certificate_number=None,
        audit_scope=None,
        next_audit_date=None,
        provenance_json={},
    )
    apply_ai_metadata_to_job(job, SimpleNamespace(provider_status="failed", organization_name="X"))
    assert job.organization_name is None
    assert job.provenance_json == {}


def test_apply_ai_metadata_copies_completed_fields() -> None:
    job = SimpleNamespace(
        organization_name=None,
        auditor_name=None,
        audit_type=None,
        certificate_number=None,
        audit_scope=None,
        next_audit_date=None,
        provenance_json={"existing": True},
    )
    result = SimpleNamespace(
        provider_status="completed",
        organization_name="Acme Ltd",
        auditor_name="A. Auditor",
        audit_type="surveillance",
        certificate_number="CERT-1",
        audit_scope="ISO 9001",
        next_audit_date="2027-01-15",
        site_name="Plant A",
        site_address="1 Road",
    )
    apply_ai_metadata_to_job(job, result)
    assert job.organization_name == "Acme Ltd"
    assert job.auditor_name == "A. Auditor"
    assert job.certificate_number == "CERT-1"
    assert job.next_audit_date.year == 2027
    assert job.provenance_json["organization_name"] == "Acme Ltd"
    assert job.provenance_json["site_name"] == "Plant A"
    assert job.provenance_json["existing"] is True
