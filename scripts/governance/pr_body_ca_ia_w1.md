# Change Ledger (CL-CA-IA-W1)

## File allowlist (exclusive)

- `frontend/src/pages/ComplianceAutomation.tsx`
- `frontend/src/pages/complianceAutomationHelpers.ts`
- `frontend/src/pages/__tests__/ComplianceAutomation.test.tsx`
- `frontend/src/pages/__tests__/complianceAutomationHelpers.test.ts`
- `frontend/src/i18n/locales/en.json`
- `frontend/src/i18n/locales/cy.json`
- `scripts/governance/pr_body_ca_ia_w1.md`

**Zero overlap** with parallel lanes: Audits board honesty, Layout spine, App.tsx, client.ts, api/__init__.py.

## 1) Summary

- **Feature / Change name:** Path11 CA-IA-W1 — Monitoring spoke honesty (certificates, audits, page copy)
- **User goal:** Operators on `/compliance-automation` never see invented certificate, scheduled-audit, or score rows when live APIs return empty; page title/subtitle reads **Monitoring** without touching nav spine.
- **In scope:** Honest empty states for regulatory, certificates, scheduled audits, and score tabs; page-level i18n title/subtitle + empty copy; helper extraction + vitest
- **Out of scope:** Layout.tsx nav rename; schedule→Audits migration; wiring Add Certificate / Schedule Audit / Mark Reviewed CTAs
- **Feature flag / kill switch:** N/A — revert commit

## 2) Impact Map (what changed)

| Surface | Before | After |
|---------|--------|-------|
| Page header | Hardcoded "Compliance Automation" | i18n `compliance.automation.title` → **Monitoring** |
| Certificates tab | Blank list shell when API empty | Honest empty state — no sample rows |
| Scheduled Audits tab | Blank list shell when API empty | Honest empty state — points to Audits module |
| Regulatory tab | Blank when no updates | Honest empty state |
| Score tab | Already honest (#1048) | i18n empty copy + regression tests |
| Helpers | Inline in page | `complianceAutomationHelpers.ts` (unit tested) |

## 3) Compatibility & Data Safety

- **Compatibility strategy:** Additive UX — empty states only when arrays are empty
- **Breaking changes:** None (route unchanged; nav label unchanged until W1c)
- **Rollback strategy:** Revert squash merge

## 4) Acceptance Criteria (AC)

- [x] AC-01: Score tab remains honest (no demo ISO scores/gaps) — regression from #1048
- [x] AC-02: Certificates tab shows honest empty when `certificates.length === 0`
- [x] AC-03: Scheduled Audits tab shows honest empty when `audits.length === 0`
- [x] AC-04: Regulatory tab shows honest empty when `updates.length === 0`
- [x] AC-05: Page title/subtitle use Monitoring i18n keys (not Layout spine)
- [x] AC-06: Vitest covers empty states + live score breakdown

## 5) Testing Evidence

- [x] Vitest — `ComplianceAutomation.test.tsx`, `complianceAutomationHelpers.test.ts`
- [ ] CI green — this PR

## 6) Critical Journeys Verified (CUJ)

- [x] CUJ-01: Fresh tenant — Monitoring page loads with 0% score and empty certificate/audit tabs
- [x] CUJ-02: Score tab with API categories — live breakdown renders (no placeholders)
- [x] CUJ-03: Page header reads Monitoring while sidebar still shows legacy nav label (until W1c)

## 7) Observability & Ops

- **Playwright hooks:** `monitoring-regulatory-empty`, `monitoring-certificates-empty`, `monitoring-audits-empty`, `monitoring-score-breakdown-empty`, `monitoring-score-gaps-empty`

## 8) Release Plan

1. Draft PR → CI green
2. Squash-merge after review (human — **do not merge from this lane**)
3. Staging tip smoke `/compliance-automation`

## 9) Rollback Plan

1. Revert squash commit on `main`
2. Redeploy previous SHA

## 10) Evidence Pack (links)

- CI run(s): Linked after PR creation
- Builds on: #1048 Score honesty, #1043 RIDDOR/Watch honesty

---

# Follow-ons (CA-IA-W1b/c/d — out of scope for this PR)

| Slice | Scope | Rationale |
|-------|-------|-----------|
| **CA-W1b** | Migrate Scheduled Audits tab to authoritative **Audits** module (deep-link, de-dupe schedule API vs audit runs) | Large spine/routing touch — separate PR |
| **CA-W1c** | **Layout.tsx** nav label `nav.compliance_automation` → "Monitoring" | Shared spine — deferred |
| **CA-W1d** | Wire Add Certificate, Schedule Audit, Mark Reviewed, Run Gap Analysis CTAs to real flows | Requires API/form work beyond honesty |
| **CA-W1e** | Full i18n sweep of tab labels and KPI cards on Monitoring page | Nice-to-have after W1c nav alignment |

---

# Gate Checklist (must be complete before merge)

- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** Exclusive allowlist respected (no Layout/App/client/api init)
- [ ] **Gate 2:** CI green
- [ ] **Gate 3:** Staging verification complete
- [ ] **Gate 4:** Canary healthy (if used)
- [x] **Gate 5:** Production verification plan ready

## Test plan

- [ ] `cd frontend && npx vitest run src/pages/__tests__/ComplianceAutomation.test.tsx src/pages/__tests__/complianceAutomationHelpers.test.ts`
- [ ] Manual: `/compliance-automation` with empty tenant — certificates/audits/score show honest empty, header reads Monitoring
- [ ] Manual: sidebar nav still shows "Compliance Automation" until W1c (expected)
