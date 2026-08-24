"""Classify every endpoint the app serves by what it actually demands of a caller.

Why this exists
---------------
:mod:`src.domain.authz.catalogue` answers "what permissions exist". It cannot
answer "which endpoints check one", and that was the larger defect: a sample of
45 endpoints suggested 6 were authorisation-checked, and nothing in the repo
could turn that sample into a number. A sample cannot, because the routers are
wildly uneven — some modules gate every write, others gate none — so any sample
small enough to read by hand is unrepresentative by construction. This module
replaces it with a census of all of them.

What a posture means
--------------------
A posture describes what a request must satisfy *before the handler runs*, read
off the route's own dependency graph. That is deliberately narrower than "is this
endpoint safe":

- An in-handler ``current_user.has_permission(...)`` call does not change the
  posture. Most of them narrow a result set rather than refuse the request, so
  the endpoint is still reachable by any authenticated caller, which is what
  :data:`Posture.AUTHENTICATED_ONLY` says. Where such a call exists it is
  recorded in the declaration's reason instead of quietly upgrading the posture.
- Tenant scoping is not authorisation and is not read here. It is a separate
  control, owned elsewhere.

Fail closed
-----------
Every posture is derived from a tag the API layer stamps on its dependency
callables — never from the callable's name. A renamed or newly added
authentication dependency that forgets to stamp itself does not get quietly
treated as authenticating: its endpoints classify as
:data:`Posture.UNAUTHENTICATED`, which is the posture that must be declared
route by route and cannot grow without a reviewer bumping a recorded count. The
mechanism's failure mode is therefore a loud one in the alarming direction.

Nothing here reads or writes a database, and nothing imports FastAPI: the app is
passed in and its routes are duck-typed, because ``src/domain`` may not import
``src/api`` (``scripts/check_import_boundaries.py`` enforces it).
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

from src.domain.authz.extraction import REQUIRED_PERMISSION_ATTR, MountedEndpoint, walk_mounted_app

#: Attribute under which the API layer records what kind of caller identity a
#: dependency establishes, so this module can classify a route without matching
#: on function names. Declared in the lower layer and imported by the API layer,
#: for the same reason as :data:`REQUIRED_PERMISSION_ATTR`: one magic string
#: needs exactly one owner, and a second copy would fall out of step.
AUTHENTICATION_KIND_ATTR = "__qgp_authentication_kind__"


class AuthenticationKind(str, Enum):
    """What a stamped authentication dependency establishes about the caller."""

    #: A valid access token is required; the request fails with 401 without one.
    REQUIRED = "required"
    #: A valid access token is required *and* the user must be a superuser.
    SUPERUSER = "superuser"
    #: A token is read when present and ignored when absent. Not a gate.
    OPTIONAL = "optional"


class Posture(str, Enum):
    """What an endpoint demands before its handler runs.

    Ordered from strongest to weakest. :func:`posture_of` picks the strongest
    that applies, so a route carrying both a permission dependency and a
    superuser dependency reports ``PERMISSION``.
    """

    #: A ``require_permission`` dependency: a named permission is checked.
    PERMISSION = "permission"
    #: ``CurrentSuperuser``: authorisation by account flag rather than permission.
    SUPERUSER = "superuser"
    #: Authenticated, and then anything goes. This is the enforcement gap.
    AUTHENTICATED_ONLY = "authenticated_only"
    #: Reads the caller if they present a token, serves them either way.
    OPTIONAL_AUTH = "optional_auth"
    #: No caller identity is established at all.
    UNAUTHENTICATED = "unauthenticated"

    @property
    def is_authorisation_checked(self) -> bool:
        return self in (Posture.PERMISSION, Posture.SUPERUSER)

    @property
    def must_be_declared(self) -> bool:
        """True for postures a human has to justify route by route.

        ``PERMISSION`` and ``SUPERUSER`` need no declaration: the route says what
        it enforces, and the catalogue guards the token. The rest are claims that
        an endpoint needs no authorisation, and a claim needs an author.
        """
        return not self.is_authorisation_checked


@dataclass(frozen=True)
class EndpointPosture:
    """One endpoint, and what it demands."""

    method: str
    path: str
    endpoint_name: str
    posture: Posture
    permissions: tuple[str, ...]
    #: False when the endpoint has no resolved dependency graph, so its posture is
    #: "nothing was readable" rather than "nothing was there". See
    #: :class:`src.domain.authz.extraction.MountedEndpoint`.
    dependencies_readable: bool = True

    @property
    def key(self) -> tuple[str, str]:
        """The identity a declaration is written against."""
        return (self.method, self.path)

    def __str__(self) -> str:
        return f"{self.method} {self.path}"


@dataclass(frozen=True)
class Census:
    """Every endpoint the app serves, classified."""

    endpoints: tuple[EndpointPosture, ...]

    @property
    def counts(self) -> dict[Posture, int]:
        tally = Counter(endpoint.posture for endpoint in self.endpoints)
        return {posture: tally.get(posture, 0) for posture in Posture}

    def with_posture(self, *postures: Posture) -> tuple[EndpointPosture, ...]:
        wanted = set(postures)
        return tuple(endpoint for endpoint in self.endpoints if endpoint.posture in wanted)

    @property
    def undeclarable_keys(self) -> set[tuple[str, str]]:
        """Keys of every endpoint whose posture a human must justify."""
        return {endpoint.key for endpoint in self.endpoints if endpoint.posture.must_be_declared}

    @property
    def permissions_in_use(self) -> set[str]:
        return {token for endpoint in self.endpoints for token in endpoint.permissions}

    @property
    def with_unreadable_dependencies(self) -> tuple[EndpointPosture, ...]:
        """Endpoints served without a dependency graph the walk could read."""
        return tuple(endpoint for endpoint in self.endpoints if not endpoint.dependencies_readable)

    def format_summary(self) -> str:
        counts = self.counts
        total = len(self.endpoints)
        checked = counts[Posture.PERMISSION] + counts[Posture.SUPERUSER]
        lines = [
            f"endpoints                        : {total}",
            f"authorisation-checked            : {checked}",
            f"  via a named permission         : {counts[Posture.PERMISSION]}",
            f"  via superuser only             : {counts[Posture.SUPERUSER]}",
            f"authenticated only (no authz)    : {counts[Posture.AUTHENTICATED_ONLY]}",
            f"optional authentication          : {counts[Posture.OPTIONAL_AUTH]}",
            f"no caller identity established   : {counts[Posture.UNAUTHENTICATED]}",
            f"  of which no readable deps      : {len(self.with_unreadable_dependencies)}",
            f"distinct permissions in use      : {len(self.permissions_in_use)}",
        ]
        return "\n".join(lines)


class DuplicateEndpointKeyError(RuntimeError):
    """Two endpoints share a (method, path) key.

    A declaration is written against that key, so a duplicate would let one
    endpoint's justification silently cover another. Raised rather than
    de-duplicated: the right answer depends on which route actually serves the
    request, and guessing is how an exemption ends up covering something nobody
    reviewed.
    """


def _permission_tokens(endpoint: MountedEndpoint) -> tuple[str, ...]:
    tokens: set[str] = set()
    for call in endpoint.calls:
        token = getattr(call, REQUIRED_PERMISSION_ATTR, None)
        if isinstance(token, str):
            tokens.add(token)
    return tuple(sorted(tokens))


def _authentication_kinds(endpoint: MountedEndpoint) -> set[AuthenticationKind]:
    kinds: set[AuthenticationKind] = set()
    for call in endpoint.calls:
        raw = getattr(call, AUTHENTICATION_KIND_ATTR, None)
        if raw is None:
            continue
        try:
            kinds.add(AuthenticationKind(raw))
        except ValueError:
            # An unrecognised value is a tag this module does not understand.
            # Ignoring it leaves the endpoint looking unauthenticated, which is
            # the direction that has to be declared, so the mistake surfaces.
            continue
    return kinds


def posture_of(endpoint: MountedEndpoint) -> tuple[Posture, tuple[str, ...]]:
    """Classify one mounted endpoint. Returns its posture and its permissions."""
    permissions = _permission_tokens(endpoint)
    if permissions:
        return Posture.PERMISSION, permissions
    kinds = _authentication_kinds(endpoint)
    if AuthenticationKind.SUPERUSER in kinds:
        return Posture.SUPERUSER, ()
    if AuthenticationKind.REQUIRED in kinds:
        return Posture.AUTHENTICATED_ONLY, ()
    if AuthenticationKind.OPTIONAL in kinds:
        return Posture.OPTIONAL_AUTH, ()
    return Posture.UNAUTHENTICATED, ()


def take_census(app: Any) -> Census:
    """Classify every endpoint mounted on ``app``.

    Raises :class:`DuplicateEndpointKeyError` if two endpoints share a
    ``(method, path)`` key, because declarations are written against that key.
    """
    classified: list[EndpointPosture] = []
    for mounted in walk_mounted_app(app).endpoints:
        posture, permissions = posture_of(mounted)
        for method in mounted.methods:
            classified.append(
                EndpointPosture(
                    method=method,
                    path=mounted.path,
                    endpoint_name=mounted.endpoint_name,
                    posture=posture,
                    permissions=permissions,
                    dependencies_readable=mounted.dependencies_readable,
                )
            )

    seen: dict[tuple[str, str], EndpointPosture] = {}
    duplicates: list[str] = []
    for endpoint in classified:
        previous = seen.get(endpoint.key)
        if previous is not None:
            duplicates.append(f"{endpoint} served by both {previous.endpoint_name} and {endpoint.endpoint_name}")
        else:
            seen[endpoint.key] = endpoint
    if duplicates:
        raise DuplicateEndpointKeyError(
            "endpoints share a (method, path) key, so an authorisation declaration written "
            "against that key would cover more than one of them:\n" + "\n".join(f"  {d}" for d in duplicates)
        )

    return Census(endpoints=tuple(sorted(classified, key=lambda e: (e.path, e.method))))


def format_undeclared_report(
    census: Census,
    *,
    declared: set[tuple[str, str]],
    limit: Optional[int] = 40,
) -> str:
    """Describe endpoints whose posture nobody has justified."""
    missing = sorted(
        (
            endpoint
            for endpoint in census.endpoints
            if endpoint.posture.must_be_declared and endpoint.key not in declared
        ),
        key=lambda e: (e.path, e.method),
    )
    shown = missing if limit is None else missing[:limit]
    lines = [f"{len(missing)} endpoint(s) have no authorisation declaration:"]
    lines += [f"  {endpoint.posture.value:18s} {endpoint}  ({endpoint.endpoint_name})" for endpoint in shown]
    if limit is not None and len(missing) > len(shown):
        lines.append(f"  ... and {len(missing) - len(shown)} more")
    return "\n".join(lines)


__all__ = [
    "AUTHENTICATION_KIND_ATTR",
    "AuthenticationKind",
    "Census",
    "DuplicateEndpointKeyError",
    "EndpointPosture",
    "Posture",
    "format_undeclared_report",
    "posture_of",
    "take_census",
]
