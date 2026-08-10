"""Attribution and ordering for the "needs my decision" read model.

The database-backed half lives in
``tests/integration/test_approvals_my_decisions.py``. What is pinned here is the
part that decides *whose* decision a row is, because it reads free-form JSON that
no constraint validates, and a wrong answer is not a crash — it is a decision
appearing in the wrong person's queue or in nobody's.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from src.domain.services.approvals_read_model import (
    MyDecisions,
    PendingDecision,
    SourceReading,
    _sort_key,
    approvers_for_step,
)


def _decision(key: str, *, due: datetime | None = None, requested: datetime | None = None) -> PendingDecision:
    return PendingDecision(
        key=key,
        source="document_approval",
        source_label="Document control approvals",
        decision="approve",
        title=f"Document {key}",
        reference=key.upper(),
        requested_at=requested,
        requested_at_basis="submitted" if requested else None,
        due_at=due,
        deep_link=None,
    )


class TestWhoMayDecideAStep:
    """``workflow_steps`` is JSON the database does not validate, so every read is defensive."""

    def test_the_named_approvers_of_the_current_step_are_returned(self):
        steps = [{"level": 1, "approvers": [7, 9]}, {"level": 2, "approvers": [4]}]

        assert approvers_for_step(steps, 1) == (frozenset({7, 9}), True)

    def test_step_number_is_one_based_to_match_current_step(self):
        """``DocumentApprovalInstance.current_step`` starts at 1, not 0.

        An off-by-one here would show every approver the step above or below
        theirs, which is not a visible failure — it is a plausible-looking queue.
        """
        steps = [{"approvers": [1]}, {"approvers": [2]}]

        assert approvers_for_step(steps, 1)[0] == frozenset({1})
        assert approvers_for_step(steps, 2)[0] == frozenset({2})

    def test_ids_written_as_strings_are_accepted(self):
        """Ids arrive as ints from the API and as strings from hand-written JSON."""
        assert approvers_for_step([{"approvers": ["7", 9]}], 1) == (frozenset({7, 9}), True)

    def test_a_step_naming_only_a_role_is_unattributable_not_empty(self):
        """A role is not a user, and this read model does not expand roles.

        Returning ``(frozenset(), True)`` would say "read successfully, and it is
        not yours", which for a step that names nobody is exactly the claim that
        must not be made: it is outstanding for someone, and nothing here knows
        who.
        """
        approvers, attributable = approvers_for_step([{"level": 1, "role": "reviewer"}], 1)

        assert approvers == frozenset()
        assert attributable is False

    def test_an_empty_approver_list_is_unattributable(self):
        assert approvers_for_step([{"approvers": []}], 1) == (frozenset(), False)

    def test_approvers_that_are_not_ids_at_all_are_unattributable(self):
        approvers, attributable = approvers_for_step([{"approvers": ["quality-manager", None]}], 1)

        assert approvers == frozenset()
        assert attributable is False

    def test_a_usable_id_beside_an_unusable_one_still_attributes(self):
        """One malformed entry must not hide the approver sitting next to it."""
        assert approvers_for_step([{"approvers": [5, "quality-manager"]}], 1) == (frozenset({5}), True)

    def test_booleans_are_not_user_ids(self):
        """``True`` is an ``int`` in Python, and user 1 is a real user."""
        assert approvers_for_step([{"approvers": [True]}], 1) == (frozenset(), False)

    def test_a_current_step_past_the_end_of_the_workflow_is_unattributable(self):
        assert approvers_for_step([{"approvers": [1]}], 2) == (frozenset(), False)

    def test_a_current_step_below_one_is_unattributable(self):
        assert approvers_for_step([{"approvers": [1]}], 0) == (frozenset(), False)

    def test_steps_that_are_not_a_list_are_unattributable(self):
        for steps in (None, {}, 3, "1,2"):
            assert approvers_for_step(steps, 1) == (frozenset(), False), steps

    def test_a_step_that_is_not_an_object_is_unattributable(self):
        assert approvers_for_step(["reviewer"], 1) == (frozenset(), False)


class TestOrdering:
    def test_the_soonest_deadline_comes_first(self):
        soon = _decision("a", due=datetime(2026, 1, 2))
        later = _decision("b", due=datetime(2026, 3, 4))

        assert sorted([later, soon], key=_sort_key) == [soon, later]

    def test_undated_decisions_sort_after_dated_ones(self):
        """A decision with no deadline is not urgent.

        Sorting undated first would push real deadlines off the bottom of a short
        panel, which is the one thing this surface exists to prevent.
        """
        dated = _decision("a", due=datetime(2099, 12, 31))
        undated = _decision("b", requested=datetime(2026, 1, 1))

        assert sorted([undated, dated], key=_sort_key) == [dated, undated]

    def test_undated_decisions_are_newest_request_first(self):
        older = _decision("a", requested=datetime(2026, 1, 1))
        newer = _decision("b", requested=datetime(2026, 6, 1))

        assert sorted([older, newer], key=_sort_key) == [newer, older]

    def test_ordering_is_stable_when_nothing_distinguishes_two_rows(self):
        first = _decision("a")
        second = _decision("b")

        assert sorted([second, first], key=_sort_key) == [first, second]


class TestWhatTheAggregateClaims:
    def test_an_unread_source_makes_the_reading_incomplete(self):
        decisions = MyDecisions(
            items=(),
            sources=(
                SourceReading(key="document_approval", label="Document", status="unavailable", count=None),
                SourceReading(key="signature_request", label="Signatures", status="live", count=0),
            ),
        )

        assert decisions.total == 0
        assert decisions.sources_complete is False
        assert decisions.unavailable_sources == ("document_approval",)

    def test_zero_is_a_measurement_only_when_every_source_answered(self):
        decisions = MyDecisions(
            items=(),
            sources=(
                SourceReading(key="document_approval", label="Document", status="live", count=0),
                SourceReading(key="signature_request", label="Signatures", status="live", count=0),
            ),
        )

        assert decisions.sources_complete is True
        assert decisions.unavailable_sources == ()

    def test_a_truncated_source_is_still_a_complete_reading(self):
        """Truncation is a cap on a list that was read, not a failure to read it.

        Conflating the two would put a source that answered into
        ``unavailable_sources``, where an operator would go looking for an outage
        that is not there.
        """
        decisions = MyDecisions(
            items=(),
            sources=(
                SourceReading(
                    key="signature_request",
                    label="Signatures",
                    status="live",
                    count=50,
                    truncated=True,
                ),
            ),
        )

        assert decisions.sources_complete is True
        assert decisions.unavailable_sources == ()

    def test_total_counts_the_items_actually_returned(self):
        decisions = MyDecisions(
            items=(
                _decision("a", due=datetime(2026, 1, 1)),
                _decision("b", due=datetime(2026, 1, 1) + timedelta(days=1)),
            ),
            sources=(SourceReading(key="document_approval", label="Document", status="live", count=2),),
        )

        assert decisions.total == 2
