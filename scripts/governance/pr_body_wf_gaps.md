# Change Ledger (CL-WF-GAPS)

## 1) Summary
- **Feature / Change name:** WF-GAPS — Competence gaps discoverable inbox + CAPA closed loop
- **User goal (1–2 lines):** Let supervisors find Assessor competence-gap signals under Workforce nav and close the loop: link engineer/requirement → create CAPA → resolve.
- **In scope:** Workforce nav child; CompetenceGaps inbox UX (per-row pickers, human labels, filter-empty copy); competenceGapClient picker helpers; Layout Workforce child + hub test; i18n; unit tests; Change Ledger
- **Out of scope:** workforceClient edits; CompetencyDashboard / EngineerProfile / Calendar / Assessments; Safety Cases hub children; backend asset files
- **Feature flag / kill switch:** N/A — surfaces existing `/api/v1/workforce/competence-gaps` APIs

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** `CompetenceGaps.tsx` inbox UX; `Layout.tsx` Workforce nav child only; Layout hub path test
- **Backend (handlers/services):** None
- **APIs (endpoints changed/added):** None — client calls existing competence-gaps + engineers + competency-requirements list endpoints
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** FE picker helper types on `competenceGapClient.ts` only
- **Database (migrations/entities/indexes):** None
- **Workflows/jobs/queues (if any):** None
- **Config/env/flags:** None
- **Dependencies (added/removed/updated):** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive nav + UX over existing closed-loop APIs
- **Tolerant reader / strict writer applied?** Yes — unknown source types fall back to `competenceGaps.source.unknown`
- **Breaking changes:** None
- **Migration plan:** N/A
- **Rollback strategy (DB):** N/A — revert PR only

## 4) Acceptance Criteria (AC)
- [x] AC-01: Workforce hub exposes “Competence gaps” child at `/workforce/competence-gaps` (Safety Cases hub untouched)
- [x] AC-02: Per-row engineer/requirement pickers (no shared draft state across rows)
- [x] AC-03: Source / engineer / requirement shown with human labels (not `type:id`)
- [x] AC-04: Filter-empty copy differs from global-empty copy
- [x] AC-05: CUJ list → link → create CAPA → resolve covered by unit tests; Layout Workforce hub path asserts competence-gaps

## 5) Testing Evidence (link to runs)
- [ ] Lint — CI after open
- [ ] Typecheck — CI after open
- [ ] Build — CI after open
- [x] Unit tests — `frontend` vitest `CompetenceGaps.test.tsx` + `Layout.test.tsx` Workforce hub path (local)
- [ ] Integration tests — N/A (FE lane)
- [ ] Contract tests (if applicable) — N/A
- [ ] E2E Smoke — N/A for this lane

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Supervisor opens Workforce → Competence gaps inbox and sees listed gap actions with human labels
- [x] CUJ-02: Supervisor links engineer + optional requirement on a specific row (per-row pickers)
- [x] CUJ-03: Supervisor creates CAPA then resolves the gap (closed loop)

## 7) Observability & Ops
- **Logs:** No change
- **Metrics:** No change
- **Alerts:** No change
- **Runbook updates:** N/A

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Workforce hub shows Competence gaps; open inbox; link → CAPA → resolve on a test gap
- **Canary plan:** N/A
- **Prod post-deploy checks:** Nav child visible for admin/supervisor; inbox loads without silent empty on API failure

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Inbox/nav regression blocking Workforce supervisors
- **Rollback steps:** Revert PR
- **Owner:** Platform / Workforce track

## 10) Evidence Pack (links)
- CI run(s): Linked after PR creation
- Staging deploy evidence: N/A (draft)
- Canary evidence (if applicable): N/A

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** FE contracts use existing competence-gap APIs
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete (evidence linked)
- [ ] **Gate 4:** Rollback plan verified
- [ ] **Gate 5:** Evidence pack linked / LIVE honesty noted

## Exclusive allowlist (this PR)
- `frontend/src/pages/CompetenceGaps.tsx`
- `frontend/src/pages/__tests__/CompetenceGaps.test.tsx`
- `frontend/src/api/competenceGapClient.ts`
- `frontend/src/components/Layout.tsx` (Workforce nav child only)
- `frontend/src/components/__tests__/Layout.test.tsx` (Workforce hub child path)
- `frontend/src/i18n/locales/en.json` / `cy.json` (gaps + nav.competence_gaps keys)
- `scripts/governance/pr_body_wf_gaps.md`

**Zero overlap with Asset Management lanes.** No workforceClient, CompetencyDashboard, EngineerProfile, Calendar, Assessments, Safety Cases Layout children, or backend asset files.
