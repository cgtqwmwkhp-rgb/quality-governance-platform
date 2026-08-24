"""Customer Feedback PR-3 — portal write path behind the kinds flag."""

from src.api.routes.employee_portal import (
    _PORTAL_REFERENCE_PREFIXES,
    _PORTAL_REFERENCE_REGISTERS,
    QuickReportCreate,
    build_complaint_portal_fields,
    portal_kind_prefix,
    resolve_portal_feedback_kind,
)
from src.domain.exceptions import ValidationError
from src.domain.models.complaint import ComplaintPriority, FeedbackKind


def _complaint_report(**overrides) -> QuickReportCreate:
    payload = {
        "report_type": "complaint",
        "title": "Late delivery crate",
        "description": "The delivery arrived three days late and the crate was damaged.",
        "reporter_name": "Sam Complainant",
        "severity": "medium",
    }
    payload.update(overrides)
    return QuickReportCreate(**payload)


def test_portal_registers_cover_kind_prefixes() -> None:
    assert _PORTAL_REFERENCE_REGISTERS["CMND"] == ("compliment", _PORTAL_REFERENCE_REGISTERS["COMP"][1])
    assert _PORTAL_REFERENCE_REGISTERS["SUGG"][0] == "suggestion"
    assert _PORTAL_REFERENCE_REGISTERS["FDBK"][0] == "general"
    assert "CMND-" in _PORTAL_REFERENCE_PREFIXES
    assert "SUGG-" in _PORTAL_REFERENCE_PREFIXES
    assert "FDBK-" in _PORTAL_REFERENCE_PREFIXES


def test_flag_off_portal_complaint_still_mints_comp() -> None:
    kind = resolve_portal_feedback_kind(_complaint_report(), {})
    assert kind is FeedbackKind.COMPLAINT
    assert portal_kind_prefix(kind) == "COMP"


def test_flag_off_rejects_portal_compliment(monkeypatch) -> None:
    from src.core.config import settings

    monkeypatch.setattr(settings, "customer_feedback_kinds_enabled", False)
    report = _complaint_report(feedback_kind="compliment")
    try:
        resolve_portal_feedback_kind(report, {"subject_name": "Alex Fitter"})
        raise AssertionError("expected ValidationError")
    except ValidationError as exc:
        assert "disabled" in exc.message


def test_flag_on_portal_compliment_requires_subject(monkeypatch) -> None:
    from src.core.config import settings

    monkeypatch.setattr(settings, "customer_feedback_kinds_enabled", True)
    report = _complaint_report(feedback_kind="compliment")
    try:
        resolve_portal_feedback_kind(report, {})
        raise AssertionError("expected ValidationError")
    except ValidationError as exc:
        assert "staff member" in exc.message


def test_flag_on_portal_compliment_uses_cmnd(monkeypatch) -> None:
    from src.core.config import settings

    monkeypatch.setattr(settings, "customer_feedback_kinds_enabled", True)
    report = _complaint_report(feedback_kind="compliment")
    kind = resolve_portal_feedback_kind(report, {"subject_name": "Alex Fitter"})
    assert kind is FeedbackKind.COMPLIMENT
    assert portal_kind_prefix(kind) == "CMND"


def test_flag_on_reads_kind_from_snapshot_when_body_omits_it(monkeypatch) -> None:
    from src.core.config import settings

    monkeypatch.setattr(settings, "customer_feedback_kinds_enabled", True)
    kind = resolve_portal_feedback_kind(
        _complaint_report(),
        {"feedback_kind": "suggestion"},
    )
    assert kind is FeedbackKind.SUGGESTION
    assert portal_kind_prefix(kind) == "SUGG"


def test_builder_promotes_kind_and_subject() -> None:
    fields = build_complaint_portal_fields(
        _complaint_report(),
        ComplaintPriority.MEDIUM,
        {"subject_name": "Alex Fitter", "complainant_name": "Sam Complainant"},
        tenant_id=1,
        feedback_kind=FeedbackKind.COMPLIMENT,
        subject_name="Alex Fitter",
    )
    assert fields["feedback_kind"] is FeedbackKind.COMPLIMENT
    assert fields["subject_name"] == "Alex Fitter"
