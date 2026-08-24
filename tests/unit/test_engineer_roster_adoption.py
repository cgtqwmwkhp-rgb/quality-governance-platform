"""Which roster row a new login adopts, when the display name does not identify one.

``ensure_engineer_for_user_*`` adopts an unlinked roster row whose display name matches
the new user. Display names are not unique, and the query took ``LIMIT 1`` with no
ordering, so two same-named employees meant the database picked one arbitrarily and the
new account silently inherited a stranger's competency and assignment history.

The match also ignored ``is_active``, so a login could be attached to a retired roster
row and then be unassignable — the exact shape of a real production lockout, where a
user held a supervisor role but could not be given an action.
"""

import types

from src.domain.services.engineer_user_link_service import _adoptable_roster_row


def _row(engineer_id, *, is_active=True):
    return types.SimpleNamespace(id=engineer_id, is_active=is_active)


def _user():
    return types.SimpleNamespace(id=7, first_name="John", last_name="Smith", email="j.smith@example.com")


def test_no_candidates_means_create_a_fresh_record():
    assert _adoptable_roster_row([], _user(), "John Smith") is None


def test_a_single_active_match_is_adopted():
    row = _row(41)
    assert _adoptable_roster_row([row], _user(), "John Smith") is row


def test_two_equally_active_matches_are_refused():
    """AC-01: adopting either would attach the login to a stranger's record."""
    assert _adoptable_roster_row([_row(41), _row(42)], _user(), "John Smith") is None


def test_an_active_match_outranks_a_retired_one():
    """AC-02: this is not ambiguity — one of the two is plainly the live employee.

    Candidates arrive ordered ``is_active DESC, id ASC``, so the active row is first.
    """
    active = _row(41, is_active=True)
    retired = _row(9, is_active=False)
    assert _adoptable_roster_row([active, retired], _user(), "John Smith") is active


def test_two_equally_retired_matches_are_refused():
    """AC-03: the tie, not the activity level, is what makes the choice arbitrary."""
    assert _adoptable_roster_row([_row(9, is_active=False), _row(10, is_active=False)], _user(), "X") is None


def test_a_lone_retired_match_is_still_adopted(caplog):
    """AC-04: it is the right person; only the upstream roster can reactivate them.

    Creating a duplicate active record instead would fork the employee's history, so
    adopt it — but say so, because the login cannot be assigned work until it is active.
    """
    retired = _row(9, is_active=False)
    with caplog.at_level("WARNING"):
        assert _adoptable_roster_row([retired], _user(), "John Smith") is retired
    assert "not_assignable_until_reactivated" in caplog.text


def test_refusal_is_logged_with_the_candidates(caplog):
    """AC-05: a silent refusal leaves nobody able to explain the duplicate person."""
    with caplog.at_level("WARNING"):
        _adoptable_roster_row([_row(41), _row(42)], _user(), "John Smith")
    assert "engineer_user_link_ambiguous" in caplog.text
    assert "[41, 42]" in caplog.text
