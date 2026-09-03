"""AUD-F3: what an answer write reads, and what it refuses to precondition on.

Two rules are pinned here, both cheap to break by accident later:

1. ``client_revision`` is a *tolerant* read out of ``response_json``. It lives
   there rather than in a new column so this save-path fix needs no migration,
   and anything that is not a whole number counts as "not supplied" rather than
   as an error — a client that has never heard of revisions must keep saving.
2. Answer writes declare no ``If-Match``. The token is the run's ``updated_at``
   and every answer bumps it, so a run-level precondition made one auditor's
   second question conflict with their own first one and report the audit as
   "updated on another device". It stays on the lifecycle transitions, where two
   devices genuinely can disagree.
"""

from __future__ import annotations

import pytest

from src.api.routes.audits import CLIENT_REVISION_KEY, _client_revision, _incoming_revision_is_older, router
from src.domain.models.audit import AuditResponse

#: The only routes on this router that may demand a matching run token.
IF_MATCH_ROUTES = {
    ("POST", "/runs/{run_id}/acknowledge"),
    ("POST", "/runs/{run_id}/start"),
    ("POST", "/runs/{run_id}/complete"),
}


@pytest.mark.parametrize(
    ("stored", "expected"),
    [
        ({CLIENT_REVISION_KEY: 4}, 4),
        ({CLIENT_REVISION_KEY: 4.0}, 4),
        ({CLIENT_REVISION_KEY: "4"}, 4),
        ({CLIENT_REVISION_KEY: " 4 "}, 4),
        ({CLIENT_REVISION_KEY: 0}, 0),
        # Not a revision: treated as absent so the write still applies.
        ({CLIENT_REVISION_KEY: True}, None),
        ({CLIENT_REVISION_KEY: 4.5}, None),
        ({CLIENT_REVISION_KEY: "latest"}, None),
        ({CLIENT_REVISION_KEY: None}, None),
        ({"evidence_asset_ids": [1]}, None),
        ({}, None),
        (None, None),
        ("not-an-object", None),
        ([{CLIENT_REVISION_KEY: 4}], None),
    ],
)
def test_client_revision_is_read_tolerantly(stored: object, expected: int | None) -> None:
    assert _client_revision(stored) == expected


def _row(response_json: object) -> AuditResponse:
    row = AuditResponse()
    row.__dict__.update({"id": 1, "run_id": 1, "question_id": 1, "response_json": response_json})
    return row


def test_a_lower_revision_is_older():
    assert _incoming_revision_is_older(_row({CLIENT_REVISION_KEY: 9}), {"response_json": {CLIENT_REVISION_KEY: 8}})


def test_an_equal_revision_is_not_older_so_a_retry_still_applies():
    """A client retrying after a timeout cannot know whether its write landed."""
    assert not _incoming_revision_is_older(_row({CLIENT_REVISION_KEY: 9}), {"response_json": {CLIENT_REVISION_KEY: 9}})


def test_a_write_with_no_revision_applies():
    assert not _incoming_revision_is_older(_row({CLIENT_REVISION_KEY: 9}), {"response_json": {"selected": ["a"]}})


def test_a_write_that_omits_response_json_entirely_applies():
    """Omitted is not the same as cleared: the stored revision is left alone."""
    assert not _incoming_revision_is_older(_row({CLIENT_REVISION_KEY: 9}), {"response_value": "yes"})


def test_a_row_with_no_stored_revision_never_refuses_a_write():
    assert not _incoming_revision_is_older(_row(None), {"response_json": {CLIENT_REVISION_KEY: 1}})


def test_only_run_lifecycle_transitions_declare_if_match() -> None:
    """Reintroducing the header on an answer write reintroduces the defect."""
    declared: set[tuple[str, str]] = set()
    for route in router.routes:
        dependant = getattr(route, "dependant", None)
        if dependant is None:
            continue
        aliases = {str(getattr(param, "alias", "")).lower() for param in dependant.header_params}
        if "if-match" not in aliases:
            continue
        for method in route.methods or set():
            declared.add((method, route.path))

    assert declared == IF_MATCH_ROUTES
