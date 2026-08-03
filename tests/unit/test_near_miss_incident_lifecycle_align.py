"""N-2: the near-miss register runs the incident lifecycle, not a lookalike.

Near misses used to hold an uppercase string of their own — ``REPORTED``,
``UNDER_REVIEW``, ``ACTION_REQUIRED``, ``IN_PROGRESS``, ``CLOSED`` — and the
difference was not only casing. The edges differed (``UNDER_REVIEW`` could jump
straight to ``IN_PROGRESS``; ``IN_PROGRESS`` could close outright), there was no
``pending_review``, and reopening landed somewhere the incident register does
not send a reopened case. Four registers, three of them agreeing, was a trap
that had already produced ``normalize_portal_status``, a case-insensitive
``is_closed_status``, and an uppercase pair in ``CASE_CONFIGS``.

Two things are worth guarding, and they are different things:

1. The two maps do not drift apart again. ``NEAR_MISS_TRANSITIONS`` is derived
   from ``INCIDENT_TRANSITIONS``, so the assertion is cheap — but a future edit
   that reintroduces a hand-written near-miss map has to fail here.
2. ``20260910_nm_status_align`` rewrites exactly the labels it claims to,
   idempotently, and never walks a record backwards through the lifecycle.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from sqlalchemy import create_engine

from src.domain.exceptions import StateTransitionError
from src.domain.models.incident import IncidentStatus
from src.domain.services.case_closure import (
    CASE_TYPE_INCIDENT,
    CASE_TYPE_NEAR_MISS,
    check_close_transition,
    is_closed_status,
    reopen_status_for,
)
from src.domain.services.incident_service import INCIDENT_TRANSITIONS
from src.domain.services.near_miss_service import NEAR_MISS_TRANSITIONS, validate_near_miss_transition

REPO_ROOT = Path(__file__).resolve().parents[2]
MIGRATION = REPO_ROOT / "alembic/versions/20260910_near_miss_status_align.py"


# ---------------------------------------------------------------------------
# One lifecycle, two registers
# ---------------------------------------------------------------------------


class TestTheTwoRegistersShareOneLifecycle:
    def test_near_miss_edges_are_the_incident_edges(self):
        expected = {
            current.value: {target.value for target in targets} for current, targets in INCIDENT_TRANSITIONS.items()
        }

        assert NEAR_MISS_TRANSITIONS == expected

    def test_every_status_is_an_incident_status(self):
        seen = set(NEAR_MISS_TRANSITIONS) | {t for targets in NEAR_MISS_TRANSITIONS.values() for t in targets}

        assert seen == {status.value for status in IncidentStatus}

    @pytest.mark.parametrize("status", [status.value for status in IncidentStatus])
    def test_the_close_gate_answers_the_same_for_both_registers(self, status):
        """Same question, same answer — including which next steps are offered."""
        incident = check_close_transition(CASE_TYPE_INCIDENT, status)
        near_miss = check_close_transition(CASE_TYPE_NEAR_MISS, status)

        assert (near_miss.allowed, near_miss.allowed_next_statuses) == (
            incident.allowed,
            incident.allowed_next_statuses,
        )

    def test_reopen_is_the_incident_reopen(self):
        assert reopen_status_for(CASE_TYPE_NEAR_MISS) == reopen_status_for(CASE_TYPE_INCIDENT) == "pending_review"
        validate_near_miss_transition("closed", "pending_review")

    def test_closed_has_no_second_way_out(self):
        """Reopen is one controlled edge, not a jump back into the lifecycle."""
        for target in ("reported", "under_investigation", "pending_actions", "actions_in_progress"):
            with pytest.raises(StateTransitionError):
                validate_near_miss_transition("closed", target)

    def test_actions_in_progress_cannot_close_outright(self):
        """It could under the old near-miss map. Under the incident map it cannot."""
        with pytest.raises(StateTransitionError) as exc_info:
            validate_near_miss_transition("actions_in_progress", "closed")

        assert exc_info.value.details["allowed"] == ["pending_actions", "pending_review"]

    @pytest.mark.parametrize("legacy", ["REPORTED", "UNDER_REVIEW", "ACTION_REQUIRED", "IN_PROGRESS", "CLOSED"])
    def test_a_legacy_uppercase_label_is_refused_rather_than_coerced(self, legacy):
        """Casing is not normalised: the schema pattern refuses these at the boundary.

        A row that survives on an unmigrated database is readable and, if it is
        ``CLOSED``, still reads as closed — but it cannot be moved until it has
        been through ``20260910_nm_status_align``, which fails closed.
        """
        with pytest.raises(StateTransitionError):
            validate_near_miss_transition(legacy, "closed")

    def test_a_legacy_closed_row_is_still_recognised_as_closed(self):
        assert is_closed_status(CASE_TYPE_NEAR_MISS, "CLOSED") is True


# ---------------------------------------------------------------------------
# 20260910_nm_status_align
# ---------------------------------------------------------------------------


def _migration_value(name: str):
    """A module constant read out of the shipped migration source.

    Read rather than imported: the repository has its own ``alembic`` package
    directory, which shadows the installed one, so ``from alembic import op``
    cannot resolve from a test process. ``20260816``/``20260826`` established the
    same idiom, and it has the same payoff — the SQL exercised below is the
    string that will run against production, not a copy of it.
    """
    module = ast.parse(MIGRATION.read_text(encoding="utf-8"))
    for node in module.body:
        targets = (
            node.targets if isinstance(node, ast.Assign) else [node.target] if isinstance(node, ast.AnnAssign) else []
        )
        if any(isinstance(target, ast.Name) and target.id == name for target in targets):
            return ast.literal_eval(node.value)
    raise AssertionError(f"{name} not found in {MIGRATION}")


def _connection():
    engine = create_engine("sqlite://")
    connection = engine.connect()
    connection.exec_driver_sql("CREATE TABLE near_misses (id INTEGER PRIMARY KEY, status TEXT NOT NULL)")
    return connection


def _statuses(connection) -> dict[int, str]:
    return {row.id: row.status for row in connection.exec_driver_sql("SELECT id, status FROM near_misses")}


class TestTheMigrationRewritesExactlyWhatItClaims:
    def test_every_legacy_label_lands_on_its_incident_counterpart(self):
        sql = _migration_value("UPGRADE_REWRITE_SQL")

        with _connection() as connection:
            connection.exec_driver_sql(
                "INSERT INTO near_misses (id, status) VALUES "
                "(1, 'REPORTED'), (2, 'UNDER_REVIEW'), (3, 'ACTION_REQUIRED'), "
                "(4, 'IN_PROGRESS'), (5, 'CLOSED')"
            )
            connection.exec_driver_sql(sql)

            assert _statuses(connection) == {
                1: "reported",
                2: "under_investigation",
                3: "pending_actions",
                4: "actions_in_progress",
                5: "closed",
            }

    def test_a_second_run_moves_nothing(self):
        """Idempotent: 'closed' upper-cases back to a key that maps to itself."""
        sql = _migration_value("UPGRADE_REWRITE_SQL")

        with _connection() as connection:
            connection.exec_driver_sql(
                "INSERT INTO near_misses (id, status) VALUES "
                "(1, 'REPORTED'), (2, 'UNDER_REVIEW'), (3, 'ACTION_REQUIRED'), "
                "(4, 'IN_PROGRESS'), (5, 'CLOSED')"
            )
            connection.exec_driver_sql(sql)
            once = _statuses(connection)
            connection.exec_driver_sql(sql)

            assert _statuses(connection) == once

    def test_an_already_aligned_record_is_not_walked_backwards(self):
        """The dangerous re-run: 'actions_in_progress' must not become 'reported'.

        ``pending_actions`` and ``actions_in_progress`` upper-case to labels that
        are not on the left-hand side of the map, which is what makes the rewrite
        safe to re-run against a half-migrated database.
        """
        sql = _migration_value("UPGRADE_REWRITE_SQL")

        with _connection() as connection:
            connection.exec_driver_sql(
                "INSERT INTO near_misses (id, status) VALUES "
                "(1, 'pending_actions'), (2, 'actions_in_progress'), (3, 'pending_review'), "
                "(4, 'under_investigation')"
            )
            connection.exec_driver_sql(sql)

            assert _statuses(connection) == {
                1: "pending_actions",
                2: "actions_in_progress",
                3: "pending_review",
                4: "under_investigation",
            }

    def test_an_unrecognised_label_is_left_alone_for_the_guard_to_refuse(self):
        """The rewrite does not guess; ``_assert_every_status_is_known`` then raises."""
        sql = _migration_value("UPGRADE_REWRITE_SQL")

        with _connection() as connection:
            connection.exec_driver_sql("INSERT INTO near_misses (id, status) VALUES (1, 'AWAITING_TRIAGE')")
            connection.exec_driver_sql(sql)

            assert _statuses(connection) == {1: "AWAITING_TRIAGE"}

    def test_downgrade_restores_the_legacy_labels_and_collapses_pending_review(self):
        sql = _migration_value("DOWNGRADE_REWRITE_SQL")

        with _connection() as connection:
            connection.exec_driver_sql(
                "INSERT INTO near_misses (id, status) VALUES "
                "(1, 'reported'), (2, 'under_investigation'), (3, 'pending_actions'), "
                "(4, 'actions_in_progress'), (5, 'pending_review'), (6, 'closed')"
            )
            connection.exec_driver_sql(sql)

            assert _statuses(connection) == {
                1: "REPORTED",
                2: "UNDER_REVIEW",
                3: "ACTION_REQUIRED",
                4: "IN_PROGRESS",
                # The state the old register had no room for.
                5: "IN_PROGRESS",
                6: "CLOSED",
            }

    def test_downgrade_is_idempotent_too(self):
        sql = _migration_value("DOWNGRADE_REWRITE_SQL")

        with _connection() as connection:
            connection.exec_driver_sql(
                "INSERT INTO near_misses (id, status) VALUES "
                "(1, 'REPORTED'), (2, 'UNDER_REVIEW'), (3, 'ACTION_REQUIRED'), "
                "(4, 'IN_PROGRESS'), (5, 'CLOSED')"
            )
            connection.exec_driver_sql(sql)

            assert _statuses(connection) == {
                1: "REPORTED",
                2: "UNDER_REVIEW",
                3: "ACTION_REQUIRED",
                4: "IN_PROGRESS",
                5: "CLOSED",
            }

    def test_the_migration_follows_the_current_head(self):
        source = MIGRATION.read_text(encoding="utf-8")

        assert 'revision: str = "20260910_nm_status_align"' in source
        assert 'down_revision: Union[str, Sequence[str], None] = "20260908_soa_align"' in source
        assert len("20260910_nm_status_align") <= 32

    def test_the_constraint_the_migration_installs_matches_the_model(self):
        """The declared constraint and the deployed one must be the same set."""
        from src.domain.models.near_miss import NearMiss

        declared = next(
            constraint
            for constraint in NearMiss.__table__.constraints
            if getattr(constraint, "name", None) == "ck_near_misses_status"
        )
        sqltext = str(declared.sqltext)

        for status in _migration_value("ALIGNED_STATUSES"):
            assert f"'{status}'" in sqltext
        assert sqltext.count("'") == 2 * len(_migration_value("ALIGNED_STATUSES"))
