"""Validation and canonical encoding for ``roles.permissions``.

``roles.permissions`` is a nullable ``Text`` column and nothing has ever
validated what goes into it, so the live databases hold three different
encodings of the same idea:

===========================  ==================================================
bare comma-separated         ``audit:read``
JSON array                   ``["complaint:create", "complaint:read"]``
PostgreSQL array literal     ``{incident:create,incident:view_all}``
===========================  ==================================================

``User.has_permission`` tries ``json.loads`` first and falls back to splitting on
commas, so the third form is the dangerous one: the braces stay attached to the
first and last tokens, meaning the role silently loses exactly its first and last
permission while the ones in the middle work. A role that half works is much
harder to diagnose than one that plainly does not.

This module makes a JSON array of catalogued tokens the only thing that can be
written from now on, and rejects everything else with a message that says which
of these encodings it looks like and what to send instead.
"""

from __future__ import annotations

import difflib
import json
from dataclasses import dataclass
from typing import Any, Optional

from src.domain.authz.catalogue import ENFORCED_PERMISSIONS, GRANTABLE_PERMISSIONS, RESERVED_PERMISSIONS

#: Encoding names reported by :func:`detect_encoding`.
JSON_ARRAY = "json_array"
JSON_SCALAR = "json_scalar"
POSTGRES_ARRAY_LITERAL = "postgres_array_literal"
BARE_COMMA_SEPARATED = "bare_comma_separated"
EMPTY = "empty"

_CANONICAL_HINT = (
    'Send permissions as a JSON array of catalogued tokens, e.g. ["incident:create", "incident:read"]. '
    "Use [] for a role with no permissions."
)

#: Cap on how many offending tokens an error message enumerates. Keeps a rejection
#: cheap and readable when the payload is large; the count is always exact.
_MAX_TOKENS_LISTED_IN_ERROR = 10


class PermissionValidationError(ValueError):
    """A rejected ``permissions`` value.

    Subclasses :class:`ValueError` so a Pydantic field validator turns it into a
    422 automatically instead of letting it escape as a 500.
    """

    def __init__(self, message: str, *, details: Optional[dict[str, Any]] = None) -> None:
        super().__init__(message)
        self.message = message
        self.details: dict[str, Any] = details or {}


def detect_encoding(raw: str) -> str:
    """Name the encoding ``raw`` appears to use, for use in error messages."""
    candidate = raw.strip()
    if not candidate:
        return EMPTY
    try:
        decoded = json.loads(candidate)
    except (json.JSONDecodeError, ValueError):
        if candidate.startswith("{") and candidate.endswith("}"):
            return POSTGRES_ARRAY_LITERAL
        return BARE_COMMA_SEPARATED
    return JSON_ARRAY if isinstance(decoded, list) else JSON_SCALAR


def parse_permissions_like_runtime(raw: Any) -> list[str]:
    """Return the tokens ``User.has_permission`` would actually see in ``raw``.

    A deliberate replica of ``User.has_permission``'s parsing, including its
    comma-splitting fallback, so that diagnostics describe what the running code
    does rather than what it ought to do. ``User.has_permission`` belongs to
    another lane and is not changed here;
    ``tests/unit/test_permission_validation.py`` pins this replica to the real
    implementation's observable behaviour so the two cannot drift apart.
    """
    if not raw:
        return []
    parsed: list[str]
    if isinstance(raw, str):
        try:
            decoded = json.loads(raw)
        except json.JSONDecodeError:
            decoded = [part.strip() for part in raw.split(",") if part.strip()]
        parsed = decoded if isinstance(decoded, list) else []
    elif isinstance(raw, list):
        parsed = [str(item) for item in raw]
    else:
        parsed = []
    return [str(item).strip().lower() for item in parsed if str(item).strip()]


def _suggestion_for(token: str) -> str:
    close = difflib.get_close_matches(token, sorted(ENFORCED_PERMISSIONS), n=1, cutoff=0.8)
    return f" (did you mean {close[0]!r}?)" if close else ""


