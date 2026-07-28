"""Write-time rules for ``roles.permissions``, and honest diagnosis of old rows.

The live databases hold three encodings of this column, and one of them —
the PostgreSQL array literal — is read lossily by ``User.has_permission``: the
braces stay attached to the outermost tokens, so the role loses exactly its first
and last permission while the ones in between work. Those cases are pinned here
against the real ``User.has_permission`` rather than against an assumption about
it, because the whole value of the diagnosis is that it describes what the running
code does.
"""

from __future__ import annotations

import json

import pytest

from src.api.schemas.user import RoleCreate, RoleUpdate
from src.domain.authz.validation import (
    BARE_COMMA_SEPARATED,
    JSON_ARRAY,
    POSTGRES_ARRAY_LITERAL,
    PermissionValidationError,
    canonicalise_permissions_input,
    describe_stored_permissions,
    detect_encoding,
    parse_permissions_like_runtime,
)
from src.domain.models.user import Role, User

# The three encodings found in the live databases, verbatim in shape.
PRODUCTION_BARE_STRING = "audit:read"
STAGING_JSON_ARRAY = '["complaint:create", "complaint:read"]'
STAGING_PG_ARRAY_LITERAL = "{incident:create,incident:view_all,incident:set_reference_number}"
STAGING_WILDCARD = '["*"]'


def _user_with(permissions: str | None) -> User:
    """A real (transient) User carrying a real Role. No database involved."""
    user = User(email="t@example.com", hashed_password="x", first_name="T", last_name="U", is_superuser=False)
    user.roles = [Role(name="r", permissions=permissions)]
    return user


# --------------------------------------------------------------------------- #
# Pin the parse replica to the real implementation
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "raw",
    [
        PRODUCTION_BARE_STRING,
        STAGING_JSON_ARRAY,
        STAGING_PG_ARRAY_LITERAL,
        STAGING_WILDCARD,
        "",
        None,
        "[]",
        '["Incident:Create"]',
        "incident:create, incident:read ,",
        '{"not": "an array"}',
    ],
)
def test_parse_replica_matches_real_has_permission(raw):
    """``parse_permissions_like_runtime`` must agree with ``User.has_permission``.

    ``User.has_permission`` belongs to another lane and is not changed here, so the
    replica used for diagnosis is pinned to its observable behaviour: any token the
    replica reports must be granted, and any token it does not report must not be.
    """
    user = _user_with(raw)
    parsed = parse_permissions_like_runtime(raw)

    for token in parsed:
        assert user.has_permission(token), f"replica reported {token!r} but has_permission denies it"

    probes = {
        "incident:create",
        "incident:view_all",
        "incident:set_reference_number",
        "complaint:create",
        "complaint:read",
        "audit:read",
        "*",
        "incident:read",
    }
    for token in probes - set(parsed):
        assert not user.has_permission(token), f"replica omitted {token!r} but has_permission grants it"


def test_postgres_array_literal_loses_exactly_its_outer_tokens():
    """The half-working case, asserted against the real permission check.

    This is the shape staging's ``etl-service`` role is stored in. It is worth an
    explicit test because a role that works for its middle permissions and fails
    for its outermost two is far harder to diagnose than one that plainly fails.
    """
    user = _user_with(STAGING_PG_ARRAY_LITERAL)

    assert not user.has_permission("incident:create"), "expected the first token to be lost"
    assert not user.has_permission("incident:set_reference_number"), "expected the last token to be lost"
    assert user.has_permission("incident:view_all"), "expected the middle token to survive"

    assert parse_permissions_like_runtime(STAGING_PG_ARRAY_LITERAL) == [
        "{incident:create",
        "incident:view_all",
        "incident:set_reference_number}",
    ]


