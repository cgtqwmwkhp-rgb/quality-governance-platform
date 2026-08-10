"""CUT-1 — one retention · one Access · QGP as system of record.

The load-bearing test in this module is
:func:`test_cut1_never_brings_a_disposal_date_forward`. Disposal hard-deletes the
row and the blob, so the only acceptable direction for a retention converge is
"keeps things longer". It is asserted against every rule in the checked-in
taxonomy, comparing the pre-CUT-1 behaviour (first regex match, counted from
approval, 365-day years) with the post-CUT-1 one.
"""

from __future__ import annotations

import ast
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.domain.services.document_library_filing_service import (
    apply_category_retention,
    apply_supersede_retention,
    compute_retention_until,
    map_category_access,
)
from src.domain.services.library_retention_policy import (
    REASON_ABSENT,
    REASON_CONDITIONAL,
    REASON_SCOPED_CLAUSES,
    REASON_SUB_YEAR_PERIOD,
    RetentionAnchor,
    add_years,
    policy_from_stored,
    resolve_retention_rule,
    retention_until_for,
)
from src.domain.services.library_rules import (
    LIBRARY_ACCESS_LEVELS,
    assert_access_level_required,
    normalize_access_level,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
TAXONOMY = REPO_ROOT / "specs" / "governance-library" / "taxonomy.json"
MIGRATION = REPO_ROOT / "alembic" / "versions" / "20261102_lib_cut1_retention_access_sor.py"
CUT1_REVISION = "20261102_lib_cut1_sor"
WJ0_HEAD = "20261101_lib_wj0_drop"

APPROVED_AT = datetime(2026, 1, 1, tzinfo=timezone.utc)
SUPERSEDED_AT = datetime(2040, 6, 15, tzinfo=timezone.utc)

# Exactly the expression `document_library_filing_service` used before CUT-1.
_PRE_CUT1_RE = re.compile(r"(\d+)\s*years?", re.IGNORECASE)


def _taxonomy_rules() -> list[str | None]:
    payload = json.loads(TAXONOMY.read_text(encoding="utf-8"))
    return sorted({row.get("retention_rule") for row in payload["categories"]}, key=lambda v: (v is not None, v or ""))


def _pre_cut1_retention_until(rule: str | None) -> datetime | None:
    """The behaviour this PR replaces, reproduced so the comparison is real."""
    text = (rule or "").strip()
    if not text or text.lower() == "current":
        return None
    match = _PRE_CUT1_RE.search(text)
    if not match:
        return None
    years = int(match.group(1))
    if years <= 0:
        return None
    return APPROVED_AT + timedelta(days=years * 365)


def _post_cut1_earliest_disposal(rule: str | None) -> datetime | None:
    """The earliest date CUT-1 can ever make a document under this rule disposable."""
    policy = resolve_retention_rule(rule).policy
    return retention_until_for(policy, issued_at=APPROVED_AT) or retention_until_for(
        policy, superseded_at=SUPERSEDED_AT
    )


def _category(rule: str | None, *, default_access: str = "managers") -> SimpleNamespace:
    return SimpleNamespace(
        retention_rule=rule,
        retention_years=None,
        retention_anchor=None,
        default_access=default_access,
    )


def _document() -> SimpleNamespace:
    return SimpleNamespace(
        retention_until=None,
        retention_years=None,
        retention_anchor=None,
        retention_basis=None,
    )


# ---------------------------------------------------------------------------
# The safety invariant
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("rule", _taxonomy_rules())
def test_cut1_never_brings_a_disposal_date_forward(rule: str | None) -> None:
    """No taxonomy rule may become disposable earlier than it was before CUT-1.

    Converging retention onto one executable policy is allowed to keep documents
    longer — the fourteen unreadable rules now keep them indefinitely — but a
    single day earlier is a record destroyed before its governance rule allowed.
    """
    before = _pre_cut1_retention_until(rule)
    after = _post_cut1_earliest_disposal(rule)
    if before is None or after is None:
        return
    assert after >= before, f"{rule!r} would be disposable at {after} but was {before} before CUT-1"


def test_every_taxonomy_rule_resolves_to_a_named_outcome() -> None:
    """The resolver is total: no rule falls through to an unexplained ``None``."""
    for rule in _taxonomy_rules():
        decision = resolve_retention_rule(rule)
        assert decision.reason, f"{rule!r} produced no reason"
        if decision.policy is None:
            assert decision.reason != RetentionAnchor.ISSUE.value
        else:
            assert decision.policy.basis == " ".join((rule or "").split())


# ---------------------------------------------------------------------------
# The grammar — the classifications the safety invariant depends on
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("rule", "years", "anchor"),
    [
        ("6 years", 6, RetentionAnchor.ISSUE),
        ("Records 6 years", 6, RetentionAnchor.ISSUE),
        ("6 years (2 certification cycles)", 6, RetentionAnchor.ISSUE),
        ("Current + superseded 6 years", 6, RetentionAnchor.SUPERSEDE),
        ("Until superseded + 6 years", 6, RetentionAnchor.SUPERSEDE),
        ("Current + previous 2 years", 2, RetentionAnchor.SUPERSEDE),
        ("Life of asset + 6 years", 6, RetentionAnchor.EVENT),
        ("Duration of employment", None, RetentionAnchor.EVENT),
        ("Current logbook + 6 years", 6, RetentionAnchor.EVENT),
        ("Current", None, RetentionAnchor.INDEFINITE),
        ("Until superseded + previous", None, RetentionAnchor.INDEFINITE),
    ],
)
def test_grammar_classifies_anchor_and_years(rule: str, years: int | None, anchor: RetentionAnchor) -> None:
    policy = resolve_retention_rule(rule).policy
    assert policy is not None
    assert (policy.years, policy.anchor) == (years, anchor)


