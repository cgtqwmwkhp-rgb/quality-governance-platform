"""Derive the permission vocabulary that the code actually enforces.

This module exists so :mod:`src.domain.authz.catalogue` can be *checked* against
reality rather than trusted. Nothing on a request path imports it; it is
verification tooling that happens to live in ``src`` so that a dry-run script and
a test can share one implementation.

Two independent extractors are provided, and both are used, because neither one
alone sees all enforcement:

``scan_source_tree``
    Static AST scan of ``src/``. Sees ``require_permission("token")``
    dependencies *and* in-handler ``current_user.has_permission("token")``
    calls. The second form is real enforcement — it is what narrows list
    endpoints to own-records-only — and it is invisible to any approach based on
    inspecting the app's dependency graph.

``tokens_from_registered_routes``
    Walks the dependency graph of the routes actually mounted on the app and
    reads the :data:`REQUIRED_PERMISSION_ATTR` tag that
    ``require_permission`` stamps on each checker. This is the truthful answer
    to "what must a request satisfy", and it catches tokens wired up by means a
    static scan cannot follow (a router-level ``dependencies=[...]``, a loop
    over a table of routes, a factory in another module).

    The app is passed in and the route objects are duck-typed, so this module
    imports neither ``src.api`` nor FastAPI: ``src/domain`` may not depend on
    ``src/api`` (``scripts/check_import_boundaries.py`` enforces it), and no
    other domain module imports a web framework either. The layering that falls
    out of that is the right way round anyway — the domain owns the name of the
    tag, the API layer stamps it, and the caller supplies the app.

The scan refuses to be quiet. A regex or a naive AST walk skips any call whose
argument is not a string literal, so enforcement built from an f-string or a
lookup table simply vanishes from the count with no warning — and a token that
vanishes from the count is a token the catalogue test cannot protect. Every
non-literal call site must therefore be declared in
:data:`DECLARED_DYNAMIC_SITES` together with a resolver that derives its tokens
from source. An undeclared one raises :class:`UndeclaredDynamicSiteError`.
"""

from __future__ import annotations

import ast
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

#: Callables whose first argument names a permission token.
PERMISSION_CALLABLES = frozenset({"require_permission", "has_permission"})

#: Keyword name accepted as an alternative to the first positional argument.
PERMISSION_KEYWORD = "permission"

#: Attribute under which ``src.api.dependencies.require_permission`` records the
#: token its checker enforces, so the route walk can read it back.
#:
#: Declared here, in the lower layer, and imported by the API layer rather than
#: the other way round. It is one magic string and it needs exactly one owner:
#: duplicating it would reintroduce, in miniature, the drift this package exists
#: to remove — the copies would fall out of step and the route walk would quietly
#: find nothing.
REQUIRED_PERMISSION_ATTR = "__qgp_required_permission__"

SRC_ROOT = Path(__file__).resolve().parents[2]


class PermissionExtractionError(RuntimeError):
    """Base class for failures that must not be swallowed into a quiet result."""


class UndeclaredDynamicSiteError(PermissionExtractionError):
    """A permission is built at runtime from something other than a literal.

    Raised rather than skipped. A skipped site is enforcement the catalogue
    cannot see, which is the drift this package exists to prevent.
    """


class AliasedImportError(PermissionExtractionError):
    """``require_permission``/``has_permission`` was imported under another name.

    The scan matches on callee name, so an alias makes its call sites invisible.
    """


class ResolverContractError(PermissionExtractionError):
    """A declared dynamic site no longer has the shape its resolver expects."""


@dataclass(frozen=True)
class PermissionUsage:
    """One place the code demands a named permission."""

    token: str
    form: str
    site: str
    lineno: int

    @property
    def location(self) -> str:
        return f"{self.site}:{self.lineno}"


@dataclass(frozen=True)
class DynamicCallSite:
    """One place a permission token is built from something other than a literal."""

    site: str
    form: str
    lineno: int
    expression: str

    @property
    def location(self) -> str:
        return f"{self.site}:{self.lineno}"


