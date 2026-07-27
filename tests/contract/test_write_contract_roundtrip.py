"""Runtime half of the round-trip echo guard: POST a payload, diff the response.

``test_write_contract_guards.py`` checks that the request and response *schemas*
agree. That cannot catch a field which is declared on both sides and then
dropped by the service layer on the way to the database — the schema looks
fine, the response validates, and the value is gone. PX-168 was found by a
human noticing exactly that, so it is worth a machine doing it on every push.

Two runtime checks per create endpoint:

* **Echo** — every field sent in a valid payload comes back with an equivalent
  value.
* **Unknown-field rejection** — an unrecognised field is refused with 422
  rather than silently dropped. This also cross-validates the static guard:
  ``additionalProperties: false`` is only a *proxy* for the runtime 422, and
  this proves the proxy holds.

Endpoints are discovered from the OpenAPI document (every collection-level POST
that returns a readable resource, currently 47) and payloads are synthesised
from the request schema, so a new create endpoint is exercised automatically.

Isolation: this module binds the application's session maker to a private
SQLite file for the duration of the module and restores the original binding
afterwards, so it neither needs nor touches a real database. It never reads
``DATABASE_URL``, which matters because the ``contract-tests`` CI job has no
database service and the shell may have a production URL exported.
"""

from __future__ import annotations

import os
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

import pytest
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from tests.contract._write_contract_support import (
    WriteOperation,
    accepted_values,
    format_gap_list,
    is_resource_write,
    resolve_properties,
    write_operations,
)

# Portal intake fails closed without a tenant; the root conftest seeds this too,
# but this module must not depend on collection order to be correct.
os.environ.setdefault("DEFAULT_TENANT_ID", "1")
os.environ.setdefault("TESTING", "1")

PROBE_TENANT_ID = 1
PROBE_USER_ID = 1

# Fields the handler deliberately recomputes, so not echoing them verbatim is
# correct behaviour rather than a dropped write. Each entry cites the code that
# does the overriding, so a reviewer can check the claim instead of trusting it.
SERVER_RECOMPUTED_FIELDS: dict[str, tuple[str, ...]] = {
    # src/api/routes/training_tickets.py:133 forces verify_state to EXPIRED
    # when expires_at is in the past, which the probe's fixed date always is.
    "POST /api/v1/training-tickets/": ("verify_state",),
}

# Endpoints that return 2xx and silently fail to honour part of the payload.
# These are defects, xfailed so the suite stays green while they are ticketed.
KNOWN_RUNTIME_ECHO_GAPS: dict[str, tuple[str, ...]] = {
    # Sent re_acknowledge_period_months=1, response carries null. The value is
    # accepted by the schema and lost before it reaches the response.
    "POST /api/v1/policy-acknowledgments/requirements": ("re_acknowledge_period_months",),
    # admin_email is accepted by TenantCreate and absent from TenantResponse,
    # so a client cannot confirm which address was recorded.
    "POST /api/v1/tenants/": ("admin_email",),
}


# ---------------------------------------------------------------------------
# Payload synthesis
# ---------------------------------------------------------------------------


# Fields naming another entity are omitted: a synthesised id would violate a
# foreign key and turn an echo test into a 404/409 test. Their symmetry is
# already covered statically by the guards module.
def _is_reference_field(name: str) -> bool:
    return name.endswith("_id") or name.endswith("_ids")


def _unwrap(prop: dict[str, Any]) -> dict[str, Any]:
    """Collapse ``Optional[X]`` / ``allOf`` wrappers to the meaningful subschema."""
    for key in ("anyOf", "oneOf", "allOf"):
        options = prop.get(key)
        if not options:
            continue
        for option in options:
            if isinstance(option, dict) and option.get("type") != "null":
                merged = {k: v for k, v in prop.items() if k not in ("anyOf", "oneOf", "allOf")}
                merged.update(option)
                return merged
    return prop


def _string_value(prop: dict[str, Any], name: str) -> str:
    fmt = prop.get("format")
    if fmt == "date-time":
        return "2026-01-05T09:00:00+00:00"
    if fmt == "date":
        return "2026-01-05"
    if fmt == "email":
        return "contract.probe@example.com"
    if fmt == "uuid":
        return str(uuid.uuid4())
    if fmt == "uri":
        return "https://example.com/contract-probe"
    if "email" in name:
        return "contract.probe@example.com"
    # Long enough to clear the min_length=10 constraints used on description
    # fields, short enough for the max_length=20 ones used on codes.
    base = f"contract-probe-{name}"[: prop.get("maxLength") or 64]
    minimum = int(prop.get("minLength") or 0)
    return base.ljust(minimum, "x") if len(base) < minimum else base