@pytest.mark.parametrize(
    ("rule", "reason"),
    [
        # Two record types, two periods. Taking the first was the defect.
        ("Tacho data 12 months; working time records 2 years", REASON_SCOPED_CLAUSES),
        ("3 years minimum (to age 21 if a minor); investigations 6 years", REASON_SCOPED_CLAUSES),
        ("EL certificates: 40 years recommended; others 6 years", REASON_SCOPED_CLAUSES),
        ("Health records: 40 years", REASON_SCOPED_CLAUSES),
        # Conditional on a fact the register does not hold.
        ("3 years (longer if incident-related)", REASON_CONDITIONAL),
        ("Current; 40 years where linked to exposure monitoring", REASON_SCOPED_CLAUSES),
        ("Current + 3 years (contract life + 6 years if contractual)", REASON_CONDITIONAL),
        # `retention_years` is years by definition (R19); months are not rounded.
        ("15 months", REASON_SUB_YEAR_PERIOD),
        (None, REASON_ABSENT),
        ("", REASON_ABSENT),
    ],
)
def test_grammar_refuses_rather_than_guesses(rule: str | None, reason: str) -> None:
    decision = resolve_retention_rule(rule)
    assert decision.policy is None
    assert decision.reason == reason


def test_multi_clause_rule_no_longer_silently_takes_the_first_number() -> None:
    """The specific defect: three years chosen over a six-year investigation leg."""
    rule = "3 years minimum (to age 21 if a minor); investigations 6 years"
    assert _pre_cut1_retention_until(rule) is not None
    assert resolve_retention_rule(rule).policy is None


def test_years_are_calendar_years_not_365_day_blocks() -> None:
    """A 40-year retention was landing ten days early on ``timedelta(days=365*n)``."""
    assert add_years(datetime(2026, 1, 1, tzinfo=timezone.utc), 40) == datetime(2066, 1, 1, tzinfo=timezone.utc)
    assert add_years(datetime(2024, 2, 29, tzinfo=timezone.utc), 1) == datetime(2025, 2, 28, tzinfo=timezone.utc)


