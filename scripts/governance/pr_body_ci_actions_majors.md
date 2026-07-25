# Change Ledger (CL-001)

## 1) Summary
- **Feature / Change name:** Controlled CI GitHub Actions majors
- **User goal (1-2 lines):** Bring CI tooling to current major action versions with zero application runtime risk.
- **In scope:** `actions/setup-node` → v7, `gitleaks/gitleaks-action` → v3, `actions/github-script` → v9, `dependabot/fetch-metadata` → v3 across workflows.
- **Out of scope:** Application dependency majors (router, i18n, redis, google-genai floor, Storybook, Express). Supersedes Dependabot #878/#873/#872/#871.
- **Feature flag / kill switch:** N/A — CI-only.

## 2) Impact Map (what changed)
- **Frontend:** None.
- **Backend:** None.
- **APIs:** None.
- **Schemas/contracts:** None.
- **Database:** None.
- **Workflows/jobs/queues:** `.github/workflows/{ci,security-scan,azure-static-web-apps-*,ux-functional-coverage,change-ledger-enforcement,nightly-contract-verification,dependabot-auto-merge}.yml`.
- **Config/env/flags:** None.
- **Dependencies:** GitHub Actions only (no requirements/lock/npm).

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Action majors are CI runtime only; gitleaks-action v3 and fetch-metadata v3 are Node 24 runtime migrations with no input/output contract change per upstream notes.
- **Tolerant reader / strict writer applied?** N/A.
- **Breaking changes:** None to application code.
- **Migration plan:** Merge; next CI run validates.
- **Rollback strategy (DB):** N/A. App rollback: revert this commit / redeploy prior SHA (workflows only).

## 4) Acceptance Criteria (AC)
- [x] AC-01: No remaining `@v2/@v4/@v6` pins for the four targeted actions in `.github/workflows`.
- [x] AC-02: Change Ledger present so Dependabot-style ledger gate passes.
- [x] AC-03: Supersedes open Dependabot PRs #878, #873, #872, #871 (close after merge).
- [x] AC-04: No application source/lockfile changes.

## 5) Testing Evidence (link to runs)
- [x] Lint/Typecheck/Build — N/A for workflow-only; CI self-validates on this PR.
- [x] Unit/Integration — unchanged application code.
- [x] Contract tests — N/A.
- [ ] E2E Smoke — CI pipeline green on this PR is the evidence.

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: CI workflow jobs start with setup-node@v7 / gitleaks@v3.
- [x] CUJ-02: Change Ledger enforcement workflow still evaluates PR bodies via github-script@v9.

## 7) Observability & Ops
- **Logs/Metrics/Alerts:** No change.
- **Runbook updates:** N/A.

## 8) Release Plan (Local -> Staging -> Canary -> Prod)
- **Staging verification:** N/A for app; CI green on PR is the gate.
- **Canary plan:** N/A — no production artifact change.
- **Prod post-deploy checks:** Confirm next main CI run succeeds after merge.

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** CI fails to checkout/setup Node or gitleaks fails to start after merge.
- **Rollback steps:** Revert this commit on main; re-run CI.
- **Owner:** Platform team.

## 10) Evidence Pack (links)
- CI run(s): This PR checks tab.
- Staging deploy evidence: N/A.
- Canary evidence (if applicable): N/A.

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved (as applicable) — N/A app contracts
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [x] **Gate 3:** Staging verification complete (evidence linked) — N/A app staging
- [x] **Gate 4:** Canary healthy (if used) (evidence linked) — N/A
- [x] **Gate 5:** Production verification plan + monitoring ready
