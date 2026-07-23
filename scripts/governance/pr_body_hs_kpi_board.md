# H&S KPI board

## Summary
- Introduces tenant-scoped reporting period inputs and workbook baseline defaults (2024: 95 FTE from 1 October; 2025: 105; 2026: 109).
- Provides H&S KPI summary and period administration endpoints, using LTIFR and AFR per 100,000 hours.

## Acceptance checks
- [x] Hours pro-rate inclusive reporting days against 365 days.
- [x] Injury, near-miss, RTA, complaint, LTI and RIDDOR metrics are counted by event date.
- [x] RTA indicators are included only when parity columns exist.
- [x] Response declares `rate_unit: per_100000_hours`.

## Test plan
- `pytest tests/unit/test_hs_kpi_service.py`