def test_naive_anchor_dates_are_treated_as_utc() -> None:
    assert add_years(datetime(2026, 5, 4), 2) == datetime(2028, 5, 4, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Anchors decide when the clock starts
# ---------------------------------------------------------------------------


def test_supersede_anchored_rule_has_no_disposal_date_while_current() -> None:
    """The bug this closes: superseded-plus-six-years counted from approval.

    A document approved in 2026 and superseded in 2040 was disposable the moment
    it stopped being current, because its ``retention_until`` had been sitting at
    2032 for eight years.
    """
    category = _category("Current + superseded 6 years")
    document = _document()
    apply_category_retention(document, category, issued_at=APPROVED_AT)

    assert document.retention_years == 6
    assert document.retention_anchor == RetentionAnchor.SUPERSEDE.value
    assert document.retention_until is None

    apply_supersede_retention(document, SUPERSEDED_AT)
    assert document.retention_until == datetime(2046, 6, 15, tzinfo=timezone.utc)


def test_issue_anchored_rule_gets_its_date_at_approval() -> None:
    document = _document()
    apply_category_retention(document, _category("6 years"), issued_at=APPROVED_AT)
    assert document.retention_anchor == RetentionAnchor.ISSUE.value
    assert document.retention_until == datetime(2032, 1, 1, tzinfo=timezone.utc)


def test_event_and_indefinite_rules_get_no_date_at_all() -> None:
    for rule in ("Life of asset + 6 years", "Current", "Health records: 40 years"):
        document = _document()
        apply_category_retention(document, _category(rule), issued_at=APPROVED_AT)
        assert document.retention_until is None, rule
        apply_supersede_retention(document, SUPERSEDED_AT)
        assert document.retention_until is None, rule


def test_supersede_never_shortens_a_legacy_date() -> None:
    """A pre-CUT-1 row already carries a too-early date; supersede repairs it, never the reverse."""
    document = _document()
    document.retention_years = 6
    document.retention_anchor = RetentionAnchor.SUPERSEDE.value
    document.retention_until = datetime(2099, 1, 1, tzinfo=timezone.utc)
    apply_supersede_retention(document, SUPERSEDED_AT)
    assert document.retention_until == datetime(2099, 1, 1, tzinfo=timezone.utc)

    document.retention_until = datetime(2031, 12, 31, tzinfo=timezone.utc)
    apply_supersede_retention(document, SUPERSEDED_AT)
    assert document.retention_until == datetime(2046, 6, 15, tzinfo=timezone.utc)


def test_supersede_tolerates_a_naive_stored_date() -> None:
    """SQLite returns naive datetimes; comparing them to an aware one must not raise."""
    document = _document()
    document.retention_years = 6
    document.retention_anchor = RetentionAnchor.SUPERSEDE.value
    document.retention_until = datetime(2031, 12, 31)
    apply_supersede_retention(document, SUPERSEDED_AT)
    assert document.retention_until == datetime(2046, 6, 15, tzinfo=timezone.utc)


def test_reapproval_under_a_new_anchor_clears_the_old_date() -> None:
    """A stale issue-anchored date must not survive a move to a supersede-anchored rule.

    Otherwise the document keeps the earlier date the old rule produced and
    becomes disposable years before the new rule allows — the same premature
    disposal, arriving by a different route.
    """
    document = _document()
    apply_category_retention(document, _category("6 years"), issued_at=APPROVED_AT)
    assert document.retention_until == datetime(2032, 1, 1, tzinfo=timezone.utc)

    apply_category_retention(document, _category("Current + superseded 6 years"), issued_at=APPROVED_AT)
    assert document.retention_until is None
    assert document.retention_anchor == RetentionAnchor.SUPERSEDE.value


def test_reapproval_under_an_unreadable_rule_clears_the_old_date() -> None:
    document = _document()
    apply_category_retention(document, _category("6 years"), issued_at=APPROVED_AT)
    apply_category_retention(document, _category("Health records: 40 years"), issued_at=APPROVED_AT)
    assert document.retention_until is None
    assert document.retention_years is None
    assert document.retention_anchor is None


def test_document_policy_survives_a_later_taxonomy_edit() -> None:
    """The document is the SoR once filed (F-7 §2), so re-filing prose cannot re-date it."""
    category = _category("6 years")
    document = _document()
    apply_category_retention(document, category, issued_at=APPROVED_AT)
    category.retention_rule = "3 years"
    stored = policy_from_stored(
        retention_years=document.retention_years,
        retention_anchor=document.retention_anchor,
        retention_basis=document.retention_basis,
    )
    assert stored is not None and stored.years == 6
    assert document.retention_basis == "6 years"


def test_steward_override_on_the_category_wins_over_the_prose() -> None:
    """Resolving a blocker means setting the columns, not rewriting the governance text."""
    category = _category("Health records: 40 years")
    assert compute_retention_until(category, APPROVED_AT) is None

    category.retention_years = 40
    category.retention_anchor = RetentionAnchor.ISSUE.value
    assert compute_retention_until(category, APPROVED_AT) == datetime(2066, 1, 1, tzinfo=timezone.utc)


def test_policy_from_stored_rejects_an_unknown_anchor() -> None:
    assert policy_from_stored(retention_years=6, retention_anchor="whenever", retention_basis="x") is None
    assert policy_from_stored(retention_years=6, retention_anchor=None, retention_basis="x") is None


# ---------------------------------------------------------------------------
# One access vocabulary
# ---------------------------------------------------------------------------


def test_one_access_vocabulary_has_one_home() -> None:
    assert LIBRARY_ACCESS_LEVELS == ("all_staff", "managers", "restricted")
    for level in LIBRARY_ACCESS_LEVELS:
        assert map_category_access(level) == level
        assert normalize_access_level(level) == level


@pytest.mark.parametrize(
    ("legacy", "canonical"),
    [
        ("internal", "all_staff"),
        ("INTERNAL", "all_staff"),
        ("public", "all_staff"),
        ("confidential", "restricted"),
        ("manager", "managers"),
    ],
)
def test_control_vocabulary_folds_onto_the_library_one(legacy: str, canonical: str) -> None:
    assert normalize_access_level(legacy) == canonical


def test_no_alias_widens_access() -> None:
    """Folding two vocabularies must never make a document readable by more people."""
    order = {level: index for index, level in enumerate(LIBRARY_ACCESS_LEVELS)}
    # `internal` and `public` are both "everyone inside the tenant", which is
    # `all_staff`; every other alias must land at least as restrictive as the
    # library level whose name it shares.
    assert order[normalize_access_level("confidential") or ""] >= order["managers"]
    assert order[normalize_access_level("restricted_access") or ""] == order["restricted"]


def test_unmappable_access_value_is_refused_not_defaulted() -> None:
    assert normalize_access_level("top_secret") is None
    assert normalize_access_level("") is None
    assert normalize_access_level(None) is None


def test_anchored_control_record_takes_the_register_access_level() -> None:
    """F-7 §3 — the Register is the access SoR; the control row does not get a second opinion."""
    from src.api.routes.document_control import _converged_access_level

    assert _converged_access_level("internal", register_level="restricted") == "restricted"
    assert _converged_access_level("restricted", register_level="all_staff") == "all_staff"


def test_unanchored_control_record_keeps_its_own_value_folded() -> None:
    from src.api.routes.document_control import _converged_access_level

    assert _converged_access_level("internal", register_level=None) == "all_staff"
    assert _converged_access_level("managers", register_level=None) == "managers"
    # A Register row with no access level of its own cannot dictate one.
    assert _converged_access_level("managers", register_level=None) == "managers"


def test_control_record_refuses_an_off_vocabulary_access_level() -> None:
    from src.api.routes.document_control import _converged_access_level
    from src.domain.exceptions import ValidationError

    with pytest.raises(ValidationError):
        _converged_access_level("top_secret", register_level=None)


def test_control_access_update_with_nothing_to_write_is_a_no_op() -> None:
    """An explicit null with no Register to inherit from must not write NULL."""
    from src.api.routes.document_control import _converged_access_level

    assert _converged_access_level(None, register_level=None) is None


def test_r26_stays_strict_on_the_library_write_path() -> None:
    """Normalising is a write-boundary convenience, never an R26 amnesty."""
    from src.domain.exceptions import ValidationError

    assert assert_access_level_required("managers") == "managers"
    with pytest.raises(ValidationError):
        assert_access_level_required("internal")
    with pytest.raises(ValidationError):
        assert_access_level_required(None)


# ---------------------------------------------------------------------------
# The migration snapshot must still agree with the resolver
# ---------------------------------------------------------------------------


def _migration_constant(name: str) -> object:
    """Read a literal out of the migration without importing alembic machinery."""
    tree = ast.parse(MIGRATION.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == name:
            assert node.value is not None
            return ast.literal_eval(node.value)
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == name for target in node.targets
        ):
            return ast.literal_eval(node.value)
    raise AssertionError(f"{name} not found in {MIGRATION.name}")


def test_migration_is_the_sole_head_on_wj0() -> None:
    text = MIGRATION.read_text(encoding="utf-8")
    assert f'revision: str = "{CUT1_REVISION}"' in text
    assert f'down_revision: Union[str, Sequence[str], None] = "{WJ0_HEAD}"' in text
    siblings = [
        path
        for path in (REPO_ROOT / "alembic" / "versions").rglob("*.py")
        if path.is_file() and CUT1_REVISION in path.read_text(encoding="utf-8")
    ]
    assert siblings == [MIGRATION], f"exactly one file may declare {CUT1_REVISION}, found {siblings}"


def test_migration_backfill_still_matches_the_resolver() -> None:
    """The frozen snapshot is only safe while it agrees with the live grammar."""
    frozen = {rule: (years, anchor) for rule, years, anchor in _migration_constant("RETENTION_BACKFILL")}
    expected: dict[str, tuple[int | None, str]] = {}
    for rule in _taxonomy_rules():
        if rule is None:
            continue
        policy = resolve_retention_rule(rule).policy
        if policy is not None:
            expected[rule] = (policy.years, policy.anchor.value)
    assert frozen == expected


def test_migration_access_normalisation_matches_library_rules() -> None:
    frozen = dict(_migration_constant("ACCESS_LEVEL_NORMALISATION"))
    for legacy, canonical in frozen.items():
        assert normalize_access_level(legacy) == canonical, legacy


def test_migration_does_not_touch_retention_until() -> None:
    """The single disposal clock is not rewritten by the converge, in either direction.

    CUT-1 changes *when* a clock starts, in application code, on documents filed
    from now on. Re-dating rows that already exist would be re-deciding retention
    for documents nobody re-reviewed.
    """
    tree = ast.parse(MIGRATION.read_text(encoding="utf-8"))
    sql_literals = [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and re.search(r"\b(UPDATE|ALTER TABLE|INSERT INTO|DELETE FROM)\b", node.value)
    ]
    assert sql_literals, "expected the migration to carry its SQL as literals"
    for statement in sql_literals:
        assert "retention_until" not in statement, statement

    # `ADDED_COLUMNS` holds `sa.SmallInteger()` calls, so read its names off the AST.
    added_columns = {
        element.elts[1].value
        for node in ast.walk(tree)
        if isinstance(node, ast.AnnAssign)
        and isinstance(node.target, ast.Name)
        and node.target.id == "ADDED_COLUMNS"
        and isinstance(node.value, ast.Tuple)
        for element in node.value.elts
        if isinstance(element, ast.Tuple) and isinstance(element.elts[1], ast.Constant)
    }
    assert added_columns == {"retention_years", "retention_anchor", "retention_basis"}
