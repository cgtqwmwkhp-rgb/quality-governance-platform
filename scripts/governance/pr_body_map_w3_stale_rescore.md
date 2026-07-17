# Change Ledger (CL-MAP-W3-STALE-RESCORE)

**Path claim:** `path11/map-w3-stale-rescore`

## File allowlist (exclusive)

- `frontend/src/pages/mapW3StaleRescoreHonesty.ts`
- `frontend/src/pages/__tests__/mapW3StaleRescoreHonesty.test.ts`
- `scripts/governance/pr_body_map_w3_stale_rescore.md`

**Zero overlap** with parallel lanes: MAP-W2 #1079 (`AuditTemplateBuilder*`, `AssessmentCreate*`, `builderMapAssistHonesty*`), PlanetMark*, Calendar*, Layout/App/client.ts, `api/__init__.py`, Alembic. No i18n (avoids soft en/cy conflict).

## 1) Summary

- **Feature / Change name:** Path11 MAP-W3 — Stale standards-link re-score + Assist audit-trail honesty helper
- **User goal:** When question text or standards library version changes, accepted Assist links become stale and authors are prompted to re-run Assist — with an audit trail of mapping decisions — never faux live multi-scheme chips.
- **In scope:** Pure FE helper (fingerprint, stale mark, re-score honesty, Assist re-run trail) + vitest
- **Out of scope:** Wiring into Inspection/Competency builders (#1079); live Assist Map accept chips API; Alembic
- **Feature flag / kill switch:** N/A — revert commit

## 2) Impact Map (what changed)

| Surface | Before | After |
|---------|--------|-------|
| Standards link freshness | No shared stale model | Hash(question text) + library version → stale |
| Assist re-run | Implicit / none | `assist_rerun` + `marked_stale` trail entries |
| Multi-scheme accept chips | N/A in this lane | `assistMapLive: false` honesty preserved |

## 3) Compatibility & Data Safety

- **Compatibility strategy:** FE-only pure helper; adopters wire later (MAP-W2 builders / Audit builder)
- **Breaking changes:** None
- **Rollback strategy:** Revert squash merge

## 4) Acceptance Criteria (AC)

- [x] AC-01: Fingerprint stable across whitespace/case; changes when question text changes
- [x] AC-02: Library version drift marks links stale (`library_version_changed` / `both`)
- [x] AC-03: `markStaleLinks` flips accepted → stale and records `marked_stale` trail
- [x] AC-04: `computeRescoreHonesty` sets `needsAssistRerun` and keeps `assistMapLive` false
- [x] AC-05: `appendAssistRerunTrail` records reconfirm Assist audit trail
- [x] AC-06: Zero overlap with #1079 file allowlist; no Layout/App/client/Alembic

## 5) Testing Evidence

- [x] Vitest — `mapW3StaleRescoreHonesty`
- [ ] CI green — this PR

## 6) Critical Journeys Verified (CUJ)

- [x] CUJ-01 (unit): Edit question text → accepted link stale → prompt re-suggest
- [x] CUJ-02 (unit): Library bump → stale → `assist_rerun` trail appendable
- [ ] CUJ-03 (manual follow-on): Wire helper into builder after #1079 lands

## 7) Observability & Ops

- **Playwright hooks:** N/A this PR (helper-only; adopters add `map-w3-*` hooks on wire-up)
- **Logs:** No change
- **Metrics:** No change
- **Alerts:** No change

## 8) Release Plan

1. Draft PR → CI green (Change Ledger + required checks)
2. Squash-merge after review when required checks green (human — **do not merge from this lane**)
3. Follow-on: adopt helper from Inspection/Competency/Audit builders once #1079 merges

## 9) Rollback Plan

1. Revert squash commit on `main`
2. Redeploy previous SHA
- **Rollback trigger:** Stale/rescore honesty regression after wire-up
- **Rollback steps:** Revert squash commit; redeploy previous SHA
- **Owner:** Platform team

## 10) Evidence Pack (links)

- PR diff + vitest proofs in this branch
- Living tracker checklist id **MAP-W3**

## 11) Gate Checklist

- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** Path claim exclusive (new helper + tests + ledger only)
- [x] **Gate 2:** Local vitest green
- [ ] **Gate 3:** Required CI green on PR
- [ ] **Gate 4:** Squash-merge to main (serial tip LIVE)
- [ ] **Gate 5:** Adopt + smoke after #1079 (builder wire-up follow-on)

## Test plan

- [x] `cd frontend && npx vitest run src/pages/__tests__/mapW3StaleRescoreHonesty.test.ts`
- [ ] Manual follow-on after adopt: edit question text on builder → stale chip → Re-suggest → trail shows `assist_rerun`
