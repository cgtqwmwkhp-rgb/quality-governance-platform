"""``roles.permissions`` may only ever be written as catalogued JSON tokens.

Covers the write path end to end, because the important property is not just that
the validator raises but that the raise surfaces as a 422 with something an
operator can act on. Nothing here may produce a 500: an unhandled error on this
endpoint would be the same class of failure as the unvalidated column itself.

Also covers the decision about rows that are *already* invalid. Production and
staging hold values this validator rejects — a wildcard, an uncatalogued token,
and a PostgreSQL array literal — so editing such a role has to do something
defined. It refuses, and says what to send instead. It never rewrites the stored
value, because quietly changing which permissions a role grants is a privilege
change nobody asked for and nobody would see.
"""

from __future__ import annotations

import json
import uuid

import pytest
from sqlalchemy import select

from src.domain.models.user import Role

pytestmark = pytest.mark.asyncio

ROLES_URL = "/api/v1/users/roles/"

WILDCARD = '["*"]'
PG_ARRAY_LITERAL = "{incident:create,incident:view_all,incident:set_reference_number}"
BARE_COMMA_STRING = "incident:create,incident:read"
VALID = '["incident:create", "incident:read"]'


def _name(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


async def _insert_role_with_raw_permissions(permissions: str | None, *, is_system_role: bool = False) -> int:
    """Write a role straight to the database, bypassing the API validation.

    Deliberately not via the endpoint: the point is to reproduce a row that
    predates the validation, which is exactly what the live databases contain.
    """
    from src.infrastructure.database import async_session_maker

    async with async_session_maker() as session:
        role = Role(
            name=_name("legacy"),
            description="pre-validation row",
            permissions=permissions,
            is_system_role=is_system_role,
        )
        session.add(role)
        await session.commit()
        await session.refresh(role)
        return role.id


async def _stored_permissions(role_id: int) -> str | None:
    from src.infrastructure.database import async_session_maker

    async with async_session_maker() as session:
        result = await session.execute(select(Role).where(Role.id == role_id))
        return result.scalar_one().permissions


def _message(response) -> str:
    """Flatten a FastAPI validation or api_error body into searchable text."""
    return json.dumps(response.json())


# --------------------------------------------------------------------------- #
# Creating a role
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("permissions", "expected_phrase"),
    [
        (WILDCARD, "wildcard"),
        (PG_ARRAY_LITERAL, "PostgreSQL array literal"),
        (BARE_COMMA_STRING, "comma-separated"),
        ('["bogus:perm"]', "not in the permission catalogue"),
        ('["policy:read"]', "reserved"),
        ('{"a": 1}', "JSON array"),
    ],
)
async def test_create_role_rejects_invalid_permissions_with_422(superuser_client, permissions, expected_phrase):
    response = await superuser_client.post(
        ROLES_URL,
        json={"name": _name("bad"), "description": "d", "permissions": permissions},
    )

    assert response.status_code == 422, f"expected 422, got {response.status_code}: {response.text}"
    assert expected_phrase in _message(response)


async def test_create_role_never_returns_500_for_any_bad_encoding(superuser_client):
    """A 500 here would mean the value reached the column before anything checked it."""
    for permissions in (WILDCARD, PG_ARRAY_LITERAL, BARE_COMMA_STRING, '["bogus:perm"]', "[1,2]", '"x"'):
        response = await superuser_client.post(
            ROLES_URL,
            json={"name": _name("bad"), "permissions": permissions},
        )
        assert response.status_code == 422, f"{permissions!r} gave {response.status_code}: {response.text}"


async def test_create_role_accepts_catalogued_tokens_and_stores_them_canonically(superuser_client):
    response = await superuser_client.post(
        ROLES_URL,
        json={"name": _name("ops"), "description": "d", "permissions": '["incident:read","incident:create"]'},
    )

    assert response.status_code == 201, response.text
    assert json.loads(response.json()["permissions"]) == ["incident:create", "incident:read"]
    assert await _stored_permissions(response.json()["id"]) == '["incident:create", "incident:read"]'


async def test_create_role_accepts_no_permissions(superuser_client):
    response = await superuser_client.post(ROLES_URL, json={"name": _name("empty"), "permissions": "[]"})
    assert response.status_code == 201, response.text
    assert response.json()["permissions"] == "[]"


# --------------------------------------------------------------------------- #
# Updating a role
# --------------------------------------------------------------------------- #


async def test_update_role_rejects_invalid_permissions_with_422(superuser_client):
    role_id = await _insert_role_with_raw_permissions(VALID)

    response = await superuser_client.patch(f"/api/v1/users/roles/{role_id}", json={"permissions": WILDCARD})

    assert response.status_code == 422, response.text
    assert "wildcard" in _message(response)
    assert await _stored_permissions(role_id) == VALID, "a rejected write must not touch the row"


async def test_update_role_with_valid_permissions_succeeds(superuser_client):
    role_id = await _insert_role_with_raw_permissions(VALID)

    response = await superuser_client.patch(
        f"/api/v1/users/roles/{role_id}",
        json={"permissions": '["audit:read"]'},
    )

    assert response.status_code == 200, response.text
    assert await _stored_permissions(role_id) == '["audit:read"]'


