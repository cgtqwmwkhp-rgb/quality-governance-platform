"""Property-based tests using Hypothesis for invariants on refs, enums, pagination, and dates."""

from __future__ import annotations

import re
from datetime import date

from hypothesis import assume, given, strategies as st

from src.api.utils.pagination import PaginationParams
from src.domain.models.incident import ActionStatus


REF_PATTERN = re.compile(r"^[A-Z0-9]+-\d{8}-\d{6}$")


@given(
    prefix=st.text(alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ", min_size=2, max_size=8),
    ymd=st.dates(min_value=date(2000, 1, 1), max_value=date(2100, 12, 31)).map(lambda d: d.strftime("%Y%m%d")),
    seq=st.integers(min_value=0, max_value=999_999),
)
def test_reference_number_format_length_and_pattern(prefix: str, ymd: str, seq: int) -> None:
    """Strings built as PREFIX-YYYYMMDD-NNNNNN are valid refs with predictable length."""
    ref = f"{prefix}-{ymd}-{seq:06d}"
    assert isinstance(ref, str)
    expected_len = len(prefix) + 1 + 8 + 1 + 6
    assert len(ref) == expected_len
    assert REF_PATTERN.match(ref) is not None


@given(st.sampled_from(list(ActionStatus)))
def test_action_status_enum_values_are_lowercase_strings(status: ActionStatus) -> None:
    """ActionStatus values remain lowercase string enums."""
    assert isinstance(status.value, str)
    assert status.value == status.value.lower()


@given(
    page=st.integers(min_value=1, max_value=10_000),
    page_size=st.integers(min_value=1, max_value=500),
)
def test_pagination_params_within_bounds(page: int, page_size: int) -> None:
    """page >= 1 and page_size in [1, 500] yield consistent PaginationParams / offset."""
    params = PaginationParams(page=page, page_size=page_size)
    assert params.page == page
    assert params.page_size == page_size
    assert params.offset == (page - 1) * page_size


@given(
    start_date=st.dates(min_value=date(1990, 1, 1), max_value=date(2100, 12, 31)),
    end_date=st.dates(min_value=date(1990, 1, 1), max_value=date(2100, 12, 31)),
)
def test_date_range_non_negative_duration(start_date: date, end_date: date) -> None:
    """When start_date <= end_date, the calendar span is never negative."""
    assume(start_date <= end_date)
    assert (end_date - start_date).days >= 0
