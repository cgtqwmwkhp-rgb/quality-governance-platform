"""Unit tests for the shared honest-percentage helpers (PX-216).

The whole point of :mod:`src.domain.metrics` is that an empty measurement is
distinguishable from a perfect one, so the zero-denominator cases carry the most
weight here.
"""

import pytest

from src.domain.metrics import compliance_percentage_or_none, percentage_or_none


class TestPercentageOrNone:
    def test_zero_denominator_is_none_not_zero_and_not_one_hundred(self):
        result = percentage_or_none(0, 0)
        assert result is None
        assert result != 0
        assert result != 100

    def test_zero_denominator_with_nonzero_numerator_is_still_none(self):
        # Nonsensical input, but it must not be dressed up as a percentage.
        assert percentage_or_none(5, 0) is None

    def test_missing_denominator_is_none(self):
        assert percentage_or_none(3, None) is None

    def test_negative_denominator_is_none(self):
        assert percentage_or_none(3, -10) is None

    def test_partial(self):
        assert percentage_or_none(1, 4) == 25.0
        assert percentage_or_none(1, 3) == 33.33

    def test_full(self):
        assert percentage_or_none(7, 7) == 100.0

    def test_empty_numerator_over_real_population_is_a_genuine_zero(self):
        assert percentage_or_none(0, 12) == 0.0
        assert percentage_or_none(None, 12) == 0.0

    def test_digits_controls_rounding(self):
        assert percentage_or_none(1, 3, digits=4) == 33.3333
        assert percentage_or_none(1, 3, digits=0) == 33.0
        assert percentage_or_none(1, 3, digits=None) == pytest.approx(100 / 3)

    def test_result_is_not_clamped_so_counting_bugs_stay_visible(self):
        assert percentage_or_none(3, 2) == 150.0

    def test_accepts_floats(self):
        assert percentage_or_none(0.5, 2.0) == 25.0


class TestCompliancePercentageOrNone:
    def test_zero_failures_out_of_zero_checks_is_not_compliant(self):
        result = compliance_percentage_or_none(0, 0)
        assert result is None
        assert result != 100

    def test_missing_total_is_none(self):
        assert compliance_percentage_or_none(0, None) is None

    def test_zero_failures_out_of_real_checks_is_full_compliance(self):
        assert compliance_percentage_or_none(0, 20) == 100.0
        assert compliance_percentage_or_none(None, 20) == 100.0

    def test_partial(self):
        assert compliance_percentage_or_none(1, 4) == 75.0

    def test_all_failing(self):
        assert compliance_percentage_or_none(9, 9) == 0.0

    def test_digits_controls_rounding(self):
        assert compliance_percentage_or_none(1, 3, digits=1) == 66.7
