# Change Ledger (CL-UAT-C2C-FE)

## 1) Summary
- **Feature / Change name:** Wave C2c — FE UX honesty + session reporter (PX-015, PX-005, PX-006, PX-009, PX-036)
- **User goal (1–2 lines):** Close remaining easy clinical/zip FE gaps not in #1199: default incident reporter from session, honest complaint/audit/form-builder dead-end UX, and decode stored incident text entities.
- **In scope:** `Incidents.tsx` reporter default + entity decode; `Complaints.tsx` empty-contract honesty; `AuditTrail.tsx` empty/dead-end honesty; `FormBuilder.tsx` Add Field palette fix; `IncidentDetail.tsx` text decode; helpers + Vitest; this Change Ledger
- **Out of scope:** PX-003/#1196; PX-004/008/011/017 (#1199); PX-056 employee↔user linking; BE audit-trail event ingestion; BE contract seeding (PX-048); full audit export/pagination APIs
- **Feature flag / kill switch:** N/A — FE-only honesty + create payload enrichment

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):**
  - `frontend/src/utils/platformSessionReporter.ts` — resolve `/auth/me` reporter identity (cached)
  - `frontend/src/pages/incidentTextDisplay.ts` — decode legacy `&amp;` storage for display (PX-009)
  - `frontend/src/pages/Incidents.tsx` — session reporter on create + list title decode + create modal hint (PX-015/009)
  - `frontend/src/pages/IncidentDetail.tsx` — decode title/description on display and edit hydrate (PX-009)
  - `frontend/src/pages/Complaints.tsx` — honest empty-contract banner + disabled submit + Admin Contracts link (PX-005)
  - `frontend/src/pages/AuditTrail.tsx` — distinguish filter-empty vs unlogged; disable Export; remove dead Load More (PX-006)
  - `frontend/src/pages/admin/FormBuilder.tsx` — inline field palette (fix clipped Add Field) + explicit button types (PX-036)
  - Vitest: Incidents, Complaints, AuditTrail, FormBuilder, platformSessionReporter, incidentTextDisplay
- **Backend (handlers/services):** None
- **APIs (endpoints changed/added):** None (reads existing `/api/v1/auth/me` on incident create open)
- **Schemas/contracts:** None
- **Database:** None
- **Workflows/jobs/queues:** None
- **Config/env/flags:** None
- **Dependencies:** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive FE payload fields + display decode; no persistence schema change
- **Tolerant reader / strict writer applied?** N/A
- **Breaking changes:** None — dead CTAs become honest/disabled instead of misleading
- **Migration plan:** N/A
- **Rollback strategy (DB):** N/A — revert PR

## 4) Acceptance Criteria (AC)
- [x] AC-01: New incident create sends `reporter_name`/`reporter_email` from signed-in session when available (PX-015)
- [x] AC-02: Create modal shows session reporter hint before submit (PX-015)
- [x] AC-03: Complaints create modal shows honest setup banner when contracts list is empty; submit disabled; Admin Contracts link (PX-005)
- [x] AC-04: Audit Trail empty API response shows “No activity logged yet” — not “adjust filters” (PX-006)
- [x] AC-05: Audit Trail Export Log disabled with honest affordance; dead Load More removed (PX-006)
- [x] AC-06: Form Builder Add Field opens inline palette and adds a typed field (PX-036)
- [x] AC-07: Incident list/detail decode `&amp;` to `&` for display/edit hydrate (PX-009 partial FE)
- [x] AC-08: Vitest covers reporter default, contract empty, audit empty, add field, entity decode

## 5) Testing Evidence (link to runs)
- [ ] Lint — CI after open
- [ ] Typecheck — CI after open
- [ ] Build — CI after open
- [x] Unit tests — targeted Vitest (local)
- [ ] Integration tests — N/A
- [ ] Contract tests — N/A
- [ ] E2E Smoke — N/A (FE hygiene lane)

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Safety & Cases → Incidents → New — reporter captured from session (PX-015)
- [x] CUJ-02: Complaints → New Complaint with zero contracts — honest dead-end + admin handoff (PX-005)
- [x] CUJ-03: Admin → Audit Trail with empty API — honest unlogged state (PX-006)
- [x] CUJ-04: Admin → Form Builder → Add Field — field appears (PX-036)
- [x] CUJ-05: Incidents register/detail — `&amp;` displays as `&` (PX-009 partial)

## 7) Observability & Ops
- **Logs:** No change
- **Metrics:** No change
- **Alerts:** No change
- **Runbook updates:** N/A

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Create incident (check reporter on detail); open complaint create with/without contracts; open Audit Trail; Form Builder Add Field; spot-check `&` titles
- **Canary plan:** N/A
- **Prod post-deploy checks:** PX-015 reporter on new incident; PX-036 Add Field

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Incident create regression; Form Builder palette regression; complaint modal cannot open
- **Rollback steps:** Revert PR on main, redeploy previous SWA SHA
- **Owner:** Platform / UAT Wave C2c track

## 10) Evidence Pack (links)
- CI run(s): Linked after PR creation
- Staging deploy evidence: N/A at draft open
- Canary evidence (if applicable): N/A

## Residuals (explicitly not in this PR)
- **PX-006 BE:** Emit audit-trail events on CRUD/login (forward-only ingestion)
- **PX-005 BE/data:** Seed contracts on staging (PX-048 host split)
- **PX-009 BE:** Stop HTML-escaping on write; repair corrupted rows
- **PX-056:** Employee↔user linking (skipped)
- **Audit Trail:** Live export job API + server pagination

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** FE-only UX honesty aligned to PX repros (no #1199 overlap)
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete (evidence linked)
- [ ] **Gate 4:** Canary healthy (if used) (evidence linked)
- [x] **Gate 5:** Production verification plan + rollback ready

## Exclusive allowlist (this PR)
- `frontend/src/utils/platformSessionReporter.ts`
- `frontend/src/utils/__tests__/platformSessionReporter.test.ts`
- `frontend/src/pages/incidentTextDisplay.ts`
- `frontend/src/pages/__tests__/incidentTextDisplay.test.ts`
- `frontend/src/pages/Incidents.tsx`
- `frontend/src/pages/IncidentDetail.tsx`
- `frontend/src/pages/Complaints.tsx`
- `frontend/src/pages/AuditTrail.tsx`
- `frontend/src/pages/admin/FormBuilder.tsx`
- `frontend/src/pages/__tests__/Incidents.test.tsx`
- `frontend/src/pages/__tests__/Complaints.test.tsx`
- `frontend/src/pages/__tests__/AuditTrail.test.tsx`
- `frontend/src/pages/admin/__tests__/FormBuilder.test.tsx`
- `scripts/governance/pr_body_uat_c2c_fe_ux_more.md`
