"""Exceptions inbox page window — peek one extra row, never raise the 200 cap."""

from src.api.routes.governed_knowledge import split_inbox_page


def test_split_inbox_page_full_window_has_next():
    rows = list(range(201))
    page, has_next = split_inbox_page(rows, 200)
    assert page == list(range(200))
    assert has_next is True


def test_split_inbox_page_short_window_is_last():
    rows = list(range(3))
    page, has_next = split_inbox_page(rows, 200)
    assert page == [0, 1, 2]
    assert has_next is False


def test_split_inbox_page_empty():
    page, has_next = split_inbox_page([], 200)
    assert page == []
    assert has_next is False
