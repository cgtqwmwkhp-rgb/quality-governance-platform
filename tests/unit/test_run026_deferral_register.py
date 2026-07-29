"""The Run026 deferral register must stay small, explained and owned.

``DEFERRED_ABSENT_COLUMNS`` in ``scripts/ops/run026/audit_attribution_schema.py``
is the one way a declared-but-absent column can pass the CI gate. That makes it
the obvious place for a future absent column to be parked instead of fixed, which
is the failure mode this whole area exists to correct — so it gets a guard.

The register is not the same thing as ``_ALEMBIC_CHECK_EXCLUDED_TABLES``. That one
is a table-level compare-noise list with 41 entries and its own maintained
inventory. This one is column-level, currently holds four entries on a single
table, and every entry has to name an owner and be documented.
"""

from __future__ import annotations

from pathlib import Path

from scripts.ops.run026.audit_attribution_schema import DEFERRED_ABSENT_COLUMNS

REPO_ROOT = Path(__file__).resolve().parents[2]
GOVERNANCE_DOC = REPO_ROOT / "docs" / "governance" / "attribution_schema_drift.md"

#: The only deferral Run026 granted, and why: the physical soa_control_entries
#: table carries a different design from the model rather than fewer columns, and
#: which of inclusion_justification / exclusion_justification the model's single
#: justification means is an IMS decision. Nothing queries the table.
EXPECTED_DEFERRALS = {
    ("soa_control_entries", "implementation_method"),
    ("soa_control_entries", "justification"),
    ("soa_control_entries", "risk_treatment_reference"),
    ("soa_control_entries", "tenant_id"),
}


def test_the_deferral_register_has_not_grown():
    """A new entry here needs a decision, not a passing build.

    If this fails because you added a column, that is the guard working. Add the
    row to docs/governance/attribution_schema_drift.md with an owner and a reason
    the absence is not breaking a query, and update EXPECTED_DEFERRALS in the same
    commit so the change is visible in review.
    """
    assert set(DEFERRED_ABSENT_COLUMNS) == EXPECTED_DEFERRALS, (
        "the declared-but-absent column deferral register changed. Every entry suppresses a "
        "latent UndefinedColumn, so each one needs a named owner and a stated reason nothing "
        "queries it.\n"
        f"  added  : {sorted(set(DEFERRED_ABSENT_COLUMNS) - EXPECTED_DEFERRALS)}\n"
        f"  removed: {sorted(EXPECTED_DEFERRALS - set(DEFERRED_ABSENT_COLUMNS))}"
    )


def test_every_deferral_names_an_owner():
    ownerless = sorted(key for key, owner in DEFERRED_ABSENT_COLUMNS.items() if not (owner or "").strip())
    assert ownerless == [], f"these deferrals name no owner, so nobody is accountable for them: {ownerless}"


def test_every_deferred_table_is_documented():
    """The register and the governance note must not drift apart."""
    prose = GOVERNANCE_DOC.read_text(encoding="utf-8")
    undocumented = sorted({table for table, _ in DEFERRED_ABSENT_COLUMNS if table not in prose})
    assert undocumented == [], (
        f"these deferred tables are absent from {GOVERNANCE_DOC.relative_to(REPO_ROOT)}, so the "
        f"reason for the deferral exists only in a code comment: {undocumented}"
    )
