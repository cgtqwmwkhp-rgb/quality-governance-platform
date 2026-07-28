"""The audit bridge must refuse an event it cannot persist, not discard it.

PX-155 / C-30. ``record_audit_event`` used to answer a missing tenant_id by
logging a warning, returning the unsaved ``AuditEvent``, and reporting a
``audit_completed`` business event with ``persisted="false"``. The caller could
not tell the difference between a written audit row and a dropped one, so 44 of
71 call sites silently wrote nothing — including ``permanent_delete`` and
``purge`` — and production held 39 audit rows in total with zero deletes among
them.

Two properties are pinned here:

* A tenant-less event raises, so the caller's transaction rolls back and the
  mutation is refused rather than performed unrecorded.
* Nothing on that path reports completion. A metric named ``audit_completed``
  firing when no row was written makes a dashboard state the opposite of the
  truth.
"""

from __future__ import annotations

import inspect

import pytest

from src.domain.exceptions import AuditNotRecordableError, DomainError
from src.domain.services import audit_service
from src.domain.services.audit_service import record_audit_event

EVENT = {
    "event_type": "audit_template.permanently_deleted",
    "entity_type": "audit_template",
    "entity_id": "4242",
    "action": "permanent_delete",
    "description": "Template 'Depot weekly' permanently deleted",
}


class _ExplodingSession:
    """Any database use on the refusal path is itself a failure."""

    def __getattr__(self, name: str):  # pragma: no cover - only on regression
        raise AssertionError(f"the bridge touched the session ({name}) before refusing")


@pytest.fixture
def captured_events(monkeypatch) -> list[tuple[str, dict[str, str]]]:
    events: list[tuple[str, dict[str, str]]] = []
    monkeypatch.setattr(
        audit_service,
        "track_business_event",
        lambda name, properties=None: events.append((name, properties or {})),
    )
    return events


@pytest.mark.asyncio
async def test_tenantless_event_raises_instead_of_returning_it_unsaved(captured_events) -> None:
    with pytest.raises(AuditNotRecordableError) as exc:
        await record_audit_event(db=_ExplodingSession(), **EVENT, tenant_id=None)

    # The message has to name the event, or an alert on it is not actionable.
    assert "permanent_delete" in str(exc.value) or "permanently_deleted" in str(exc.value)
    assert "tenant_id" in str(exc.value)


@pytest.mark.asyncio
async def test_refusal_does_not_report_audit_completed(captured_events) -> None:
    with pytest.raises(AuditNotRecordableError):
        await record_audit_event(db=_ExplodingSession(), **EVENT, tenant_id=None)

    reported = [name for name, _ in captured_events]
    assert "audit_completed" not in reported, (
        "the non-persisted path still reports completion, so any dashboard "
        "counting audit_completed overstates audit coverage"
    )


@pytest.mark.asyncio
async def test_refusal_reports_a_distinctly_named_failure_event(captured_events) -> None:
    with pytest.raises(AuditNotRecordableError):
        await record_audit_event(db=_ExplodingSession(), **EVENT, tenant_id=None)

    assert [name for name, _ in captured_events] == ["audit_not_recorded"]
    properties = captured_events[0][1]
    assert properties["action"] == "permanent_delete"
    assert properties["reason"] == "no_tenant"


def test_tenant_id_is_required_and_keyword_only() -> None:
    """An omitted tenant must be a TypeError at the call site, not a silent drop."""
    parameter = inspect.signature(record_audit_event).parameters["tenant_id"]

    assert parameter.default is inspect.Parameter.empty
    assert parameter.kind is inspect.Parameter.KEYWORD_ONLY


def test_the_error_is_a_domain_error_so_the_envelope_stays_consistent() -> None:
    """Raised inside a request, it must render as the standard 500 envelope."""
    assert issubclass(AuditNotRecordableError, DomainError)
    assert AuditNotRecordableError("x").http_status == 500
