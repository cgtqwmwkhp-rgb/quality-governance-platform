# Change Ledger (CL-FIX-SWA-STAGING-UI-GATE)

## File allowlist (exclusive)

- `frontend/tests/e2e/import-reset-promote.spec.ts`
- `scripts/governance/pr_body_fix_swa_staging_ui_gate.md`

**Zero overlap** with parallel owners: product UI, Layout/admin hub, SWA workflow YAML, backend handlers, GKB, Workforce, portal inbox. Test-only fix — no application code changes.

## 1) Summary

- **Feature / Change name:** fix(e2e) — unblock SWA Staging UI Verification gate (import promote assertion)
- **User goal:** Restore green **Staging UI Verification (GATE)** on main so **Deploy Production SWA (prod API bake)** is unblocked; Playwright promote test must assert the real success notice, not LiveAnnouncer's empty `role="alert"`.
- **In scope:** `import-reset-promote.spec.ts` — serial describe mode; promote success assertion via `getByText(/Successfully promoted/i)`; governance Change Ledger for PR #973
- **Out of scope:** Import review product UI; LiveAnnouncer component; SWA deploy workflow; backend promote API; unrelated e2e specs
- **Feature flag / kill switch:** N/A — revert commit
- **Root cause:** Staging UI Verification failed on run [29329862705](https://github.com/cgtqwmwkhp-rgb/quality-governance-platform/actions/runs/29329862705) after #964 merge — 2/9 Playwright failures in `import-reset-promote.spec.ts`. `getByRole('alert')` matched LiveAnnouncer's empty sr-only alert instead of the import review success notice (promote API mock succeeded). Not a #964 product regression; chronic gate failure on **Promote** test; intermittent Reset setup redirect to `/login` under parallel execution.

## 2) Impact Map (what changed)

| Surface | Before | After |
|---------|--------|-------|
| E2E promote assertion | `getByRole('alert')` — matched LiveAnnouncer empty alert | `getByText(/Successfully promoted/i)` — targets success copy |
| Describe execution | Parallel (default) — flaky Reset setup / login redirect | `test.describe.configure({ mode: "serial" })` — stable ordering |
| Frontend (routes/screens/components) | None | None |
| Backend (handlers/services) | None | None |
| APIs (endpoints changed/added) | None | None |
| Schemas/contracts (OpenAPI/Zod/DTO/types) | None | None |
| Database (migrations/entities/indexes) | None | None |
| Workflows/jobs/queues | None | None |
| Config/env/flags | None | None |
| Dependencies | None | None |

## 3) Compatibility & Data Safety

- **Compatibility strategy:** Test-only — no runtime or API behaviour change
- **Tolerant reader / strict writer applied?** N/A — no production code touched
- **Breaking changes:** None
- **Migration plan:** No migration required
- **Rollback strategy (DB):** No DB change — revert commit only

## 4) Acceptance Criteria (AC)

- [x] AC-01: Promote test asserts success via `getByText(/Successfully promoted/i)` with 20s timeout (not generic `role="alert"`)
- [x] AC-02: Import review Reset / Promote describe block runs serially to avoid parallel login/setup flake
- [x] AC-03: Exclusive allowlist respected — only `import-reset-promote.spec.ts` + governance markdown; no product UI or SWA workflow edits
- [x] AC-04: Reset test unchanged in behaviour — still verifies review PATCH reset flow and button state transitions

## 5) Testing Evidence (link to runs)

- [x] Local — Playwright `import-reset-promote.spec.ts` promote + reset paths pass with updated selectors
- [x] Root-cause — promote API mock succeeded; failure was assertion targeting wrong alert element
- [ ] CI — Frontend Tests + **Staging UI Verification (GATE)** green post-merge on main
- [ ] Contract tests — N/A (no API change)
- [ ] Integration tests — N/A (no backend change)

## 6) Critical Journeys Verified (CUJ)

- [x] CUJ-01: Import review — Reset accepted finding to draft via review PATCH (serial setup)
- [x] CUJ-02: Import review — Promote accepted drafts → success notice → View Audit Actions → `/actions?sourceType=audit_finding`

## 7) Observability & Ops

- **Logs:** No change — test-only
- **Metrics:** No change
- **Alerts:** Staging UI Verification gate failure on main is the signal this PR addresses
- **Runbook updates:** N/A — if promote e2e flakes again, check for new `role="alert"` elements (LiveAnnouncer) before broadening selector

## 8) Release Plan (Local → Staging → Canary → Prod)

1. Merge PR #973 to `main` after CI green + Change Ledger gate pass
2. **Staging verification:** Azure Static Web Apps CI/CD **Staging UI Verification (GATE)** must pass on main (9/9 Playwright specs including `import-reset-promote.spec.ts`)
3. **Canary plan:** N/A — test-only change; no runtime deploy artefact
4. **Prod post-deploy checks:** Confirm **Deploy Production SWA (prod API bake)** unblocked once staging gate is green

## 9) Rollback Plan (Mandatory)

- **Rollback trigger:** Unexpected e2e regression in unrelated specs or staging gate still red after merge
- **Rollback steps:** Revert squash commit on `main`; re-run Staging UI Verification on previous known-good SHA
- **Owner:** Platform team / PR author

## 10) Evidence Pack (links)

- Failing staging run: [29329862705](https://github.com/cgtqwmwkhp-rgb/quality-governance-platform/actions/runs/29329862705)
- PR #973 CI: linked after merge
- Staging UI Verification (GATE) green on main: linked after merge

---

# Gate Checklist (must be complete before merge)

- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** Allowlist only — e2e spec + governance markdown; no product/SWA workflow overlap
- [ ] **Gate 2:** CI green (lint/type/build/tests including Frontend Tests)
- [ ] **Gate 3:** Staging verification complete — **Staging UI Verification (GATE)** green on main (evidence linked)
- [ ] **Gate 4:** Canary healthy (if used) — N/A for test-only change
- [x] **Gate 5:** Production verification plan ready — unblock **Deploy Production SWA** after staging gate green
