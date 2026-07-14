# Change Ledger (CL-WF-CAL)

## 1) Summary
- **Feature / Change name:** WF-CAL — operational calendar week/list views + fetch honesty
- **User goal (1–2 lines):** Supervisors can scan the workforce calendar in month, week, or list/agenda views with colour by type/status, click-through to execute, and honest truncation / engineer-map failure signals (no silent swallow).
- **In scope:** `Calendar.tsx` week + list views; type/status colouring; execute-route click-through; truncation banner when `total > page_size`; engineer-map load failure / truncation warning; unit + mocked Playwright smoke
- **Out of scope:** Drag-create / drag-reschedule (WF1); `workforceClient.ts`; Layout/nav; other workforce pages; backend
- **Feature flag / kill switch:** N/A — FE calendar UX only

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** `/workforce/calendar` — month (existing) + week + list/agenda; honesty banners
- **Backend (handlers/services):** None
- **APIs (endpoints changed/added):** None — still uses `listAssessments` / `listInductions` / `listEngineers` at page_size 500
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** None
- **Database (migrations/entities/indexes):** None
- **Workflows/jobs/queues (if any):** None
- **Config/env/flags:** None
- **Dependencies (added/removed/updated):** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive UI views; month grid behaviour preserved; fetch still page 1 / size 500 with honesty when truncated
- **Tolerant reader / strict writer applied?** Yes — truncation uses `total` when present, else full-page fallback
- **Breaking changes:** None
- **Migration plan:** N/A
- **Rollback strategy (DB):** N/A — revert PR only

## 4) Acceptance Criteria (AC)
- [x] AC-01: Week + list/agenda views available in addition to month on Calendar
- [x] AC-02: Events coloured by type/status; click-through to assessment/induction execute routes
- [x] AC-03: Truncation surfaced when `total > page_size`; engineer-map failures are not silently swallowed
- [x] AC-04: Unit tests + mocked Playwright smoke (`workforce-calendar.spec.ts`); exclusive allowlist only

## 5) Testing Evidence (link to runs)
- [ ] Lint — CI after open
- [ ] Typecheck — CI after open
- [ ] Build — CI after open
- [x] Unit tests — `frontend` vitest `src/pages/workforce/__tests__/Calendar.test.tsx` (local)
- [ ] Integration tests — N/A
- [ ] Contract tests (if applicable) — N/A
- [x] E2E Smoke — `frontend/tests/e2e/workforce-calendar.spec.ts` (mocked; run in CI / local with FE up)

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Switch Month → Week → List and see scheduled assessment/induction chips
- [x] CUJ-02: Click event → navigate to `/workforce/assessments/:id/execute` or training execute
- [x] CUJ-03: When assessments `total > 500`, truncation notice is visible
- [x] CUJ-04: When engineers list fails, warning banner shown and events still render with `#id` fallback

## 7) Observability & Ops
- **Logs:** `trackError` on calendar load + engineer list failures (existing tracker)
- **Metrics:** No change
- **Alerts:** No change
- **Runbook updates:** N/A

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Open `/workforce/calendar`, exercise view toggles, confirm click-through and honesty banners with seeded / truncated fixtures if available
- **Canary plan:** N/A
- **Prod post-deploy checks:** Calendar loads; no console-only failures for engineer map

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Calendar regressions blocking supervisor schedule scan
- **Rollback steps:** Revert PR
- **Owner:** Platform / Workforce track

## 10) Evidence Pack (links)
- CI run(s): Linked after PR creation
- Staging deploy evidence: Draft — FE calendar UX
- Canary evidence (if applicable): N/A

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** FE calendar views + honesty (no backend / client / Layout)
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete (evidence linked)
- [ ] **Gate 4:** Rollback plan verified
- [ ] **Gate 5:** Evidence pack linked / LIVE honesty noted

## Exclusive allowlist (this PR)
- `frontend/src/pages/workforce/Calendar.tsx`
- `frontend/src/pages/workforce/__tests__/Calendar.test.tsx` (supersedes former `Calendar.test.ts`)
- `frontend/tests/e2e/workforce-calendar.spec.ts`
- `scripts/governance/pr_body_wf_cal.md`

**Zero overlap with Asset Management lanes.** No `workforceClient.ts`, Layout, other workforce pages, or backend.
