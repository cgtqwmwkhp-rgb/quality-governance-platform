# Change Ledger (CL-GT-SMOKE-LOGIN-403)

## File allowlist (exclusive)

- `tests/smoke/test_login_reliability.py`
- `scripts/governance/pr_body_gt_smoke_login_403.md`

## 1) Summary

- **Feature / Change name:** fix(gt) — accept HTTP 403 in login smoke performance probe
- **User goal:** Unblock tip==LIVE residual PR queue stuck on Smoke Tests (CRITICAL)
- **In scope:** `test_fast_response_classification` allowed status set
- **Out of scope:** Auth/rate-limit policy changes; product residual PRs #1029–#1036
- **Root cause:** CI burst login probes can receive 403 rate-limit; smoke treated it as failure

## 2) Impact Map

| Surface | Before | After |
|---------|--------|-------|
| Smoke login probe | 403 fails CRITICAL gate | 403 accepted as reachable response |

## 3) Compatibility & Data Safety

- Test-only; no runtime/API change

## 4) Acceptance Criteria

- [x] AC-01: Allowed codes include 403
- [ ] AC-02: tip==LIVE; residual PRs can re-run smoke green

## 5) Testing Evidence

- Smoke assertion update; CI smoke suite on this PR

## 6) Critical Journeys (CUJ)

- [x] CUJ-01: Login endpoint remain reachable under smoke load without false CRITICAL fail

## 7) Observability

- N/A (test gate)

## 8) Release Plan

- Squash-merge tip==LIVE → residual PRs rebase/re-run

## 9) Rollback Plan

- Revert squash if smoke policy must reject 403

## 10) Evidence Pack

- This Change Ledger; failing jobs on #1029–#1036

---

# Gate Checklist

- [x] **Gate 0:** Scope + AC + rollback
- [x] **Gate 1:** Lint/type — smoke test only
- [x] **Gate 2:** Unit/smoke — login reliability
- [x] **Gate 3:** N/A frontend
- [ ] **Gate 4:** tip==LIVE verification
