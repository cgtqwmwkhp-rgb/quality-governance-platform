# Change Ledger (CL-WF-GATE)

## 1) Summary
- **Feature / Change name:** WF-GATE — Assessment/Training start-gate honesty + dead filter fixes
- **User goal (1–2 lines):** Surface competency soft/hard gate honestly at assessment & training start, and stop pretending unsupported list filters work.
- **In scope:** Assessments / AssessmentExecution / Training / TrainingExecution filter + gate UX; workforce `__tests__/WfGate.test.tsx`; this Change Ledger
- **Out of scope:** Layout, CompetencyDashboard, EngineerProfile, Calendar, workforceClient.ts, CompetenceGaps, InductionCreate (parity not required), backend gate mode changes
- **Feature flag / kill switch:** N/A — FE honesty only; hard mode already enforced by backend `COMPETENCY_GATE_MODE`

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):**
  - `Assessments.tsx` — client-side search only (no `search` query); wired engineer filter; disabled inert Filters button
  - `Training.tsx` — no `search`/`stage` API params; stage client-side; wired engineer filter; disabled Filters button
  - `AssessmentExecution.tsx` / `TrainingExecution.tsx` — soft-gate warning banner from `competency_gate_*`; hard-gate remediation (competencies / tickets / contact)
- **Backend (handlers/services):** None
- **APIs (endpoints changed/added):** None — consumes existing `/start` gate fields + list filters
- **Schemas/contracts:** None
- **Database:** None
- **Workflows/jobs/queues:** None
- **Config/env/flags:** None (reads existing gate fields / error code)
- **Dependencies:** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive FE UX; list calls stop sending ignored params
- **Tolerant reader / strict writer applied?** Yes — optional `competency_gate_*` fields; aliases `competency_gate_blocked` / `competency_gate_message`
- **Breaking changes:** None
- **Migration plan:** N/A
- **Rollback strategy (DB):** N/A — revert PR

## 4) Acceptance Criteria (AC)
- [x] AC-01: Soft gate warning shown at start using `competency_gate_cleared` / `reason` / `mode`
- [x] AC-02: Hard gate blocked start shows remediation links (competencies, tickets/passport, contact guidance)
- [x] AC-03: Assessment list never sends unsupported `search`; engineer filter wired to `engineer_id`
- [x] AC-04: Training list never sends unsupported `stage`/`search`; stage filtered client-side; engineer filter wired
- [x] AC-05: Inert Filters buttons disabled (not clickable dead controls)
- [x] AC-06: TrainingExecution mirrors AssessmentExecution gate honesty
- [x] AC-07: Unit tests under `frontend/src/pages/workforce/__tests__/WfGate.test.tsx`

## 5) Testing Evidence (link to runs)
- [ ] Lint — CI after open
- [ ] Typecheck — CI after open
- [ ] Build — CI after open
- [x] Unit tests — `frontend` vitest `src/pages/workforce/__tests__/WfGate.test.tsx` (local)
- [ ] Integration tests — N/A
- [ ] Contract tests — N/A
- [ ] E2E Smoke — N/A (FE honesty lane)

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Supervisor opens draft assessment → soft gate warning visible while execution continues
- [x] CUJ-02: Hard gate blocks assessment start → remediation CTAs (dashboard / engineer passport)
- [x] CUJ-03: Training list stage filter does not hit API; engineer filter uses `engineer_id`

## 7) Observability & Ops
- **Logs:** No change
- **Metrics:** No change
- **Alerts:** No change
- **Runbook updates:** N/A

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Draft assessment/induction with uncleared competency — soft warning; hard mode env shows remediation
- **Canary plan:** N/A
- **Prod post-deploy checks:** Spot-check Assessments/Training filters + one start path

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Gate UI false positives / list filter regressions blocking supervisors
- **Rollback steps:** Revert PR
- **Owner:** Platform / Workforce track

## 10) Evidence Pack (links)
- CI run(s): Linked after PR creation
- Staging deploy evidence: N/A at draft open
- Canary evidence (if applicable): N/A

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** FE contracts aligned to existing AssessmentRun/InductionRun gate fields
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete (evidence linked)
- [ ] **Gate 4:** Rollback plan verified
- [ ] **Gate 5:** Evidence pack linked / LIVE honesty noted

## Exclusive allowlist (this PR)
- `frontend/src/pages/workforce/Assessments.tsx`
- `frontend/src/pages/workforce/AssessmentExecution.tsx`
- `frontend/src/pages/workforce/Training.tsx`
- `frontend/src/pages/workforce/TrainingExecution.tsx`
- `frontend/src/pages/workforce/__tests__/WfGate.test.tsx`
- `scripts/governance/pr_body_wf_gate.md`