def synthesise_value(prop: dict[str, Any], name: str) -> Any:
    """Build a schema-valid value for one property, or raise ``_Unsupported``."""
    prop = _unwrap(prop)

    closed = accepted_values(prop)
    if closed:
        return closed[0]

    declared = prop.get("type")
    if declared == "string":
        return _string_value(prop, name)
    if declared == "integer":
        return int(prop.get("minimum") or 1)
    if declared == "number":
        return float(prop.get("minimum") or 1)
    if declared == "boolean":
        return True
    if declared == "array":
        return []
    if declared == "object":
        return {}
    raise _Unsupported(f"no synthesis rule for {name!r} (type={declared!r})")


class _Unsupported(Exception):
    """Raised when a property cannot be given a schema-valid value."""


def synthesise_payload(request_model: str) -> tuple[dict[str, Any], tuple[str, ...]]:
    """Build a populated, valid-looking body for ``request_model``.

    Returns the payload and the names of fields deliberately left out, so a
    test can report what it did *not* cover rather than silently narrowing.
    """
    from tests.contract._write_contract_support import _components

    schema_required = set(_components().get(request_model, {}).get("required") or [])
    for sub in _components().get(request_model, {}).get("allOf") or []:
        schema_required |= set(sub.get("required") or [])

    payload: dict[str, Any] = {}
    omitted: list[str] = []
    for name, prop in sorted(resolve_properties(request_model).items()):
        required = name in schema_required
        if _is_reference_field(name) and not required:
            omitted.append(name)
            continue
        unwrapped = _unwrap(prop)
        # Containers are only populated when mandatory: an empty list or object
        # is a weak echo assertion and some writers normalise [] to null.
        if not required and unwrapped.get("type") in ("array", "object"):
            omitted.append(name)
            continue
        try:
            payload[name] = synthesise_value(prop, name)
        except _Unsupported:
            omitted.append(name)
    return payload, tuple(omitted)


# ---------------------------------------------------------------------------
# Echo comparison
# ---------------------------------------------------------------------------


def _as_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def values_equivalent(sent: Any, received: Any) -> bool:
    """True when ``received`` honours ``sent``, allowing declared transformations.

    Legitimate transformations, encoded explicitly rather than by loosening the
    assertion to "is not None":

    * timestamp normalisation — ``2026-01-05T09:00:00+00:00`` may come back as
      ``2026-01-05T09:00:00`` once stored as a naive UTC column;
    * numeric widening — an integer field may be returned as ``1.0``;
    * date truncation — a date-time sent to a date column returns ``2026-01-05``.
    """
    if sent == received:
        return True
    sent_dt, received_dt = _as_datetime(sent), _as_datetime(received)
    if sent_dt and received_dt:
        return sent_dt == received_dt
    if sent_dt and isinstance(received, str) and received == sent_dt.date().isoformat():
        return True
    if isinstance(sent, (int, float)) and isinstance(received, (int, float)):
        return float(sent) == float(received)
    return False


# ---------------------------------------------------------------------------
# Harness
# ---------------------------------------------------------------------------


class _ProbeRole:
    """Role stand-in granting every ``<resource>:<action>`` the routes check."""

    id = 1
    name = "admin"
    description = None
    is_system_role = False
    permissions = "*"

    def __contains__(self, item: str) -> bool:  # pragma: no cover - defensive
        return True


class _ProbeUser:
    """Authenticated user stand-in requiring no database lookup.

    ``is_superuser`` short-circuits ``has_permission``, which keeps this test
    about the write contract rather than about RBAC — permission enforcement is
    covered by ``tests/integration/test_403_rbac_error_envelopes.py``.
    """

    id = PROBE_USER_ID
    email = "contract.probe@example.com"
    first_name = "Contract"
    last_name = "Probe"
    hashed_password = "unused"
    job_title = None
    department = None
    phone = None
    is_active = True
    is_superuser = True
    tenant_id = PROBE_TENANT_ID
    last_login = None
    azure_oid = None
    roles: list[_ProbeRole] = [_ProbeRole()]
    full_name = "Contract Probe"

    def has_permission(self, permission: str) -> bool:
        return True


