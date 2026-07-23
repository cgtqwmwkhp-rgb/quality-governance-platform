from datetime import date
from types import SimpleNamespace

from src.domain.services.hs_kpi_service import (
    RATE_UNIT,
    effective_hours,
    pro_rated_hours,
    rate_per_100000,
)


def test_pro_rated_hours_uses_excel_style_inclusive_days():
    hours = pro_rated_hours(
        average_fte=95,
        hours_per_fte_year=2124,
        period_start=date(2024, 10, 1),
        period_end=date(2024, 12, 31),
    )
    assert round(hours, 2) == round(95 * 2124 * 92 / 365, 2)


def test_effective_hours_prefers_manual_admin_entry():
    period = SimpleNamespace(
        manual_hours=50859.62,
        average_fte=95,
        hours_per_fte_year=2124,
        period_start=date(2024, 10, 1),
        period_end=date(2024, 12, 31),
    )
    assert effective_hours(period) == 50859.62


def test_effective_hours_falls_back_to_fte_pro_rata():
    period = SimpleNamespace(
        manual_hours=None,
        average_fte=105,
        hours_per_fte_year=2124,
        period_start=date(2025, 1, 1),
        period_end=date(2025, 12, 31),
    )
    assert effective_hours(period) == 105 * 2124


def test_rates_use_locked_100000_hour_unit():
    assert rate_per_100000(count=2, hours=100000) == 2
    assert rate_per_100000(count=1, hours=0) == 0
    assert RATE_UNIT == "per_100000_hours"
