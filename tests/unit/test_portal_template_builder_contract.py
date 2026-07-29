"""C-41: a published template field the builder never reads is data thrown away.

The portal's four intake paths are drifting from hardcoded forms to
template-driven ones. ``report/incident``, ``report/near-miss`` and
``report/complaint`` already render ``PortalDynamicForm`` from a published
template; ``report/rta`` still renders the hardcoded ``PortalRTAForm``
(``frontend/src/App.tsx``), which is why the published 'rta' template is
currently unreachable configuration.

Unreachable is not the same as harmless. The 'rta' template names the collision
date, time, vehicle registration and third-party answer differently from the keys
``build_rta_portal_fields`` reads, so converting ``report/rta`` the way
'incident-legacy' and 'near-miss-static' were already converted would silently
drop all four at once. And the names are not fixed by code review: they live in
admin-editable ``form_fields`` rows, so an administrator can reintroduce a
mismatch at runtime with no deploy and no gate.

This suite is that gate. For every published template it asserts that every field
the template defines is either read by that report type's builder or carried by a
named other mechanism, and that no date or time field may ever be excused.

Consumption is measured, not inferred: the builder is handed a submission that
records every key it is asked for, so keys reached through helper functions and
module-level key tuples count exactly as much as literal ``.get`` calls in the
builder body.
"""

from __future__ import annotations

import ast
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import pytest

from src.api.routes.employee_portal import (
    QuickReportCreate,
    build_complaint_portal_fields,
    build_incident_portal_fields,
    build_near_miss_portal_fields,
    build_rta_portal_fields,
)
from src.domain.models.complaint import ComplaintPriority
from src.domain.models.incident import IncidentSeverity

REPO_ROOT = Path(__file__).resolve().parents[2]
SEED_MIGRATION = REPO_ROOT / "alembic/versions/20260827_backfill_lookup_tenant_and_seed_portal_forms.py"

_PORTAL_TENANT_ID = 1


def _migration_literal(path: Path, name: str) -> Any:
    """Read a module-level literal out of a migration without importing it.

    Importing the module would need ``alembic.op``, which is only bound while a
    migration is running. Same approach as ``test_near_miss_contract_migrations``.
    """
    module = ast.parse(path.read_text(encoding="utf-8"))
    for node in module.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if any(isinstance(target, ast.Name) and target.id == name for target in targets):
                return ast.literal_eval(node.value)
    raise AssertionError(f"{name} not found in {path}")


PUBLISHED_TEMPLATES: tuple[dict[str, Any], ...] = _migration_literal(SEED_MIGRATION, "PORTAL_FORM_TEMPLATES")


# --- What the reporter's answers look like, per field_type ------------------
#
# Values only need to be plausible enough that the builder does not bail out
# before reaching a read. What is asserted is which keys were *asked for*.
_SAMPLE_BY_FIELD_TYPE: dict[str, Any] = {
    "date": "2026-03-04",
    "time": "13:45",
    "toggle": "yes",
    "select": "sample-option",
    "text": "sample text",
    "textarea": "sample longer text",
    "phone": "+441234567890",
    "location": "Depot A, Bay 3",
    "body_map": [{"body_part": "left hand"}],
    "image": {"count": 0, "files": []},
    "file": {"count": 0, "files": []},
}


