# Change Ledger (CL-WF-OPS-SWA-SERIAL-IMPORT-MOCK-RESET)

## File allowlist (exclusive)

- `frontend/tests/e2e/import-reset-promote.spec.ts`
- `scripts/governance/pr_body_wf_ops_swa.md`

**Zero overlap** with workforce product (`frontend/src/pages/workforce/*`), assets product code, Layout nav, or Wave 2 CAPA lanes. E2E isolation fix only.

## 1) Summary

- **Feature / Change name:** fix(e2e/ci) — WF-OPS SWA serial import mock reset
- **User goal:** Green **Staging UI Verification (GATE)** on main so **Deploy Production SWA (prod API bake)** is unblocked
- **In scope:** Isolate serial Reset → Promote Playwright tests — `page.unrouteAll` before mock install, fresh browser context per test, `serviceWorkers: "block"`
- **Out of scope:** Import review product UI; SWA workflow YAML; workforce/assets product code
- **Root cause:** After #974 (`workers=1` + hardened mocks), gate run [29338469383](https://github.com/cgtqwmwkhp-rgb/quality-governance-platform/actions/runs/29338469383) still failed: Reset passed (flaky retry), Promote timed out waiting for `Needs follow-up` while import-review stayed on **Loading cards**. Serial describe + retries can stack `page.route` handlers; a stale Reset mock (draft already flipped) starves Promote hydration. SWA service workers can also bypass `page.route` (other CUJs already set `serviceWorkers: "block"`; this suite did not).

## 2) Impact Map

| Surface | Before | After |
|---------|--------|-------|
| Route lifecycle | `page.route` stacked across serial/retry runs | `page.unrouteAll({ behavior: "ignoreErrors" })` before each mock install |
| Browser isolation | Default fixture page (serial group retry risk) | Fresh `browser.newContext({ serviceWorkers: "block" })` per test, closed in `finally` |
| Service workers | Allowed (SWA SW can bypass mocks) | Blocked (parity with inspection/complaint CUJs) |
| Product runtime | None | None |

## 3) Compatibility & Data Safety

- Test/CI only — no runtime behaviour change
- No schema, migration, or auth changes
- Rollback: revert merge commit

## 4) Acceptance Criteria

- [x] AC-01: `installImportMocks` clears prior routes via `unrouteAll` before registering handlers
- [x] AC-02: Reset and Promote each run in a fresh browser context that is closed after the test
- [x] AC-03: Suite sets `serviceWorkers: "block"` (describe + context)
- [x] AC-04: Allowlist exclusive — only import-reset-promote e2e + this Change Ledger; no workforce/assets/product files
- [ ] AC-05: Staging UI Verification (GATE) green on this PR / post-merge main

## 5) Testing Evidence

- Root-cause evidence: run 29338469383 — Promote failure at `openImportReview` `getByText('Needs follow-up')`; error-context shows authenticated shell stuck on **Loading cards** after Reset passed
- [ ] Staging UI Verification (GATE) green on this PR / post-merge main

## 6) Critical Journeys (CUJ)

- [x] CUJ-01: External Audit Import Review → Reset accepted draft via review PATCH (mocked, isolated context)
- [x] CUJ-02: External Audit Import Review → Promote accepted drafts confirms and completes (mocked, isolated context; no pollution from CUJ-01)

## 7) Observability

- No change — gate artifacts (`playwright-*-staging`) remain the signal

## 8) Release Plan

- Squash-merge → SWA CI on main → Staging UI Verification → Deploy Production SWA when green

## 9) Rollback Plan

- **Rollback steps:** Revert squash/merge commit on `main`; re-run Staging UI Verification on previous known-good SHA
- **Owner:** Platform / QGP conveyor

## 10) Evidence Pack

- This Change Ledger
- Failing gate run [29338469383](https://github.com/cgtqwmwkhp-rgb/quality-governance-platform/actions/runs/29338469383) + artifact `playwright-test-results-staging`
- Prior related fixes: #973 (promote assertion), #974 (workers=1 + mock harden)

---

# Gate Checklist

- [x] **Gate 0:** Scope + AC + rollback
- [x] **Gate 1:** Lint/type — N/A product (e2e only)
- [x] **Gate 2:** Unit + integration — N/A product
- [x] **Gate 3:** Frontend tests — e2e gate coverage via Staging UI Verification
- [ ] **Gate 4:** Staging after merge — Staging UI Verification green
- [ ] **Gate 5:** Prod verification — SWA bake unblocked
