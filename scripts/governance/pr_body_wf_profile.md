# Change Ledger (CL-WF-PROFILE)

## 1) Summary
- **Feature / Change name:** WF-PROFILE — engineer skills passport (training tickets + requirements % match)
- **User goal (1–2 lines):** Give supervisors an audit-honest engineer passport: identity, full competency lifecycle, statutory tickets (create/edit), and mandatory requirements coverage as **% match**.
- **In scope:** `EngineerProfile` sections (identity, competency records/state KPIs, training tickets via `workforceApi.trainingTickets.*`, requirements coverage via `workforceApi.competencyRequirements.*`), deep link to competence-gaps by engineer, asset-type map failure surfacing, unit tests, `workforce.engineers.*` i18n keys, this ledger
- **Out of scope:** Layout/nav; CompetencyDashboard; Calendar; Assessments/Training pages; CompetenceGaps.tsx; workforceClient; backend
- **Feature flag / kill switch:** N/A — FE page wiring to existing spine APIs

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** `EngineerProfile.tsx` — passport sections + ticket dialog; list→profile already on `Engineers.tsx` (unchanged)
- **Backend (handlers/services):** None
- **APIs (endpoints changed/added):** None — consumes `/api/v1/training-tickets/` and `/api/v1/competency-requirements/` via existing `workforceApi`
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** None (uses WF-CLIENT types)
- **Database (migrations/entities/indexes):** None
- **Workflows/jobs/queues (if any):** None
- **Config/env/flags:** None
- **Dependencies (added/removed/updated):** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive UI on existing engineer profile route
- **Tolerant reader / strict writer applied?** Yes — ticket/requirement list errors shown explicitly (no silent 0%); asset-type map failures surfaced; empty mandatory set shows empty state (not 0%)
- **Breaking changes:** None
- **Migration plan:** N/A
- **Rollback strategy (DB):** N/A — revert PR only

## 4) Acceptance Criteria (AC)
- [x] AC-01: Identity + competency records with full state set (active/due/expired/failed/not_assessed)
- [x] AC-02: Training tickets list (scheme/number/expiry/verify_state/evidence) via `workforceApi.trainingTickets.*`; create/edit dialog
- [x] AC-03: Requirements coverage **% match** = mandatory met / mandatory total via `workforceApi.competencyRequirements.*`
- [x] AC-04: Deep link to `/workforce/competence-gaps?engineer_id=:id`
- [x] AC-05: No silent asset-type map failure
- [x] AC-06: Unit tests for ticket list + % match empty/error; exclusive allowlist only

## 5) Testing Evidence (link to runs)
- [ ] Lint — CI after open
- [ ] Typecheck — CI after open
- [ ] Build — CI after open
- [x] Unit tests — `frontend` vitest `src/pages/workforce/__tests__/EngineerProfile.test.tsx` (11 passed, local)
- [ ] Integration tests — N/A
- [ ] Contract tests (if applicable) — N/A
- [ ] E2E Smoke — N/A (page lane; supervisor Playwright deferred to WF1)

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Open engineer profile → see identity, competency states, tickets, % match
- [x] CUJ-02: Ticket list renders scheme/number/expiry/verify_state/evidence; create/edit form available
- [x] CUJ-03: Requirements empty → empty copy; requirements error → error alert (not 0%); happy path → percent + met/total
- [x] CUJ-04: Competence gaps deep link carries `engineer_id`

## 7) Observability & Ops
- **Logs:** `trackError` on asset-type / ticket / requirement / profile load failures
- **Metrics:** No change
- **Alerts:** No change
- **Runbook updates:** N/A

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Open `/workforce/engineers/:id` with seeded tickets + mandatory requirements; confirm % match and ticket create/edit
- **Canary plan:** N/A
- **Prod post-deploy checks:** Spot-check one engineer passport; confirm competence-gaps link

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Profile page regression / ticket API mismatch blocking FE
- **Rollback steps:** Revert PR
- **Owner:** Platform / Workforce track

## 10) Evidence Pack (links)
- CI run(s): Linked after PR creation
- Staging deploy evidence: N/A (draft)
- Canary evidence (if applicable): N/A

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** FE wires existing spine client (WF-CLIENT) — no new axios
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete (evidence linked)
- [ ] **Gate 4:** Rollback plan verified
- [ ] **Gate 5:** Evidence pack linked / LIVE honesty noted

## Exclusive allowlist (this PR)
- `frontend/src/pages/workforce/EngineerProfile.tsx`
- `frontend/src/pages/workforce/__tests__/EngineerProfile.test.tsx`
- `frontend/src/i18n/locales/en.json` (`workforce.engineers.*` / tickets keys only)
- `scripts/governance/pr_body_wf_profile.md`

**Forbidden / not touched:** workforceClient.ts, Layout, CompetencyDashboard, Calendar, Assessments/Training, CompetenceGaps.tsx, backend.  
**Zero overlap with Asset Management lanes.** Engineers.tsx unchanged (list→profile already present).
