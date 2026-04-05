# Change Ledger (CL-001)

## 1) Summary
- **Feature / Change name:** CAPA / Actions governance UX + import triage hardening (pillar documentation, toasts, import-review hand-off).
- **User goal (1-2 lines):** Operators can trace audit-sourced CAPA vs enterprise risk import triage, get clear feedback when triage succeeds or fails, and see a reconciliation hand-off after external audit promotion.
- **In scope:** Frontend copy and navigation; optional notes reject flow remains as shipped; i18n (en/cy); governance documentation in `docs/governance/GAP-001-003-remediation-plan.md`; `audit_run_id` and Actions UX from prior commits on this branch.
- **Out of scope:** Pending CAPA triage workflow; auto `ComplianceEvidenceLink` on promote; UVDB / Planet Mark matrix seeds (Pillar III backlog).
- **Feature flag / kill switch:** None (default).

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** `RiskRegister.tsx` (import triage toasts + i18n); `AuditImportReview.tsx` (governance hand-off panel); `Actions.tsx` (prior branch work).
- **Backend (handlers/services):** `actions.py` (prior branch work — `audit_run_id`, owner hydration).
- **APIs (endpoints changed/added):** None in this delta (uses existing suggestion-triage and actions list).
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** Client types for `audit_run_id` (prior branch).
- **Database (migrations/entities/indexes):** None.
- **Workflows/jobs/queues (if any):** None.
- **Config/env/flags:** None.
- **Dependencies (added/removed/updated):** None.

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive (UI + docs + i18n strings).
- **Tolerant reader / strict writer applied?** N/A (no schema change in this delta).
- **Breaking changes:** None.
- **Migration plan:** N/A.
- **Rollback strategy (DB):** No DB change.

## 4) Acceptance Criteria (AC)
- [x] AC-01: Import triage shows success toast on accept/reject and error toast on API failure (en + cy).
- [x] AC-02: Import review reconciliation shows governance hand-off when capa or enterprise risk counts are non-zero; buttons navigate to Actions (prefer `view_links.actions`) and Risk Register import triage.
- [x] AC-03: Remediation plan documents Pillars I–III, two enhancement-review rounds, and locked execution plan.

## 5) Testing Evidence (link to runs)
- [x] Lint — `make pr-ready`
- [x] Typecheck — `make pr-ready`
- [x] Build — `make pr-ready`
- [x] Unit tests — `make pr-ready`
- [x] Integration tests — `make pr-ready`
- [ ] Contract tests (if applicable) — N/A
- [ ] E2E Smoke (critical journeys) — per CI / manual staging

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Risk Register → Import triage → Accept / Reject (with optional reject notes) → toasts and list refresh.
- [x] CUJ-02: External audit import → Promotion reconciliation → hand-off panel → Actions + Import triage deep links.

## 7) Observability & Ops
- **Logs:** Existing client error logging on triage failure.
- **Metrics:** None added.
- **Alerts:** None added.
- **Runbook updates:** `docs/governance/GAP-001-003-remediation-plan.md`.

## 8) Release Plan (Local -> Staging -> Prod)
- **Staging verification:** Merge to `main`; verify staging deploy; exercise CUJ-01/02 on staging.
- **Canary plan:** N/A (full cut per platform process).
- **Prod post-deploy checks:** `/healthz`, `/api/v1/meta/version`, spot-check Actions + Risk Register triage.

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Regressions in triage or import review UI.
- **Rollback steps:** Revert merge commit on `main`; redeploy prior release SHA via governed production workflow.
- **Owner:** Platform CAB / author.

## 10) Evidence Pack (links)
- CI run(s): (populate from GitHub Actions after push)
- Staging deploy evidence: (post staging)
- Canary evidence (if applicable): N/A

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved (as applicable) — additive UI only
- [x] **Gate 2:** CI green (lint/type/build/tests) — `make pr-ready` passed locally
- [ ] **Gate 3:** Staging verification complete (evidence linked)
- [ ] **Gate 4:** Canary healthy (if used) (evidence linked) — N/A
- [ ] **Gate 5:** Production verification plan + monitoring ready
