# Change Ledger (CL-GT-D22-OPENAPI)

## File allowlist (exclusive)

- `openapi-baseline.json`
- `docs/contracts/openapi.json`
- `tests/unit/test_gt_openapi_list_routes.py`
- `scripts/governance/pr_body_gt_d22_openapi.md`
- `requirements.lock`

**Zero overlap** with schema FK/NOT NULL migrations, Azure DI enablement, or SWA workflow YAML.

## 1) Summary

- **Feature / Change name:** fix(gt) — D22 OpenAPI baseline regen (golden-thread list routes freeze)
- **User goal:** Close UAT D22 / A12 — committed OpenAPI baseline matches live FastAPI mounts after #1022
- **In scope:** Regenerate `openapi-baseline.json` + `docs/contracts/openapi.json`; freeze GT list/create paths in unit tests
- **Out of scope:** Enabling `/docs` in production; schema FK/NOT NULL migrations; CSV/JSONB retirement
- **Root cause:** Wave-1 tip `a0f2da85` shipped dual-mount + honesty fields but did not refresh the OpenAPI baseline (532 → 611 paths)

## 2) Impact Map

| Surface | Before | After |
|---------|--------|-------|
| openapi-baseline.json | 532 paths / stale vs tip | 611 paths = `app.openapi()` |
| docs/contracts/openapi.json | Identical stale twin | Synced to baseline |
| GT list routes | Published in app, missing from baseline history | Frozen in contract tests |
| Runtime API | Unchanged | Unchanged |

## 3) Compatibility & Data Safety

- Additive only vs prior baseline (compatibility check PASSED; 0 breaking)
- No runtime behaviour change; docs/OpenAPI remain disabled in production by design

## 4) Acceptance Criteria

- [x] AC-01: `openapi-baseline.json` == `docs/contracts/openapi.json` == `app.openapi()` path set
- [x] AC-02: GT list paths `/actions/` `/capa` `/incidents/` `/investigations/` `/risk-register/` `/near-misses/` present with get+post
- [x] AC-03: Supporting paths view-counts, engineers/by-user/me, meta OCR, privacy register present
- [x] AC-04: `check_openapi_compatibility.py` old→new PASS (additive)
- [ ] AC-05: tip==LIVE; canvas D22 CLOSED; R10/R80 re-scored

## 5) Testing Evidence

- Unit: `tests/unit/test_gt_openapi_list_routes.py`
- Local: `scripts/check_openapi_compatibility.py` old baseline → new PASS
- [ ] CI green post-push

## 6) Critical Journeys (CUJ)

- [x] CUJ-01: Partner/OpenAPI consumer can discover golden-thread list mounts from committed contract

## 7) Observability

- N/A (contract artifact only)

## 8) Release Plan

- Squash-merge tip==LIVE → no migration → SWA bake N/A → canvas re-score D22

## 9) Rollback Plan

- **Rollback steps:** Revert squash on main
- **Owner:** Platform / QGP conveyor

## 10) Evidence Pack

- Golden-thread UAT canvas D22 / A12
- Prior tip: `a0f2da85` (#1022)

---

# Gate Checklist

- [x] **Gate 0:** Scope + AC + rollback
- [x] **Gate 1:** Contract artifacts aligned
- [ ] **Gate 2:** CI green
- [ ] **Gate 3:** Staging verification (auto after merge)
- [x] **Gate 4:** Canary N/A (contract artifact only)
- [ ] **Gate 5:** tip==LIVE + canvas update