class _RecordingSubmission(dict):
    """A submission dict that records every key the builder asks for.

    Subclasses ``dict`` so it is indistinguishable from a real
    ``reporter_submission`` to the builder and to every helper the builder hands
    it to — which is the point: a key reached via
    ``_NEAR_MISS_EVENT_DATETIME_KEYS`` or ``promote_injury_fields_from_submission``
    is just as consumed as one named inline.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.accessed: set[str] = set()

    def get(self, key: Any, default: Any = None) -> Any:
        self.accessed.add(key)
        return super().get(key, default)

    def __getitem__(self, key: Any) -> Any:
        self.accessed.add(key)
        return super().__getitem__(key)

    def __contains__(self, key: Any) -> bool:
        self.accessed.add(key)
        return super().__contains__(key)


# --- The register of fields no builder reads, and why ----------------------
#
# ``MECHANISM`` entries are carried by a named code path other than the builder
# and are correct as they stand. ``UNPROMOTED`` entries are measured gaps that
# this change does not close: the reporter's answer survives in the immutable
# ``reporter_submission`` snapshot but never reaches a typed column, so staff
# views cannot show it without reading raw JSON. They are listed so the gap is
# visible and frozen — not so it can be ignored.
#
# The register is asserted to be *exact*: an entry that stops being needed must
# be deleted, and no date or time field may be registered at all.
MECHANISM = "mechanism"
UNPROMOTED = "unpromoted"

FIELD_REGISTER: dict[str, dict[str, tuple[str, str]]] = {
    "incident": {
        "description": (MECHANISM, "QuickReportCreate.description — set on the record by the submit route"),
        "location": (MECHANISM, "QuickReportCreate.location — the builder reads report.location"),
        "photos": (MECHANISM, "uploaded via the portal attachment endpoint, not the JSON body"),
        "contract": (MECHANISM, "resolved to Incident.contract_id in the submit route"),
        "asset_number": (UNPROMOTED, "no Incident column; snapshot only"),
        "has_witnesses": (UNPROMOTED, "UI gate for witness_names, which is promoted"),
        "person_contact": (UNPROMOTED, "no Incident column for an involved person's number; snapshot only"),
        "person_role": (UNPROMOTED, "no Incident column; snapshot only"),
        "was_involved": (UNPROMOTED, "promoted on NearMiss but has no Incident column"),
    },
    "near-miss": {
        "description": (MECHANISM, "QuickReportCreate.description — set on the record by the submit route"),
        "location": (MECHANISM, "QuickReportCreate.location — the builder reads report.location"),
        "photos": (MECHANISM, "uploaded via the portal attachment endpoint, not the JSON body"),
    },
    "complaint": {
        "description": (MECHANISM, "QuickReportCreate.description — set on the record by the submit route"),
        "location": (MECHANISM, "QuickReportCreate.location — no Complaint site column to promote it to"),
        "photos": (MECHANISM, "uploaded via the portal attachment endpoint, not the JSON body"),
        "complainant_contact": (
            UNPROMOTED,
            "complainant_email/phone come from QuickReportCreate, not this field; snapshot only",
        ),
        "complainant_role": (UNPROMOTED, "no Complaint column; snapshot only"),
        "contract": (UNPROMOTED, "no contract resolution on the complaint path, unlike incident"),
        "impact": (UNPROMOTED, "no Complaint column; snapshot only"),
        "resolution_requested": (UNPROMOTED, "no Complaint column; snapshot only"),
    },
    "rta": {
        "description": (MECHANISM, "QuickReportCreate.description — set on the record by the submit route"),
        "location": (MECHANISM, "QuickReportCreate.location — the builder reads report.location"),
        "photos": (MECHANISM, "uploaded via the portal attachment endpoint, not the JSON body"),
        "contract": (UNPROMOTED, "no contract resolution on the RTA path, unlike incident"),
    },
}


def _template(slug: str) -> dict[str, Any]:
    for definition in PUBLISHED_TEMPLATES:
        if definition["slug"] == slug:
            return definition
    raise AssertionError(f"no published template with slug {slug!r}")


def _template_fields(slug: str) -> list[dict[str, Any]]:
    return [field for step in _template(slug)["steps"] for field in step["fields"]]


def _report(slug: str) -> QuickReportCreate:
    return QuickReportCreate(
        report_type=slug,
        title="Contract probe submission",
        description="A description long enough to satisfy the intake schema.",
        location="Depot A, Bay 3",
        severity="medium",
        reporter_name="Alex Reporter",
        reporter_email="alex@example.com",
    )


BUILDERS: dict[str, Callable[[QuickReportCreate, dict[str, Any]], dict[str, Any]]] = {
    "incident": lambda report, submission: build_incident_portal_fields(
        report, IncidentSeverity.LOW, submission, _PORTAL_TENANT_ID
    ),
    "near-miss": lambda report, submission: build_near_miss_portal_fields(
        report, "MEDIUM", submission, _PORTAL_TENANT_ID
    ),
    "complaint": lambda report, submission: build_complaint_portal_fields(
        report, ComplaintPriority.MEDIUM, submission, _PORTAL_TENANT_ID
    ),
    "rta": lambda report, submission: build_rta_portal_fields(report, submission, _PORTAL_TENANT_ID),
}


def _submission_for(slug: str) -> _RecordingSubmission:
    """A submission shaped exactly like the published template for *slug*."""
    submission = _RecordingSubmission(
        {field["name"]: _SAMPLE_BY_FIELD_TYPE[field["field_type"]] for field in _template_fields(slug)}
    )
    # The reporter's identity arrives on QuickReportCreate as well as (sometimes)
    # in the snapshot; without a name every builder raises 422 before reading
    # anything, which would make this suite pass for the wrong reason.
    submission["reporter_name"] = "Alex Reporter"
    return submission


def _keys_consumed(slug: str) -> set[str]:
    submission = _submission_for(slug)
    BUILDERS[slug](_report(slug), submission)
    return set(submission.accessed)


# --- The contract ----------------------------------------------------------


def test_every_report_path_has_a_published_template_and_a_builder() -> None:
    """All four intake paths are covered here, so none can drift unwatched."""
    slugs = {definition["slug"] for definition in PUBLISHED_TEMPLATES}

    assert slugs == {"incident", "near-miss", "complaint", "rta"}
    assert set(BUILDERS) == slugs
    assert set(FIELD_REGISTER) == slugs


@pytest.mark.parametrize("slug", ["incident", "near-miss", "complaint", "rta"])
def test_every_published_template_field_is_consumed_or_registered(slug: str) -> None:
    """A field the reporter is asked for must reach a column or be accounted for."""
    defined = {field["name"] for field in _template_fields(slug)}
    unread = defined - _keys_consumed(slug)
    unaccounted = sorted(unread - set(FIELD_REGISTER[slug]))

    assert not unaccounted, (
        f"the published '{slug}' template asks the reporter for "
        f"{unaccounted} but the builder never reads those keys, so the answers "
        "are discarded. Either read them in the builder or add them to "
        "FIELD_REGISTER with the mechanism that carries them."
    )


@pytest.mark.parametrize("slug", ["incident", "near-miss", "complaint", "rta"])
def test_no_date_or_time_field_may_be_excused(slug: str) -> None:
    """The register must never be usable to hide a lost date.

    ``received_date`` is what complaint time limits run from and ``collision_date``
    is what a road traffic collision is reported against. A date silently replaced
    by the submission instant is the whole of C-41.
    """
    registered_datetime_fields = sorted(
        field["name"]
        for field in _template_fields(slug)
        if field["field_type"] in ("date", "time") and field["name"] in FIELD_REGISTER[slug]
    )

    assert not registered_datetime_fields, (
        f"'{slug}' registers {registered_datetime_fields} as unread. Date and time "
        "fields carry the compliance clock and must be consumed by the builder."
    )


@pytest.mark.parametrize("slug", ["incident", "near-miss", "complaint", "rta"])
def test_the_register_holds_no_stale_entries(slug: str) -> None:
    """An entry that is no longer needed must be deleted, not left to rot.

    A register that outlives the gap it describes stops describing anything, and
    the next real mismatch hides behind it.
    """
    consumed = _keys_consumed(slug)
    defined = {field["name"] for field in _template_fields(slug)}

    stale = sorted(name for name in FIELD_REGISTER[slug] if name in consumed or name not in defined)

    assert not stale, f"FIELD_REGISTER['{slug}'] excuses {stale}, which the builder now reads or the template dropped"


@pytest.mark.parametrize("slug", ["incident", "near-miss", "complaint", "rta"])
def test_every_register_entry_names_a_reason(slug: str) -> None:
    for name, (kind, reason) in FIELD_REGISTER[slug].items():
        assert kind in (MECHANISM, UNPROMOTED), f"{slug}.{name} has an unknown register kind {kind!r}"
        assert reason.strip(), f"{slug}.{name} is registered with no reason"


# --- The RTA mismatch, end to end -----------------------------------------


def _rta_template_submission() -> dict[str, Any]:
    """A submission in the shape the published 'rta' template would produce."""
    return {
        "contract": "responsive_repairs",
        "location": "A14 westbound, junction 52",
        "incident_date": "2026-03-16",
        "incident_time": "18:05",
        "vehicle_reg": "ML23RRZ",
        "description": "Rear-ended while stationary on the slip road.",
        "third_party_involved": "yes",
        "photos": {"count": 0, "files": []},
        "reporter_name": "Dan Driver",
    }


def test_a_template_shaped_rta_keeps_its_date_time_and_registration() -> None:
    """The day report/rta is converted, none of this may go missing."""
    submission = _rta_template_submission()

    fields = build_rta_portal_fields(_report("rta"), submission, _PORTAL_TENANT_ID)

    assert fields["collision_date"].date().isoformat() == "2026-03-16"
    assert fields["collision_time"] == "18:05"
    assert fields["company_vehicle_registration"] == "ML23RRZ"
    assert fields["vehicles_involved_count"] >= 2, "a reported third party means more than one party"


def test_the_live_hardcoded_rta_keys_still_win() -> None:
    """RTA-2026-0002 posts accident_date / accident_time / pe_vehicle and works today.

    Accepting the template's names must not reorder that precedence: the live
    ``PortalRTAForm`` path is the one with real records behind it.
    """
    submission = {
        "pe_vehicle": "ML23RRZ",
        "accident_date": "2026-07-27",
        "accident_time": "08:15",
        # A stale template-shaped value must lose to the live one, not overwrite it.
        "incident_date": "2020-01-01",
        "incident_time": "23:59",
        "vehicle_reg": "WRONG1",
        "reporter_name": "UX Super",
    }

    fields = build_rta_portal_fields(_report("rta"), submission, _PORTAL_TENANT_ID)

    assert fields["collision_date"].date().isoformat() == "2026-07-27"
    assert fields["collision_time"] == "08:15"
    assert fields["company_vehicle_registration"] == "ML23RRZ"


def test_an_rta_with_no_date_under_any_accepted_key_still_records_the_collision() -> None:
    """Losing a collision report is worse than an imprecise timestamp."""
    fields = build_rta_portal_fields(_report("rta"), {"reporter_name": "Dan Driver"}, _PORTAL_TENANT_ID)

    assert fields["collision_date"] is not None
    assert fields["collision_time"] is None, "no time may be invented to go with a substituted date"


# --- The complaint date, which is a live loss ------------------------------


def test_the_reporters_complaint_date_becomes_received_date() -> None:
    """``received_date`` is the column complaint time limits are measured from."""
    submission = {"complaint_date": "2026-02-11", "complainant_name": "Carol Customer"}

    fields = build_complaint_portal_fields(
        _report("complaint"), ComplaintPriority.MEDIUM, submission, _PORTAL_TENANT_ID
    )

    assert fields["received_date"].date().isoformat() == "2026-02-11"


def test_a_complaint_with_no_stated_date_falls_back_to_the_submission_instant() -> None:
    before = datetime.now(timezone.utc)

    fields = build_complaint_portal_fields(
        _report("complaint"), ComplaintPriority.MEDIUM, {"complainant_name": "Carol Customer"}, _PORTAL_TENANT_ID
    )

    assert fields["received_date"] >= before


def test_an_unparseable_complaint_date_does_not_abort_intake() -> None:
    """Arbitrary client JSON must not turn a complaint into a 500."""
    submission = {"complaint_date": "not a date", "complainant_name": "Carol Customer"}
    before = datetime.now(timezone.utc)

    fields = build_complaint_portal_fields(
        _report("complaint"), ComplaintPriority.MEDIUM, submission, _PORTAL_TENANT_ID
    )

    assert fields["received_date"] >= before


def test_a_staff_shaped_received_date_is_also_accepted() -> None:
    """Template field names are admin-editable, so one spelling cannot be assumed."""
    submission = {"received_date": "2026-01-05", "complainant_name": "Carol Customer"}

    fields = build_complaint_portal_fields(
        _report("complaint"), ComplaintPriority.MEDIUM, submission, _PORTAL_TENANT_ID
    )

    assert fields["received_date"].date().isoformat() == "2026-01-05"
