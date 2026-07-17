# Change Ledger (CL-CA-W1a)

## File allowlist (exclusive)

- `frontend/src/i18n/locales/en.json`
- `frontend/src/i18n/locales/cy.json`
- `frontend/src/pages/IMSDashboard.tsx`
- `frontend/src/pages/__tests__/IMSDashboard.test.tsx`
- `scripts/governance/pr_body_ca_w1a.md`

**Zero overlap** with parallel lanes: `Layout.tsx` (unchanged — nav reads `nav.compliance_automation` i18n), `App.tsx`, `client.ts`, `api/__init__.py`, Alembic, `PlanetMark*` (#1065).

## 1) Summary

- **Feature / Change name:** Path11 CA-W1a — Rename Compliance Automation → Monitoring via i18n + IMS hub card
- **User goal:** Sidebar nav and IMS compliance hub show **Monitoring** (not “Compliance Automation” / “Monitoring & Certificates”) while route `/compliance-automation` stays stable.
- **In scope:** Flat i18n keys `nav.compliance_automation`, `ims.hub.monitoring.*`; IMS hub monitoring card wired to i18n; vitest regression
- **Out of scope:** `Layout.tsx` edit (deferred — not required because nav already uses `t('nav.compliance_automation')`); role/nav-gate fixes; backend rename
- **Feature flag / kill switch:** N/A — revert commit

## 2) Impact Map (what changed)

| Surface | Before | After |
|---------|--------|-------|
| Sidebar nav label | “Compliance Automation” (`nav.compliance_automation`) | **Monitoring** (same key, new copy) |
| IMS hub monitoring card | Hardcoded “Monitoring & Certificates” | **Monitoring** via `ims.hub.monitoring.title` |
| IMS hub card body | Hardcoded regulatory/cert/audit blurb | i18n `ims.hub.monitoring.description` (Audits-module honest wording) |
| Route / roles | `/compliance-automation` | Unchanged |

## 3) Compatibility & Data Safety

- **Compatibility strategy:** Copy-only — no API, route, or permission changes
- **Breaking changes:** None
- **Rollback strategy:** Revert squash merge

## 4) Acceptance Criteria (AC)

- [x] AC-01: `nav.compliance_automation` resolves to “Monitoring” in `en.json`
- [x] AC-02: Welsh locale updates `nav.compliance_automation` to “Monitro”
- [x] AC-03: IMS compliance hub monitoring card uses `ims.hub.monitoring.title` / `.description` (no hardcoded “Compliance Automation”)
- [x] AC-04: `Layout.tsx` untouched — nav picks up rename via existing `t('nav.compliance_automation')`
- [x] AC-05: Vitest confirms hub card renders i18n monitoring title key

## 5) Testing Evidence

- [x] Vitest — `IMSDashboard.test.tsx`
- [ ] CI green — this PR

## 6) Critical Journeys Verified (CUJ)

- [x] CUJ-01: Operator opens IMS → Compliance hub → monitoring card reads “Monitoring” and navigates to `/compliance-automation`
- [x] CUJ-02: Operator sees sidebar item “Monitoring” (was “Compliance Automation”) without route change

## 7) Observability & Ops

- **Playwright hooks:** existing `compliance-hub-monitoring` unchanged

## 8) Release Plan

1. Draft PR → CI green
2. Squash-merge after review (human — **do not merge from this lane**)
3. Staging smoke: sidebar label + IMS hub card copy

## 9) Rollback Plan

1. Revert squash commit on `main`
2. Redeploy previous SHA

## 10) Evidence Pack (links)

- CI run(s): Linked after PR creation
- Builds on: CA-W1b scheduled-audits handoff + CA-W1d Changes inbox (#1064 tip)

---

# Gate Checklist (must be complete before merge)

- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** Exclusive allowlist respected (no Layout/App/client/api init/Alembic)
- [ ] **Gate 2:** CI green
- [ ] **Gate 3:** Staging verification complete
- [ ] **Gate 4:** Canary healthy (if used)
- [x] **Gate 5:** Production verification plan ready

## Test plan

- [ ] `cd frontend && npx vitest run src/pages/__tests__/IMSDashboard.test.tsx`
- [ ] Manual: sidebar shows “Monitoring”
- [ ] Manual: `/ims` hub monitoring card title = “Monitoring”