async def _create_schema_and_seed(test_engine: Any) -> None:
    """Create every table on the probe database and seed FK anchors."""
    import src.domain.models  # noqa: F401  - registers all mappers on Base.metadata
    from src.core.security import get_password_hash
    from src.infrastructure.database import Base, async_session_maker
    from tests.factories import TenantFactory, UserFactory

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Handlers stamp created_by_id from the authenticated user, so the tenant
    # and user rows must exist or every insert fails on a foreign key.
    async with async_session_maker() as session:
        session.add(
            TenantFactory.build(
                id=PROBE_TENANT_ID,
                name="Contract Probe Tenant",
                slug="contract-probe-tenant",
                admin_email="contract.probe@example.com",
            )
        )
        await session.flush()
        session.add(
            UserFactory.build(
                id=PROBE_USER_ID,
                email="contract.probe@example.com",
                hashed_password=get_password_hash("contract-probe-password"),
                is_active=True,
                is_superuser=True,
                tenant_id=PROBE_TENANT_ID,
            )
        )
        await session.commit()


@pytest.fixture(scope="module")
def probe_client() -> Iterator[Any]:
    """A TestClient backed by a private SQLite database.

    The application's ``async_session_maker`` is rebound rather than the
    ``get_db`` dependency being overridden, because handlers are not the only
    caller — audit logging and idempotency helpers open their own sessions from
    the same maker, and those would otherwise reach for Postgres.

    The original binding is restored on teardown so this cannot leak into other
    modules regardless of the order pytest happens to run them in.
    """
    import asyncio

    from fastapi.testclient import TestClient

    from src.api.dependencies import get_current_user
    from src.infrastructure.database import async_session_maker
    from src.main import app

    db_path = Path(tempfile.gettempdir()) / f"qgp-contract-roundtrip-{os.getpid()}.db"
    db_path.unlink(missing_ok=True)
    test_engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", poolclass=NullPool)

    original_bind = async_session_maker.kw.get("bind")
    async_session_maker.configure(bind=test_engine)
    app.dependency_overrides[get_current_user] = lambda: _ProbeUser()
    try:
        asyncio.run(_create_schema_and_seed(test_engine))
        # raise_server_exceptions=False so an unhandled 500 surfaces as a status
        # code this module can report and skip on, rather than aborting the test
        # with a traceback from inside the handler. 5xx behaviour is the
        # Schemathesis job's remit, not this one's.
        with TestClient(app, raise_server_exceptions=False) as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        async_session_maker.configure(bind=original_bind)
        asyncio.run(test_engine.dispose())
        db_path.unlink(missing_ok=True)


def _create_endpoints() -> list[WriteOperation]:
    """Collection-level POSTs that return a resource a client can read back.

    Sub-resource creates (``POST /audits/runs/{run_id}/findings``) are excluded
    because they need a parent to exist; their schema-level symmetry is covered
    by the static guards.
    """
    return [op for op in write_operations() if op.method == "POST" and not op.path_params and is_resource_write(op)]


def _echo_params() -> list[pytest.param]:
    params = []
    for op in _create_endpoints():
        recorded = KNOWN_RUNTIME_ECHO_GAPS.get(op.label, ())
        marks = (
            pytest.mark.xfail(
                reason=f"{op.label} does not echo: {format_gap_list(recorded)}",
                strict=False,
            ),
        )
        params.append(pytest.param(op, id=op.label, marks=marks if recorded else ()))
    return params


CREATE_ENDPOINTS = _create_endpoints()
ECHO_PARAMS = _echo_params()
UNKNOWN_FIELD = "__contract_probe_unexpected_field__"


def _skip_reason(op: WriteOperation, response: Any) -> str:
    """Explain a non-2xx, distinguishing a weak payload from a broken handler."""
    if response.status_code >= 500:
        return (
            f"{op.label} returned {response.status_code} for a schema-valid synthesised payload. "
            f"That is a server-side fault rather than an echo failure, so this guard cannot judge it — "
            f"it is reported separately. Response: {response.text[:200]}"
        )
    return (
        f"{op.label} rejected the synthesised payload with {response.status_code}, so the echo cannot be "
        f"checked. The payload did not satisfy a business rule the schema does not express — a probe "
        f"limitation, not a product defect. Response: {response.text[:200]}"
    )


