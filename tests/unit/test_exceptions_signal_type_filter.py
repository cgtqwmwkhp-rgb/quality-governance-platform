"""CUJ standards-map-inputs — exceptions signal_type server filter + reject rationale."""

from pydantic import ValidationError

from src.api.routes.governed_knowledge import RejectEvidenceRequest
from src.domain.models.compliance_evidence import EvidenceSignalType


def test_reject_evidence_request_requires_rationale_min_length():
    req = RejectEvidenceRequest(rationale="Not applicable to clause")
    assert req.rationale.startswith("Not")
    try:
        RejectEvidenceRequest(rationale="ab")
        assert False, "expected validation error"
    except ValidationError:
        pass


def test_evidence_signal_type_enum_covers_assessor_signals():
    assert EvidenceSignalType("gap").value == "gap"
    assert EvidenceSignalType("evidence").value == "evidence"
    assert EvidenceSignalType("nonconformity").value == "nonconformity"
    assert EvidenceSignalType("opportunity").value == "opportunity"
