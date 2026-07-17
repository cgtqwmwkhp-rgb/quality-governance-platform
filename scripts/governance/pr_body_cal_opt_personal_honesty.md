# Change Ledger (CL-CAL-OPT-PERSONAL-HONESTY)

**Path claim:** `path11/cal-opt-personal-honesty`

## File allowlist (exclusive)

- `frontend/src/pages/CalendarView.tsx`
- `frontend/src/pages/calendarPersonalHonesty.ts`
- `frontend/src/pages/__tests__/calendarPersonalHonesty.test.ts`
- `frontend/src/pages/__tests__/CalendarView.test.tsx`
- `frontend/src/i18n/locales/en.json`
- `frontend/src/i18n/locales/cy.json`
- `scripts/governance/pr_body_cal_opt_personal_honesty.md`

**Zero overlap** with parallel lanes: MAP-W2 builders*, PlanetMark*, AuditExecution* (#1076), Portal* (#1077), Complaint* (#1078). Soft i18n only. Skipped MAP-W3 (would collide with MAP-W2 builder files). Not full Option C.

## 1) Summary

- **Feature / Change name:** Path11 CAL personal-product honesty shell
- **User goal:** On Insights Calendar, operators see that the governance feed + Audits/Actions create paths are live, while personal events, ICS sync, and rooms remain awaiting (Option C follow-on).
- **In scope:** CalendarView honesty banner + capability chips; helper; vitest; i18n
- **Out of scope:** Full Option C personal calendar product; ICS backend; rooms; workforce Calendar.tsx; Layout/App/client.ts; Alembic
- **Feature flag / kill switch:** N/A — revert commit

## 2) Impact Map (what changed)

| Surface | Before | After |
|---------|--------|-------|
| Calendar header | Subtitle only | Personal-product honesty banner + live/awaiting chips |
| Add Event menu | Audits / Actions chooser | Unchanged; honesty clarifies it is source-module create, not personal events |

## 3) Compatibility & Data Safety

- **Compatibility strategy:** FE-only honesty; no API/Alembic
- **Breaking changes:** None
- **Rollback strategy:** Revert squash merge

## 4) Acceptance Criteria (AC)

- [x] AC-01: Calendar shows personal honesty banner under title/subtitle
- [x] AC-02: Capability chips mark governance feed + source create live
- [x] AC-03: Personal events / ICS / rooms marked awaiting
- [x] AC-04: Option C follow-on copy present; no faux personal event editor
- [x] AC-05: Vitest covers helper + CalendarView honesty panel
- [x] AC-06: en + cy flat keys (≥95% cy for new keys)

## 5) Testing Evidence

- [x] Vitest — calendarPersonalHonesty + CalendarView personal honesty
- [ ] CI green — this PR

## 6) Critical Journeys Verified (CUJ)

- [x] CUJ-01: Insights → Calendar → personal honesty banner visible
- [x] CUJ-02: Add Event still routes to Audits/Actions (source create), not personal editor

## 7) Observability & Ops

- **Playwright hooks:** `calendar-personal-honesty`, `calendar-personal-honesty-copy`, `calendar-personal-capability-chips`, `calendar-personal-cap-*`
- **Logs:** No change
- **Metrics:** No change
- **Alerts:** No change

## 8) Release Plan

1. Draft PR → CI green
2. Squash-merge after review (human — **do not merge from this lane**)
3. Staging smoke: `/calendar` personal honesty banner

## 9) Rollback Plan

1. Revert squash commit on `main`
2. Redeploy previous SHA
- **Rollback trigger:** Calendar honesty regression post-deploy
- **Rollback steps:** Revert squash commit; redeploy previous SHA
- **Owner:** Platform team

## 10) Evidence Pack (links)

- PR diff + vitest proofs in this branch
- Living tracker note: CAL personal honesty (Option C deferred)

## 11) Gate Checklist

- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** Exclusive Calendar* allowlist respected
- [x] **Gate 2:** Local vitest green
- [ ] **Gate 3:** Required CI green on PR
- [ ] **Gate 4:** Squash-merge to main (serial tip LIVE)
- [ ] **Gate 5:** Staging smoke Calendar personal honesty

## Test plan

- [x] `cd frontend && npx vitest run src/pages/__tests__/calendarPersonalHonesty.test.ts src/pages/__tests__/CalendarView.test.tsx`
- [ ] Manual: `/calendar` — honesty banner + capability chips
