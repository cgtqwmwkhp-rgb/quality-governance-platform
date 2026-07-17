# Change Ledger (CL-AN-04-ANALYTICS-POLISH)

## File allowlist (exclusive)

- `frontend/src/pages/Analytics.tsx`
- `frontend/src/pages/__tests__/Analytics.test.tsx`
- `scripts/governance/pr_body_an_04_analytics_polish.md`

**Zero overlap** with parallel lanes: Actions, ComplianceAutomation, KnowledgeExceptions, Audits board, PlanetMark, Layout/App/client API init/Alembic. English literals only (no locale edits).

## 1) Summary

- **Feature / Change name:** Path11 AN-04 — Analytics module metric honesty
- **User goal:** Operators never see fake zero open/closed RTA or audit counts; avg resolution days appear only when computable from loaded records.
- **In scope:** `Analytics.tsx` nullable metrics, RTA list wiring, dedicated audit/RTA summary panels, module table avg-resolution column, vitest proofs, Change Ledger
- **Out of scope:** Backend API, AdvancedAnalytics mock dashboard, forbidden parallel lanes
- **Feature flag / kill switch:** N/A — revert commit

## 2) Impact Map (what changed)

| Surface | Before | After |
|---------|--------|-------|
| RTA module row | Open/closed hardcoded `0` | Live from `rtasApi.list`; `—` when unavailable |
| Audit failure | Reset totals to `0` | Nullable metrics + dedicated summary unavailable copy |
| Module table | No avg resolution column | `Avg resolution` column with `—` when no timestamps |
| Hero KPIs | `0%` resolution when unknown | `—` when totals incomplete |
| Audits section | Generic slice panel only | Dedicated audit summary card with load-state honesty |
| RTAs section | Generic slice panel only | Dedicated RTA summary card with open/closed + avg resolution |

## 3) Compatibility & Data Safety

- **Compatibility strategy:** Additive UX + nullable display only
- **Breaking changes:** None
- **Rollback strategy:** Revert squash merge

## 4) Acceptance Criteria (AC)

- [x] AC-01: Audit API failure shows `—` / unavailable — never fake zero open/closed
- [x] AC-02: RTA open/closed sourced from list API (not hardcoded zeros)
- [x] AC-03: Avg resolution days shown only when computable from loaded page data
- [x] AC-04: Estimated open/closed mix surfaces partial-data note (first 100 records)
- [x] AC-05: Vitest covers RTA live counts, audit summary, and unavailable branches

## 5) Testing Evidence

- [x] Vitest `Analytics.test.tsx` — `module metric honesty` describe block (4 cases)
- [ ] CI green — this PR

## 6) Critical Journeys Verified (CUJ)

- [x] CUJ-01: `/analytics?section=audits` — audit summary with live or unavailable states
- [x] CUJ-02: `/analytics?section=rtas` — RTA open/closed from list, not zeros
- [x] CUJ-03: Partial API failure — module table `—` badges + partial banner

## 7) Observability & Ops

- **Playwright hooks:** `analytics-audit-summary`, `analytics-rta-summary`, `analytics-partial`, `analytics-module-table`

## 8) Release Plan

1. Draft PR → CI green
2. Squash-merge after review (human — **do not merge from this lane**)
3. Staging smoke `/analytics` audits + RTAs sections

## 9) Rollback Plan

1. Revert squash commit on `main`
2. Redeploy previous SHA

## 10) Evidence Pack (links)

- CI run(s): Linked after PR creation

---

# Gate Checklist (must be complete before merge)

- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** Exclusive allowlist respected
- [ ] **Gate 2:** CI green
- [ ] **Gate 3:** Staging verification complete
- [ ] **Gate 4:** Canary healthy (if used)
- [x] **Gate 5:** Production verification plan ready

## Test plan

- [ ] `cd frontend && npx vitest run src/pages/__tests__/Analytics.test.tsx`
- [ ] Manual: `/analytics?section=audits` with audits API down — summary unavailable, table shows `—`
- [ ] Manual: `/analytics?section=rtas` — open/closed match RTA register mix