def test_wildcard_row_grants_nothing_any_route_asks_for():
    """Staging role 1 is in this state: one permission, literally named ``*``."""
    user = _user_with(STAGING_WILDCARD)
    assert user.has_permission("*")
    for token in ("incident:create", "audit:read", "admin:manage", "incident:read"):
        assert not user.has_permission(token)


# --------------------------------------------------------------------------- #
# Encoding detection
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (STAGING_JSON_ARRAY, JSON_ARRAY),
        ("[]", JSON_ARRAY),
        (PRODUCTION_BARE_STRING, BARE_COMMA_SEPARATED),
        ("incident:create,incident:read", BARE_COMMA_SEPARATED),
        (STAGING_PG_ARRAY_LITERAL, POSTGRES_ARRAY_LITERAL),
    ],
)
def test_detect_encoding(raw, expected):
    assert detect_encoding(raw) == expected


# --------------------------------------------------------------------------- #
# What may be written
# --------------------------------------------------------------------------- #


def test_canonical_json_array_is_accepted_and_normalised():
    result = canonicalise_permissions_input('["incident:read", "  INCIDENT:create ", "incident:read"]')
    assert json.loads(result) == ["incident:create", "incident:read"]


def test_none_is_left_alone_and_empty_becomes_an_empty_array():
    assert canonicalise_permissions_input(None) is None
    assert canonicalise_permissions_input("") == "[]"
    assert canonicalise_permissions_input("[]") == "[]"


def test_normalisation_does_not_change_meaning():
    """Lower-casing and de-duplicating are safe: the real check already does both."""
    raw = '["INCIDENT:Read", "incident:read"]'
    canonical = canonicalise_permissions_input(raw)
    assert _user_with(canonical).has_permission("incident:read")
    assert _user_with(raw).has_permission("incident:read")


def test_wildcard_is_rejected_as_invalid_data():
    with pytest.raises(PermissionValidationError) as excinfo:
        canonicalise_permissions_input(STAGING_WILDCARD)
    message = str(excinfo.value)
    assert "wildcard" in message
    assert "exact set-membership" in message
    assert excinfo.value.details["wildcard_tokens"] == ["*"]


@pytest.mark.parametrize("raw", ['["incident:*"]', '["*:read"]', '["incident:read", "*"]'])
def test_glob_shaped_tokens_are_rejected_too(raw):
    """``incident:*`` is exactly as powerless as ``*``; neither is a feature."""
    with pytest.raises(PermissionValidationError, match="wildcard"):
        canonicalise_permissions_input(raw)


def test_unknown_token_is_rejected():
    with pytest.raises(PermissionValidationError) as excinfo:
        canonicalise_permissions_input('["bogus:perm"]')
    assert "not in the permission catalogue" in str(excinfo.value)
    assert excinfo.value.details["unknown_tokens"] == ["bogus:perm"]


def test_near_miss_token_gets_a_suggestion():
    with pytest.raises(PermissionValidationError) as excinfo:
        canonicalise_permissions_input('["incident:crate"]')
    assert "did you mean 'incident:create'" in str(excinfo.value)


def test_a_large_junk_payload_is_rejected_cheaply_and_readably():
    """Close-match search is per-token, so the message must not enumerate thousands.

    The count stays exact; only the listing is capped. Otherwise a rejection turns
    into a CPU sink and an error body nobody can read.
    """
    raw = json.dumps([f"junk{index}:perm" for index in range(2000)])

    with pytest.raises(PermissionValidationError) as excinfo:
        canonicalise_permissions_input(raw)

    message = str(excinfo.value)
    assert "2000 token(s)" in message
    assert "and 1990 more" in message
    assert len(message) < 2000, "the error message itself must stay readable"


def test_reserved_token_is_rejected_with_the_reason():
    with pytest.raises(PermissionValidationError) as excinfo:
        canonicalise_permissions_input('["policy:read"]')
    message = str(excinfo.value)
    assert "reserved" in message
    assert "no permission dependency" in message
    assert excinfo.value.details["reserved_tokens"] == ["policy:read"]


