# Change Ledger (CL-CA-W1b-SCORE-TAB-KILL)

**Path claim:** `path11/ca-w1b-score-tab-kill`

## File allowlist (exclusive)

- `frontend/src/pages/ComplianceAutomation.tsx`
- `frontend/src/pages/complianceAutomationHelpers.ts`
- `frontend/src/pages/__tests__/ComplianceAutomation.test.tsx`
- `frontend/src/pages/__tests__/complianceAutomationHelpers.test.ts`
- `frontend/src/i18n/locales/en.json`
- `frontend/src/i18n/locales/cy.json`
- `scripts/governance/pr_body_ca_w1b_score_tab_kill.md`

**Zero overlap** with parallel lanes: AUD-PHOTO-03 (`AuditExecution*`), EVD-02 (`PortalIncidentForm*`), CMP-08 (`ComplaintDetail*`), `IMSDashboard*` / `imsMapHonesty*` (#1074), Layout/App/client.ts, `api/__init__.py`, Alembic.

## 1) Summary

- **Feature / Change name:** Path11 CA-W1b — Kill Monitoring Score tab + KPI handoff
- **User goal:** Operators no longer see a Score tab with faux bars/gaps; the overview KPI chip stays honest and hands off to IMS / Compliance Evidence for live scores.
- **In scope:** Remove Score tab UI; retire breakdown/gaps panels; KPI handoff links; helpers + vitest; minimal i18n
- **Out of scope:** Backend score API; Layout nav rename; IMS map internals
- **Feature flag / kill switch:** N/A — revert commit

## 2) Impact Map (what changed)

| Surface | Before | After |
|---------|--------|-------|
| Score tab | Breakdown bars + key gaps panels | Removed |
| Score overview KPI | % / empty honesty only | Same KPI + retired-tab copy + links to `/ims` and `/compliance` |
| Monitoring subtitle | Mentioned compliance scoring | Points scores to IMS / Compliance Evidence |

## 3) Compatibility & Data Safety

- **Compatibility strategy:** UI-only — still reads score API for KPI chip
- **Breaking changes:** None (route unchanged; Score tab control removed)
- **Rollback strategy:** Revert squash merge

## 4) Acceptance Criteria (AC)

- [x] AC-01: Monitoring has no Compliance Score tab control
- [x] AC-02: Score breakdown / key-gaps panels are gone (no faux bars)
- [x] AC-03: KPI chip links to `/ims` and `/compliance`
- [x] AC-04: Empty score still shows `—` / no live score copy (CA-W1c preserved)
- [x] AC-05: Vitest covers tab retirement + handoff paths

## 5) Testing Evidence

- [x] Vitest — `ComplianceAutomation.test.tsx`, `complianceAutomationHelpers.test.ts` (27 passed)
- [ ] CI green — this PR

## 6) Critical Journeys Verified (CUJ)

- [x] CUJ-01: Fresh tenant Monitoring — Score tab absent; KPI empty honesty + handoffs
- [x] CUJ-02: Tenant with live categories — KPI shows % without Score tab bars

## 7) Observability & Ops

- **Playwright hooks:** `monitoring-score-overview`, `monitoring-score-tab-retired`, `monitoring-score-handoff-ims`, `monitoring-score-handoff-evidence`

## 8) Release Plan

1. Draft PR → CI green
2. Squash-merge after review (human — **do not merge from this lane**)
3. Staging smoke `/compliance-automation` — no Score tab; KPI handoffs work

## 9) Rollback Plan

1. Revert squash commit on `main`
2. Redeploy previous SHA

## 10) Evidence Pack (links)

- CI run(s): Linked after PR creation
- Builds on: CA-W1c (#1071), MAP-W1 tip (#1074)

---

# Gate Checklist (must be complete before merge)

- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** Exclusive allowlist respected (ComplianceAutomation* + soft en/cy only)
- [ ] **Gate 2:** CI green
- [ ] **Gate 3:** Staging verification complete
- [ ] **Gate 4:** Canary healthy (if used)
- [x] **Gate 5:** Production verification plan ready

## Test plan

- [ ] `cd frontend && npx vitest run src/pages/__tests__/ComplianceAutomation.test.tsx src/pages/__tests__/complianceAutomationHelpers.test.ts`
- [ ] Manual: `/compliance-automation` — no Score tab; Open IMS / Compliance Evidence links
