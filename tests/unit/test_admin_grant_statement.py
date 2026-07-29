"""Keep the hand-back SQL in step with the catalogue it claims to come from.

``docs/data/admin-role-permissions-grant.md`` holds an ``UPDATE`` statement written
for a human to run against production. It is the one artefact in this repository
whose staleness is not caught by anything else: the catalogue tests check the
catalogue against the code, but nothing checks a literal sitting in a document, and
a document that has been reviewed and approved is precisely the thing somebody will
paste into a database months later.

So the statement is parsed back out of the document and compared to
:data:`ADMIN_ROLE_PERMISSIONS`. Add a permission to the catalogue and this fails
until the hand-back is regenerated, which is the only way an approved statement and
the code can be kept from disagreeing.

This applies nothing and connects to no database.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from src.domain.authz.catalogue import (
    ADMIN_ROLE_PERMISSIONS,
    GRANTABLE_PERMISSIONS,
    REFERENCE_NUMBER_PERMISSIONS,
    RESERVED_PERMISSIONS,
    VIEW_ALL_PERMISSIONS,
)

DOCUMENT = Path(__file__).resolve().parents[2] / "docs" / "data" / "admin-role-permissions-grant.md"

#: The value assigned by each ``UPDATE``, i.e. the JSON array between the single
#: quotes on every ``SET permissions = '...'`` line. Both the wildcard repair
#: (Step 2) and the 75→77 upgrade (Step 2b) must write the same catalogue value.
_SET_CLAUSE = re.compile(r"^SET permissions = '(\[.*\])'$", re.MULTILINE)


@pytest.fixture(scope="module")
def document() -> str:
    assert DOCUMENT.exists(), f"{DOCUMENT} is missing; the C-1 hand-back has been deleted"
    return DOCUMENT.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def granted_token_lists(document: str) -> list[list[str]]:
    matches = _SET_CLAUSE.findall(document)
    assert len(matches) >= 1, (
        f"expected at least one `SET permissions = '[...]'` line in {DOCUMENT.name}, found "
        f"{len(matches)}. This guard reads the statement out of the document, so it cannot check "
        "a statement it cannot find."
    )
    return [json.loads(match) for match in matches]


@pytest.fixture(scope="module")
def granted_tokens(granted_token_lists: list[list[str]]) -> list[str]:
    """Canonical grant from the document; every SET clause must agree with it."""
    first = granted_token_lists[0]
    for other in granted_token_lists[1:]:
        assert other == first, (
            "every SET permissions value in docs/data/admin-role-permissions-grant.md must be "
            "identical; the wildcard repair and the 75→77 upgrade write the same catalogue grant"
        )
    return first


def test_the_statement_grants_exactly_the_catalogued_admin_list(granted_tokens: list[str]) -> None:
    """The document and the catalogue must not be able to disagree."""
    assert granted_tokens == list(ADMIN_ROLE_PERMISSIONS), (
        "the UPDATE in docs/data/admin-role-permissions-grant.md no longer matches "
        "ADMIN_ROLE_PERMISSIONS in src/domain/authz/catalogue.py.\n"
        f"  document: {len(granted_tokens)} tokens\n"
        f"  catalogue: {len(ADMIN_ROLE_PERMISSIONS)} tokens\n"
        f"  only in document: {sorted(set(granted_tokens) - set(ADMIN_ROLE_PERMISSIONS))}\n"
        f"  only in catalogue: {sorted(set(ADMIN_ROLE_PERMISSIONS) - set(granted_tokens))}\n"
        "Regenerate the statement. An approved-but-stale statement is the one that gets pasted "
        "into production."
    )
    assert len(granted_tokens) == 77
    assert "action:read" in granted_tokens
    assert "risk:read" in granted_tokens
    assert "*" not in granted_tokens


def test_the_document_includes_the_75_to_77_upgrade(document: str) -> None:
    """Live DBs hold 75 tokens; the upgrade statement must be present and scoped."""
    assert "json_array_length(permissions::json) = 75" in document
    assert "action:read" in document
    assert "risk:read" in document


def test_the_statement_grants_nothing_outside_the_catalogue(granted_tokens: list[str]) -> None:
    """A token nothing checks would make the role look more restricted than it is."""
    ungrantable = sorted(set(granted_tokens) - GRANTABLE_PERMISSIONS)
    assert not ungrantable, f"the statement grants {ungrantable}, which no code path checks"
    assert not set(granted_tokens) & set(RESERVED_PERMISSIONS)


def test_the_statement_omits_the_two_excluded_families(granted_tokens: list[str]) -> None:
    """The exclusions are a product decision, not an accident of sorting."""
    assert not set(granted_tokens) & VIEW_ALL_PERMISSIONS, (
        "*:view_all defeats the own-records-only narrowing some list endpoints apply, and was "
        "excluded from the admin grant on purpose"
    )
    assert not set(granted_tokens) & REFERENCE_NUMBER_PERMISSIONS


def test_the_statement_contains_no_wildcard(granted_tokens: list[str]) -> None:
    """The whole point of C-1: an enumerated grant, not a wildcard.

    ``has_permission`` does exact set-membership, so a wildcard grants one
    permission literally named ``*`` and satisfies nothing.
    """
    assert not [token for token in granted_tokens if "*" in token]


def test_the_update_is_scoped_to_the_row_and_the_value_it_was_written_for(document: str) -> None:
    """An unscoped UPDATE would rewrite every role in the table.

    The ``WHERE`` clause is the difference between fixing one row and granting 77
    permissions to every role in the database, so it is asserted rather than
    trusted to survive editing.
    """
    statement = document[document.index("UPDATE roles") :]
    statement = statement[: statement.index("```")]

    assert "WHERE name = 'admin'" in statement, "the UPDATE is not restricted to the admin role"
    assert "AND permissions = '[\"*\"]'" in statement, (
        "the UPDATE is not restricted to the wildcard value it was written for, so re-running it "
        "would overwrite a row somebody has already corrected"
    )


def test_the_document_says_it_has_not_been_applied(document: str) -> None:
    """The 77-token hand-back has to keep saying so, or somebody will assume it was done."""
    assert "NOT APPLIED" in document
    assert "rollback" in document.lower()


def test_nothing_in_the_repository_executes_the_grant() -> None:
    """The proposal must stay a proposal: no migration or seed may apply it.

    ``ADMIN_ROLE_PERMISSIONS`` is deliberately read by tests and documentation
    only. If a revision or a startup hook starts writing it, applying the grant
    stops being a human decision and this file's whole premise is gone.
    """
    repo = Path(__file__).resolve().parents[2]
    allowed_prefixes = (
        "src/domain/authz/",
        "tests/",
        "docs/",
        "scripts/",
    )
    offenders: list[str] = []
    for path in sorted(repo.glob("src/**/*.py")) + sorted(repo.glob("alembic/**/*.py")):
        relative = path.relative_to(repo).as_posix()
        if relative.startswith(allowed_prefixes):
            continue
        if "ADMIN_ROLE_PERMISSIONS" in path.read_text(encoding="utf-8"):
            offenders.append(relative)

    assert not offenders, (
        f"{offenders} reference ADMIN_ROLE_PERMISSIONS. It is a reviewable proposal, not a "
        "migration: writing it to a database has to stay a human decision taken against "
        "docs/data/admin-role-permissions-grant.md."
    )
