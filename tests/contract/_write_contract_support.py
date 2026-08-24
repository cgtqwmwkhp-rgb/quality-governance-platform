"""Shared OpenAPI discovery for the API write-contract guards.

The guards in ``test_write_contract_guards.py`` are driven off the generated
OpenAPI document rather than a hand-maintained endpoint list, so a new write
endpoint is covered the moment it is registered on the router. This module
does the discovery; the test module does the asserting.

Generating the schema needs no database — ``app.openapi()`` only introspects
the registered routes and their Pydantic models — which is what lets these
guards run in the ``contract-tests`` CI job, where no Postgres service exists.

Module name is underscore-prefixed so pytest's ``python_files = test_*.py``
does not try to collect it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Iterable

WRITE_METHODS = ("post", "put", "patch")
JSON_CONTENT_TYPE = "application/json"
SUCCESS_CODES = ("200", "201")


@lru_cache(maxsize=1)
def openapi_schema() -> dict[str, Any]:
    """Return the generated OpenAPI document.

    Imported lazily so that merely importing this module does not pull in the
    whole application (and its database engine) at pytest collection time.
    """
    from src.main import app

    return app.openapi()


@lru_cache(maxsize=1)
def _components() -> dict[str, Any]:
    return openapi_schema().get("components", {}).get("schemas", {})


def _ref_name(node: dict[str, Any] | None) -> str | None:
    """Return the component name of a ``$ref`` node, or None."""
    if not node:
        return None
    ref = node.get("$ref")
    if not isinstance(ref, str) or not ref.startswith("#/components/schemas/"):
        return None
    return ref.rsplit("/", 1)[-1]


def resolve_properties(name: str, _seen: frozenset[str] = frozenset()) -> dict[str, dict[str, Any]]:
    """Flatten a component schema's properties, following ``allOf`` composition.

    Pydantic emits inheritance (``IncidentCreate(IncidentBase)``) as ``allOf``,
    so a naive read of ``properties`` sees only the fields declared on the leaf
    class. Cycle-safe: self-referential models (a tree node whose children are
    the same model) would otherwise recurse forever.
    """
    if name in _seen:
        return {}
    seen = _seen | {name}
    schema = _components().get(name, {})
    props: dict[str, dict[str, Any]] = dict(schema.get("properties") or {})
    for sub in schema.get("allOf") or []:
        sub_name = _ref_name(sub)
        if sub_name:
            props.update(resolve_properties(sub_name, seen))
        else:
            props.update(sub.get("properties") or {})
    return props


def forbids_extra_fields(name: str) -> bool:
    """True when the component schema rejects unknown properties.

    Pydantic's ``model_config = ConfigDict(extra="forbid")`` is the only thing
    that emits ``additionalProperties: false``; the default ``extra="ignore"``
    emits nothing. So this is a faithful read of whether the endpoint 422s on
    an unrecognised body field or silently discards it.
    """
    schema = _components().get(name, {})
    if schema.get("additionalProperties") is False:
        return True
    return any((sub.get("additionalProperties") is False) for sub in (schema.get("allOf") or []))


@dataclass(frozen=True)
class WriteOperation:
    """One request-body-bearing write operation discovered in the OpenAPI doc."""

    method: str
    path: str
    request_model: str
    response_model: str | None
    path_params: frozenset[str]

    @property
    def label(self) -> str:
        """Human-actionable identifier used in assertion messages and test ids."""
        return f"{self.method} {self.path}"


def _path_params(path_item: dict[str, Any], operation: dict[str, Any]) -> frozenset[str]:
    params: set[str] = set()
    for source in (path_item.get("parameters") or [], operation.get("parameters") or []):
        for param in source:
            if isinstance(param, dict) and param.get("in") == "path":
                params.add(str(param.get("name")))
    return frozenset(params)


def _success_response_model(operation: dict[str, Any]) -> str | None:
    responses = operation.get("responses") or {}
    for code in SUCCESS_CODES:
        content = (responses.get(code) or {}).get("content") or {}
        name = _ref_name((content.get(JSON_CONTENT_TYPE) or {}).get("schema"))
        if name:
            return name
    return None


@lru_cache(maxsize=1)
def write_operations() -> tuple[WriteOperation, ...]:
    """Every POST/PUT/PATCH operation that takes a ``$ref``-modelled JSON body.

    Operations with an inline (anonymous) body schema are skipped: there is no
    named model to reason about, and in this codebase they are file uploads and
    form posts rather than resource writes.
    """
    found: list[WriteOperation] = []
    for path, path_item in openapi_schema().get("paths", {}).items():
        for method, operation in path_item.items():
            if method not in WRITE_METHODS or not isinstance(operation, dict):
                continue
            body = (operation.get("requestBody") or {}).get("content") or {}
            request_model = _ref_name((body.get(JSON_CONTENT_TYPE) or {}).get("schema"))
            if not request_model:
                continue
            found.append(
                WriteOperation(
                    method=method.upper(),
                    path=path,
                    request_model=request_model,
                    response_model=_success_response_model(operation),
                    path_params=_path_params(path_item, operation),
                )
            )
    return tuple(sorted(found, key=lambda op: (op.path, op.method)))


@lru_cache(maxsize=1)
def readable_models() -> frozenset[str]:
    """Component names a client can GET back, directly or as a list item.

    This is the filter that separates a *resource* from an RPC-style result
    envelope. Asymmetry only means something for state you can read back: it is
    not a defect that ``BatchImportResponse.imported`` cannot be sent, because
    nobody ever reads an import summary and echoes it to a writer. It *is* a
    defect that ``ActionResponse.owner_id`` cannot be sent (PX-168).
    """
    names: set[str] = set()
    for path_item in openapi_schema().get("paths", {}).values():
        operation = path_item.get("get") if isinstance(path_item, dict) else None
        if not isinstance(operation, dict):
            continue
        model = _success_response_model(operation)
        if not model:
            continue
        names.add(model)
        # List envelopes expose the real resource under ``items``.
        items = (resolve_properties(model).get("items") or {}).get("items") or {}
        item_model = _ref_name(items)
        if item_model:
            names.add(item_model)
    return frozenset(names)


@dataclass(frozen=True)
class Resource:
    """A readable resource, with the union of everything its writers accept."""

    response_model: str
    writable_fields: frozenset[str]
    response_fields: frozenset[str]
    path_params: frozenset[str]
    operations: tuple[str, ...]


@lru_cache(maxsize=1)
def readable_resources() -> tuple[Resource, ...]:
    """Group write operations by the resource they return.

    Create and update are unioned deliberately: ``owner_id`` would not be a
    contract gap if you could not set it on create but could PATCH it
    afterwards. PX-168 is a gap precisely because neither writer accepts it.
    """
    grouped: dict[str, dict[str, Any]] = {}
    for op in write_operations():
        model = op.response_model
        if model is None or model not in readable_models():
            continue
        entry = grouped.setdefault(
            model,
            {"writable": set(), "response": set(), "path_params": set(), "operations": []},
        )
        entry["writable"].update(resolve_properties(op.request_model))
        entry["response"].update(resolve_properties(model))
        entry["path_params"].update(op.path_params)
        entry["operations"].append(f"{op.label} [{op.request_model}]")

    return tuple(
        Resource(
            response_model=model,
            writable_fields=frozenset(entry["writable"]),
            response_fields=frozenset(entry["response"]),
            path_params=frozenset(entry["path_params"]),
            operations=tuple(sorted(entry["operations"])),
        )
        for model, entry in sorted(grouped.items())
    )


# ---------------------------------------------------------------------------
# Legitimate transformations and server-owned state
# ---------------------------------------------------------------------------

# Fields the server owns outright. A client cannot set these and should not
# expect to: they are identity, audit stamps, or optimistic-concurrency tokens.
# Kept as an explicit list rather than a loose regex so that adding an
# exemption is a visible, reviewable act.
SERVER_OWNED_FIELDS = frozenset(
    {
        "confirmed_by_id",  # Doc Graph edge confirm actor (server-set)
        # JL-3 job cell links. The parent cell is addressed by the
        # (job_type_id, lane_id, step_id) triple in the URL and resolved to a
        # surrogate cell_id by the server, so cell_id is client-supplied in the
        # same sense a path parameter is — just not under that name.
        "cell_id",
        # Navigation targets the server resolves through the X-1 href_registry
        # (job cell links, Entity 360, Doc Graph, risk register). Accepting an
        # href from a client would be both meaningless — it is recomputed from
        # the structured refs on every read — and a way to smuggle a URL past
        # the registry.
        "href",
        # Sub-resource collections projected onto their parent for reading.
        # JobCellResponse.links is written through
        # POST/DELETE .../cells/{lane_id}/{step_id}/links, never through the
        # parent cell body, so no parent writer can or should accept it.
        "links",
        # JL-UX-W3 audit-lapse cue on an audit_outcome cell link. Derived on
        # every read from the linked AuditRun's dates and its template cadence.
        # Accepting it from a client would let the composer assert an audit is
        # in date independently of the audit record — exactly the second source
        # of truth the freshness work exists to avoid.
        "audit_lapse",
        # JL-UX-W5 cycle baseline response. The snapshot JSON is captured by the
        # server at POST time from the live tip; clients may only supply
        # label/note. The remaining fields are read-side cues that say the row
        # is a snapshot and that edit always targets the live tip — accepting
        # them from a client would let the composer claim a fork or suppress
        # the viewing banner.
        "snapshot",
        "is_snapshot",
        "edit_targets_live",
        "viewing_baseline",
        "banner",
        # WC-1 control/hold projection on DocumentResponse. All four are read
        # sides of state owned elsewhere, and none is settable through the
        # document writer by design:
        #   * controlled_document_id / control_status are read from the anchored
        #     `controlled_documents` row. They move when Document Control moves,
        #     or when a library approve/publish writes through to it — never
        #     because a client asserted a status on a document body.
        #   * legal_matter_reference is written only by
        #     PUT /legal-holds/documents/{id} under `admin:manage`. Accepting it
        #     on the document writer would let `document:update` file a record out
        #     of the scope of the hold that is blocking that same writer.
        #   * legal_hold_active is the live verdict from `matter_legal_holds`,
        #     recomputed per read so it cannot contradict a released hold.
        "controlled_document_id",
        "control_status",
        "legal_matter_reference",
        "legal_hold_active",
        "id",
        "tenant_id",
        "created_at",
        "updated_at",
        "deleted_at",
        "created_by_id",
        "updated_by_id",
        "created_by",
        "created_by_name",
        "created_by_email",
        "reference_number",
        "version",
        # Derived from feedback_kind. Kind itself is writable on Create/Update (FB-PR2).
        "feedback_polarity",
    }
)

# Values the server computes from other fields. Sending them would be
# meaningless because the server would recompute and overwrite. Patterns are
# used here because the naming is highly regular (``risk_score``,
# ``score_percentage``, ``completion_rate``, ``assigned_count``).
DERIVED_FIELD_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"^(.*_)?score$"),
    re.compile(r"^score_percentage$"),
    re.compile(r"^(.*_)?count$"),
    re.compile(r"^(.*_)?rate$"),
    re.compile(r"^(.*_)?level$"),
    re.compile(r"^display_.*$"),
    re.compile(r"^full_name$"),
    # Lifecycle stamps the server writes on a state transition: closed_at,
    # completed_at, launched_at, promoted_at, last_login_at. Client-settable
    # dates in this codebase are consistently named ``*_date`` (received_date,
    # report_date, next_audit_date), so they are deliberately not exempt.
    re.compile(r"^.*_at$"),
)


def is_server_controlled(field: str) -> bool:
    """True when a response-only field is legitimately not client-settable."""
    if field in SERVER_OWNED_FIELDS:
        return True
    return any(pattern.match(field) for pattern in DERIVED_FIELD_PATTERNS)


def equivalent_names(field: str) -> frozenset[str]:
    """Names on the other side of the contract that represent the same state.

    A field does not have to be echoed back verbatim to be honoured; some are
    legitimately transformed on the way through, and the brief for these guards
    calls for those to be explicit exceptions rather than dropped assertions:

    * ``tags_json`` (request) is stored raw and returned parsed as ``tags``.
    * ``assigned_to_email`` (request) resolves to ``owner_id`` / ``owner_email``.
    * ``clause_ids`` (request) may be returned as ``clauses``.
    """
    names = {field}
    if field.endswith("_json"):
        names.add(field[: -len("_json")])
    else:
        names.add(f"{field}_json")
    if field.endswith("_email"):
        names.add(f"{field[: -len('_email')]}_id")
    if field.endswith("_ids"):
        names.add(f"{field[: -len('_ids')]}s")
    if field.endswith("_id"):
        names.add(f"{field[: -len('_id')]}_email")
    names |= RENAMED_ACROSS_CONTRACT.get(field, frozenset())
    return frozenset(names)


# Fields whose request-side and response-side names differ for reasons no
# naming rule can infer. Kept tiny and specific on purpose: a loose rule here
# silently exempts real gaps, which is the opposite of what these guards are
# for.
RENAMED_ACROSS_CONTRACT: dict[str, frozenset[str]] = {
    # actions.py resolves assigned_to_email to a user and stores it as the
    # owner, surfacing it as owner_id/owner_email. This is the transformation
    # at the heart of PX-168: the write path is by email, the read path is by
    # id, and the two names never meet.
    "assigned_to_email": frozenset({"owner_id", "owner_email"}),
    "assignee_email": frozenset({"owner_id", "owner_email", "assigned_to_id"}),
}


def is_list_envelope(model: str) -> bool:
    """True for paginated list wrappers, which are not resource representations.

    ``PolicyAcknowledgmentListResponse`` returning ``items``/``total`` that a
    client cannot send is the shape working correctly, not an asymmetry.
    """
    props = resolve_properties(model)
    return "items" in props and "total" in props


def asymmetric_fields(resource: Resource) -> tuple[str, ...]:
    """Fields a resource returns that no writer accepts, excluding known-good cases.

    A path parameter is excluded because it *is* client-supplied — just in the
    URL rather than the body (``run_id`` on ``POST /audits/runs/{run_id}/...``).
    """
    if is_list_envelope(resource.response_model):
        return ()
    sendable: set[str] = set()
    for field in resource.writable_fields:
        sendable |= equivalent_names(field)
    return tuple(
        sorted(
            field
            for field in resource.response_fields - sendable
            if not is_server_controlled(field) and field not in resource.path_params
        )
    )


def is_resource_write(op: WriteOperation) -> bool:
    """True when ``op`` writes a resource, rather than invoking a command.

    ``POST /assignments/{id}/snooze`` taking ``hours`` and returning a
    ``SnoozeAssignmentResponse`` is a command: nobody expects ``hours`` echoed
    back. ``POST /incidents/`` returning an ``IncidentResponse`` a client can
    later GET is a resource write, and there the echo is the contract.
    """
    model = op.response_model
    return model is not None and model in readable_models() and not is_list_envelope(model)


def unreadable_request_fields(op: WriteOperation) -> tuple[str, ...]:
    """Request fields of ``op`` that its own success response never returns.

    This is the static form of the round-trip echo check and the shape of
    PX-327: a client sends a value, gets 201, and has no way to read the value
    back to confirm it landed.
    """
    if not is_resource_write(op):
        return ()
    assert op.response_model is not None  # narrowed by is_resource_write
    response_fields = set(resolve_properties(op.response_model))
    return tuple(
        sorted(
            field
            for field in resolve_properties(op.request_model)
            if field not in WRITE_ONLY_BY_DESIGN and not (equivalent_names(field) & response_fields)
        )
    )


# Credentials and control flags that must never be echoed, or that steer the
# write rather than forming part of the resource's state.
WRITE_ONLY_BY_DESIGN = frozenset(
    {
        "password",
        "current_password",
        "new_password",
        "token",
        "id_token",
        "refresh_token",
        "secret",
        # Optimistic-concurrency and idempotency controls.
        "expected_updated_at",
        "expected_version",
        "idempotency_key",
        # Flags that modify how the write behaves, not what is stored.
        "force",
        "notify",
        "send_email",
    }
)


def format_gap_list(items: Iterable[str], limit: int = 12) -> str:
    """Render a violation list for an assertion message without flooding output."""
    ordered = sorted(items)
    shown = ordered[:limit]
    suffix = f" (+{len(ordered) - limit} more)" if len(ordered) > limit else ""
    return ", ".join(shown) + suffix


# ---------------------------------------------------------------------------
# Enum <-> lookup pairing
# ---------------------------------------------------------------------------

_SIMPLE_ALTERNATION = re.compile(r"^\^\(([\w|]+)\)\$$")


def accepted_values(prop: dict[str, Any]) -> tuple[str, ...]:
    """Return the closed set of values a request property accepts.

    Handles the three ways this codebase constrains a string field:
    a direct ``enum``, a ``$ref`` to an enum component, and a regex
    ``pattern`` of the form ``^(a|b|c)$`` (used by
    ``NearMissCreate.potential_severity``). ``anyOf``/``allOf`` wrappers are
    unwrapped because ``Optional[Enum]`` renders as ``anyOf: [$ref, null]``.

    Returns an empty tuple for open-ended fields, which the caller treats as
    "not enum-backed" rather than "accepts nothing".
    """
    enum_vals = prop.get("enum")
    if isinstance(enum_vals, list):
        return tuple(str(v) for v in enum_vals)

    ref = _ref_name(prop)
    if ref:
        component_enum = _components().get(ref, {}).get("enum")
        if isinstance(component_enum, list):
            return tuple(str(v) for v in component_enum)

    pattern = prop.get("pattern")
    if isinstance(pattern, str):
        match = _SIMPLE_ALTERNATION.match(pattern)
        if match:
            return tuple(match.group(1).split("|"))

    for key in ("anyOf", "allOf", "oneOf"):
        for sub in prop.get(key) or []:
            if isinstance(sub, dict):
                values = accepted_values(sub)
                if values:
                    return values
    return ()


@dataclass(frozen=True)
class LookupBinding:
    """One (lookup category -> request field) pairing the UI actually relies on."""

    category: str
    request_model: str
    field: str
    ui_evidence: str


# The backend holds no machine-readable link between a ``lookup_options``
# category and the request field it populates -- the binding lives in the
# frontend, which fetches a category and feeds it into one select. So the
# pairings are enumerated here with the source line that proves each one.
#
# Deliberately NOT inferred from field-name similarity: that produces false
# pairings. ``RTACreate.severity`` is an RTASeverity (fatal/serious_injury/
# damage_only) and ``SecurityIncidentCreate.incident_type`` is an ISO 27001
# security taxonomy; neither page loads these lookup categories, so neither is
# a contract gap.
LOOKUP_BINDINGS: tuple[LookupBinding, ...] = (
    LookupBinding(
        category="incident_types",
        request_model="IncidentCreate",
        field="incident_type",
        ui_evidence="frontend/src/pages/Incidents.tsx: lookupsApi.list('incident_types', true)",
    ),
    LookupBinding(
        category="incident_types",
        request_model="src__api__schemas__incident__IncidentUpdate",
        field="incident_type",
        ui_evidence="frontend/src/pages/IncidentDetail.tsx: lookupsApi.list('incident_types', true)",
    ),
    LookupBinding(
        category="severity_levels",
        request_model="IncidentCreate",
        field="severity",
        ui_evidence="frontend/src/pages/Incidents.tsx: lookupsApi.list('severity_levels', true)",
    ),
    LookupBinding(
        category="severity_levels",
        request_model="src__api__schemas__incident__IncidentUpdate",
        field="severity",
        ui_evidence="frontend/src/pages/IncidentDetail.tsx: lookupsApi.list('severity_levels', true)",
    ),
    LookupBinding(
        category="complaint_types",
        request_model="ComplaintCreate",
        field="complaint_type",
        ui_evidence="frontend/src/pages/Complaints.tsx: lookupsApi.list('complaint_types', true)",
    ),
    LookupBinding(
        category="complaint_types",
        request_model="ComplaintUpdate",
        field="complaint_type",
        ui_evidence="frontend/src/pages/ComplaintDetail.tsx: lookupsApi.list('complaint_types', true)",
    ),
    LookupBinding(
        category="feedback_kinds",
        request_model="ComplaintCreate",
        field="feedback_kind",
        ui_evidence="frontend/src/pages/Complaints.tsx: lookupsApi.list('feedback_kinds', true)",
    ),
    LookupBinding(
        category="feedback_kinds",
        request_model="ComplaintUpdate",
        field="feedback_kind",
        ui_evidence="frontend/src/pages/ComplaintDetail.tsx: lookupsApi.list('feedback_kinds', true)",
    ),
    # severity_levels is merged into the *priority* select on complaints, not a
    # field called "severity" -- name-based matching would have missed this.
    LookupBinding(
        category="severity_levels",
        request_model="ComplaintCreate",
        field="priority",
        ui_evidence="frontend/src/pages/Complaints.tsx: setPriorityOptions(mergeLookupSelectOptions(...severityRes))",
    ),
    LookupBinding(
        category="severity_levels",
        request_model="NearMissCreate",
        field="potential_severity",
        ui_evidence="frontend/src/pages/NearMisses.tsx: setSeverityOptions(mergeLookupSelectOptions(...severityRes))",
    ),
)


def seeded_lookup_codes(category: str) -> tuple[str, ...]:
    """Active lookup codes a fresh tenant is seeded with for ``category``.

    Read from the seed module rather than the database so the guard runs in the
    no-Postgres ``contract-tests`` job. This is the set of options an
    unconfigured tenant's form will actually offer.
    """
    from src.domain.services.lookup_defaults_seed_data import rows_for_category

    return tuple(row.code for row in rows_for_category(category))


def operations_using(request_model: str) -> tuple[str, ...]:
    """Endpoints that accept ``request_model`` as their body, for error messages."""
    return tuple(op.label for op in write_operations() if op.request_model == request_model)
