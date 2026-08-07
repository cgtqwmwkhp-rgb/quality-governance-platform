"""Inbound partner bearer authentication: the route opt-in and the principal.

How a ``qgp_pt_`` bearer reaches a handler
------------------------------------------
There is one identity dependency in this application, :func:`
src.api.dependencies.get_current_user`, and everything downstream of it —
``require_permission``, the library ACL, the tenant scoping helpers — reads the
caller it returns. Partner support is therefore added *inside* that dependency
rather than beside it. The alternative, a parallel
``require_permission_or_partner_scope`` factory replacing the dependency on each
partner-callable route, was tried first and is the wrong shape: it takes
``get_current_user`` out of those routes' dependency graphs (so every test that
overrides it stops applying), it duplicates the JWT path (so the two drift), and
it reaches ``has_permission`` with a non-literal token, which
``src.domain.authz.extraction`` refuses outright.

Default deny, and where it comes from
-------------------------------------
Accepting partner tokens in the one shared dependency would otherwise open every
authenticated route in the app to them. So a route is partner-callable only if
it says so, by carrying :data:`PARTNER_SCOPE_OPENAPI_KEY` in its
``openapi_extra``:

    @router.get("/search/content", openapi_extra=partner_readable("documents:read"))

:func:`required_partner_scope` reads that marker back off the matched route. A
route with no marker yields ``None``, and a ``None`` required scope refuses the
token — which is exactly what happens today, since ``decode_token`` cannot read
a ``qgp_pt_`` string either. The opt-in is read from the route object rather
than from a sibling dependency on purpose: dependency *resolution order* is not
a contract this repo should rest a security decision on, and a route that cannot
be read at all yields ``None`` and denies.

The marker is not decoration. It is the authorisation decision, so
``tests/unit/test_partner_bearer_scopes.py`` pins the exact set of routes that
carry one; adding a sixth cannot pass unnoticed.
"""

from __future__ import annotations

from typing import Optional

from fastapi import HTTPException, Request, status

from src.domain.services.partner_auth_service import PartnerAuthService, PartnerPrincipal, is_partner_bearer_token

#: OpenAPI operation extension naming the partner scope a route accepts. An
#: ``x-`` extension is a legal operation field, so the opt-in also documents
#: itself in the published schema instead of living only in Python.
PARTNER_SCOPE_OPENAPI_KEY = "x-qgp-partner-scope"


def partner_readable(scope: str) -> dict[str, str]:
    """``openapi_extra`` marking a route callable with a partner token.

    The single constructor for the marker, so every partner-callable route is
    greppable by one name and the key is spelled in one place.
    """
    return {PARTNER_SCOPE_OPENAPI_KEY: scope}


async def required_partner_scope(request: Request) -> Optional[str]:
    """The partner scope this route accepts, or ``None`` if it accepts none.

    ``None`` is the deny answer and is returned for every route that has not
    opted in, as well as for anything about the request this cannot read. It is
    also what a direct (non-FastAPI) call to ``get_current_user`` gets by
    default, which keeps partner tokens refused in unit tests that construct the
    dependency by hand.
    """
    route = request.scope.get("route")
    extra = getattr(route, "openapi_extra", None)
    if not isinstance(extra, dict):
        return None
    scope = extra.get(PARTNER_SCOPE_OPENAPI_KEY)
    return scope if isinstance(scope, str) and scope else None


def _partner_credentials_exception() -> HTTPException:
    """401 for a partner bearer that is unusable, or used somewhere it may not be.

    One message for "no such active token" and for "this route does not accept
    partner tokens" deliberately: telling an unauthenticated caller which of the
    two it hit turns the endpoint into an oracle for both the route list and the
    validity of a guessed secret.
    """
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def resolve_partner_principal(
    raw_token: str,
    db,
    *,
    required_scope: Optional[str],
) -> PartnerPrincipal:
    """Verify a partner bearer for this route and return the caller it proves.

    Raises 401 when the route accepts no partner token or the credential matches
    no active one, and 403 when a genuine token lacks the route's scope. The
    caller is responsible for binding the tenant RLS GUC, so both the JWT and
    partner paths bind it in the same place.
    """
    if required_scope is None:
        raise _partner_credentials_exception()

    service = PartnerAuthService(db)
    token = await service.authenticate(raw_token)
    if token is None:
        raise _partner_credentials_exception()

    principal = PartnerPrincipal(token)
    if not principal.has_partner_scope(required_scope):
        # 403, not 401: the credential is good, the grant is missing. A 401 would
        # tell the integrator to re-issue a token that is working fine.
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Partner scope '{required_scope}' required",
        )

    # Scopes are already copied onto the principal, so recording usage cannot
    # expire anything still needed. Deliberately after the scope check: this
    # records use of the token, not attempts against it.
    if principal.partner_token_id is not None:
        await service.touch_last_used(principal.partner_token_id)
    return principal


def is_partner_caller(caller: object) -> bool:
    """True when ``caller`` was established by a partner API token.

    Handlers use this where a partner has to be served *less* than a session
    user would be, rather than to decide whether to serve them at all — that
    decision is already made by the time a handler runs.
    """
    return isinstance(caller, PartnerPrincipal)


__all__ = [
    "PARTNER_SCOPE_OPENAPI_KEY",
    "is_partner_bearer_token",
    "is_partner_caller",
    "partner_readable",
    "required_partner_scope",
    "resolve_partner_principal",
]
