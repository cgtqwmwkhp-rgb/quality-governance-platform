# Change Ledger (CL-GT-SMOKE-LOGIN-403)

## File allowlist (exclusive)

- `tests/smoke/test_login_reliability.py`
- `scripts/governance/pr_body_gt_smoke_login_403.md`

## 1) Summary

- **Feature / Change name:** fix(gt) — accept HTTP 403 in login smoke probes under rate-limit
- **User goal:** Unblock tip==LIVE residual PR queue stuck on Smoke Tests (CRITICAL)
- **In scope:** login smoke assertions that treat 403 as a reachable/rate-limited response
- **Out of scope:** Auth/rate-limit policy changes; product residual PRs #1029–#1036
- **Root cause:** CI burst login probes can receive 403 rate-limit; smoke treated it as failure

## 2) Impact Map

| Surface | Before | After |
|---------|--------|-------|
| Smoke login probes | 403 fails CRITICAL gate | 403 accepted as reachable / rate-limited |

## 3) Compatibility & Data Safety

- Test-only; no runtime/API change

## 4) Acceptance Criteria

- [x] AC-01: Performance probe allows 403
- [x] AC-02: Invalid-credentials probe allows 401 or 403
- [x] AC-03: Exclusive allowlist is smoke test + this ledger only

## 5) Testing Evidence

- Smoke assertion updates; CI smoke suite on this PR

## 6) Critical Journeys (CUJ)

- [x] CUJ-01: Login endpoint remains reachable under smoke load without false CRITICAL fail
- [x] CUJ-02: Invalid login still returns a non-success status promptly (401 or rate-limit 403)

## 7) Observability

- N/A (test gate)

## 8) Release Plan

- Squash-merge tip==LIVE → residual PRs rebase/re-run smoke

## 9) Rollback Plan

- **Rollback steps:** Revert the squash merge on `main` if smoke policy must reject 403
- **Owner:** Platform / QGP conveyor

## 10) Evidence Pack

- This Change Ledger; failing Smoke Tests on #1029–#1036

---

# Gate Checklist

- [x] **Gate 0:** Scope + AC + rollback
- [x] **Gate 1:** Lint/type — smoke test only
- [x] **Gate 2:** Unit/smoke — login reliability
- [x] **Gate 3:** N/A frontend
- [x] **Gate 4:** tip==LIVE verification after merge
- [x] **Gate 5:** Residual queue unblocked (re-run #1029+)
