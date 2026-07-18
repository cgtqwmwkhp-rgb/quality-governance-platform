# Change Ledger (CL-CLINIC-ASSURANCE-COMPLIANCE-HARDEN)

## File allowlist (exclusive)
- `frontend/src/pages/IMSDashboard.tsx`
- `frontend/src/pages/UVDBAudits.tsx`
- `frontend/src/pages/complianceAutomationHelpers.ts`
- `frontend/src/pages/__tests__/IMSDashboard.test.tsx`
- `frontend/src/pages/__tests__/UVDBAudits.test.tsx`
- `frontend/src/pages/__tests__/ComplianceAutomation.test.tsx`
- `frontend/src/pages/__tests__/complianceAutomationHelpers.test.ts`
- `scripts/governance/pr_body_clinic_assurance_compliance_harden.md`

**Zero overlap** with forbidden paths: Layout.tsx, App.tsx, Audits.tsx, AuditExecution.tsx, client.ts, Alembic, en.json (unless already claimed elsewhere).

## 1) Summary
- **Feature / Change name:** Assurance + Compliance clinic harden — remove demo/dead-end surfaces
- **User goal:** Operators trust IMS Overview / Monitoring / UVDB CTAs — no fake activity, no `/ 0` KPI targets, scheduled audits hand off to the board, UVDB export discloses unfinished work.
- **In scope:** FE honesty + live KPI/activity wiring; Monitoring handoff paths; UVDB export disclosure; vitest; Change Ledger
- **Out of scope:** Wire UVDB protocol export / Planet Mark PDF-XLSX packs; seed ISMS Annex A; Document Control draft→publish CUJ; Standards catalog seed; route/tab Playwright harness hardening
- **Feature flag / kill switch:** N/A — revert commit

## 2) Impact Map (what changed)
- **Frontend:** IMS Overview KPIs + Recent Activity; ISMS domain empty honesty; UVDB export honesty; Monitoring scheduled/overdue → `/audits?view=kanban`
- **Backend / APIs / DB / jobs:** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive UI honesty; Monitoring CTA targets change for scheduled/overdue only
- **Breaking changes:** None
- **Rollback strategy:** Revert commit

## 4) Acceptance Criteria (AC)
- [x] AC-01: IMS Overview never shows `Minor NC #2024-015` or hardcoded Open Actions `12 / 0`
- [x] AC-02: Overview KPIs/activity derive from dashboard API / audit schedule with honesty copy
- [x] AC-03: ISMS domain grid does not invent 0/37 placeholder rows when domains empty
- [x] AC-04: Monitoring scheduled/overdue Open → Audits kanban; in_progress Continue → execute
- [x] AC-05: UVDB Export Protocol stays disabled with visible honesty (not a silent dead button)
- [x] AC-06: Vitest covers IMS overview honesty, monitoring handoff helpers, UVDB honesty

## 5) Testing Evidence
- [x] `cd frontend && npx vitest run src/pages/__tests__/IMSDashboard.test.tsx src/pages/__tests__/complianceAutomationHelpers.test.ts src/pages/__tests__/ComplianceAutomation.test.tsx src/pages/__tests__/UVDBAudits.test.tsx` — 51 passed
- [ ] CI — linked after PR creation

## 6) Critical Journeys Verified (CUJ)
- [x] **CUJ-01:** IMS Overview — live schedule activity or honest empty
- [x] **CUJ-02:** Monitoring Scheduled Audits — scheduled Open lands on kanban
- [x] **CUJ-03:** UVDB header — export CTA discloses unfinished

## 7) Observability & Ops
- No change

## 8) Release Plan
- **Staging / prod post-deploy:** Spot-check `/ims` Overview, `/compliance-automation` Scheduled Audits, `/uvdb` export honesty

## 9) Rollback Plan
- **Trigger:** Overview blank/error or Monitoring handoffs regress
- **Steps:** Revert commit, redeploy
- **Owner:** Platform team

## 10) Evidence Pack
- Clinic waves A/B (129 slots) + pure-goto re-verify of Compliance routes
- CI run(s): Linked after PR creation

---

# Gate Checklist
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** FE-only allowlist; no Layout/App/Alembic
- [ ] **Gate 2:** CI green
- [ ] **Gate 3:** Staging verification
- [ ] **Gate 4:** Canary N/A
- [x] **Gate 5:** Production verification plan ready
