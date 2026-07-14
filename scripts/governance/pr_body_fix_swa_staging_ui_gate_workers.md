# Change Ledger (CL-FIX-SWA-STAGING-UI-GATE-WORKERS)

## File allowlist (exclusive)

- `frontend/tests/e2e/import-reset-promote.spec.ts`
- `.github/workflows/azure-static-web-apps-purple-water-03205fa03.yml`
- `scripts/governance/pr_body_fix_swa_staging_ui_gate_workers.md`

**Zero overlap** with product UI, backend, or Wave 2 CAPA lanes. Gate-isolation fix only.

## 1) Summary

- **Feature / Change name:** fix(e2e/ci) — SWA Staging UI gate: serial workers + tighter import mocks
- **User goal:** Unblock **Deploy Production SWA (prod API bake)** by greening Staging UI Verification on main
- **In scope:** Playwright `--workers=1` for the gate command; harden `import-reset-promote` mocks (`**/api/v1/**`, `/readyz`, OPTIONS); assert URL + draft title before Reset control
- **Out of scope:** Import review product code; backend rate limits; unrelated e2e suites
- **Root cause:** Gate run 29335903653 — Reset test timed out; page left import-review for Dashboard with toast **Too many requests (429)**. Parallel Playwright workers + live staging API share runner IP.

## 2) Impact Map

| Surface | Before | After |
|---------|--------|-------|
| Gate Playwright command | Default workers (parallel specs) | `--workers=1` sequential |
| Import mocks | `**/api/**` only | `**/api/v1/**` + `/readyz` + OPTIONS soft-default |
| openImportReview waits | Heading then Reset button | Heading → URL → draft title → Reset |
| Product runtime | None | None |

## 3) Compatibility & Data Safety

- Test/CI only — no runtime behaviour change
- Rollback: revert commit

## 4) Acceptance Criteria

- [x] AC-01: Gate workflow invokes Playwright with `--workers=1`
- [x] AC-02: Import suite never depends on live staging `/api` or `/readyz`
- [x] AC-03: openImportReview asserts still on import-review URL before Reset

## 5) Testing Evidence

- [ ] Staging UI Verification (GATE) green on this PR / post-merge main
- Root-cause evidence: Playwright error-context shows 429 toast + Dashboard Loading cards instead of Reset control

## 6) Critical Journeys (CUJ)

- [x] CUJ-01: External Audit Import Review → Reset accepted draft via review PATCH (mocked)
- [x] CUJ-02: External Audit Import Review → Promote accepted drafts confirms and completes (mocked)

## 7) Observability

- No change

## 8) Release Plan

- Squash-merge → SWA CI on main → Staging UI Verification → Deploy Production SWA when green

## 9) Rollback Plan

- **Rollback steps:** Revert merge commit on main
- **Owner:** Platform / QGP conveyor

## 10) Evidence Pack

- This Change Ledger + failing run 29335903653 artifact `playwright-test-results-staging`

---

# Gate Checklist

- [x] **Gate 0:** Scope + AC + rollback
- [x] **Gate 1:** Lint/type — N/A product (CI/e2e only)
- [x] **Gate 2:** Unit + integration — N/A product
- [x] **Gate 3:** Frontend tests — e2e gate coverage via Staging UI Verification
- [ ] **Gate 4:** Staging after merge — Staging UI Verification green
- [ ] **Gate 5:** Prod verification — SWA bake unblocked