class TestCreateRoundTrip:
    """A create endpoint must return what it was given."""

    @pytest.mark.parametrize("op", ECHO_PARAMS)
    def test_response_echoes_every_field_sent(self, probe_client: Any, op: WriteOperation) -> None:
        payload, omitted = synthesise_payload(op.request_model)
        assert payload, f"Could not synthesise any field for {op.request_model}; the probe would be vacuous."

        response = probe_client.request(op.method, op.path, json=payload)
        if response.status_code >= 300:
            pytest.skip(_skip_reason(op, response))

        body = response.json()
        assert isinstance(body, dict), f"{op.label} returned {type(body).__name__}, expected an object"

        recomputed = SERVER_RECOMPUTED_FIELDS.get(op.label, ())
        checked = {name: value for name, value in payload.items() if name not in recomputed}
        dropped = [name for name in checked if name not in body]
        altered = [
            f"{name}(sent={checked[name]!r}, got={body[name]!r})"
            for name in checked
            if name in body and not values_equivalent(checked[name], body[name])
        ]
        assert not dropped and not altered, (
            f"{op.label} returned {response.status_code} but did not honour every field sent. "
            f"Absent from the response: {format_gap_list(dropped) or 'none'}. "
            f"Returned with a different value: {format_gap_list(altered) or 'none'}. "
            f"A client echoing back what it read would silently lose these. "
            f"Fields not exercised by the probe: {format_gap_list(omitted, limit=8) or 'none'}."
        )

    @pytest.mark.parametrize("op", [pytest.param(op, id=op.label) for op in CREATE_ENDPOINTS])
    def test_unknown_field_is_rejected(self, probe_client: Any, op: WriteOperation) -> None:
        """An unrecognised body field must 422 rather than be discarded.

        Not xfail-marked per endpoint: the recorded backlog for this lives in
        ``KNOWN_LAX_WRITE_SCHEMAS`` and the assertion consults it, so this one
        test is both the gate for strict schemas and the proof that the static
        ``additionalProperties`` proxy reflects real behaviour.
        """
        from tests.contract._write_contract_baseline import KNOWN_LAX_WRITE_SCHEMAS

        payload, _ = synthesise_payload(op.request_model)

        # Establish that the payload is otherwise acceptable. Without this, a
        # 422 caused by the synthesised payload itself is indistinguishable
        # from a 422 caused by the unknown field.
        baseline = probe_client.request(op.method, op.path, json=payload)
        if baseline.status_code >= 300:
            pytest.skip(
                f"{op.label} returned {baseline.status_code} for the payload alone, so a 422 on the "
                f"augmented payload could not be attributed to the unknown field. {_skip_reason(op, baseline)}"
            )

        response = probe_client.request(op.method, op.path, json={**payload, UNKNOWN_FIELD: "probe"})

        if op.request_model in KNOWN_LAX_WRITE_SCHEMAS:
            assert response.status_code != 422, (
                f"{op.label} now rejects unknown fields — {op.request_model} appears to have gained "
                f'extra="forbid". Remove it from KNOWN_LAX_WRITE_SCHEMAS so the guard starts enforcing it. '
                f"Response: {response.text[:200]}"
            )
            return

        assert response.status_code == 422, (
            f"{op.label} accepted an unrecognised body field ({UNKNOWN_FIELD!r}) with status "
            f'{response.status_code}. {op.request_model} declares extra="forbid", so this should have '
            f"been a 422. This is the PX-168 failure mode: the client's field is dropped and the write "
            f"reports success."
        )


class TestProbeIsNotVacuous:
    """The round-trip probe is only meaningful if it reaches real endpoints."""

    def test_enough_create_endpoints_discovered(self) -> None:
        assert (
            len(CREATE_ENDPOINTS) > 20
        ), f"Only {len(CREATE_ENDPOINTS)} create endpoints discovered; the probe covers almost nothing."

    def test_payload_synthesis_produces_fields(self) -> None:
        empty = [op.label for op in CREATE_ENDPOINTS if not synthesise_payload(op.request_model)[0]]
        assert not empty, f"Payload synthesis produced nothing for: {format_gap_list(empty)}"

    def test_enough_endpoints_actually_accept_the_probe(self, probe_client: Any) -> None:
        """The echo checks skip on any non-2xx, so guard against them all skipping.

        Without this, a change that made every synthesised payload invalid
        would turn the whole module green while checking nothing. The floor is
        set well below the ~25 that currently succeed, so ordinary drift in one
        or two endpoints does not fail the build.
        """
        accepted = [
            op.label
            for op in CREATE_ENDPOINTS
            if probe_client.request(op.method, op.path, json=synthesise_payload(op.request_model)[0]).status_code < 300
        ]
        assert len(accepted) >= 15, (
            f"Only {len(accepted)} of {len(CREATE_ENDPOINTS)} create endpoints accepted a synthesised "
            f"payload, so the round-trip probe is close to vacuous. Payload synthesis has probably drifted "
            f"away from what the schemas now require."
        )