async def test_unrelated_edit_of_a_healthy_role_still_works(superuser_client):
    """The stored-value guard must not get in the way of ordinary edits."""
    role_id = await _insert_role_with_raw_permissions(VALID)

    response = await superuser_client.patch(f"/api/v1/users/roles/{role_id}", json={"description": "renamed"})

    assert response.status_code == 200, response.text
    assert response.json()["description"] == "renamed"


# --------------------------------------------------------------------------- #
# Rows that were already invalid before any of this existed
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("stored", "expected_phrase"),
    [
        (WILDCARD, "wildcard"),
        (PG_ARRAY_LITERAL, "silently lossy"),
        (BARE_COMMA_STRING, "comma-separated string"),
        ('["bogus:perm"]', "unknown token"),
    ],
)
async def test_unrelated_edit_is_refused_when_stored_permissions_are_invalid(superuser_client, stored, expected_phrase):
    """Refuse, rather than edit a defective access-control record or rewrite it."""
    role_id = await _insert_role_with_raw_permissions(stored)

    response = await superuser_client.patch(f"/api/v1/users/roles/{role_id}", json={"description": "touched"})

    assert response.status_code == 422, response.text
    body = _message(response)
    assert expected_phrase in body
    assert "Resend this request including a valid 'permissions' JSON array" in body
    assert await _stored_permissions(role_id) == stored, "the row must be left exactly as it was"


async def test_refusal_reports_the_tokens_currently_in_effect(superuser_client):
    """An operator cannot rebuild the grant without knowing what it resolves to now.

    For the PostgreSQL array-literal row that means naming the mangled tokens, so
    it is visible that the first and last permissions are not in force.
    """
    role_id = await _insert_role_with_raw_permissions(PG_ARRAY_LITERAL)

    response = await superuser_client.patch(f"/api/v1/users/roles/{role_id}", json={"description": "touched"})

    assert response.status_code == 422
    # The app normalises every error into a {"error": {...}} envelope.
    details = response.json()["error"]["details"]
    assert details["tokens_currently_effective"] == [
        "{incident:create",
        "incident:view_all",
        "incident:set_reference_number}",
    ]
    assert details["stored_encoding"] == "postgres_array_literal"


async def test_supplying_valid_permissions_repairs_an_invalid_row(superuser_client):
    """The escape hatch: fixing permissions is the one edit an invalid role accepts."""
    role_id = await _insert_role_with_raw_permissions(WILDCARD)

    response = await superuser_client.patch(
        f"/api/v1/users/roles/{role_id}",
        json={"description": "repaired", "permissions": '["incident:read"]'},
    )

    assert response.status_code == 200, response.text
    assert await _stored_permissions(role_id) == '["incident:read"]'
    assert response.json()["description"] == "repaired"


async def test_explicit_null_permissions_clears_an_invalid_row(superuser_client):
    """Sending ``permissions: null`` counts as supplying it, and clears the role.

    Pinned because it is a subtle path: ``null`` is a valid stored state, and a
    superuser sending it is making a deliberate choice rather than having the row
    rewritten underneath them. It is the second way out of an invalid row.
    """
    role_id = await _insert_role_with_raw_permissions(PG_ARRAY_LITERAL)

    response = await superuser_client.patch(
        f"/api/v1/users/roles/{role_id}",
        json={"description": "cleared", "permissions": None},
    )

    assert response.status_code == 200, response.text
    assert await _stored_permissions(role_id) is None


async def test_reading_roles_with_invalid_stored_values_does_not_error(superuser_client):
    """Listing must keep working; the response model must not validate the column.

    Rows written before this validation existed still hold values it rejects, and a
    response model that applied the same rules would turn every list request into a
    500 — which is how ``RoleResponse`` came not to inherit from ``RoleBase``.
    """
    for stored in (WILDCARD, PG_ARRAY_LITERAL, BARE_COMMA_STRING, None):
        await _insert_role_with_raw_permissions(stored)

    response = await superuser_client.get(ROLES_URL)

    assert response.status_code == 200, response.text
    stored_values = {role["permissions"] for role in response.json()}
    assert WILDCARD in stored_values
    assert PG_ARRAY_LITERAL in stored_values


async def test_system_role_refusal_still_takes_precedence(superuser_client):
    """A defective *system* role cannot be repaired through this API at all.

    Pre-existing behaviour, asserted so it is not mistaken for something the
    stored-value guard introduced: the system-role check runs first, so a
    superuser gets 400 and has to correct such a role outside the API.
    """
    role_id = await _insert_role_with_raw_permissions(WILDCARD, is_system_role=True)

    response = await superuser_client.patch(
        f"/api/v1/users/roles/{role_id}",
        json={"permissions": '["incident:read"]'},
    )

    assert response.status_code == 400, response.text
    assert "system role" in _message(response).lower()
    assert await _stored_permissions(role_id) == WILDCARD
