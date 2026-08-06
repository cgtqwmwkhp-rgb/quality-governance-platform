# Change Ledger (CL-W10-WORKFLOW-REGISTRY-COMPLIANCE-SCHEDULE)

## 1) Summary
- **Feature / Change name:** W10 WORKFLOW_REGISTRY — compliance-schedule journey
- **User goal (1–2 lines):** Register the admin compliance schedule register as a P1 UX coverage workflow so the gate can exercise `/compliance-schedule` like peer modules.
- **In scope:** `docs/ops/WORKFLOW_REGISTRY.yml` entry `compliance-schedule` + summary counts + `last_updated`
- **Out of scope:** Playwright suite changes, feature flag enablement, Export Center, API changes
- **Feature flag / kill switch:** Journey assumes admin JWT; live env still needs `COMPLIANCE_SCHEDULE_ENABLED` / FE flag for the page to be useful (same as other gated modules)

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** None
- **Backend (handlers/services):** None
- **APIs (endpoints changed/added):** None (workflow declares expected GETs only)
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** None
- **Database (migrations/entities/indexes):** None
- **Workflows/jobs/queues (if any):** `docs/ops/WORKFLOW_REGISTRY.yml` — new P1 `compliance-schedule`
- **Config/env/flags:** None
- **Dependencies (added/removed/updated):** None
- **Tests:** Registry YAML validated via `scripts/validate_registries.py` freshness keys

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive registry entry; existing workflows unchanged
- **Tolerant reader / strict writer applied?** N/A
- **Breaking changes:** None
- **Migration plan:** None
- **Rollback strategy (DB):** N/A — revert file

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| UX workflow coverage for obligations register | Not in WORKFLOW_REGISTRY | P1 `compliance-schedule` with route + testid + expected APIs |
| Registry freshness | `last_updated: 2026-07-26` | `2026-08-06` |
| Summary counts | 11 total / 4 P1 | 12 total / 5 P1 |

## 4) Acceptance Criteria (AC)
- [x] AC-01: `workflowId: compliance-schedule` present under `p1_workflows`
- [x] AC-02: Steps use `/compliance-schedule` and `[data-testid='compliance-schedule-page']`
- [x] AC-03: Summary `total_workflows` / `p1_workflows` counts match list lengths
- [x] AC-04: `last_updated` bumped

## 5) Testing Evidence (link to runs)
- [ ] Lint
- [ ] Typecheck
- [ ] Build
- [x] Unit tests — N/A (docs-only); YAML parse + summary counts checked locally
- [ ] Integration tests
- [ ] Contract tests (if applicable)
- [ ] E2E Smoke (critical journeys)

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Registry YAML loads; `compliance-schedule` listed in P1
- [x] CUJ-02: Summary counts equal workflow list lengths (12 / 5 / 5 / 2)

## 7) Observability & Ops
- **Logs:** N/A
- **Metrics:** N/A
- **Alerts:** N/A
- **Runbook updates:** N/A

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** UX coverage gate can discover the new workflow id after merge
- **Canary plan:** N/A
- **Prod post-deploy checks:** Docs-only; no runtime deploy required for behaviour change

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** UX coverage gate false failures from the new journey
- **Rollback steps:** Revert this squash commit on `main`
- **Owner:** Platform team

## 10) Evidence Pack (links)
- CI run(s): Linked after PR creation
- Staging deploy evidence: N/A (docs-only)
- Canary evidence (if applicable): N/A

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved (as applicable)
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete (evidence linked)
- [ ] **Gate 4:** Canary healthy (if used) (evidence linked)
- [x] **Gate 5:** Production verification plan + monitoring ready
