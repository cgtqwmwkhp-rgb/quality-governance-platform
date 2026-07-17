# Change Ledger (CL-RR-CUJ-GATE)

## File allowlist (exclusive)
- `docs/evidence/RR_CUJ_GATE_2026-07-17.md` (NEW)
- `scripts/governance/pr_body_rr_cuj_gate.md` (NEW)

**Zero overlap** with product lanes (RiskProfile feature work, Planet Mark, Admin, Alembic, App.tsx). Docs/evidence only.

## 1) Summary
- **Feature / Change name:** RR-CUJ gate — Risk Profile lane verification against tip
- **User goal:** Record pass/fail for nine Risk Profile CUJs with code + test evidence and a staging UAT checklist; mark gate complete without inventing product changes.
- **In scope:** Evidence pack + this ledger on tip `2077f30e`
- **Out of scope:** Product/runtime changes; Governance Framework canvas; Action Plan→CAPA import (deferred by design)
- **Feature flag / kill switch:** N/A — documentation only
- **Stack:** Tip `2077f30e` (all RR waves + Admin + PM-PDF + PM-W1b + kill-popup)

## 2) Impact Map (what changed)
- **Frontend / Backend / APIs / DB:** None
- **Documentation:** `docs/evidence/RR_CUJ_GATE_2026-07-17.md` — CUJ table + staging UAT checklist
- **Workflows:** Local Vitest + pytest evidence recorded in pack

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive docs only
- **Breaking changes:** None
- **Migration plan:** N/A
- **Rollback strategy (DB):** N/A — revert docs commit

## 4) Acceptance Criteria (AC)
- [x] AC-01: Nine Risk Profile CUJs evaluated pass/fail/blocked with evidence pointers
- [x] AC-02: Targeted Vitest + pytest run on tip `2077f30e` (37 + 83 passed)
- [x] AC-03: Staging UAT checklist included
- [x] AC-04: No product fix PRs required (no CUJ-blocking bugs found)

## 5) Testing Evidence (link to runs)
- [x] Frontend Vitest — `RiskProfile`, `RiskRegister`, `riskRegisterClient`, `riskRegisterPaths`, `RiskHeatMap` (37 passed, local tip)
- [x] Unit tests — risk profile / notes / actions+upstream / service / import / SLT / heatmap / calendar feed (83 passed, local tip)
- [ ] Staging UAT — checklist in evidence pack (operator)

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-1: Register → profile, no detail popup (#1102)
- [x] CUJ-2: Assess → history + trend + activity
- [x] CUJ-3: Add note → notes timeline
- [x] CUJ-4: Create CAPA with `returnTo` (#1101)
- [x] CUJ-5: Upstream links panel
- [x] CUJ-6: Calendar `next_review` → profile (#1091)
- [x] CUJ-7: Owner User picker (#1101)
- [x] CUJ-8: Close / status honesty
- [x] CUJ-9: Excel Register dry-run/commit (#1093); Action Plan→CAPA deferred

## 7) Observability & Ops
- N/A — gate documentation; no runtime change

## 8) Release Plan (Local -> Staging -> Prod)
- Docs-only merge; no deploy required for behaviour
- Staging operators may execute the UAT checklist against tip after RR deploy

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** N/A (docs)
- **Rollback steps:** Revert squash-merge
- **Owner:** Platform team

## 10) Evidence Pack (links)
- Gate pack: `docs/evidence/RR_CUJ_GATE_2026-07-17.md`
- Tip: `2077f30e`

## 11) Merged PR cross-refs
- #1102 kill detail popup; #1101 CAPA/upstream/owner; #1091 calendar reviews; #1093 Excel import; #1095 notes/activity; #1092 assess/trend; #1100 SLT; prior RR-P0 profile

---

## PR body

### Summary
- RR-CUJ gate complete on tip `2077f30e`: nine Risk Profile CUJs **PASS** via automated Vitest/pytest evidence.
- Adds evidence pack + staging UAT checklist; no product code changes.

### Test plan
- [x] Local Vitest risk suites (37)
- [x] Local pytest risk/calendar suites (83)
- [ ] Optional: operator staging UAT checklist in evidence pack