def test_postgres_array_literal_is_rejected_and_explained():
    with pytest.raises(PermissionValidationError) as excinfo:
        canonicalise_permissions_input(STAGING_PG_ARRAY_LITERAL)
    message = str(excinfo.value)
    assert "PostgreSQL array literal" in message
    assert "first and last permission" in message
    assert "JSON array" in message


def test_bare_comma_separated_is_rejected():
    with pytest.raises(PermissionValidationError) as excinfo:
        canonicalise_permissions_input("incident:create,incident:read")
    assert "comma-separated" in str(excinfo.value)


@pytest.mark.parametrize("raw", ['{"a": 1}', '"incident:read"', "42", "[1, 2]", '["incident:read", 5]'])
def test_shapes_that_are_not_arrays_of_strings_are_rejected(raw):
    with pytest.raises(PermissionValidationError):
        canonicalise_permissions_input(raw)


# --------------------------------------------------------------------------- #
# The schemas are wired to the rules
# --------------------------------------------------------------------------- #


def test_role_create_rejects_wildcard_as_a_validation_error():
    """A ``ValueError`` from the validator is what makes this a 422 and not a 500."""
    with pytest.raises(ValueError, match="wildcard"):
        RoleCreate(name="admin", permissions=STAGING_WILDCARD)


def test_role_update_rejects_uncatalogued_token():
    with pytest.raises(ValueError, match="not in the permission catalogue"):
        RoleUpdate(permissions='["bogus:perm"]')


def test_role_create_accepts_and_canonicalises():
    role = RoleCreate(name="ops", permissions='["incident:read","incident:create"]')
    assert json.loads(role.permissions) == ["incident:create", "incident:read"]


def test_role_update_without_permissions_is_untouched():
    """``exclude_unset`` must still be able to tell "absent" from "explicitly null"."""
    assert "permissions" not in RoleUpdate(description="x").model_dump(exclude_unset=True)
    assert RoleUpdate(permissions=None).model_dump(exclude_unset=True) == {"permissions": None}


# --------------------------------------------------------------------------- #
# Diagnosing rows that already exist
# --------------------------------------------------------------------------- #


def test_valid_stored_values_report_no_defect():
    assert describe_stored_permissions(None) is None
    assert describe_stored_permissions("[]") is None
    assert describe_stored_permissions(STAGING_JSON_ARRAY) is None
    assert describe_stored_permissions(json.dumps(["incident:create"])) is None


def test_stored_wildcard_is_diagnosed():
    defect = describe_stored_permissions(STAGING_WILDCARD)
    assert defect is not None
    assert defect.encoding == JSON_ARRAY
    assert defect.wildcard_tokens == ("*",)
    assert "grant nothing" in defect.message


def test_stored_postgres_array_literal_is_diagnosed_with_its_effective_tokens():
    defect = describe_stored_permissions(STAGING_PG_ARRAY_LITERAL)
    assert defect is not None
    assert defect.encoding == POSTGRES_ARRAY_LITERAL
    assert "silently lossy" in defect.message
    assert defect.tokens_seen == (
        "{incident:create",
        "incident:view_all",
        "incident:set_reference_number}",
    )
    assert "{incident:create" in defect.unknown_tokens


def test_stored_bare_string_is_diagnosed_without_claiming_the_tokens_are_wrong():
    """``audit:read`` is a real permission; only the encoding is wrong."""
    defect = describe_stored_permissions(PRODUCTION_BARE_STRING)
    assert defect is not None
    assert defect.encoding == BARE_COMMA_SEPARATED
    assert defect.unknown_tokens == ()
    assert defect.tokens_seen == ("audit:read",)


def test_stored_uncatalogued_token_is_diagnosed():
    defect = describe_stored_permissions('["bogus:perm"]')
    assert defect is not None
    assert defect.unknown_tokens == ("bogus:perm",)
