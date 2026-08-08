"""Optimistic concurrency for Job Lifecycle axis edits (JL-UX-W4).

Two operators editing the same pack used to last-write-wins in silence: the
loser's rename simply disappeared. A ``PATCH`` may now carry ``If-Match`` with
the ``updated_at`` the client actually read, and the server refuses the write
with **409** when the row has moved on.

The token is the row's ``updated_at`` rather than a new ``version`` column, so
this needs no schema change and no second stamp to keep in step with the one
SQLAlchemy already maintains. It is deliberately *opt-in*: a request with no
``If-Match`` behaves exactly as it did before, so existing clients are not
broken by a header they do not send.

Scope, stated plainly: the precondition is evaluated on the row as read and the
write follows in the same transaction, so a committer that lands in the gap
between that read and this write is not caught. This closes the window an
operator can actually lose a rename in — minutes of an open form — not the
sub-millisecond one. Closing that too needs the predicate carried on the UPDATE
itself and a rowcount check, which is a wider change than this wave.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

#: RFC 7232 wildcard — "any current representation". The row existing is the
#: whole of the precondition.
ANY_ETAG = "*"


def as_aware_utc(value: Optional[datetime]) -> Optional[datetime]:
    """Read a naive timestamp as UTC so aware/naive never meet in a compare."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def job_lifecycle_etag(updated_at: Optional[datetime]) -> Optional[str]:
    """Canonical concurrency token for a row: its ``updated_at`` in UTC ISO.

    Returned in the 409 body so a client can see what the server is holding
    without having to re-read the row to find out why it was refused.
    """
    aware = as_aware_utc(updated_at)
    if aware is None:
        return None
    return aware.isoformat()


def parse_if_match(raw: Optional[str]) -> Optional[datetime]:
    """Parse an ``If-Match`` value into an aware UTC datetime.

    Accepts what a client can reasonably send back: the ``updated_at`` string
    from the response body, optionally quoted and optionally weak-tagged
    (``W/"…"``), with either ``+00:00`` or ``Z``. Returns ``None`` for an
    absent header or the ``*`` wildcard — both mean "no timestamp to compare".

    Raises ``ValueError`` on a value that is present but unparsable. Guessing
    at a malformed precondition would defeat the point of sending one.
    """
    if raw is None:
        return None
    token = raw.strip()
    if not token or token == ANY_ETAG:
        return None
    if token[:2].upper() == "W/":
        token = token[2:].strip()
    if len(token) >= 2 and token[0] == '"' and token[-1] == '"':
        token = token[1:-1]
    token = token.strip()
    if not token:
        raise ValueError("If-Match must carry the updated_at value that was read")
    if token.endswith(("Z", "z")):
        token = f"{token[:-1]}+00:00"
    parsed = datetime.fromisoformat(token)
    aware = as_aware_utc(parsed)
    assert aware is not None  # fromisoformat cannot yield None
    return aware


def if_match_matches(*, if_match: Optional[str], updated_at: Optional[datetime]) -> bool:
    """Whether the precondition holds for a row with this ``updated_at``.

    A missing header or ``*`` passes: the caller opted out of the check, or
    asked only that the row exist. An unparsable header raises, and a row with
    no ``updated_at`` at all cannot satisfy a timestamp precondition, so it
    fails rather than being waved through.
    """
    expected = parse_if_match(if_match)
    if expected is None:
        return True
    current = as_aware_utc(updated_at)
    if current is None:
        return False
    return current == expected


__all__ = [
    "ANY_ETAG",
    "as_aware_utc",
    "if_match_matches",
    "job_lifecycle_etag",
    "parse_if_match",
]
