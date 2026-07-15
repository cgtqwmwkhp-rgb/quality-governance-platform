# Change Ledger (CL-FIX-SWA-FAIL-EVIDENCE-E2E)

## File allowlist (exclusive)

- `frontend/tests/e2e/inspection-capa-risk-cuj.spec.ts`
- `scripts/governance/pr_body_fix_swa_fail_evidence_e2e.md`

**Zero overlap** with product UI (`AuditExecution.tsx` / Mobile), SWA workflow YAML, backend, or alembic. Gate-unblock e2e only.

## 1) Summary

- **Feature / Change name:** fix(e2e/ci) — live inspection CUJ respects R2 fail→mandatory evidence
- **User goal:** Green **Staging UI Verification (GATE)** on main so **Deploy Production SWA (prod API bake)** can run and purple-water leaves the staging API bake
- **In scope:** Update `inspection-capa-risk-cuj` live-completion test to attach photo after NO, Continue to review, then submit
- **Out of scope:** Product gate logic (already shipped in #1018); OCR keys; partner tokens; investigation builders
- **Root cause:** After #1018, `failure_triggers_action: true` + NO blocks auto-advance until ≥1 photo. The CUJ still expected **Submit Audit & Generate Action Plan** immediately after NO → Staging UI Verification fails → prod SWA bake skipped → FE remains on staging API.

## 2) Impact Map

| Surface | Before | After |
|---------|--------|-------|
| Live completion CUJ | NO → expect Submit (broken vs R2) | NO → evidence alert → attach photo → Continue → Submit |
| Staging UI Verification | 8 pass / 1 fail on tip `b5c8f48e` | Expected green for this suite |
| Deploy Production SWA | Skipped while gate red | Unblocked once gate green |
| Product runtime | None | None |

## 3) Compatibility & Data Safety

- Test/CI only — no runtime behaviour change
- No schema, migration, or auth changes
- Rollback: revert merge commit

## 4) Acceptance Criteria

- [x] AC-01: After NO on gated question, test asserts fail-evidence alert and Submit is absent
- [x] AC-02: Test attaches a PNG via hidden file input and waits for Evidence 1 preview
- [x] AC-03: Test Continues to review, submits, and still proves CAPA Actions handoff
- [x] AC-04: Exclusive allowlist only (e2e + this Change Ledger)
- [ ] AC-05: Staging UI Verification (GATE) green on this PR / post-merge main
- [ ] AC-06: Deploy Production SWA runs; purple-water API host = `app-qgp-prod`

## 5) Testing Evidence

- Failing gate: [SWA run 29444036522](https://github.com/cgtqwmwkhp-rgb/quality-governance-platform/actions/runs/29444036522) on tip `b5c8f48e` — `live inspection completion hands generated work to CAPA Actions`
- [ ] Staging UI Verification (GATE) green on this PR / post-merge main

## 6) Critical Journeys (CUJ)

- [x] CUJ-01: Auditor answers NO on `failure_triggers_action` PPE question → mandatory evidence gate blocks Submit
- [x] CUJ-02: Auditor attaches photo → Continue → Submit Audit & Generate Action Plan → CAPA Actions filtered handoff

## 7) Observability

- No change — gate artifacts (`playwright-*-staging`) remain the signal

## 8) Release Plan

- Squash-merge → SWA CI on main → Staging UI Verification → Deploy Production SWA when green → verify FE calls prod API

## 9) Rollback Plan

- **Rollback steps:** Revert squash/merge commit on `main`; re-run Staging UI Verification on previous known-good SHA
- **Owner:** Platform / QGP conveyor

## 10) Evidence Pack

- This Change Ledger
- Failing gate run [29444036522](https://github.com/cgtqwmwkhp-rgb/quality-governance-platform/actions/runs/29444036522)
- Related product: #1018 R2 fail→mandatory evidence

---

# Gate Checklist

- [x] **Gate 0:** Scope + AC + rollback
- [x] **Gate 1:** Lint/type — N/A product (e2e only)
- [x] **Gate 2:** Unit + integration — N/A product
- [x] **Gate 3:** Frontend tests — e2e gate coverage via Staging UI Verification
- [ ] **Gate 4:** Staging after merge — Staging UI Verification green
- [ ] **Gate 5:** Prod verification — SWA prod API bake + purple-water → `app-qgp-prod`
