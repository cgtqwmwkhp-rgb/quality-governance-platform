"""Write-contract guards: catch silently dropped fields and unusable options.

Two independent verifications of build ``c95350b`` kept finding the same shape
of defect — a write endpoint accepts a request, returns 2xx, and quietly does
not honour part of what was sent. PX-168 (``owner_id`` discarded, 201 returned
for an unowned action), PX-281/282 (the only ``complaint_type`` the form offers
is not in the backend enum) and PX-327 (attachments accepted, never readable
back) are three instances. This module turns that shape into a CI guard.

Four guards, all driven off ``app.openapi()`` so that a newly registered
endpoint is covered without anyone remembering to add it here:

1. **Round-trip echo** — a field a client can send must be readable back.
2. **Unknown-field rejection** — an unrecognised body field must 422, not be
   ignored.
3. **Enum/lookup agreement** — every option a seeded lookup offers must be
   accepted by the field it populates.
4. **Response/request symmetry** — settable state the API returns must be
   sendable.

Relationship to the existing Schemathesis job ("Schemathesis API Property
Tests (D10)", ``tests/integration/test_schemathesis_api.py``): that job fuzzes
a *running* app for 5xx and response-schema conformance, and needs Postgres,
Redis and a live uvicorn. These guards are static and need none of that, which
is why they live in ``tests/contract/`` and run in the ``contract-tests`` job.
They are complementary — Schemathesis checks that responses match the declared
schema; these check that the declared schemas agree with each other and with
the seeded configuration. Schemathesis cannot catch PX-168, because returning
``owner_id: null`` conforms to ``ActionResponse`` perfectly.

Known blind spot — PX-327 specifically. These guards compare *declared* schema
fields, so they catch a field that one side declares and the other does not.
``attachments`` is declared on neither the incident request nor the response
model, so there is nothing for a schema-driven check to compare and this module
does **not** detect it. Guard 1 catches the general class (a field that can be
written with no read path); catching PX-327 itself needs a test that uploads to
the attachment endpoint and then re-reads the incident, which is a fixture cost
this module deliberately does not carry. It is called out here so nobody reads
green as evidence that PX-327 is fixed.

Known gaps live in ``_write_contract_baseline.py``. Each guard is therefore two
tests: an **active** one that fails when a gap appears that is not recorded
(the gate that keeps the backlog from growing), and an **xfail** one asserting
the goal state (the roadmap, which flips to XPASS when someone fixes it).
"""

from __future__ import annotations

import pytest

from tests.contract._write_contract_baseline import (
    KNOWN_ASYMMETRIC_RESPONSE_FIELDS,
    KNOWN_LAX_WRITE_SCHEMAS,
    KNOWN_LOOKUP_ENUM_GAPS,
    KNOWN_UNREADABLE_REQUEST_FIELDS,
)
from tests.contract._write_contract_support import (
    LOOKUP_BINDINGS,
    LookupBinding,
    Resource,
    WriteOperation,
    accepted_values,
    asymmetric_fields,
    forbids_extra_fields,
    format_gap_list,
    is_resource_write,
    operations_using,
    readable_resources,
    resolve_properties,
    seeded_lookup_codes,
    unreadable_request_fields,
    write_operations,
)

# ---------------------------------------------------------------------------
# Parametrisation
#
# Discovery runs at collection time, which means importing the application.
# That costs a few seconds once and buys coverage of every endpoint instead of
# a hand-maintained list that would rot the next time someone adds a router.
# ---------------------------------------------------------------------------


def _resource_params() -> list[pytest.param]:
    params = []
    for resource in readable_resources():
        recorded = KNOWN_ASYMMETRIC_RESPONSE_FIELDS.get(resource.response_model, ())
        marks = (
            pytest.mark.xfail(
                reason=(
                    f"{resource.response_model} returns {len(recorded)} field(s) no writer accepts: "
                    f"{format_gap_list(recorded)}"
                ),
                strict=False,
            ),
        )
        params.append(pytest.param(resource, id=resource.response_model, marks=marks if recorded else ()))
    return params


def _write_op_params() -> list[pytest.param]:
    params = []
    for op in write_operations():
        if not is_resource_write(op):
            continue
        recorded = KNOWN_UNREADABLE_REQUEST_FIELDS.get(op.label, ())
        marks = (
            pytest.mark.xfail(
                reason=(f"{op.label} accepts {len(recorded)} field(s) it never returns: {format_gap_list(recorded)}"),
                strict=False,
            ),
        )
        params.append(pytest.param(op, id=op.label, marks=marks if recorded else ()))
    return params


