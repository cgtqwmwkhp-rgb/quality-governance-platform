# H&S RTA parity

## Summary
- Adds collision classification, drivability, lost-time and RIDDOR fields to RTAs.
- Exposes those fields through RTA API schemas and client contracts; KPI aggregation picks them up after migration.

## Test plan
- `pytest tests/unit/test_hs_rta_normalization.py`