@dataclass(frozen=True)
class DeclaredDynamicSite:
    """A known non-literal call site, with the reason it is allowed to exist.

    ``resolver`` derives the tokens the site can produce *from source*, so that
    adding a fifth module to a shared helper changes the derived set and trips
    the catalogue test — rather than quietly adding unenforceable tokens.
    ``resolver`` is ``None`` for a site that produces no token of its own
    (the generic dispatcher inside ``require_permission``).
    """

    site: str
    reason: str
    resolver: Optional[Callable[[Path], set[str]]] = None


@dataclass
class SourceScanResult:
    """Everything the static scan learned about enforcement."""

    literal_usages: list[PermissionUsage] = field(default_factory=list)
    dynamic_sites: list[DynamicCallSite] = field(default_factory=list)
    derived_tokens: dict[str, set[str]] = field(default_factory=dict)
    files_scanned: int = 0

    @property
    def require_permission_tokens(self) -> set[str]:
        return {u.token for u in self.literal_usages if u.form == "require_permission"}

    @property
    def has_permission_tokens(self) -> set[str]:
        return {u.token for u in self.literal_usages if u.form == "has_permission"}

    @property
    def literal_tokens(self) -> set[str]:
        return {u.token for u in self.literal_usages}

    @property
    def dynamic_tokens(self) -> set[str]:
        return set().union(*self.derived_tokens.values()) if self.derived_tokens else set()

    @property
    def enforced_tokens(self) -> set[str]:
        """Every token the code can actually ask ``has_permission`` for."""
        return self.literal_tokens | self.dynamic_tokens

    def locations_for(self, token: str) -> list[str]:
        found = [u.location for u in self.literal_usages if u.token == token]
        found += [f"{site} (derived)" for site, tokens in self.derived_tokens.items() if token in tokens]
        return sorted(found)


@dataclass
class RouteScanResult:
    """Tokens reachable through the dependency graph of the mounted app."""

    tokens: dict[str, set[str]] = field(default_factory=dict)
    untagged_checkers: list[str] = field(default_factory=list)
    route_count: int = 0

    @property
    def token_set(self) -> set[str]:
        return set(self.tokens)


#: Method recorded for a route that declares none, i.e. a websocket.
WEBSOCKET_METHOD = "WEBSOCKET"


@dataclass(frozen=True)
class MountedEndpoint:
    """One endpoint the app serves, with every dependency callable that gates it.

    ``calls`` holds the callables from the route's own dependency graph *and* any
    attached to a router it was included under. Both are needed: FastAPI merges
    router-level dependencies into each route's dependant when it flattens, but
    the versions that do not flatten leave them on the include context instead,
    reachable only from the wrapper the route hangs beneath.

    ``dependencies_readable`` is ``False`` for an endpoint that has no resolved
    dependency graph at all — a plain Starlette route added with ``add_route``,
    such as the ones FastAPI installs for ``/docs`` and ``/openapi.json``. Those
    are still served, so they are still counted, but ``calls`` is empty because
    there was nothing to read rather than because nothing gates them. Keeping the
    distinction visible matters: an endpoint reported as ungated because it *is*
    and one reported so because the walk could not look are different facts.
    """

    methods: tuple[str, ...]
    path: str
    endpoint: Any
    calls: tuple[Any, ...]
    dependencies_readable: bool = True

    @property
    def label(self) -> str:
        return f"{','.join(self.methods)} {self.path}"

    @property
    def endpoint_name(self) -> str:
        module = getattr(self.endpoint, "__module__", "?")
        name = getattr(self.endpoint, "__name__", "?")
        return f"{module}.{name}"


@dataclass(frozen=True)
class RouterLevelDependency:
    """A dependency attached to a whole router rather than to one endpoint."""

    prefix: str
    call: Any