def _lookup_params() -> list[pytest.param]:
    params = []
    for binding in LOOKUP_BINDINGS:
        key = (binding.category, binding.request_model, binding.field)
        recorded = KNOWN_LOOKUP_ENUM_GAPS.get(key, ())
        marks = (
            pytest.mark.xfail(
                reason=(
                    f"{binding.category} offers {len(recorded)} option(s) that "
                    f"{binding.request_model}.{binding.field} rejects with 422: {format_gap_list(recorded)}"
                ),
                strict=False,
            ),
        )
        params.append(pytest.param(binding, id=_binding_id(binding), marks=marks if recorded else ()))
    return params


def _binding_id(binding: LookupBinding) -> str:
    """Test id that stays unique when one category feeds several models."""
    return f"{binding.category}->{binding.request_model}.{binding.field}"


RESOURCE_PARAMS = _resource_params()
WRITE_OP_PARAMS = _write_op_params()
LOOKUP_PARAMS = _lookup_params()


# ---------------------------------------------------------------------------
# Guard 1 — round-trip echo (static half)
# ---------------------------------------------------------------------------


class TestRoundTripEcho:
    """A field a client can send must be readable back off the same resource.

    The runtime half of this guard — POST a populated payload and diff the
    response against it — lives in ``test_write_contract_roundtrip.py``. This
    half is the schema-level precondition: if the response model has nowhere to
    *put* the value, no amount of correct service-layer code makes the write
    observable.
    """

    @pytest.mark.parametrize("op", WRITE_OP_PARAMS)
    def test_every_request_field_is_readable_back(self, op: WriteOperation) -> None:
        gaps = unreadable_request_fields(op)
        assert not gaps, (
            f"{op.label} accepts {len(gaps)} field(s) that {op.response_model} never returns: "
            f"{format_gap_list(gaps)}. A client cannot confirm these persisted. Either add them to "
            f"{op.response_model}, or record them in KNOWN_UNREADABLE_REQUEST_FIELDS with a reason."
        )

    @pytest.mark.parametrize(
        "op",
        [pytest.param(op, id=op.label) for op in write_operations() if is_resource_write(op)],
    )
    def test_no_unrecorded_write_only_fields(self, op: WriteOperation) -> None:
        """Active gate: a *new* write-only field must not appear unrecorded."""
        recorded = set(KNOWN_UNREADABLE_REQUEST_FIELDS.get(op.label, ()))
        new_gaps = sorted(set(unreadable_request_fields(op)) - recorded)
        assert not new_gaps, (
            f"{op.label} has NEW write-only field(s) not in the recorded backlog: "
            f"{format_gap_list(new_gaps)}. These are accepted by {op.request_model} but never returned "
            f"by {op.response_model}, so a client cannot read them back. Add them to the response model."
        )


# ---------------------------------------------------------------------------
# Guard 2 — unknown-field rejection
# ---------------------------------------------------------------------------


class TestUnknownFieldRejection:
    """An unrecognised body field must be rejected, not silently discarded.

    ``additionalProperties: false`` in the generated schema is emitted only by
    ``model_config = ConfigDict(extra="forbid")``, and that config is exactly
    what makes FastAPI return 422 for an unknown field. So this is a faithful
    static proxy for the runtime behaviour, and it covers all 296 write schemas
    rather than the handful a request-driven test could afford to exercise.

    Enumerating all 296 as individual xfails would bury the CI log, so the
    per-schema list lives in ``KNOWN_LAX_WRITE_SCHEMAS`` and is asserted in
    aggregate here.
    """

    def test_no_new_write_schema_ignores_unknown_fields(self) -> None:
        """Active gate: a newly added write schema must reject unknown fields.

        This also catches regression in the other direction. Once a schema is
        fixed and removed from ``KNOWN_LAX_WRITE_SCHEMAS``, deleting its
        ``extra="forbid"`` puts it back in ``current_lax`` while it is no
        longer recorded, so it fails here.
        """
        current_lax = {op.request_model for op in write_operations() if not forbids_extra_fields(op.request_model)}
        unrecorded = sorted(current_lax - KNOWN_LAX_WRITE_SCHEMAS)
        assert not unrecorded, (
            f"{len(unrecorded)} write schema(s) accept unknown body fields and are not in the recorded "
            f"backlog: {format_gap_list(unrecorded)}. Add "
            f'`model_config = ConfigDict(extra="forbid")` so an unrecognised field returns 422 instead '
            f"of being silently dropped (PX-168). Endpoints affected: "
            f"{format_gap_list({label for name in unrecorded for label in operations_using(name)}, limit=6)}"
        )

    @pytest.mark.xfail(
        reason=(
            f"{len(KNOWN_LAX_WRITE_SCHEMAS)} write schemas still default to Pydantic extra='ignore' and "
            "silently discard unknown body fields. See KNOWN_LAX_WRITE_SCHEMAS for the full list."
        ),
        strict=False,
    )
    def test_all_write_schemas_reject_unknown_fields(self) -> None:
        """Goal state. XPASSes when the backlog is cleared."""
        lax = sorted({op.request_model for op in write_operations() if not forbids_extra_fields(op.request_model)})
        assert not lax, f"{len(lax)} write schemas ignore unknown fields: {format_gap_list(lax)}"