def _reject_non_array(raw: str, encoding: str) -> PermissionValidationError:
    if encoding == POSTGRES_ARRAY_LITERAL:
        seen = parse_permissions_like_runtime(raw)
        return PermissionValidationError(
            "permissions looks like a PostgreSQL array literal, not a JSON array. "
            "This encoding is silently lossy: the permission check falls back to splitting on "
            "commas, so the braces stay attached and the role loses exactly its first and last "
            f"permission while the rest work. Parsed as {seen!r}. " + _CANONICAL_HINT,
            details={"encoding": encoding, "parsed_as": seen},
        )
    if encoding == BARE_COMMA_SEPARATED:
        seen = parse_permissions_like_runtime(raw)
        return PermissionValidationError(
            "permissions must be a JSON array, not a comma-separated string. "
            f"Received {len(seen)} comma-separated token(s). " + _CANONICAL_HINT,
            details={"encoding": encoding, "parsed_as": seen},
        )
    return PermissionValidationError(
        f"permissions must be a JSON array; received a JSON {encoding.replace('json_', '')}. " + _CANONICAL_HINT,
        details={"encoding": encoding},
    )


def canonicalise_permissions_input(raw: Optional[str]) -> Optional[str]:
    """Validate an incoming ``permissions`` value and return its canonical form.

    Accepts ``None`` (unchanged), an empty string (meaning "no permissions", and
    canonicalised to ``[]``), or a JSON array of catalogued tokens. Tokens are
    stripped, lower-cased, de-duplicated and sorted, which is safe because
    ``User.has_permission`` already compares case-insensitively on stripped
    tokens — the stored value changes shape, never meaning.

    Raises :class:`PermissionValidationError` for anything else, including the
    wildcard ``*``, unknown tokens, and reserved tokens that nothing enforces.
    """
    if raw is None:
        return None
    if not isinstance(raw, str):
        raise PermissionValidationError(
            f"permissions must be a JSON array encoded as a string; received {type(raw).__name__}. " + _CANONICAL_HINT,
            details={"encoding": "not_a_string"},
        )

    encoding = detect_encoding(raw)
    if encoding == EMPTY:
        return "[]"
    if encoding != JSON_ARRAY:
        raise _reject_non_array(raw, encoding)

    decoded = json.loads(raw)
    non_strings = [item for item in decoded if not isinstance(item, str)]
    if non_strings:
        raise PermissionValidationError(
            "permissions must be a JSON array of strings; found "
            f"{', '.join(sorted({type(item).__name__ for item in non_strings}))}. " + _CANONICAL_HINT,
            details={"encoding": encoding, "non_string_items": [repr(item) for item in non_strings]},
        )

    tokens = [item.strip().lower() for item in decoded if item.strip()]

    wildcards = sorted({token for token in tokens if "*" in token})
    if wildcards:
        raise PermissionValidationError(
            f"permissions may not contain a wildcard: {wildcards!r}. Permission checks are exact "
            "set-membership — there is no wildcard, prefix or glob expansion anywhere in the "
            'permission check, so a role holding ["*"] holds one permission literally named "*" '
            "and satisfies nothing any route asks for. List the tokens explicitly. " + _CANONICAL_HINT,
            details={"wildcard_tokens": wildcards},
        )

    reserved = sorted({token for token in tokens if token in RESERVED_PERMISSIONS})
    if reserved:
        explanations = "; ".join(f"{token}: {RESERVED_PERMISSIONS[token]}" for token in reserved)
        raise PermissionValidationError(
            f"permissions contains reserved token(s) that no code path checks: {reserved!r}. "
            "Granting one would make a role look restricted in an access review while restricting "
            f"nothing. Reasons — {explanations}. If the check now exists, promote the token into "
            "ENFORCED_PERMISSIONS in src/domain/authz/catalogue.py.",
            details={"reserved_tokens": reserved},
        )

    unknown = sorted({token for token in tokens if token not in GRANTABLE_PERMISSIONS})
    if unknown:
        # Only the first few are spelled out with a suggestion. Close-match search
        # is O(catalogue) per token, so a request carrying thousands of junk tokens
        # would otherwise turn a rejection into a CPU sink and an unreadable message.
        shown = unknown[:_MAX_TOKENS_LISTED_IN_ERROR]
        listed = ", ".join(f"{token!r}{_suggestion_for(token)}" for token in shown)
        if len(unknown) > len(shown):
            listed += f", and {len(unknown) - len(shown)} more"
        raise PermissionValidationError(
            f"permissions contains {len(unknown)} token(s) that are not in the permission "
            f"catalogue: {listed}. Only tokens the code actually checks may be granted; see "
            "src/domain/authz/catalogue.py.",
            details={"unknown_tokens": unknown[:_MAX_TOKENS_LISTED_IN_ERROR]},
        )

    return json.dumps(sorted(set(tokens)))