@dataclass
class MountedApp:
    """The result of one traversal of the mounted router graph.

    Everything that needs to know what the app serves reads this, so the
    knowledge of FastAPI's routing shape — the part that broke once already
    between 0.135 and 0.140 — exists in exactly one place. A second copy would
    drift, and a drifted copy of this walk reports a smaller app rather than an
    error.
    """

    endpoints: list[MountedEndpoint] = field(default_factory=list)
    router_level: list[RouterLevelDependency] = field(default_factory=list)

    @property
    def api_endpoints(self) -> list[MountedEndpoint]:
        """Endpoints with a dependency graph, i.e. everything but raw ASGI routes.

        The authorisation census wants :attr:`endpoints`, because a route serving
        traffic counts whether or not its dependencies can be read. Permission
        extraction wants this narrower set: a route with no dependency graph
        cannot carry a permission dependency, so including it would inflate the
        denominator of a count that exists to notice when the walk stops finding
        routes at all.
        """
        return [endpoint for endpoint in self.endpoints if endpoint.dependencies_readable]


# --------------------------------------------------------------------------- #
# Resolvers for the declared dynamic sites
# --------------------------------------------------------------------------- #


def _module_ast(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _literal_module_constant(path: Path, name: str) -> Any:
    """Return the literal value assigned to a module-level ``name``."""
    for node in _module_ast(path).body:
        if isinstance(node, ast.Assign):
            targets: list[ast.expr] = list(node.targets)
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
        else:
            continue
        if not any(isinstance(target, ast.Name) and target.id == name for target in targets):
            continue
        if node.value is None:
            continue
        try:
            return ast.literal_eval(node.value)
        except ValueError as exc:
            raise ResolverContractError(f"{path.name}:{name} is no longer a literal: {exc}") from exc
    raise ResolverContractError(f"{path.name} no longer defines a module-level {name}")


def _resolve_runner_sheet_delete_tokens(src_root: Path) -> set[str]:
    """Tokens produced by ``assert_can_delete_runner_sheet_entry``.

    That helper checks ``f"{module_name}:delete"`` plus any per-module fallback,
    so the vocabulary it enforces is the set of module names its callers pass.
    Both halves are read back out of source: adopt the helper in a new module
    and the derived set grows, which is what makes the catalogue test notice.
    """
    helper = src_root / "api" / "routes" / "_runner_sheet.py"
    if not helper.exists():
        raise ResolverContractError(f"expected runner-sheet helper at {helper}")

    fallbacks = _literal_module_constant(helper, "_DELETE_PERMISSION_FALLBACKS")
    if not isinstance(fallbacks, dict):
        raise ResolverContractError("_DELETE_PERMISSION_FALLBACKS is no longer a dict")

    tokens: set[str] = set()
    for value in fallbacks.values():
        tokens.update(str(item) for item in value)

    module_names = _literal_argument_values(
        src_root,
        callee="assert_can_delete_runner_sheet_entry",
        argument_index=2,
    )
    tokens.update(f"{name}:delete" for name in module_names)
    if not module_names:
        raise ResolverContractError("no caller of assert_can_delete_runner_sheet_entry passes a literal module name")
    return tokens


def _resolve_portal_triage_tokens(src_root: Path) -> set[str]:
    """Tokens looked up by portal triage from ``_UPDATE_PERMISSION_BY_ENTITY``."""
    module = src_root / "domain" / "services" / "portal_triage_service.py"
    if not module.exists():
        raise ResolverContractError(f"expected portal triage service at {module}")
    mapping = _literal_module_constant(module, "_UPDATE_PERMISSION_BY_ENTITY")
    if not isinstance(mapping, dict):
        raise ResolverContractError("_UPDATE_PERMISSION_BY_ENTITY is no longer a dict")
    return {str(value) for value in mapping.values()}


#: Non-literal call sites that are known and accounted for. Keyed by
#: ``<path relative to repo root>::<enclosing qualname>`` so the key survives
#: edits above the call, unlike a line number.
DECLARED_DYNAMIC_SITES: tuple[DeclaredDynamicSite, ...] = (
    DeclaredDynamicSite(
        site="src/api/dependencies/__init__.py::require_permission.permission_checker",
        reason=(
            "The generic dispatcher. Its argument is whatever token the caller "
            "asked for, so it contributes no token of its own; the callers of "
            "require_permission are what the scan counts."
        ),
        resolver=None,
    ),
    DeclaredDynamicSite(
        site="src/api/routes/_runner_sheet.py::assert_can_delete_runner_sheet_entry",
        reason=(
            'Builds f"{module_name}:delete" plus per-module fallbacks. Tokens '
            "are derived from the module names its callers pass and from "
            "_DELETE_PERMISSION_FALLBACKS."
        ),
        resolver=_resolve_runner_sheet_delete_tokens,
    ),
    DeclaredDynamicSite(
        site="src/domain/services/portal_triage_service.py::_user_can_triage_entity",
        reason=(
            "Looks the token up in _UPDATE_PERMISSION_BY_ENTITY. Tokens are " "derived from that mapping's values."
        ),
        resolver=_resolve_portal_triage_tokens,
    ),
)


# --------------------------------------------------------------------------- #
# Static scan
# --------------------------------------------------------------------------- #


def _callee_name(func: ast.expr) -> Optional[str]:
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _permission_argument(node: ast.Call) -> tuple[str, Any]:
    """Return ``("literal", value)`` or ``("dynamic", source_expression)``.

    Keyword form is handled too: ``require_permission(permission="x")`` reads
    identically to the positional form at runtime, and a scan that only looked
    at ``args[0]`` would drop it.
    """
    candidate: Optional[ast.expr] = node.args[0] if node.args else None
    if candidate is None:
        for keyword in node.keywords:
            if keyword.arg == PERMISSION_KEYWORD:
                candidate = keyword.value
                break
    if candidate is None:
        return "dynamic", "<no permission argument>"
    if isinstance(candidate, ast.Constant) and isinstance(candidate.value, str):
        return "literal", candidate.value
    return "dynamic", ast.unparse(candidate)


class _PermissionCallCollector(ast.NodeVisitor):
    """Collect permission call sites, tracking the enclosing qualname."""

    def __init__(self, relative_path: str) -> None:
        self.relative_path = relative_path
        self._scope: list[str] = []
        self.literal_usages: list[PermissionUsage] = []
        self.dynamic_sites: list[DynamicCallSite] = []

    def _descend(self, name: str, node: ast.AST) -> None:
        self._scope.append(name)
        self.generic_visit(node)
        self._scope.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._descend(node.name, node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._descend(node.name, node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._descend(node.name, node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        for alias in node.names:
            if alias.name in PERMISSION_CALLABLES and alias.asname and alias.asname != alias.name:
                raise AliasedImportError(
                    f"{self.relative_path}:{node.lineno} imports {alias.name} as {alias.asname}. "
                    "The permission scan matches on callee name, so an alias hides every call "
                    "site behind it. Import it under its own name."
                )
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        name = _callee_name(node.func)
        if name in PERMISSION_CALLABLES:
            site = f"{self.relative_path}::{'.'.join(self._scope) or '<module>'}"
            kind, value = _permission_argument(node)
            if kind == "literal":
                self.literal_usages.append(PermissionUsage(token=value, form=name, site=site, lineno=node.lineno))
            else:
                self.dynamic_sites.append(DynamicCallSite(site=site, form=name, lineno=node.lineno, expression=value))
        self.generic_visit(node)


def _literal_argument_values(src_root: Path, *, callee: str, argument_index: int) -> set[str]:
    """Collect the literal string values passed positionally to ``callee``.

    A non-literal in that position raises: it would be a caller the resolver
    cannot account for, and guessing is how the vocabulary drifts.
    """
    values: set[str] = set()
    for path in _python_files(src_root):
        for node in ast.walk(_module_ast(path)):
            if not isinstance(node, ast.Call) or _callee_name(node.func) != callee:
                continue
            if len(node.args) <= argument_index:
                continue
            argument = node.args[argument_index]
            if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
                values.add(argument.value)
            else:
                raise ResolverContractError(
                    f"{path}:{node.lineno} calls {callee} with a non-literal argument "
                    f"{argument_index} ({ast.unparse(argument)}); the resolver cannot "
                    "derive the tokens it enforces."
                )
    return values


def _python_files(src_root: Path) -> Iterator[Path]:
    for path in sorted(src_root.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        yield path


def scan_source_tree(src_root: Optional[Path] = None) -> SourceScanResult:
    """Scan ``src/`` for every permission the code demands.

    Raises :class:`UndeclaredDynamicSiteError` if enforcement is built from
    something the scan cannot read, so that such a site has to be declared
    (and resolved) rather than silently dropped from the vocabulary.
    """
    src_root = (src_root or SRC_ROOT).resolve()
    repo_root = src_root.parent
    result = SourceScanResult()

    for path in _python_files(src_root):
        relative = path.relative_to(repo_root).as_posix()
        collector = _PermissionCallCollector(relative)
        collector.visit(_module_ast(path))
        result.literal_usages.extend(collector.literal_usages)
        result.dynamic_sites.extend(collector.dynamic_sites)
        result.files_scanned += 1

    declared = {site.site: site for site in DECLARED_DYNAMIC_SITES}
    undeclared = sorted({site.location for site in result.dynamic_sites if site.site not in declared})
    if undeclared:
        detail = "\n".join(f"  {location}" for location in undeclared)
        raise UndeclaredDynamicSiteError(
            "Permission enforcement is built from a non-literal value at:\n"
            f"{detail}\n"
            "A site the scan cannot read is enforcement the permission catalogue "
            "cannot protect. Either pass a literal token, or add the site to "
            "DECLARED_DYNAMIC_SITES in src/domain/authz/extraction.py with a "
            "resolver that derives its tokens from source."
        )

    for site in DECLARED_DYNAMIC_SITES:
        if site.resolver is not None:
            result.derived_tokens[site.site] = site.resolver(src_root)

    return result


# --------------------------------------------------------------------------- #
# Runtime scan of the mounted app
# --------------------------------------------------------------------------- #


def _iter_dependants(dependant: Any) -> Iterator[Any]:
    yield dependant
    for sub in getattr(dependant, "dependencies", None) or ():
        yield from _iter_dependants(sub)


#: Guards the recursive walk against a router graph that contains a cycle. Far
#: deeper than any real nesting; exceeded means the shape is not what we think.
MAX_ROUTER_DEPTH = 25


class RouteWalkError(PermissionExtractionError):
    """The mounted router graph is not a shape the walk can traverse."""


def _looks_like_an_untagged_checker(call: Any) -> bool:
    """Was this callable produced by something named ``require_permission``?

    Matched on a whole dotted component of the qualname, not a substring: a
    function defined inside ``def test_require_permission_...`` has
    ``require_permission`` in its qualname without being a checker at all.

    This is a backstop, and a narrow one. It catches a second copy of the
    existing factory that forgot to tag its checker; it cannot catch a factory
    under a different name. What guarantees *that* is not caught silently is the
    static scan, which raises on any permission built from a value it cannot
    read.
    """
    parts = getattr(call, "__qualname__", "").split(".")
    return "require_permission" in parts


def _router_level_calls(holder: Any) -> tuple[Any, ...]:
    """Dependency callables attached to a whole router rather than one route.

    ``APIRouter(dependencies=[...])`` and ``include_router(..., dependencies=[...])``
    gate every route beneath them. Nothing in this repo enforces a permission that
    way today, but it is exactly the "wired up by means a source scan cannot
    follow" case this walk exists to catch, so it is read rather than assumed
    absent.
    """
    calls = (getattr(dependency, "dependency", None) for dependency in getattr(holder, "dependencies", None) or ())
    return tuple(call for call in calls if call is not None)


def _visit_route_node(
    result: MountedApp,
    node: Any,
    prefix: str,
    inherited: tuple[Any, ...],
    seen: set[tuple[int, str]],
    depth: int,
) -> None:
    """Walk one node of the mounted router graph.

    The graph is traversed rather than the top-level list iterated, because
    ``include_router`` does not necessarily flatten. Under FastAPI 0.135 it
    copied every route onto ``app.routes``; under 0.140 it appends a single
    wrapper object holding the original router, and the routes below it are
    reachable only by descending. A flat loop therefore saw 980 routes on one
    version and 6 on the other. Nothing here names a FastAPI internal: each
    shape is recognised by the attribute that makes it traversable, so a
    version that changes the wrapper's name still works, and a version that
    changes the *shape* trips the vacuity floor and the synthetic-app tests
    rather than quietly returning less.

    ``inherited`` carries router-level dependencies down to the endpoints they
    gate. On a version that flattens they are already in the route's own
    dependant, so the union is idempotent; on one that does not, this is the only
    way an endpoint knows it is gated.
    """
    if depth > MAX_ROUTER_DEPTH:
        raise RouteWalkError(
            f"router nesting exceeded {MAX_ROUTER_DEPTH} levels at {prefix!r}; "
            "the mounted graph is not the shape this walk expects."
        )
    key = (id(node), prefix)
    if key in seen:
        return
    seen.add(key)

    # A leaf: something with a resolved dependency graph, i.e. a real endpoint.
    dependant = getattr(node, "dependant", None)
    if dependant is not None:
        methods = tuple(sorted(getattr(node, "methods", None) or ())) or (WEBSOCKET_METHOD,)
        own = tuple(getattr(dep, "call", None) for dep in _iter_dependants(dependant))
        result.endpoints.append(
            MountedEndpoint(
                methods=methods,
                path=f"{prefix}{getattr(node, 'path', '<unknown>')}",
                endpoint=getattr(node, "endpoint", None),
                calls=tuple(call for call in own if call is not None) + inherited,
            )
        )
        return

    # A wrapper around a single route, carrying the prefix it was included under.
    original_route = getattr(node, "original_route", None)
    if original_route is not None:
        _visit_route_node(result, original_route, prefix, inherited, seen, depth + 1)
        return

    # A wrapper around a whole included router.
    original_router = getattr(node, "original_router", None)
    if original_router is not None:
        context = getattr(node, "include_context", None)
        child_prefix = prefix + str(getattr(context, "prefix", "") or "")
        calls = _router_level_calls(context)
        result.router_level.extend(RouterLevelDependency(prefix=child_prefix, call=call) for call in calls)
        _visit_route_node(result, original_router, child_prefix, inherited + calls, seen, depth + 1)
        return

    # Anything holding a route list: the app, a router, a mount.
    routes = getattr(node, "routes", None)
    if routes is not None:
        calls = _router_level_calls(node)
        result.router_level.extend(RouterLevelDependency(prefix=prefix, call=call) for call in calls)
        for child in routes:
            _visit_route_node(result, child, prefix, inherited + calls, seen, depth + 1)
        # Routes deprioritised in matching are still served, so still counted.
        for child in getattr(node, "_low_priority_routes", None) or ():
            _visit_route_node(result, child, prefix, inherited + calls, seen, depth + 1)
        return

    sub_app = getattr(node, "app", None)
    if sub_app is not None and getattr(sub_app, "routes", None) is not None:
        _visit_route_node(result, sub_app, prefix + str(getattr(node, "path", "") or ""), inherited, seen, depth + 1)
        return

    # A served endpoint with no resolved dependency graph: a plain Starlette route
    # added through ``add_route``, which is how FastAPI installs /docs, /redoc and
    # /openapi.json. Counted, not skipped. Skipping was a hole in this walk: a
    # route added that way served traffic while being invisible to the census, so
    # nothing would have asked whether it needed authorisation.
    path = getattr(node, "path", None)
    if path is not None and getattr(node, "endpoint", None) is not None:
        methods = tuple(sorted(getattr(node, "methods", None) or ())) or (WEBSOCKET_METHOD,)
        result.endpoints.append(
            MountedEndpoint(
                methods=methods,
                path=f"{prefix}{path}",
                endpoint=node.endpoint,
                calls=inherited,
                dependencies_readable=False,
            )
        )
        return

    if path is not None:
        raise RouteWalkError(
            f"reached a route-like node at {prefix}{path!r} of type "
            f"{type(node).__module__}.{type(node).__name__} that this walk cannot classify: it "
            "has no dependency graph, no endpoint, and no routes to descend into. Teach "
            "_visit_route_node about it rather than letting it be skipped — a skipped node is an "
            "endpoint the authorisation census cannot see."
        )


def walk_mounted_app(app: Any) -> MountedApp:
    """Traverse ``app`` once and return every endpoint it serves.

    ``app`` is supplied by the caller rather than imported, to keep this module
    free of any dependency on the API layer.

    This is the single traversal. :func:`tokens_from_registered_routes` and
    :func:`src.domain.authz.census.take_census` both read its output rather than
    walking the graph themselves.
    """
    result = MountedApp()
    _visit_route_node(result, app, "", (), set(), 0)
    return result


def tokens_from_registered_routes(app: Any) -> RouteScanResult:
    """Read the permissions wired into the routes ``app`` actually serves.

    An untagged checker is reported rather than ignored: a second
    permission-dependency factory that forgot the tag would otherwise shrink this
    result with no complaint, and a cross-check that silently stops seeing things
    is worse than none.
    """
    mounted = walk_mounted_app(app)
    result = RouteScanResult(route_count=len(mounted.api_endpoints))

    def record(call: Any, label: str) -> None:
        token = getattr(call, REQUIRED_PERMISSION_ATTR, None)
        if isinstance(token, str):
            result.tokens.setdefault(token, set()).add(label)
        elif _looks_like_an_untagged_checker(call):
            result.untagged_checkers.append(f"{label} -> {call.__qualname__}")

    for endpoint in mounted.endpoints:
        for call in endpoint.calls:
            record(call, endpoint.label)
    # Recorded separately as well as through the endpoints they gate, so a
    # permission on a router with nothing beneath it is still visible rather
    # than silently dropped.
    for router_dependency in mounted.router_level:
        record(router_dependency.call, f"{router_dependency.prefix} (router-level)")

    return result


def format_divergence_report(
    *,
    catalogued: Iterable[str],
    reserved: Iterable[str],
    scan: Optional[SourceScanResult] = None,
) -> str:
    """Human-readable comparison of catalogue against code, for dry runs."""
    scan = scan or scan_source_tree()
    catalogued = set(catalogued)
    reserved = set(reserved)
    enforced = scan.enforced_tokens

    lines = [
        f"files scanned                : {scan.files_scanned}",
        f"require_permission tokens    : {len(scan.require_permission_tokens)}",
        f"has_permission tokens        : {len(scan.has_permission_tokens)}",
        f"literal union                : {len(scan.literal_tokens)}",
        f"derived from dynamic sites   : {len(scan.dynamic_tokens)}",
        f"enforced total               : {len(enforced)}",
        f"catalogued (enforced)        : {len(catalogued)}",
        f"catalogued (reserved)        : {len(reserved)}",
    ]
    for label, tokens in (
        ("enforced but NOT catalogued", enforced - catalogued),
        ("catalogued but enforced NOWHERE", catalogued - enforced),
        ("reserved yet enforced (promote it)", reserved & enforced),
    ):
        lines.append(f"{label}: {len(tokens)}")
        for token in sorted(tokens):
            where = ", ".join(scan.locations_for(token)) or "-"
            lines.append(f"    {token}  {where}")
    return "\n".join(lines)