# ---------------------------------------------------------------------------
# Guard 3 — enum / lookup agreement
# ---------------------------------------------------------------------------


class TestLookupEnumAgreement:
    """Every option a seeded lookup offers must be accepted by the field it fills.

    PX-281/282 was ``complaint_types`` offering only ``workmanship``, which
    ``ComplaintType`` has never contained. #1385 realigned that taxonomy (and
    ``incident_types``) to the enums; the active gate below holds the seed and
    the schema together so the drift cannot return unrecorded.

    ``severity_levels`` was the last residual: it feeds three fields and
    ``negligible`` was accepted by incident severity but not by complaint
    priority or near-miss potential severity. B-9 settled that as one shared
    severity set, so ``KNOWN_LOOKUP_ENUM_GAPS`` is now empty and every parameter
    below is an active assertion rather than an xfail.
    """

    @pytest.mark.parametrize("binding", LOOKUP_PARAMS)
    def test_every_seeded_option_is_accepted(self, binding: LookupBinding) -> None:
        prop = resolve_properties(binding.request_model).get(binding.field)
        assert prop is not None, (
            f"Lookup binding points at {binding.request_model}.{binding.field}, which no longer exists. "
            f"Update LOOKUP_BINDINGS. UI evidence for the binding: {binding.ui_evidence}"
        )
        accepted = accepted_values(prop)
        assert accepted, (
            f"{binding.request_model}.{binding.field} is no longer a closed value set, so the "
            f"'{binding.category}' lookup can no longer be checked against it. Update LOOKUP_BINDINGS."
        )
        codes = seeded_lookup_codes(binding.category)
        assert codes, f"Lookup category '{binding.category}' seeds no options; the form would be empty."

        rejected = [code for code in codes if code not in accepted]
        endpoints = format_gap_list(operations_using(binding.request_model), limit=4)
        assert not rejected, (
            f"Lookup category '{binding.category}' offers {len(rejected)} of {len(codes)} option(s) that "
            f"{binding.request_model}.{binding.field} rejects with 422: {format_gap_list(rejected)}. "
            f"A user picking one of these from the form cannot submit at all. "
            f"Affected endpoint(s): {endpoints}. Accepted values are: {format_gap_list(accepted)}. "
            f"Fix by extending the backend enum or correcting the seeded codes — they must agree. "
            f"UI binding evidence: {binding.ui_evidence}"
        )

    @pytest.mark.parametrize("binding", [pytest.param(b, id=_binding_id(b)) for b in LOOKUP_BINDINGS])
    def test_no_unrecorded_lookup_gaps(self, binding: LookupBinding) -> None:
        """Active gate: adding a seed option with no matching enum member fails here."""
        prop = resolve_properties(binding.request_model).get(binding.field)
        if prop is None:
            pytest.fail(f"LOOKUP_BINDINGS references a missing field: {binding.request_model}.{binding.field}")
        accepted = accepted_values(prop)
        recorded = set(KNOWN_LOOKUP_ENUM_GAPS.get((binding.category, binding.request_model, binding.field), ()))
        new_gaps = [c for c in seeded_lookup_codes(binding.category) if c not in accepted and c not in recorded]
        assert not new_gaps, (
            f"NEW unusable option(s) in lookup category '{binding.category}': {format_gap_list(new_gaps)}. "
            f"{binding.request_model}.{binding.field} rejects them, so the form offers a choice that "
            f"cannot be submitted. Add the matching enum member before seeding the option."
        )


# ---------------------------------------------------------------------------
# Guard 4 — response / request symmetry
# ---------------------------------------------------------------------------


