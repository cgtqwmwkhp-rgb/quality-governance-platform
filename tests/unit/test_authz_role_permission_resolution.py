"""RUN-025: how a non-superuser's role permissions actually resolve.

``User.has_permission`` short-circuits on ``is_superuser`` before it reads a
single role, and every prior UAT run and verification used a dual-role
superuser — so no test in this repo had ever driven the resolution path with a
real ``Role`` row. A 28 Jul 2026 authenticated run against staging with a
non-superuser (user 8, ``tenant_id=1``, one ``user_roles`` row to role 1
``admin``, whose ``permissions`` column holds the literal JSON string
``["*"]``) returned 403 ``Permission 'incident:read' required`` on the core case
registers.

These tests reproduce that offline against the real ``User``/``Role`` models and
the real ``require_permission`` dependency, and pin the resolution contract:
``roles.permissions`` is a set of exact tokens, so ``"*"`` is a token named
``*`` rather than a wildcard.

Whether ``"*"`` *should* expand to every permission is a policy decision and is
deliberately not settled here. Nothing in the repository writes ``["*"]``:
``ETL_ROLE_PERMISSIONS`` (``src/api/routes/testing.py``), ``_CI_OPERATOR_PERMS``
(``scripts/seed_ci_locust_users.py``) and ``_ADMIN_PERMS``
(``tests/integration/conftest.py``) all enumerate ``<resource>:<action>`` grants
explicitly. If the wildcard is ever adopted, the assertions below change with it
as part of that decision.
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from src.api.dependencies import require_permission
from src.domain.models.user import Role, User

# The four denials reproduced over HTTP against staging build 51a8fa4c.
STAGING_DENIALS = ["incident:read", "complaint:read", "near_miss:read", "action:create"]

WILDCARD_PERMISSIONS = '["*"]'


def _user(permissions: object, *, is_superuser: bool = False, with_role: bool = True) -> User:
    """Build a transient user that mirrors staging user 8's row shape."""
    user = User(
        id=8,
        email="non.superuser@example.com",
        hashed_password="unused",
        first_name="Non",
        last_name="Superuser",
        is_active=True,
        is_superuser=is_superuser,
        tenant_id=1,
    )
    if with_role:
        role = Role(id=1, name="admin", is_system_role=True)
        role.permissions = permissions  # type: ignore[assignment]  # exercises the non-str branches too
        user.roles = [role]
    return user


# ---------------------------------------------------------------------------
# The mechanism: exact-token matching, so ["*"] grants only the token "*".
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("permission", STAGING_DENIALS)
def test_wildcard_role_does_not_grant_enforced_permissions(permission):
    assert _user(WILDCARD_PERMISSIONS).has_permission(permission) is False


def test_wildcard_resolves_as_a_literal_token_not_a_pattern():
    """Positive control: ``["*"]`` parses fine and grants exactly one token."""
    assert _user(WILDCARD_PERMISSIONS).has_permission("*") is True


@pytest.mark.asyncio
@pytest.mark.parametrize("permission", STAGING_DENIALS)
async def test_require_permission_returns_403_for_wildcard_role(permission):
    checker = require_permission(permission)

    with pytest.raises(HTTPException) as exc:
        await checker(current_user=_user(WILDCARD_PERMISSIONS))

    assert exc.value.status_code == 403
    assert exc.value.detail == f"Permission '{permission}' required"


# ---------------------------------------------------------------------------
# A granular grant admits the same user, and only for what it names.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("permission", STAGING_DENIALS)
async def test_granular_grant_admits_the_same_user(permission):
    user = _user(f'["{permission}"]')
    checker = require_permission(permission)

    assert await checker(current_user=user) is user


@pytest.mark.asyncio
async def test_granular_grant_stays_scoped_to_the_token_it_names():
    user = _user('["incident:read"]')

    with pytest.raises(HTTPException) as exc:
        await require_permission("incident:delete")(current_user=user)

    assert exc.value.status_code == 403


@pytest.mark.parametrize(
    "permissions",
    [
        pytest.param('["incident:read", "complaint:read"]', id="json-list-string"),
        pytest.param("incident:read,complaint:read", id="comma-separated-string"),
        pytest.param(["incident:read", "complaint:read"], id="python-list"),
        pytest.param('[" INCIDENT:READ ", "complaint:read"]', id="whitespace-and-case"),
    ],
)
def test_supported_permission_column_shapes_all_resolve(permissions):
    user = _user(permissions)

    assert user.has_permission("incident:read") is True
    assert user.has_permission("complaint:read") is True
    assert user.has_permission("incident:delete") is False


# ---------------------------------------------------------------------------
# Superuser short-circuit: why every prior run missed this.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("permission", STAGING_DENIALS)
async def test_superuser_is_admitted_whatever_the_role_grants(permission):
    checker = require_permission(permission)
    wildcard_superuser = _user(WILDCARD_PERMISSIONS, is_superuser=True)
    roleless_superuser = _user(None, is_superuser=True, with_role=False)

    assert await checker(current_user=wildcard_superuser) is wildcard_superuser
    assert await checker(current_user=roleless_superuser) is roleless_superuser


# ---------------------------------------------------------------------------
# Malformed / empty permission data fails closed rather than raising.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "permissions",
    [
        pytest.param(None, id="null-column"),
        pytest.param("", id="empty-string"),
        pytest.param("[]", id="empty-json-list"),
        pytest.param("   ", id="whitespace-only"),
        pytest.param("not json at all", id="unparseable"),
        pytest.param('{"all": true}', id="valid-json-but-not-a-list"),
        pytest.param("[123]", id="non-string-members"),
    ],
)
def test_unusable_permission_data_denies_without_raising(permissions):
    assert _user(permissions).has_permission("incident:read") is False


def test_user_with_no_roles_is_denied():
    assert _user(None, with_role=False).has_permission("incident:read") is False
