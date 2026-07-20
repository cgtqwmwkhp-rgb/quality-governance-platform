# Change Ledger (CL-PX-056-H2)

## 1) Summary
- **Feature / Change name:** PX-056 H2 — bulk/guided engineer↔user link UX
- **User goal:** Workforce managers can multi-select unlinked employees and link each to a QGP user via the existing link-user API.
- **In scope:** Engineers roster multi-select + guided link dialog; Vitest; uses POST /engineers/{id}/link-user only.
- **Out of scope:** Campaign audience by engineer_ids (H3); PATCH user_id; disposal flags.
- **Feature flag / kill switch:** None. Revert PR to restore prior UI.

## 2) Impact Map
| ID | Surface | Before | After |
|---|---|---|---|
| PX-056 H2 | Workforce → Employees | One-by-one link only / weak bulk path | Multi-select guided link dialog |

- **Frontend:** `Engineers.tsx`, `Engineers.test.tsx`

## 3) Compatibility & Data Safety
- UI-only; backend dual-gate unchanged (`engineer:update` + workforce manager).
- No PATCH of user_id; sequential link-user calls.

## 4) Acceptance Criteria
- [x] AC-01: Manager can multi-select unlinked employees for linking.
- [x] AC-02: Each selected employee requires an explicit user choice before submit.
- [x] AC-03: Links call POST link-user only (no PATCH user_id).
- [x] AC-04: Vitest covers the guided-link entry point.

## 5) Testing Evidence
- [x] `npx vitest run src/pages/workforce/__tests__/Engineers.test.tsx`
- [x] `npx tsc --noEmit`

## 6) Critical Journeys
- [x] CUJ-01: Manager selects multiple unlinked employees and links each to a user.
- [x] CUJ-02: Non-manager cannot use bulk link controls (existing dual-gate).

## 7) Observability & Ops
- No new telemetry. Failures surface per-employee in the dialog.

## 8) Release Plan
1. Merge after CI green (prefer after H1 #1206).
2. Deploy SWA via standard conveyor.
3. Spot-check Employees bulk link on staging.

## 9) Rollback Plan
- **Trigger:** Roster link UX regression.
- **Steps:** Revert merge; redeploy prior SWA.
- **Owner:** Platform release operator.

## 10) Evidence Pack
- `frontend/src/pages/workforce/__tests__/Engineers.test.tsx`
- This ledger.

---

## Gate Checklist
- [x] Gate 0: H2 scope only.
- [x] Gate 1: FE-only guided link.
- [x] Gate 2: Vitest + tsc.
- [ ] Gate 3: Hosted CI pending.
- [x] Gate 4: No destructive ops.
- [x] Gate 5: Rollback documented.
