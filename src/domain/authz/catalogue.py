"""The permission vocabulary of this product, as a reviewable literal.

Why this file exists
--------------------
``User.has_permission`` does exact set-membership on the tokens stored in
``roles.permissions``. There is no wildcard, no prefix match and no expansion, so
a role holds precisely the tokens spelled out on it and nothing else. That makes
the spelling of every token load-bearing, and until now nothing in the repo wrote
the vocabulary down: the only list was ``_ADMIN_PERMS`` in the integration
conftest, which had drifted to 54 tokens of which 14 were checked nowhere while
41 enforced tokens were missing.

Why the lists below are literals and not generated
--------------------------------------------------
:mod:`src.domain.authz.extraction` can derive this vocabulary from the source
tree, and it is what produced the initial contents here. It is deliberately *not*
used to build these constants at import time. A catalogue computed from the code
cannot disagree with the code, so the test that compares them would pass no
matter what — the same vacuity that let this codebase's OpenAPI contract suite
stay green while it checked nothing. Keeping the vocabulary as a literal means
adding a permission shows up as a reviewable diff, and
``tests/unit/test_permission_catalogue.py`` fails until the two agree.

Adding a permission
-------------------
Add the ``require_permission`` (or ``has_permission``) call, then add the token to
:data:`ENFORCED_PERMISSIONS`. The catalogue test tells you if you forget either
half, in either direction.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import Mapping

#: Every token the code actually checks, whether through a
#: ``require_permission`` route dependency or a ``has_permission`` call inside a
#: handler or service. These are the only tokens a role may be granted.
ENFORCED_PERMISSIONS: frozenset[str] = frozenset(
    {
        "action:create",
        "action:update",
        "admin:manage",
        "analytics:create",
        "analytics:delete",
        "analytics:manage",
        "analytics:update",
        "assessment:create",
        "assessment:update",
        "asset:create",
        "asset:delete",
        "asset:update",
        "audit:create",
        "audit:delete",
        "audit:read",
        "audit:update",
        "capa:create",
        "capa:update",
        "complaint:create",
        "complaint:delete",
        "complaint:read",
        "complaint:update",
        "complaint:view_all",
        "document:create",
        "document:read",
        "document:update",
        "driver:create",
        "driver:update",
        "engineer:create",
        "engineer:update",
        "evidence:create",
        "evidence:update",
        "form:create",
        "form:delete",
        "form:update",
        "incident:create",
        "incident:delete",
        "incident:read",
        "incident:set_reference_number",
        "incident:update",
        "incident:view_all",
        "induction:create",
        "induction:update",
        "investigation:approve_customer_omit",
        "investigation:create",
        "investigation:delete",
        "investigation:update",
        "investigations:comments:read_deleted",
        "investigations:view_all",
        "kri:create",
        "kri:delete",
        "kri:update",
        "near_miss:create",
        "near_miss:delete",
        "near_miss:read",
        "near_miss:update",
        "notifications:delete",
        "notifications:send",
        "notifications:update",
        "policy:create",
        "policy:delete",
        "policy:set_reference_number",
        "policy:update",
        "rca:create",
        "rca:update",
        "risk:create",
        "risk:update",
        "rta:create",
        "rta:delete",
        "rta:read",
        "rta:update",
        "rta:view_all",
        "signature:create",
        "signature:update",
        "standard:create",
        "standard:update",
        "vehicle:allocate",
        "vehicle:update",
        "workflow:create",
        "workflow:delete",
        "workflow:update",
    }
)

#: Tokens that belong to the vocabulary but that no code path checks, each with
#: the verified reason why. They are recorded rather than deleted, and they are
#: **not grantable**.
#:
#: Recorded, because most of these name a control the product is missing. Eight
#: of them are reads whose endpoints are gated by authentication alone, so the
#: token is the only written evidence that the gate was intended and is absent.
#: Deleting them would delete that evidence and invite someone to reinvent the
#: token under a slightly different spelling — the exact drift this package
#: exists to stop.
#:
#: Not grantable, because a role carrying ``policy:read`` reads as a restricted
#: role in an access review while restricting nothing. Claiming a control that
#: does not exist is worse than having no control, so
#: :func:`src.domain.authz.validation.canonicalise_permissions_input` rejects
#: these with an explanation instead of accepting them.
#:
#: A token here that later acquires a real check will fail the catalogue test
#: until it is promoted into :data:`ENFORCED_PERMISSIONS`.
RESERVED_PERMISSIONS: Mapping[str, str] = MappingProxyType(
    {
        # Named under a different prefix. The audit-template routes exist, but
        # they are gated on audit:create / audit:update / audit:delete, so these
        # four tokens grant nothing and mislead anyone who reads them.
        "audit_template:create": "audit-template routes are gated on audit:create",
        "audit_template:read": "audit-template reads are gated by authentication only",
        "audit_template:update": "audit-template routes are gated on audit:update",
        "audit_template:delete": "audit-template routes are gated on audit:delete",
        # Reads gated by authentication only: the endpoint exists and takes
        # CurrentUser, with no permission dependency. Any authenticated user can
        # read these resources today.
        "action:read": "GET /actions takes CurrentUser with no permission dependency",
        "assessment:read": "GET /assessments takes CurrentUser with no permission dependency",
        "capa:read": "GET /capa takes CurrentUser with no permission dependency",
        "engineer:read": "GET /engineers takes CurrentUser with no permission dependency",
        "investigation:read": "investigation reads take CurrentUser with no permission dependency",
        "policy:read": "policy reads take CurrentUser with no permission dependency",
        "risk:read": "risk reads take CurrentUser with no permission dependency",
        "standard:read": "standard reads take CurrentUser with no permission dependency",
        # Deletes that are not permission-gated.
        "action:delete": "no DELETE endpoint exists for actions",
        "capa:delete": "DELETE /capa/{id} is gated on CurrentSuperuser, not a permission",
    }
)

#: Tokens a role may be granted. Reserved tokens are excluded on purpose.
GRANTABLE_PERMISSIONS: frozenset[str] = ENFORCED_PERMISSIONS

#: Tokens that defeat the own-records-only narrowing some list endpoints apply.
#: Holding one turns a scoped list into a tenant-wide list.
VIEW_ALL_PERMISSIONS: frozenset[str] = frozenset(token for token in ENFORCED_PERMISSIONS if token.endswith(":view_all"))

#: Tokens that allow overriding a generated reference number.
REFERENCE_NUMBER_PERMISSIONS: frozenset[str] = frozenset(
    token for token in ENFORCED_PERMISSIONS if token.endswith(":set_reference_number")
)

#: The token list intended for the ``admin`` role: every enforced token except
#: the ``*:view_all`` and ``*:set_reference_number`` families, per the product
#: owner's decision (David Harris, Run025).
#:
#: This is a proposal, not a migration. Nothing applies it: no seed, no Alembic
#: revision and no startup hook reads it. Writing it to a live database is a
#: human decision. ``scripts`` are not owned by this lane, so the dry run lives
#: in ``tests/unit/test_permission_catalogue.py::test_admin_role_permission_list_is_reviewable``,
#: which prints the exact JSON value a reviewer would apply.
ADMIN_ROLE_PERMISSIONS: tuple[str, ...] = tuple(
    sorted(ENFORCED_PERMISSIONS - VIEW_ALL_PERMISSIONS - REFERENCE_NUMBER_PERMISSIONS)
)


def is_enforced(token: str) -> bool:
    """True when some code path actually checks ``token``."""
    return token.strip().lower() in ENFORCED_PERMISSIONS


def is_reserved(token: str) -> bool:
    """True when ``token`` is a known part of the vocabulary that nothing checks."""
    return token.strip().lower() in RESERVED_PERMISSIONS


__all__ = [
    "ADMIN_ROLE_PERMISSIONS",
    "ENFORCED_PERMISSIONS",
    "GRANTABLE_PERMISSIONS",
    "REFERENCE_NUMBER_PERMISSIONS",
    "RESERVED_PERMISSIONS",
    "VIEW_ALL_PERMISSIONS",
    "is_enforced",
    "is_reserved",
]
