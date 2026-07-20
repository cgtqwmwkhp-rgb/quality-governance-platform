# Change Ledger (CL-PX-056-H2)

## Scope
- Workforce Employees roster: managers can select multiple unlinked employees and use a guided per-employee QGP-user linking dialog.
- The UI calls only the existing `POST /api/v1/engineers/{id}/link-user` endpoint; it never PATCHes `user_id`.
- Vitest coverage for the multi-select guided-link entry point.

## Controls
- [x] Existing API dual gate remains authoritative: `engineer:update` permission and workforce-manager facet.
- [x] Each selected employee must receive an explicitly chosen QGP user before submission.
- [x] The existing backend uniqueness, active-user, and tenant-scope validation remains in force.
- [x] Links are sent sequentially so a failure is reported without fabricating a bulk-success result.

## Verification
- [x] `npx vitest run src/pages/workforce/__tests__/Engineers.test.tsx`
- [x] `npx tsc --noEmit`
- [x] `pytest -q tests/unit/test_engineer_user_link_and_override.py tests/unit/test_engineer_identity_controls.py`
