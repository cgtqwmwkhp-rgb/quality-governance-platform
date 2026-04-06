# Change Ledger (CL-PREDATOR-V3)

## 1) Summary
- **Feature / Change name:** Predator Sweep v3 — release signoff alignment to live production `b580c57d`
- **User goal (1-2 lines):** Close evidence gap where `docs/evidence/release_signoff.json` lagged behind live `build_sha` after PR #479 production deploy; record CI/staging/production run IDs for governed audit trail.
- **In scope:** `docs/evidence/release_signoff.json` only
- **Out of scope:** Application code, migrations, feature behaviour
- **Feature flag / kill switch:** N/A

## 2) Impact Map (what changed)
- **Governance artifacts:** `release_signoff.json` — `release_sha` `b580c57d`, workflow run links, live HTTP proof timestamp

## 3) Compatibility & Data Safety
- **Strategy:** Documentation-only JSON
- **Breaking changes:** None

## 4) Acceptance Criteria (AC)
- [x] AC-01: `release_sha` matches live prod `build_sha` at verification (`curl` 2026-04-06T21:47:02Z)
- [x] AC-02: `validate_release_signoff.py --sha b580c57d31da426e9c22f73a623b8c9f4e56cb76` exits 0
- [x] AC-03: CUJ-01..CUJ-03 labels present

## 5) Testing Evidence (link to runs)
- [x] CI — post-merge on PR
- [x] Prior prod deploy — https://github.com/cgtqwmwkhp-rgb/quality-governance-platform/actions/runs/24052571576

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Production `/api/v1/meta/version` returns `build_sha` matching PR #479 merge ancestry
- [x] CUJ-02: Production `/readyz` returns `ready` (agent curl)
- [x] CUJ-03: Authenticated compliance APIs remain protected (`/api/v1/compliance/standards` returned 401 without token — expected)

## 7) Observability & Ops
- **No change**

## 8) Release Plan
- Merge signoff PR; standard CI → staging → production chain updates git-only artifact in repo; runtime unchanged materially

## 9) Rollback Plan
- Revert PR restores prior signoff text

## 10) Evidence Pack
- Live version JSON captured in Predator Sweep v3 report

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Change Ledger complete
- [x] **Gate 1:** N/A JSON-only
- [ ] **Gate 2:** CI green on PR
- [x] **Gate 3:** Staging workflow success for `b580c57d` recorded (run 24052325404); HTTP deferred DNS
- [x] **Gate 4:** N/A canary
- [x] **Gate 5:** Live prod verified `b580c57d` pre-signoff-merge
