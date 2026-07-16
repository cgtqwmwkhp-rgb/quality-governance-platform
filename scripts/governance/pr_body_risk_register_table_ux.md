# Change Ledger (RISK-REGISTER-TABLE-UX)

## 1) Summary
- **Feature / Change name:** Risk Register hero filters + table UX (Active + Import triage)
- **User goal (1–2 lines):** Click hero KPIs to filter; understand columns via tooltips; see/edit owner names; View/Edit and triage Accept/Reject work; Export/Add Risk functional.
- **In scope:** Hero filter cards; column header tooltips; Inherent=Gross / Residual=Net labels; owner edit; detail dialog; CSV export; create risk dialog; shared Active + Import triage chrome.
- **Out of scope:** Heat map popup (PR #1040); new backend tables.
- **Feature flag / kill switch:** None — FE UX.

## 2) Impact Map (what changed)
- **Frontend:** `frontend/src/pages/RiskRegister.tsx`; `frontend/src/pages/__tests__/RiskRegister.test.tsx`; heat map a11y follow-up in `RiskHeatMap.tsx`.
- **Backend:** None (uses existing update/create APIs).
- **APIs:** None new.
- **Schemas/contracts:** None.
- **Database:** None.
- **Workflows/jobs/queues:** None.
- **Config/env/flags:** None.
- **Dependencies:** None.

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Client-side hero filter on loaded list; owner update via existing PUT.
- **Tolerant reader / strict writer applied?** N/A.
- **Breaking changes:** None.
- **Migration plan:** None.
- **Rollback strategy (DB):** Not applicable — revert deploy.

## 4) Acceptance Criteria (AC)
- [x] **AC-01:** Hero KPI cards toggle filters for Total/Critical/High/Medium/Outside appetite/Overdue in Active and Import triage.
- [x] **AC-02:** Column headers have explanatory tooltips; Inherent labeled Gross; Residual labeled Net.
- [x] **AC-03:** Owner shows name or Unassigned; edit via dialog persists `risk_owner_name`.
- [x] **AC-04:** View/Edit open detail dialog; Import triage keeps Accept/Reject and adds View.

## 5) Testing Evidence (link to runs)
- [x] `npx vitest run src/pages/__tests__/RiskRegister.test.tsx src/components/risk/__tests__/RiskHeatMap.test.tsx` — passed locally.
- [ ] Full CI suite: pending PR CI.

## 6) Critical Journeys Verified (CUJ)
- [x] **CUJ-01:** Active register → click Overdue hero → table filters → View/Edit owner → Save.
- [x] **CUJ-02:** Import triage → same hero filter + Accept/Reject still work; View opens detail.

## 7) Observability & Ops
- **Logs:** None new.
- **Metrics:** None new.
- **Alerts:** None.
- **Runbook updates:** None.

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Exercise Active + Import triage hero filters, tooltips, owner edit, Export CSV, Add Risk.
- **Canary plan:** Normal staging → prod path.
- **Prod post-deploy checks:** tip==LIVE; smoke register + triage actions.

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Filters break list, dialogs block triage Accept/Reject, or create/update errors.
- **Rollback steps:** Revert this PR and redeploy prior release.
- **Owner:** Quality Governance Platform team.

## 10) Evidence Pack (links)
- **PR:** (filled after create)
- **CI run(s):** Added by GitHub Actions.
- **Staging deploy evidence:** Pending.
- **Canary evidence:** Pending.

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock, acceptance criteria, and Change Ledger complete.
- [x] **Gate 1:** FE-only; no migration.
- [x] **Gate 2:** Local unit tests pass.
- [ ] **Gate 3:** PR CI green.
- [ ] **Gate 4:** Staging verification complete.
- [ ] **Gate 5:** Production verification complete.
