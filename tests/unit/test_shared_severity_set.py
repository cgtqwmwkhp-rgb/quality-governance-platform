"""B-9 — the three fields the ``severity_levels`` lookup fills carry one set.

The defect this pins down is not a bug in any single module: it is three modules
each holding their own idea of what a severity is. ``severity_levels`` seeds five
options; ``IncidentSeverity`` had five members, ``ComplaintPriority`` had four and
the near-miss schema pattern listed four, so ``negligible`` was submittable on an
incident and a guaranteed 422 on a complaint or a near miss.

These tests assert the agreement in every place a copy of the set exists — the two
enums, the near-miss request pattern, the two database CHECK constraints and the
migration that installs them — so a fourth copy cannot be introduced quietly, and
so shrinking one of them fails here rather than in production.

Deliberately *not* asserted: ``RTASeverity`` (an injury-outcome scale derived from
reported harm, never from a triage word), ``NearMiss.priority`` (a four-value
workflow queue), audit finding grading and ``CAPAPriority``. Those measure other
things and are not fed by this lookup.
"""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest
import sqlalchemy as sa
from sqlalchemy import create_engine

from src.api.schemas.complaint import ComplaintCreate
from src.api.schemas.near_miss import SHARED_SEVERITY_PATTERN, NearMissCreate, NearMissUpdate
from src.domain.models.complaint import Complaint, ComplaintPriority
from src.domain.models.incident import Incident, IncidentSeverity
from src.domain.models.near_miss import NearMiss
from src.domain.services.shared_severity import (
    SHARED_SEVERITY_VALUES,
    map_portal_severity,
    near_miss_priority_for_severity,
    normalize_portal_severity,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
MIGRATION_PATH = REPO_ROOT / "alembic" / "versions" / "20260911_shared_severity_negligible.py"

EXPECTED = {"critical", "high", "medium", "low", "negligible"}


def _load_migration() -> ModuleType:
    """Load the B-9 migration by path; ``alembic/versions`` is not a package."""
    import alembic

    if not hasattr(alembic, "op"):
        alembic.op = SimpleNamespace(get_bind=lambda: None)  # type: ignore[attr-defined]

    spec = importlib.util.spec_from_file_location("qgp_shared_severity_migration", MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _check_constraint_values(model: type, constraint_name: str) -> set[str]:
    """The quoted literals inside a model's named CHECK constraint."""
    for constraint in model.__table__.constraints:
        if constraint.name == constraint_name:
            return set(re.findall(r"'([A-Za-z_]+)'", str(constraint.sqltext)))
    raise AssertionError(f"{model.__name__} no longer declares {constraint_name}")


class TestTheEnumsAgree:
    def test_incident_severity_is_the_shared_set(self):
        assert {member.value for member in IncidentSeverity} == EXPECTED

    def test_complaint_priority_mirrors_incident_severity(self):
        """``map_portal_severity`` resolves one word on both; it needs them equal."""
        assert {member.value for member in ComplaintPriority} == {member.value for member in IncidentSeverity}

    def test_the_service_constant_is_derived_not_copied(self):
        assert SHARED_SEVERITY_VALUES == frozenset(EXPECTED)


class TestTheRequestSchemasAgree:
    def test_near_miss_pattern_covers_the_shared_set(self):
        assert set(re.findall(r"[a-z]+", SHARED_SEVERITY_PATTERN)) == EXPECTED

    @pytest.mark.parametrize("value", sorted(EXPECTED))
    def test_near_miss_update_accepts_every_shared_value(self, value: str):
        assert NearMissUpdate(potential_severity=value).potential_severity == value

    def test_near_miss_update_still_rejects_a_value_outside_the_set(self):
        with pytest.raises(ValueError):
            NearMissUpdate(potential_severity="extreme")

    def test_complaint_create_accepts_negligible(self):
        """The 422 B-9 exists to remove: this is the request the dropdown produced."""
        complaint = ComplaintCreate(
            title="Contract test complaint",
            description="Raised at the lowest severity the dropdown offers.",
            received_date="2026-01-01T09:00:00+00:00",
            complainant_name="Contract Test",
            priority="negligible",
        )
        assert complaint.priority is ComplaintPriority.NEGLIGIBLE

    def test_complaint_create_still_rejects_a_value_outside_the_set(self):
        with pytest.raises(ValueError):
            ComplaintCreate(
                title="Contract test complaint",
                description="Raised with a severity nobody defined.",
                received_date="2026-01-01T09:00:00+00:00",
                complainant_name="Contract Test",
                priority="catastrophic",
            )

    def test_near_miss_create_accepts_negligible(self):
        near_miss = NearMissCreate(
            reporter_name="Contract Test",
            contract="thames_water",
            location="Depot yard",
            event_date="2026-01-01T09:00:00+00:00",
            description="Pallet slipped but nobody was near it.",
            potential_severity="negligible",
        )
        assert near_miss.potential_severity == "negligible"


class TestTheDatabaseConstraintsAgree:
    def test_incident_severity_check_is_the_shared_set(self):
        assert _check_constraint_values(Incident, "ck_incidents_severity") == EXPECTED

    def test_complaint_priority_check_is_the_shared_set(self):
        assert _check_constraint_values(Complaint, "ck_complaints_priority") == EXPECTED

    def test_near_miss_potential_severity_check_is_the_shared_set(self):
        assert _check_constraint_values(NearMiss, "ck_nm_severity_values") == EXPECTED

    def test_near_miss_priority_is_a_separate_four_value_scale(self):
        """The workflow queue is not part of the shared set and must not drift into it."""
        assert _check_constraint_values(NearMiss, "ck_near_misses_priority") == {"LOW", "MEDIUM", "HIGH", "CRITICAL"}

    def test_the_migration_inlines_the_same_values(self):
        """The migration keeps its own copy so it stays self-contained; pin it here."""
        assert set(_load_migration().SHARED_SEVERITY_VALUES) == EXPECTED


class TestPortalIntakeCannotWriteFreeText:
    """``QuickReportCreate.severity`` is an unvalidated string, so normalise it."""

    @pytest.mark.parametrize("value", sorted(EXPECTED))
    def test_a_known_word_passes_through(self, value: str):
        assert normalize_portal_severity(value) == value

    @pytest.mark.parametrize("value", ["URGENT", "", None, "  ", "sev1", "negligible "])
    def test_an_unknown_word_becomes_a_known_one(self, value):
        """Including the empty and null cases — the column is a closed set either way."""
        assert normalize_portal_severity(value) in EXPECTED

    def test_casing_and_padding_are_tolerated(self):
        assert normalize_portal_severity("  NEGLIGIBLE ") == "negligible"

    def test_an_unrecognised_word_does_not_silently_escalate(self):
        assert normalize_portal_severity("catastrophic") == IncidentSeverity.MEDIUM.value

    @pytest.mark.parametrize("value", sorted(EXPECTED))
    def test_both_case_enums_resolve_from_one_word(self, value: str):
        severity, priority = map_portal_severity(value)
        assert severity.value == value
        assert priority.value == value


class TestNearMissPriorityProjection:
    """Near-miss priority is four-valued, so the fifth severity has to land somewhere."""

    def test_negligible_is_queued_lowest(self):
        assert near_miss_priority_for_severity("negligible") == "LOW"

    @pytest.mark.parametrize(
        ("severity", "expected"),
        [("low", "LOW"), ("medium", "MEDIUM"), ("high", "HIGH"), ("critical", "CRITICAL")],
    )
    def test_the_other_four_are_unchanged(self, severity: str, expected: str):
        assert near_miss_priority_for_severity(severity) == expected

    def test_every_shared_value_projects_onto_the_priority_constraint(self):
        allowed = _check_constraint_values(NearMiss, "ck_near_misses_priority")
        assert {near_miss_priority_for_severity(value) for value in EXPECTED} <= allowed


# ---------------------------------------------------------------------------
# Constraint half — known alias remap, then refuse unknown
# ---------------------------------------------------------------------------


def _constraint_scratch():
    """Minimal tables for the CHECK-constraint half of ``20260911_shared_severity``."""
    engine = create_engine("sqlite://")
    connection = engine.connect()
    connection.exec_driver_sql("CREATE TABLE complaints (id INTEGER PRIMARY KEY, priority TEXT)")
    connection.exec_driver_sql("CREATE TABLE near_misses (id INTEGER PRIMARY KEY, potential_severity TEXT)")
    return connection


def _wire_op(module: ModuleType, connection, monkeypatch: pytest.MonkeyPatch) -> list[tuple]:
    """Point the migration's ``op`` at ``connection``; capture constraint creates."""
    created: list[tuple] = []

    monkeypatch.setattr(module.op, "get_bind", lambda: connection)
    monkeypatch.setattr(module, "_has_table", lambda table: True)
    monkeypatch.setattr(module, "_has_constraint", lambda table, name: False)
    monkeypatch.setattr(module.op, "drop_constraint", lambda *args, **kwargs: None, raising=False)
    monkeypatch.setattr(
        module.op,
        "create_check_constraint",
        lambda name, table, predicate: created.append((name, table, predicate)),
        raising=False,
    )
    return created


class TestKnownSeverityAliasRemap:
    """Prod blocker: one ``near_misses`` row held ``extreme``; remap then constrain."""

    def test_the_alias_map_is_only_the_locked_decision(self):
        assert _load_migration().KNOWN_SEVERITY_ALIASES == {"extreme": "critical"}

    @pytest.mark.parametrize("stored", ["extreme", "EXTREME", "Extreme"])
    def test_extreme_remaps_then_the_constraint_applies(self, stored: str, monkeypatch: pytest.MonkeyPatch):
        module = _load_migration()
        with _constraint_scratch() as connection:
            connection.execute(
                sa.text("INSERT INTO near_misses (id, potential_severity) VALUES (1, :v)"),
                {"v": stored},
            )
            created = _wire_op(module, connection, monkeypatch)

            module._widen_check_constraints()

            value = connection.execute(sa.text("SELECT potential_severity FROM near_misses WHERE id = 1")).scalar_one()
            assert value == "critical"
            assert ("ck_nm_severity_values", "near_misses") == (
                created[-1][0],
                created[-1][1],
            )
            assert {name for name, _table, _pred in created} == {
                "ck_complaints_priority",
                "ck_nm_severity_values",
            }

    def test_extreme_on_complaints_priority_is_remapped_too(self, monkeypatch: pytest.MonkeyPatch):
        module = _load_migration()
        with _constraint_scratch() as connection:
            connection.execute(sa.text("INSERT INTO complaints (id, priority) VALUES (1, 'EXTREME')"))
            _wire_op(module, connection, monkeypatch)

            module._widen_check_constraints()

            assert (
                connection.execute(sa.text("SELECT priority FROM complaints WHERE id = 1")).scalar_one() == "critical"
            )

    def test_urgent_still_raises_unconstrainable(self, monkeypatch: pytest.MonkeyPatch):
        """Unknown values are not guessed — same refuse path as the original migration."""
        module = _load_migration()
        with _constraint_scratch() as connection:
            connection.execute(sa.text("INSERT INTO near_misses (id, potential_severity) VALUES (1, 'urgent')"))
            _wire_op(module, connection, monkeypatch)

            with pytest.raises(module.UnconstrainableSeverityValuesError, match="urgent"):
                module._widen_check_constraints()

            assert (
                connection.execute(sa.text("SELECT potential_severity FROM near_misses WHERE id = 1")).scalar_one()
                == "urgent"
            )

    def test_shared_values_are_left_alone(self, monkeypatch: pytest.MonkeyPatch):
        module = _load_migration()
        with _constraint_scratch() as connection:
            connection.execute(sa.text("INSERT INTO near_misses (id, potential_severity) VALUES (1, 'high')"))
            created = _wire_op(module, connection, monkeypatch)

            module._widen_check_constraints()

            assert (
                connection.execute(sa.text("SELECT potential_severity FROM near_misses WHERE id = 1")).scalar_one()
                == "high"
            )
            assert len(created) == 2
