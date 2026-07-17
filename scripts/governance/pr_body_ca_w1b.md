# Change Ledger (CL-CA-W1b)

## File allowlist (exclusive)

- `frontend/src/pages/ComplianceAutomation.tsx`
- `frontend/src/pages/complianceAutomationHelpers.ts`
- `frontend/src/pages/__tests__/ComplianceAutomation.test.tsx`
- `frontend/src/pages/__tests__/complianceAutomationHelpers.test.ts`
- `frontend/src/i18n/locales/en.json`
- `frontend/src/i18n/locales/cy.json`
- `scripts/governance/pr_body_ca_w1b.md`

**Zero overlap** with parallel lanes: `Actions.tsx` (#1054 ACT-R3), `Audits.tsx` board honesty, Layout/App/client spines, `api/__init__.py`, Alembic.

## 1) Summary

- **Feature / Change name:** Path11 CA-W1b — Monitoring scheduled-audits handoff to authoritative Audits module
- **User goal:** Operators on `/compliance-automation` see upcoming audit **runs** from `auditsApi.listRuns`, deep-link to Audits workspace to schedule/continue, and never rely on the duplicate compliance-automation schedule feed.
- **In scope:** Replace `listScheduledAudits` with authoritative audit runs; handoff CTAs + row deep-links; overdue KPI from run due dates; helper extraction + vitest; minimal i18n
- **Out of scope:** `Audits.tsx` board changes; Layout nav rename (W1c); wiring Add Certificate / legacy schedule POST; backend API removal
- **Feature flag / kill switch:** N/A — revert commit

## 2) Impact Map (what changed)

| Surface | Before | After |
|---------|--------|-------|
| Data source | `complianceAutomationApi.listScheduledAudits()` (duplicate schedule table) | `auditsApi.listRuns(1, 100)` filtered to scheduled + in-progress |
| Scheduled Audits tab empty | Honest empty + text mention of Audits | Empty + **Schedule in Audits** CTA → `/audits?view=kanban` |
| Tab header CTA | Non-functional “Schedule Audit” button | **Open Audits** link to authoritative module |
| Run rows | Legacy schedule fields (frequency, standards) | Live run title/ref/scheme + **Open/Continue** → execute/import-review |
| Overdue KPI | From legacy schedule due dates | From overdue scheduled runs (past due, still scheduled) |
| Helpers | Score/format only | + run mapping, handoff paths, workspace deep-links (unit tested) |

## 3) Compatibility & Data Safety

- **Compatibility strategy:** Read path only — Monitoring reads existing audit runs; legacy schedule API untouched (unused by this page)
- **Breaking changes:** None (route unchanged; tenants with only legacy schedule rows and no audit runs see honest empty + Audits handoff)
- **Rollback strategy:** Revert squash merge

## 4) Acceptance Criteria (AC)

- [x] AC-01: Monitoring page does **not** call `listScheduledAudits`
- [x] AC-02: Scheduled Audits tab lists scheduled + in-progress runs from `auditsApi.listRuns`
- [x] AC-03: Empty state includes Audits handoff CTA (`/audits?view=kanban`)
- [x] AC-04: Each run row deep-links to `/audits/{id}/execute` or import-review for external imports
- [x] AC-05: Overdue KPI counts runs with past due date and status `scheduled`
- [x] AC-06: Vitest covers empty handoff, run rows, helper mapping

## 5) Testing Evidence

- [x] Vitest — `ComplianceAutomation.test.tsx`, `complianceAutomationHelpers.test.ts`
- [ ] CI green — this PR

## 6) Critical Journeys Verified (CUJ)

- [x] CUJ-01: Fresh tenant — Monitoring Scheduled Audits tab empty with Audits CTA (no legacy schedule rows)
- [x] CUJ-02: Tenant with scheduled/in-progress runs — rows render with Open/Continue links
- [x] CUJ-03: Operator clicks Open Audits — navigates to Audits kanban (authoritative schedule surface)

## 7) Observability & Ops

- **Playwright hooks:** `monitoring-audits-empty`, `monitoring-audits-empty-cta`, `monitoring-audits-schedule-link`, `monitoring-audit-run-{id}`

## 8) Release Plan

1. Draft PR → CI green
2. Squash-merge after review (human — **do not merge from this lane**)
3. Staging tip smoke `/compliance-automation` → Scheduled Audits tab

## 9) Rollback Plan

1. Revert squash commit on `main`
2. Redeploy previous SHA

## 10) Evidence Pack (links)

- CI run(s): Linked after PR creation
- Builds on: CA-IA-W1 Monitoring honesty (#1048 lineage)

---

# Follow-ons (CA-W1c/d/e — out of scope for this PR)

| Slice | Scope | Rationale |
|-------|-------|-----------|
| **CA-W1c** | **Layout.tsx** nav label `nav.compliance_automation` → "Monitoring" | Shared spine — deferred |
| **CA-W1d** | Wire Add Certificate, Mark Reviewed, Run Gap Analysis CTAs to real flows | Requires API/form work |
| **CA-W1e** | Full i18n sweep of tab labels and KPI cards on Monitoring page | Nice-to-have after W1c |
| **CA-W1f** | Retire backend `/compliance-automation/scheduled-audits` when no callers remain | Backend spine — separate lane |

---

# Gate Checklist (must be complete before merge)

- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** Exclusive allowlist respected (no Layout/App/client/api init/Audits.tsx/Actions.tsx)
- [ ] **Gate 2:** CI green
- [ ] **Gate 3:** Staging verification complete
- [ ] **Gate 4:** Canary healthy (if used)
- [x] **Gate 5:** Production verification plan ready

## Test plan

- [ ] `cd frontend && npx vitest run src/pages/__tests__/ComplianceAutomation.test.tsx src/pages/__tests__/complianceAutomationHelpers.test.ts`
- [ ] Manual: `/compliance-automation` with no audit runs — empty + Schedule in Audits CTA
- [ ] Manual: tenant with scheduled run — row links to `/audits/{id}/execute`
- [ ] Manual: overdue scheduled run — KPI badge > 0
