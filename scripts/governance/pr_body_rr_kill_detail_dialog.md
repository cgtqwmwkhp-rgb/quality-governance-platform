# Change Ledger (CL-RR-KILL-DETAIL-DIALOG)

## 1) Summary
- **Feature / Change name:** RR-KILL-POPUP — Remove Risk Register detail Dialog; profile is sole view/edit surface
- **User goal (1–2 lines):** Clicking a risk on the register (row, reference, Open, Edit, owner) opens the full Risk Profile page — never the legacy popup.
- **In scope:** Remove view/edit `risk-detail-dialog`; row/keyboard/owner/edit → `/risk-register/:id`; `?riskId=` redirects to profile; create dialog retained (then navigate to new profile); Vitest; this ledger
- **Out of scope:** RiskProfile feature work (assess/notes/CAPA), heat-map rail, Alembic, App.tsx, Layout.tsx, Admin, Planet Mark
- **Feature flag / kill switch:** N/A — removes obsolete UI path

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** `RiskRegister.tsx` — kill view/edit Dialog; create-only dialog; navigate helpers; bow-tie honesty without selectedRisk stub
- **Backend (handlers/services):** None
- **APIs (endpoints changed/added):** None
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** None
- **Database (migrations/entities/indexes):** None
- **Workflows/jobs/queues (if any):** None
- **Config/env/flags:** None
- **Dependencies (added/removed/updated):** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive navigation to existing `/risk-register/:id` (RR-P0). Import triage Accept/Reject dialogs unchanged.
- **Tolerant reader / strict writer applied?** N/A FE-only
- **Breaking changes:** View/edit popup removed (intentional product change)
- **Migration plan:** N/A
- **Rollback strategy (DB):** N/A — revert PR only

## 4) Acceptance Criteria (AC)
- [x] AC-01: No `risk-detail-dialog` for view/edit on register list
- [x] AC-02: Row click / Enter / Open / Edit / owner → `/risk-register/:id`
- [x] AC-03: Legacy `?riskId=` on list redirects to profile (`replace`)
- [x] AC-04: Create risk dialog retained; success navigates to new profile when id returned
- [x] AC-05: Import reject + Excel import dialogs unchanged
- [x] AC-06: Vitest covers row/Open/edit → profile and asserts detail dialog absent

## 5) Testing Evidence (link to runs)
- [ ] Lint — CI after open
- [ ] Typecheck — CI after open
- [ ] Build — CI after open
- [x] Frontend Vitest — `RiskRegister.test.tsx` (10 passed, local)
- [ ] Integration / E2E — CI

## 6) Critical Journeys Verified (CUJ)
- [x] **CUJ-01 (RR):** Register row or reference → Risk Profile page (no popup)
- [x] **CUJ-02 (RR):** Open / Edit / owner controls → same profile route
- [x] **CUJ-03 (RR):** Add Risk create dialog still works; triage reject dialog intact

## 7) Observability & Ops
- **Logs:** No change
- **Metrics:** No change
- **Alerts:** No change
- **Runbook updates:** N/A

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Click RSK row on register — lands on profile; Confirm no Close/Edit popup
- **Canary plan:** N/A
- **Prod post-deploy checks:** Hard-refresh SWA; click one risk reference

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Profile navigation broken / create risk broken
- **Rollback steps:** Revert PR
- **Owner:** Platform / Risk Register track

## 10) Evidence Pack (links)
- CI run(s): Linked after PR creation
- Staging deploy evidence: N/A (draft)
- Canary evidence (if applicable): N/A

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** Popup removed; profile navigation wired
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete (evidence linked)
- [ ] **Gate 4:** Rollback plan verified
- [ ] **Gate 5:** Evidence pack linked / LIVE honesty noted

## Exclusive allowlist (this PR)
- `frontend/src/pages/RiskRegister.tsx`
- `frontend/src/pages/__tests__/RiskRegister.test.tsx`
- `scripts/governance/pr_body_rr_kill_detail_dialog.md`

**Forbidden / not touched:** App.tsx, Layout.tsx, RiskProfile.tsx, Alembic, client.ts, Admin, Planet Mark.
