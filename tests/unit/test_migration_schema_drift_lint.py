"""Lint: a migration may not decide nullability from row data and carry on.

This is the guard that would have prevented the July 2026 ``tenant_id`` drift
from spreading, and it is worth more than the fix for any one table.

The WCS-TEN2 wave established a copy-paste idiom: backfill ``tenant_id`` from a
parent, ``SELECT COUNT(*) ... WHERE tenant_id IS NULL``, and issue
``SET NOT NULL`` only if that count is zero — otherwise log a FAIL-SAFE warning,
``return``, and report success. Thirty-seven migrations now use it.

The idiom is not wrong to be cautious. It is wrong to be *silent*. On an empty
database the count is always zero, so the columns are tightened in CI and on every
fresh developer database; on staging and production the count is non-zero, the
column stays nullable, and ``alembic upgrade head`` exits 0. The declared schema
and the physical schema then disagree in a way that no fresh-database check can
observe, because the fresh database is the one that agrees.

So the rule is: **if a migration's nullability outcome depends on row data, it
must be capable of failing.** A migration that counts NULLs and then alters
nullability must contain a ``raise``. Refusing is fine. Quietly leaving the
database in a state the models forbid is not.

That single discriminator separates the two populations exactly: all thirty-seven
pre-existing instances contain zero ``raise`` statements. They are grandfathered
below; the list is a backlog, and it should only ever shrink.

Known limitation: this is a static check over migration source. It stops the
idiom being copied again and catches a re-invention that still counts NULLs
before altering — ``20260719_rls_gt_exp`` is caught that way despite using none of
the wave's naming. It cannot catch an arbitrary data-dependent DDL decision
expressed some other way. The complementary runtime check is
``scripts/ops/run025/verify_model_schema_parity.py`` run against staging and
production, which compares the models against the database that actually holds
the data.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
VERSIONS_DIR = REPO_ROOT / "alembic/versions"

_COUNTS_NULLS = re.compile(r"COUNT\(\*\)[^\"']*IS NULL", re.IGNORECASE)
_TIGHTENS_NULLABILITY = ("nullable=False", "nullable=nullable")

# Migrations that already shipped with a data-conditional NOT NULL that cannot
# fail. Each one can leave its column nullable on a database that held orphaned
# rows when it ran, while still reporting success.
#
# Do not add to this list. Removing an entry means the migration was either
# replaced by an unconditional convergence or reworked to raise; both are
# improvements. Coverage for the case and action registers is provided by
# 20260901_case_tenant_nn.
GRANDFATHERED: frozenset[str] = frozenset(
    {
        "20260710_audit_findings_tenant_not_null.py",
        "20260710_audit_runs_tenant_not_null.py",
        "20260710_capa_actions_tenant_not_null.py",
        "20260710_complaint_actions_tenant_not_null.py",
        "20260710_complaints_tenant_not_null.py",
        "20260710_external_audit_import_drafts_tenant_not_null.py",
        "20260710_external_audit_import_jobs_tenant_not_null.py",
        "20260710_incident_actions_tenant_not_null.py",
        "20260710_incidents_tenant_not_null.py",
        "20260710_investigation_actions_tenant_not_null.py",
        "20260710_investigation_comments_tenant_not_null.py",
        "20260710_investigation_customer_packs_tenant_not_null.py",
        "20260710_investigation_revision_events_tenant_not_null.py",
        "20260710_investigation_runs_tenant_not_null.py",
        "20260710_rta_actions_tenant_not_null.py",
        "20260711_bow_tie_elements_tenant_not_null.py",
        "20260711_controlled_document_versions_tenant_not_null.py",
        "20260711_controlled_documents_tenant_not_null.py",
        "20260711_document_access_logs_tenant_not_null.py",
        "20260711_document_annotations_tenant_not_null.py",
        "20260711_document_versions_tenant_not_null.py",
        "20260711_documents_tenant_not_null.py",
        "20260711_enterprise_risk_controls_tenant_not_null.py",
        "20260711_key_risk_indicators_tenant_not_null.py",
        "20260711_obsolete_document_records_tenant_not_null.py",
        "20260711_policies_tenant_not_null.py",
        "20260711_policy_versions_tenant_not_null.py",
        "20260711_risk_assessment_history_tenant_not_null.py",
        "20260711_risk_assessments_tenant_not_null.py",
        "20260711_risk_control_mappings_tenant_not_null.py",
        "20260711_risks_tenant_not_null.py",
        "20260711_risks_v2_tenant_not_null.py",
        "20260711_rta_parent_tenant_not_null.py",
        "20260713_near_misses_tenant_not_null.py",
        "20260713_workforce_tenant_not_null.py",
        "20260719_rls_gt_exp.py",
        "20260720_ea_tenant_nn.py",
    }
)


def _decides_nullability_from_data(source: str) -> bool:
    return bool(_COUNTS_NULLS.search(source)) and any(token in source for token in _TIGHTENS_NULLABILITY)


def _can_fail(source: str) -> bool:
    return any(isinstance(node, ast.Raise) for node in ast.walk(ast.parse(source)))


def _migration_files() -> list[Path]:
    return sorted(p for p in VERSIONS_DIR.glob("*.py") if p.name != "__init__.py")


def test_no_new_migration_decides_nullability_from_data_without_being_able_to_fail():
    offenders = []
    for path in _migration_files():
        if path.name in GRANDFATHERED:
            continue
        source = path.read_text(encoding="utf-8")
        if _decides_nullability_from_data(source) and not _can_fail(source):
            offenders.append(path.name)

    assert not offenders, (
        "These migrations decide a column's nullability from row counts but cannot fail, "
        "so they will silently leave the physical schema disagreeing with the models on "
        "any database that holds non-conforming rows:\n  "
        + "\n  ".join(offenders)
        + "\nEither converge unconditionally, or raise when the data will not allow it. "
        "See alembic/versions/20260901_case_action_tenant_id_not_null.py."
    )


def test_the_grandfather_list_is_accurate_and_not_padded():
    """Every grandfathered file must exist and must really be an offender.

    A stale entry silently widens the exemption, which is how a ratchet stops
    ratcheting.
    """
    names = {path.name for path in _migration_files()}
    missing = sorted(GRANDFATHERED - names)
    assert not missing, f"grandfathered migrations no longer exist; remove them: {missing}"

    not_actually_offending = []
    for name in sorted(GRANDFATHERED):
        source = (VERSIONS_DIR / name).read_text(encoding="utf-8")
        if not (_decides_nullability_from_data(source) and not _can_fail(source)):
            not_actually_offending.append(name)
    assert not not_actually_offending, (
        "These migrations no longer decide nullability from data without being able to "
        f"fail — remove them from GRANDFATHERED: {not_actually_offending}"
    )


def test_the_backlog_does_not_grow():
    """Pin the size of the exemption so growth requires an explicit edit here."""
    assert len(GRANDFATHERED) == 37


def test_the_lint_detects_the_wave_pattern():
    """Sanity-check the detector against a known instance and a known good one."""
    wave = (VERSIONS_DIR / "20260711_rta_parent_tenant_not_null.py").read_text(encoding="utf-8")
    assert _decides_nullability_from_data(wave)
    assert not _can_fail(wave)

    corrective = (VERSIONS_DIR / "20260901_case_action_tenant_id_not_null.py").read_text(encoding="utf-8")
    assert _decides_nullability_from_data(corrective)
    assert _can_fail(corrective), "the corrective migration must be able to refuse"


def test_the_lint_detects_a_reinvention_without_the_waves_naming():
    """20260719_rls_gt_exp uses none of the wave's helper names but the same shape."""
    source = (VERSIONS_DIR / "20260719_rls_gt_exp.py").read_text(encoding="utf-8")
    assert "should_enforce_not_null" not in source
    assert "FAIL-SAFE" not in source
    assert _decides_nullability_from_data(source)
    assert not _can_fail(source)