class TestResponseRequestSymmetry:
    """State the API returns as settable must be settable.

    This is PX-168 stated as a rule. ``ActionResponse`` returns ``owner_id``;
    ``ActionCreate`` and ``ActionUpdate`` between them have no field that can
    receive it. A client that reads an action, changes the owner and posts it
    back gets 201 and an unowned action.

    Fields excluded from the rule — identity, audit stamps, server-computed
    values, lifecycle timestamps and path parameters — are listed explicitly in
    ``_write_contract_support`` rather than being pattern-matched away here, so
    that widening the exclusion is a visible change in review.
    """

    @pytest.mark.parametrize("resource", RESOURCE_PARAMS)
    def test_returned_state_is_settable(self, resource: Resource) -> None:
        gaps = asymmetric_fields(resource)
        assert not gaps, (
            f"{resource.response_model} returns {len(gaps)} field(s) that no writer accepts: "
            f"{format_gap_list(gaps)}. A client cannot set state the API shows it. "
            f"Writer(s): {format_gap_list(resource.operations, limit=4)}. "
            f"Either add the field to the create/update model, or mark it server-controlled in "
            f"_write_contract_support.SERVER_OWNED_FIELDS with a reason."
        )

    @pytest.mark.parametrize(
        "resource",
        [pytest.param(r, id=r.response_model) for r in readable_resources()],
    )
    def test_no_unrecorded_asymmetry(self, resource: Resource) -> None:
        """Active gate: a new unsettable-but-returned field must not appear."""
        recorded = set(KNOWN_ASYMMETRIC_RESPONSE_FIELDS.get(resource.response_model, ()))
        new_gaps = sorted(set(asymmetric_fields(resource)) - recorded)
        assert not new_gaps, (
            f"{resource.response_model} has NEW field(s) it returns but no writer accepts: "
            f"{format_gap_list(new_gaps)}. This is the PX-168 shape: the API advertises state the "
            f"client has no way to set. Writer(s): {format_gap_list(resource.operations, limit=4)}."
        )


# ---------------------------------------------------------------------------
# Discovery self-checks
#
# The guards are only as good as the discovery behind them. If a refactor makes
# discovery silently return nothing, every guard above would pass vacuously.
# ---------------------------------------------------------------------------


class TestDiscoveryIsNotVacuous:
    """Fail loudly if schema discovery stops finding anything to check."""

    def test_write_operations_discovered(self) -> None:
        ops = write_operations()
        assert len(ops) > 200, f"Only {len(ops)} write operations discovered; discovery is probably broken."

    def test_resource_writes_discovered(self) -> None:
        resource_writes = [op for op in write_operations() if is_resource_write(op)]
        assert len(resource_writes) > 50, (
            f"Only {len(resource_writes)} resource writes discovered from {len(write_operations())} write "
            "operations; the readable-model filter is probably broken."
        )

    def test_readable_resources_discovered(self) -> None:
        assert len(readable_resources()) > 40, "Readable-resource grouping found almost nothing."

    def test_every_lookup_binding_resolves(self) -> None:
        """Guard 3's pairings are hand-maintained; catch them going stale."""
        unresolved = [
            f"{b.request_model}.{b.field}"
            for b in LOOKUP_BINDINGS
            if resolve_properties(b.request_model).get(b.field) is None
        ]
        assert not unresolved, (
            f"LOOKUP_BINDINGS references field(s) that no longer exist: {format_gap_list(unresolved)}. "
            "The lookup/enum guard is silently not checking them."
        )

    def test_seed_categories_are_covered_or_unbound(self) -> None:
        """Every seeded lookup category should either be paired or knowingly unpaired.

        ``workforce_roles``, ``medical_assistance`` and ``emergency_services``
        are seeded but populate free-text or portal-only fields with no closed
        value set on the API side, so there is nothing to compare them against.
        """
        from src.domain.services.lookup_defaults_seed_data import SEED_CATEGORIES

        unbound_by_design = {"workforce_roles", "medical_assistance", "emergency_services"}
        bound = {b.category for b in LOOKUP_BINDINGS}
        unaccounted = sorted(set(SEED_CATEGORIES) - bound - unbound_by_design)
        assert not unaccounted, (
            f"Lookup category/categories {format_gap_list(unaccounted)} are seeded but not checked against "
            "any API field. Add a LOOKUP_BINDINGS entry (with UI evidence) or list them as unbound."
        )

    def test_enum_backed_categories_have_no_recorded_gaps(self) -> None:
        """1:1 enum-backed lookups must stay out of KNOWN_LOOKUP_ENUM_GAPS.

        Those categories are held by ``lookup_enum_contract`` (seed + admin write
        + integration probe). Recording a gap here would re-xfail a defect the
        durable contract already forbids.
        """
        from src.domain.services.lookup_enum_contract import ENUM_BACKED_CATEGORIES
        from tests.contract._write_contract_baseline import KNOWN_LOOKUP_ENUM_GAPS

        leaked = sorted(
            f"{category}->{model}.{field}"
            for (category, model, field), codes in KNOWN_LOOKUP_ENUM_GAPS.items()
            if category in ENUM_BACKED_CATEGORIES and codes
        )
        assert not leaked, (
            f"Enum-backed lookup gap(s) recorded in the write-contract baseline: "
            f"{format_gap_list(leaked)}. Clear them — the durable contract owns these."
        )
