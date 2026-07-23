# H&S RIDDOR staff workflow

## Summary
- Adds incident edit controls for reportability, classification and rationale, with eligibility checking and honest draft-pack preparation.
- Enriches draft packs from the existing incident injury spine (body parts, days lost, LTI and response signals).

## Acceptance checks
- [x] RIDDOR status supports Yes, No and Unset.
- [x] Check maps incident injury signals to the existing eligibility endpoint.
- [x] Prepare only creates a local draft; it does not represent filing with HSE.
- [x] Draft data carries body part and lost-time information.

## Test plan
- `pytest tests/unit/test_riddor_prepare_honesty.py`
- Frontend typecheck/lint for `IncidentDetail.tsx`
