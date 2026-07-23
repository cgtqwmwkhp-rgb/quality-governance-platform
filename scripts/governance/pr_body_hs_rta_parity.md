# H&S RTA parity

## Summary
- Adds collision classification, drivability, lost-time and RIDDOR fields to RTAs.
- Exposes those fields through RTA API schemas and client contracts; KPI aggregation picks them up after migration.

## Test plan
- `pytest tests/unit/test_hs_rta_normalization.py`

## Change ledger
- **Data:** adds nullable collision/drivability/RIDDOR data and non-null lost-time indicator to RTAs.
- **UI:** RTADetail view and edit now expose the parity fields.
- **KPI impact:** H&S KPI service includes RTA LTI/RIDDOR values after the RTA parity migration.
- **Roll-back:** remove the UI fields and downgrade `20260810_hs_rta_parity`; no records are deleted.
