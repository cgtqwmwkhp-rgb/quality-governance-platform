# Change Ledger (CL-UAT-C2B-FE)

## 1) Summary
- **Feature / Change name:** Wave C2b — FE UX hygiene (PX-004 partial, PX-008, PX-011, PX-017)
- **User goal (1–2 lines):** Close high-impact UAT polish gaps: keyboard-open incidents, honest Export Center, paginated incidents register, and no silent discard on complaint create.
- **In scope:** `Incidents.tsx` pagination + a11y + search honesty; `ExportCenter.tsx` honest unavailable shell; `Complaints.tsx` dirty-modal confirm; Vitest proofs; this Change Ledger
- **Out of scope:** PX-003 (merged #1196); PX-056 employee↔user linking; full server-side incidents search; live export job APIs; PX-015 reporter BE default
- **Feature flag / kill switch:** N/A — FE-only honesty/a11y

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):**
  - `frontend/src/pages/Incidents.tsx` — list pagination footer (Showing X–Y of Z); keyboard row open; search page-scope honesty; improved no-match empty copy
  - `frontend/src/pages/ExportCenter.tsx` — replace fabricated mock counts/history with AI Hub-style “not available yet” card
  - `frontend/src/pages/Complaints.tsx` — confirm before closing dirty New Complaint modal (Escape / cancel / overlay)
  - Vitest: `Incidents.test.tsx`, `ExportCenter.test.tsx`, `Complaints.test.tsx`
- **Backend (handlers/services):** None
- **APIs (endpoints changed/added):** None
- **Schemas/contracts:** None
- **Database:** None
- **Workflows/jobs/queues:** None
- **Config/env/flags:** None
- **Dependencies:** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive UX honesty + a11y; no persistence change
- **Tolerant reader / strict writer applied?** N/A
- **Breaking changes:** None — Export Center loses demo theatre (intentional)
- **Migration plan:** N/A
- **Rollback strategy (DB):** N/A — revert PR

## 4) Acceptance Criteria (AC)
- [x] AC-01: Incidents table rows are focusable; Enter/Space opens detail (PX-008)
- [x] AC-02: Incidents list shows Previous/Next + “Showing X–Y of Z” when `pages > 1` (PX-004 partial)
- [x] AC-03: Active search shows page-scope honesty (does not imply full-register search) (PX-004 partial)
- [x] AC-04: Export Center shows honest unavailable state — no fabricated counts or Jan-2024 demo history (PX-011)
- [x] AC-05: Dirty New Complaint modal prompts before discard on Escape/cancel (PX-017)
- [x] AC-06: Vitest covers keyboard open, pagination banner, export honesty, dirty-modal confirm

## 5) Testing Evidence (link to runs)
- [ ] Lint — CI after open
- [ ] Typecheck — CI after open
- [ ] Build — CI after open
- [x] Unit tests — `frontend` vitest Incidents / ExportCenter / Complaints (local)
- [ ] Integration tests — N/A
- [ ] Contract tests — N/A
- [ ] E2E Smoke — N/A (FE hygiene lane)

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Safety & Cases → Incidents — keyboard user tabs to row, Enter opens case file (PX-008)
- [x] CUJ-02: Incidents register beyond 50 — pagination controls reach older records (PX-004 partial)
- [x] CUJ-03: Insights → Export Center — honest “not available” instead of fake analytics (PX-011)
- [x] CUJ-04: Complaints → New Complaint — Escape on dirty form confirms discard (PX-017)

## 7) Observability & Ops
- **Logs:** No change
- **Metrics:** No change
- **Alerts:** No change
- **Runbook updates:** N/A

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Tab through Incidents rows; paginate if >50; open Export Center; start complaint, type, press Escape
- **Canary plan:** N/A
- **Prod post-deploy checks:** Spot-check Incidents keyboard + Export Center honesty

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Pagination regression blanking list; modal cannot close; Export Center link breakage
- **Rollback steps:** Revert PR on main, redeploy previous SWA SHA
- **Owner:** Platform / UAT Wave C2b track

## 10) Evidence Pack (links)
- CI run(s): Linked after PR creation
- Staging deploy evidence: N/A at draft open
- Canary evidence (if applicable): N/A

## Residuals (explicitly not in this PR)
- **PX-004:** Server-side search/filter across full register (BE `q` param + FE wire-up)
- **PX-015:** Reporter default from session on incident create (BE + FE)
- **PX-056:** Employee↔user linking (large)
- **Export Center:** Live job APIs, templates, scheduled exports when backend ready

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** FE-only UX honesty/a11y aligned to PX repros
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete (evidence linked)
- [ ] **Gate 4:** Canary healthy (if used) (evidence linked)
- [x] **Gate 5:** Production verification plan + rollback ready

## Exclusive allowlist (this PR)
- `frontend/src/pages/Incidents.tsx`
- `frontend/src/pages/ExportCenter.tsx`
- `frontend/src/pages/Complaints.tsx`
- `frontend/src/pages/__tests__/Incidents.test.tsx`
- `frontend/src/pages/__tests__/ExportCenter.test.tsx`
- `frontend/src/pages/__tests__/Complaints.test.tsx`
- `scripts/governance/pr_body_uat_c2b_fe_ux_hygiene.md`
