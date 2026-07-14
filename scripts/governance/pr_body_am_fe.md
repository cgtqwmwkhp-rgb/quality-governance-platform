# Change Ledger (CL-AM-FE)

## 1) Summary
- **Feature / Change name:** AM-FE — Safety Asset Register KPI hub + detail
- **User goal (1–2 lines):** Give Safety a dedicated Asset Register hub (not spreadsheet CRUD) with honest KPIs, filters, and detail — mirroring Risk Register / Van Checklists honesty patterns.
- **In scope:** `safetyAssetsClient`, SafetyAssetRegister + SafetyAssetDetail pages, `/safety-assets` routes, Safety Cases nav child only, i18n, unit tests, this ledger.
- **Out of scope:** workforceClient / Workforce nav, VehicleChecklists, CompetenceGaps, incident detail pickers (AM-THREAD), backend models.
- **Feature flag / kill switch:** None.
- **Depends on:** #976 (AM-MODEL).

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** `/safety-assets`, `/safety-assets/:id`; Layout Safety Cases → Asset Register.
- **Backend (handlers/services):** None (consumes AM-MODEL APIs).
- **APIs (endpoints changed/added):** Client wrappers for `/api/v1/assets` + `/locations` + evidence upload (`source_module=asset`).
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** FE TypeScript types in `safetyAssetsClient.ts`.
- **Database (migrations/entities/indexes):** None.
- **Workflows/jobs/queues (if any):** None.
- **Config/env/flags:** None.
- **Dependencies (added/removed/updated):** None.

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive FE only; KPIs use parallel count queries; failures show `—` / unavailable banner (no silent zeros).
- **Tolerant reader / strict writer applied?** Yes — null metrics on fetch failure; placeholders for Linked cases / Open actions (AM-THREAD).
- **Breaking changes:** None.
- **Migration plan:** N/A.
- **Rollback strategy (DB):** N/A — revert FE PR.

## 4) Acceptance Criteria (AC)
- [x] AC-01: List hub with KPI row (total, in-date, due 30/60/90, overdue, quarantined) — no silent zeros on failure.
- [x] AC-02: Filters for type, location, vehicle, owner, expiry band.
- [x] AC-03: Detail shows identity, assignment, owner, expiry, status, QR, photo upload via evidence pattern; Linked cases / Open actions placeholders are honest.
- [x] AC-04: Routes + Safety Cases nav only; workforceClient untouched.

## 5) Testing Evidence (link to runs)
- [x] Unit — `safetyAssetsClient.test.ts`, `SafetyAssetRegister.test.tsx` (local)
- [ ] Lint / typecheck / build — CI
- [ ] Integration / E2E — N/A for this lane (FE hub)

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Open Asset Register → KPI row + filtered list
- [x] CUJ-02: Open asset detail → identity / assignment / status / QR / photo upload path
- [x] CUJ-03: KPI failure path shows `—` + unavailable banner (not zeros)

## 7) Observability & Ops
- **Logs / Metrics / Alerts:** No change
- **Runbook updates:** N/A

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** After #976 merge — open `/safety-assets`, confirm KPIs + detail against seeded assets
- **Canary plan:** N/A
- **Prod post-deploy checks:** Nav child visible under Safety Cases; smoke list/detail

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** FE crash on `/safety-assets` or nav regression
- **Rollback steps:** Revert this PR
- **Owner:** Platform / Safety Assets track

## 10) Evidence Pack (links)
- CI run(s): Linked on PR checks
- Depends on: https://github.com/cgtqwmwkhp-rgb/quality-governance-platform/pull/976

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data contracts (consumes AM-MODEL)
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification (after AM-MODEL)
- [ ] **Gate 4:** Canary (if used)
- [x] **Gate 5:** Production verification plan ready

## Exclusive allowlist
- `frontend/src/pages/SafetyAssetRegister.tsx`, `SafetyAssetDetail.tsx`
- `frontend/src/pages/__tests__/SafetyAssetRegister.test.tsx`
- `frontend/src/api/safetyAssetsClient.ts` + `.test.ts`
- `frontend/src/App.tsx` (route / lazy lines only)
- `frontend/src/components/Layout.tsx` (Safety Cases child only)
- `frontend/src/i18n/locales/en.json`, `cy.json` (safety asset keys)
- `scripts/governance/pr_body_am_fe.md`