@dataclass(frozen=True)
class StoredPermissionsDefect:
    """What is wrong with a ``permissions`` value already in the database."""

    encoding: str
    tokens_seen: tuple[str, ...]
    wildcard_tokens: tuple[str, ...]
    reserved_tokens: tuple[str, ...]
    unknown_tokens: tuple[str, ...]
    message: str


def describe_stored_permissions(raw: Optional[str]) -> Optional[StoredPermissionsDefect]:
    """Describe a stored value that the write-time rules would now reject.

    Returns ``None`` when the stored value is already valid. Diagnosis only —
    this never modifies anything.
    """
    if raw is None:
        return None
    encoding = detect_encoding(raw) if isinstance(raw, str) else "not_a_string"
    seen = tuple(parse_permissions_like_runtime(raw))
    wildcards = tuple(sorted({token for token in seen if "*" in token}))
    reserved = tuple(sorted({token for token in seen if token in RESERVED_PERMISSIONS}))
    unknown = tuple(
        sorted({token for token in seen if token not in GRANTABLE_PERMISSIONS and token not in RESERVED_PERMISSIONS})
    )

    if encoding in (EMPTY, JSON_ARRAY) and not wildcards and not reserved and not unknown:
        return None

    faults: list[str] = []
    if encoding == POSTGRES_ARRAY_LITERAL:
        faults.append(
            "it is a PostgreSQL array literal rather than a JSON array, which is silently lossy: "
            "the permission check falls back to splitting on commas, so the braces stay attached "
            "and the role loses exactly its first and last permission while the rest work"
        )
    elif encoding == BARE_COMMA_SEPARATED:
        faults.append("it is a comma-separated string rather than a JSON array")
    elif encoding == JSON_SCALAR:
        faults.append("it is a JSON scalar rather than a JSON array")
    elif encoding == "not_a_string":
        faults.append("it is not stored as a string")
    if wildcards:
        faults.append(
            f"it contains the wildcard token(s) {list(wildcards)!r}, which grant nothing because "
            "permission checks are exact set-membership"
        )
    if reserved:
        faults.append(f"it grants reserved token(s) {list(reserved)!r} that no code path checks")
    if unknown:
        faults.append(f"it grants unknown token(s) {list(unknown)!r} that are not in the catalogue")

    return StoredPermissionsDefect(
        encoding=encoding,
        tokens_seen=seen,
        wildcard_tokens=wildcards,
        reserved_tokens=reserved,
        unknown_tokens=unknown,
        message="; and ".join(faults),
    )


__all__ = [
    "BARE_COMMA_SEPARATED",
    "EMPTY",
    "JSON_ARRAY",
    "JSON_SCALAR",
    "POSTGRES_ARRAY_LITERAL",
    "PermissionValidationError",
    "StoredPermissionsDefect",
    "canonicalise_permissions_input",
    "describe_stored_permissions",
    "detect_encoding",
    "parse_permissions_like_runtime",
]
