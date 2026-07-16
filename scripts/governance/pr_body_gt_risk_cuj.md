# Change Ledger (CL-GT-RISK-CUJ-R60-R32-R61)

## File allowlist (exclusive)

- `frontend/src/pages/RiskRegister.tsx`
- `frontend/src/pages/IncidentDetail.tsx`
- `frontend/src/pages/__tests__/RiskRegister.test.tsx`
- `frontend/src/pages/__tests__/IncidentDetail.test.tsx`
- `scripts/governance/pr_body_gt_risk_cuj.md`

**Zero overlap** with API honesty (#1026), schema migrations, or auth/login gating.

## 1) Summary

- **Feature / Change name:** fix(gt) — surface risk bands and incident evidence (R60/R61; R32 waived data)
- **User goal:** Stop false-zero risk bands and empty incident evidence when linked assets exist
- **In scope:** Heat-map-derived `by_level` fallback; Incident Detail evidence-asset list; targeted FE tests; this ledger
- **Out of scope:** Schema/data seeding; creating missing INC-2 action/risk links; API honesty contracts
- **Root cause:** Stale/missing summary bands rendered as zero; Incident Detail never queried evidence assets

## 2) Impact Map

| Flag | Before | After |
|------|--------|-------|
| R60 | Missing `by_level` shown as 0 Critical/High/Medium with populated heat map | Derive band counts from heat-map cells when summary bands absent |
| R61 | Only `reporter_submission.photos.count` shown | Load/list evidence assets for incident source |
| R32 | Empty INC-2 actions/risks looked like aggregation bugs | Verified aggregation OK — **WAIVE** as tenant-data when none linked |

## 3) Compatibility & Data Safety

- Frontend-only; no migration; no persistence change
- Fallback only when band counts are absent; populated `by_level` unchanged
- Evidence list additive; empty state remains honest when no assets

## 4) Acceptance Criteria

- [x] AC-01: Missing summary bands do not render as false zeros when heat-map cells contain risks
- [x] AC-02: Incident detail loads and lists evidence assets for its incident ID
- [x] AC-03: Action and linked-risk aggregation paths verified; R32 waived as tenant-data
- [x] AC-04: Targeted Vitest coverage for heat-map fallback and evidence path
- [ ] AC-05: tip==LIVE squash merge + UAT canvas re-score

## 5) Testing Evidence

- `npm test -- --run src/pages/__tests__/RiskRegister.test.tsx src/pages/__tests__/IncidentDetail.test.tsx`
- `npm run typecheck` / production frontend build
- [ ] CI green post-push

## 6) Critical Journeys

- [x] CUJ-01: Risk Register summary bands match populated heat-map residual cells when `by_level` missing
- [x] CUJ-02: Incident Detail shows linked evidence assets for `source_module=incident`

## 7) Observability

- No new metrics; UI empty/error states retained. Residual R32 emptiness remains data-honest.

## 8) Release Plan

- Squash-merge when based on tip==LIVE `main`; SWA bake picks up FE. No Alembic.

## 9) Rollback Plan

- Owner: GT remediation owner
- Rollback steps: Revert the squash commit on `main`; redeploy prior SWA artifact.

## 10) Evidence Pack

- Canvas GT UAT flags R32/R60/R61
- Prior tip: `2b9d7066` schema wave (#1024)

---

# Gate Checklist

- [x] **Gate 0:** Scope + AC + rollback
- [x] **Gate 1:** Lint/type — touched FE surfaces
- [x] **Gate 2:** Unit suites green (local Vitest)
- [ ] **Gate 3:** Staging verification (auto after merge)
- [x] **Gate 4:** Canary N/A (FE honesty; SWA bake)
- [ ] **Gate 5:** tip==LIVE + canvas update
