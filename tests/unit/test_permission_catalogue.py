"""Fail when the permission catalogue and the code disagree, in either direction.

This is the load-bearing test of the authz package. The catalogue itself is only
a list; what stops it drifting back out of date is that this test breaks when a
token is enforced but not catalogued, *or* catalogued but enforced nowhere.

Both directions matter and for different reasons. A token enforced but not
catalogued means the write-time validator will refuse a grant the code actually
needs, so a role cannot be given a permission a route demands. A token catalogued
but enforced nowhere means a role can be granted something that restricts
nothing, which is how ``_ADMIN_PERMS`` came to hold 14 tokens no route has ever
asked for.

Several assertions here exist only to stop this file passing vacuously. This
codebase already had an OpenAPI contract suite that stayed green while checking
nothing, so a set comparison between two things that are both empty is a failure
mode worth spending assertions on.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from src.domain.authz.catalogue import (
    ADMIN_ROLE_PERMISSIONS,
    ENFORCED_PERMISSIONS,
    GRANTABLE_PERMISSIONS,
    REFERENCE_NUMBER_PERMISSIONS,
    RESERVED_PERMISSIONS,
    VIEW_ALL_PERMISSIONS,
)
from src.domain.authz.extraction import (
    DECLARED_DYNAMIC_SITES,
    UndeclaredDynamicSiteError,
    format_divergence_report,
    scan_source_tree,
    tokens_from_registered_routes,
)

REPO_ROOT = Path(__file__).resolve().parents[2]

# Floors, not expected values. They are set well below the real figures so that
# ordinary growth never trips them, while a scanner that silently stops finding
# anything does.
MIN_FILES_SCANNED = 300
MIN_REQUIRE_PERMISSION_TOKENS = 60
MIN_LITERAL_CALL_SITES = 300
MIN_REGISTERED_ROUTES = 500


@pytest.fixture(scope="module")
def scan():
    return scan_source_tree()


# --------------------------------------------------------------------------- #
# Guards against this file passing without checking anything
# --------------------------------------------------------------------------- #


def test_scan_actually_found_the_source_tree(scan):
    """A scan that finds nothing would make every comparison below trivially true."""
    assert scan.files_scanned >= MIN_FILES_SCANNED, (
        f"only {scan.files_scanned} Python files scanned; the scanner is probably "
        "pointed at the wrong directory, which would make this whole file vacuous"
    )
    assert len(scan.literal_usages) >= MIN_LITERAL_CALL_SITES
    assert len(scan.require_permission_tokens) >= MIN_REQUIRE_PERMISSION_TOKENS
    assert ENFORCED_PERMISSIONS, "the catalogue is empty"


def test_catalogue_is_not_generated_from_the_scanner():
    """The catalogue must be a literal, or this test compares the code to itself.

    If ``catalogue.py`` ever imports the extractor to build its own constants,
    every assertion in this file becomes a tautology that passes no matter how
    wrong the vocabulary is.
    """
    module = ast.parse((REPO_ROOT / "src" / "domain" / "authz" / "catalogue.py").read_text())
    imported: list[str] = []
    for node in ast.walk(module):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)
        elif isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
    offenders = [name for name in imported if "extraction" in name]
    assert not offenders, (
        f"catalogue.py imports {offenders}. The catalogue must stay a checked-in literal: "
        "deriving it from the scanner would make test_every_enforced_token_is_catalogued "
        "compare the scan against itself and always pass."
    )


# --------------------------------------------------------------------------- #
# The divergence test proper
# --------------------------------------------------------------------------- #


def test_every_enforced_token_is_catalogued(scan):
    """A token the code demands must be in the catalogue.

    Otherwise the write-time validator rejects a grant that a route requires, and
    the permission becomes impossible to hold.
    """
    missing = sorted(scan.enforced_tokens - ENFORCED_PERMISSIONS)
    detail = "\n".join(f"  {token}  enforced at {', '.join(scan.locations_for(token))}" for token in missing)
    assert not missing, (
        f"{len(missing)} permission(s) are enforced by code but absent from "
        f"ENFORCED_PERMISSIONS in src/domain/authz/catalogue.py:\n{detail}\n"
        "Add them to the catalogue. Until you do, no role can be granted them, "
        "because the write-time validator only accepts catalogued tokens."
    )


def test_every_catalogued_token_is_enforced_somewhere(scan):
    """A catalogued token nothing checks must not stay quietly grantable.

    This is the direction that had already rotted: ``_ADMIN_PERMS`` listed 14
    tokens no route has ever asked for. Either wire the check up, or move the
    token to ``RESERVED_PERMISSIONS`` with the reason it is not enforced.
    """
    unenforced = sorted(ENFORCED_PERMISSIONS - scan.enforced_tokens)
    assert not unenforced, (
        f"{len(unenforced)} token(s) are in ENFORCED_PERMISSIONS but no code path checks them:\n"
        + "\n".join(f"  {token}" for token in unenforced)
        + "\nGranting one makes a role look restricted while restricting nothing. Either add the "
        "check, or move the token into RESERVED_PERMISSIONS with the reason it is not enforced."
    )


def test_reserved_tokens_are_genuinely_not_enforced(scan):
    """A reserved token that acquires a real check must be promoted, not left behind.

    Reserved tokens are refused at write time on the grounds that nothing checks
    them. The moment that stops being true, the refusal is wrong.
    """
    promoted = sorted(set(RESERVED_PERMISSIONS) & scan.enforced_tokens)
    assert not promoted, (
        f"{promoted} are listed in RESERVED_PERMISSIONS but the code now checks them at "
        f"{[scan.locations_for(t) for t in promoted]}. Move them into ENFORCED_PERMISSIONS: while "
        "they stay reserved the write-time validator refuses to grant a permission that is now "
        "genuinely required."
    )


def test_reserved_and_enforced_do_not_overlap():
    overlap = sorted(set(RESERVED_PERMISSIONS) & ENFORCED_PERMISSIONS)
    assert not overlap, f"{overlap} are both enforced and reserved; a token must be exactly one"


def test_every_reserved_token_has_a_stated_reason():
    """A reserved token without a reason is indistinguishable from a forgotten one."""
    vague = sorted(token for token, reason in RESERVED_PERMISSIONS.items() if len(reason.strip()) < 15)
    assert not vague, f"reserved tokens need a real explanation of why nothing enforces them: {vague}"


# --------------------------------------------------------------------------- #
# Cross-check: the routes the app actually serves
# --------------------------------------------------------------------------- #


def test_registered_routes_agree_with_the_static_scan(scan):
    """Cross-check the AST scan against the app's real dependency graph.

    The static scan reads source text; this walks the dependency graph of the
    routes the app actually mounts. They should see the same
    ``require_permission`` tokens, and a disagreement means one of them is
    lying — most likely a permission wired up by means a source scan cannot
    follow, such as a router-level ``dependencies=[...]`` or a loop over a table.
    """
    routes = tokens_from_registered_routes()

    assert routes.route_count >= MIN_REGISTERED_ROUTES, (
        f"only {routes.route_count} API routes found; the app is probably not fully "
        "mounted, which would make this cross-check meaningless"
    )
    assert not routes.untagged_checkers, (
        "found permission checkers on live routes with no "
        f"__qgp_required_permission__ tag: {routes.untagged_checkers}. Anything building a "
        "permission dependency must tag it, or this cross-check silently stops seeing it."
    )

    only_on_routes = sorted(routes.token_set - scan.require_permission_tokens)
    assert not only_on_routes, (
        f"{only_on_routes} are enforced on mounted routes but the static scan did not find them. "
        "Something is wiring permissions in a way the source scan cannot read."
    )

    only_in_source = sorted(scan.require_permission_tokens - routes.token_set)
    assert not only_in_source, (
        f"{only_in_source} appear in require_permission calls but on no mounted route. "
        "Either the router is not included in the app, or the route was removed and the "
        "call site left behind."
    )

    uncatalogued = sorted(routes.token_set - ENFORCED_PERMISSIONS)
    assert not uncatalogued, f"routes enforce uncatalogued tokens: {uncatalogued}"


def test_dynamic_permission_sites_are_all_declared_and_resolved(scan):
    """Every non-literal call site must be declared, with tokens derived from source.

    This is what keeps the scan from being a fragile regex. Enforcement built
    from an f-string or a lookup table is invisible to a literal scan, and
    invisible enforcement cannot be catalogued — so ``scan_source_tree`` raises on
    an undeclared one rather than quietly returning a smaller set.
    """
    declared = {site.site for site in DECLARED_DYNAMIC_SITES}
    seen = {site.site for site in scan.dynamic_sites}

    assert seen <= declared, f"undeclared dynamic permission sites: {sorted(seen - declared)}"

    stale = sorted(declared - seen)
    assert not stale, (
        f"DECLARED_DYNAMIC_SITES lists {stale}, which no longer exists. Remove the declaration; "
        "a stale entry is an exemption nobody is checking."
    )

    for site in DECLARED_DYNAMIC_SITES:
        if site.resolver is None:
            continue
        resolved = scan.derived_tokens[site.site]
        assert resolved, f"resolver for {site.site} derived no tokens; it has stopped working"
        uncatalogued = sorted(resolved - ENFORCED_PERMISSIONS)
        assert not uncatalogued, f"{site.site} enforces uncatalogued tokens {uncatalogued}"


def test_an_undeclared_dynamic_site_is_refused(tmp_path):
    """Prove the scan raises rather than skipping enforcement it cannot read.

    Without this, the promise that dynamic sites cannot hide is untested, and a
    regex-equivalent scanner would pass every other test in this file.
    """
    src = tmp_path / "src"
    (src / "api").mkdir(parents=True)
    (src / "api" / "sneaky.py").write_text(
        "def check(user, kind):\n" "    return user.has_permission(f'{kind}:read')\n"
    )

    with pytest.raises(UndeclaredDynamicSiteError) as excinfo:
        scan_source_tree(src)

    assert "sneaky.py" in str(excinfo.value)


def test_aliased_import_of_require_permission_is_refused(tmp_path):
    """An alias would hide every call site behind it from a name-matching scan."""
    from src.domain.authz.extraction import AliasedImportError

    src = tmp_path / "src"
    src.mkdir()
    (src / "aliased.py").write_text(
        "from src.api.dependencies import require_permission as rp\n" "dep = rp('incident:create')\n"
    )

    with pytest.raises(AliasedImportError):
        scan_source_tree(src)


# --------------------------------------------------------------------------- #
# The families excluded from the admin grant, and the grant itself
# --------------------------------------------------------------------------- #


def test_narrowing_and_reference_number_families_are_the_expected_size():
    """Pin the two families the admin grant deliberately excludes.

    The product decision names four ``*:view_all`` tokens and two
    ``*:set_reference_number`` tokens. A fifth of either would silently be
    excluded from the admin grant by the suffix rule without anyone deciding
    that, so the count is asserted rather than assumed.
    """
    assert sorted(VIEW_ALL_PERMISSIONS) == [
        "complaint:view_all",
        "incident:view_all",
        "investigations:view_all",
        "rta:view_all",
    ]
    assert sorted(REFERENCE_NUMBER_PERMISSIONS) == [
        "incident:set_reference_number",
        "policy:set_reference_number",
    ]


def test_admin_role_permission_list_is_reviewable(capsys):
    """Print the proposed admin grant. This applies nothing.

    Deliberately a dry run: it asserts the shape of the proposal and prints the
    exact JSON a reviewer would apply. Writing it to a database is a human
    decision, so nothing here connects to one.
    """
    expected = ENFORCED_PERMISSIONS - VIEW_ALL_PERMISSIONS - REFERENCE_NUMBER_PERMISSIONS
    assert set(ADMIN_ROLE_PERMISSIONS) == expected
    assert list(ADMIN_ROLE_PERMISSIONS) == sorted(ADMIN_ROLE_PERMISSIONS), "keep it sorted for reviewable diffs"

    assert not VIEW_ALL_PERMISSIONS & set(
        ADMIN_ROLE_PERMISSIONS
    ), "*:view_all defeats the own-records-only narrowing some list endpoints apply"
    assert not REFERENCE_NUMBER_PERMISSIONS & set(
        ADMIN_ROLE_PERMISSIONS
    ), "*:set_reference_number allows overriding generated reference numbers"
    assert set(ADMIN_ROLE_PERMISSIONS) <= GRANTABLE_PERMISSIONS
    assert not set(ADMIN_ROLE_PERMISSIONS) & set(RESERVED_PERMISSIONS)

    with capsys.disabled():
        print(f"\nProposed admin role grant — {len(ADMIN_ROLE_PERMISSIONS)} tokens. NOT APPLIED.")
        print("Excluded on purpose:")
        print(f"  {sorted(VIEW_ALL_PERMISSIONS)} — defeat own-records-only narrowing")
        print(f"  {sorted(REFERENCE_NUMBER_PERMISSIONS)} — allow overriding generated reference numbers")
        print("Value to write into roles.permissions:")
        print(json.dumps(list(ADMIN_ROLE_PERMISSIONS)))


def test_admin_fixture_only_grants_catalogued_tokens():
    """``_ADMIN_PERMS`` is where the drift started; keep it inside the catalogue.

    A subset is fine — the fixture is one admin persona, not the full grant — but
    a token outside the catalogue is not, because it cannot affect any check and
    so only misleads whoever reads the fixture.

    Read out of the source rather than imported: importing that conftest sets
    ``DATABASE_URL`` and opens an engine, which a unit test should not do.
    """
    tokens = _admin_perm_tokens_from_conftest()

    assert len(tokens) >= 20, f"only found {len(tokens)} tokens; the fixture parse has broken"
    assert len(tokens) == len(set(tokens)), f"duplicates: {sorted({t for t in tokens if tokens.count(t) > 1})}"

    uncatalogued = sorted(set(tokens) - GRANTABLE_PERMISSIONS)
    assert not uncatalogued, (
        f"_ADMIN_PERMS in tests/integration/conftest.py grants {uncatalogued}, which "
        "src/domain/authz/catalogue.py does not list as enforced. Nothing checks these, so they "
        "grant nothing; remove them, or catalogue them if a check now exists."
    )


def _admin_perm_tokens_from_conftest() -> list[str]:
    """Extract the ``_ADMIN_PERMS`` token list from the integration conftest source."""
    module = ast.parse((REPO_ROOT / "tests" / "integration" / "conftest.py").read_text())
    for node in module.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(t, ast.Name) and t.id == "_ADMIN_PERMS" for t in node.targets):
            continue
        value = node.value
        # Shape today is ",".join([...]); a plain list would be fine too.
        if isinstance(value, ast.Call) and isinstance(value.func, ast.Attribute) and value.func.attr == "join":
            value = value.args[0]
        if isinstance(value, (ast.List, ast.Tuple)):
            return list(ast.literal_eval(value))
        raise AssertionError(
            "_ADMIN_PERMS is no longer a literal list (or a join of one), so this guard can no "
            f"longer read it. Found {type(value).__name__}."
        )
    raise AssertionError("tests/integration/conftest.py no longer defines _ADMIN_PERMS")


def test_divergence_report_renders(scan):
    """The dry-run report must not blow up; it is the human-facing view of all this."""
    report = format_divergence_report(
        catalogued=ENFORCED_PERMISSIONS,
        reserved=set(RESERVED_PERMISSIONS),
        scan=scan,
    )
    assert "enforced total" in report
    assert "enforced but NOT catalogued: 0" in report
    assert "catalogued but enforced NOWHERE: 0" in report
