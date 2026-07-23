from datetime import date

from src.domain.services.hs_kpi_service import RATE_UNIT, pro_rated_hours, rate_per_100000


def test_pro_rated_hours_uses_excel_style_inclusive_days():
    hours = pro_rated_hours(
        average_fte=95,
        hours_per_fte_year=2124,
        period_start=date(2024, 10, 1),
        period_end=date(2024, 12, 31),
    )
    assert round(hours, 2) == round(95 * 2124 * 92 / 365, 2)


def test_rates_use_locked_100000_hour_unit():
    assert rate_per_100000(count=2, hours=100000) == 2
    assert rate_per_100000(count=1, hours=0) == 0
    assert RATE_UNIT == "per_100000_hours"
