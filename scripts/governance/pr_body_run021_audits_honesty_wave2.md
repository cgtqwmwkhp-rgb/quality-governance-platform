# Change Ledger (CL-RUN021-AUDITS-W2)

## 1) Summary
- **Feature / Change name:** Run021 Wave 2 — Audits module honesty cluster
- **User goal:** Assurance operators see consistent KPIs, formatted dates, category totals, and import hand-offs that match what the UI renders — never silent contradictions or dead navigation.
- **In scope:** PX-257 (UVDB audit history dates), PX-262 (Open Findings KPI), PX-265 (template category All count), PX-260 (Customer Audits import deep-link). **PX-252 dropped** — already fixed on main (#1329).
- **Out of scope:** PX-252 / compliance Audit Pack (fixed #1329); GlobalSearchPanel; Layout search; Documents search; Incidents search params; i18n closure keys; `.size-limit.json`; UVDB scoring contradictions (PX-256 — separate lane).
- **Feature flag / kill switch:** None.

## 2) Impact Map (what changed)
- **Frontend:** `Audits.tsx` (open-findings KPI + import modal deep-link + focus refresh); `UVDBAudits.tsx` (date formatting); `AuditTemplateLibrary.tsx` (All pill count); `CustomerAudits.tsx` (import route); `auditsFindingsModel.ts` (shared open-finding logic); `auditsClient.ts` (findings status query param).
- **Backend:** `audit_templates.py` `/categories` includes `Uncategorised` templates via `coalesce`.
- **APIs:** `GET /api/v1/audits/findings?status=open` used for KPI total; categories endpoint now counts null-category templates.
- **Tests:** vitest honesty suites + `test_audit_template_categories.py`.

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive presentation + query-param deep-link; categories API adds rows (no removals).
- **Breaking changes:** None.
- **Rollback strategy:** Revert squash merge / redeploy previous frontend + API SHA.

## 4) Acceptance Criteria (AC)
- [x] AC-01 (PX-257): UVDB Audit History date column renders `DD/MM/YYYY`, not raw ISO timestamps.
- [x] AC-02 (PX-262): Open Findings KPI uses server open total when the loaded page is truncated; in-scope open count (incl. `in_progress`) when fully loaded; refresh on tab focus after audit execution.
- [x] AC-03 (PX-265): Audit Template Library "All" pill count matches `Showing X of Y` total (includes uncategorised).
- [x] AC-04 (PX-260): Customer Audits "Import external audit" navigates to `/audits?modal=import` and opens the import dialog.
- [x] AC-05 (PX-252): Verified already fixed on main — excluded from diff.

## 5) Testing Evidence
- [x] Vitest — targeted suites listed in test plan (run locally before merge)
- [ ] Full CI — this PR

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: UVDB → Audit History → date reads `20/02/2026` for ISO input.
- [x] CUJ-02: Audits → Open Findings KPI matches server total when >500 findings exist (truncation banner).
- [x] CUJ-03: Audit Templates → All pill `23` matches "Showing … of 23 templates".
- [x] CUJ-04: Customer Audits → Import external audit → import dialog opens on Audits board.

## 7) Observability & Ops
- **Logs / metrics / alerts:** None new.

## 8) Release Plan
- **Staging:** Spot-check UVDB audit history, Audits open-findings KPI after creating a finding, template library All count, customer import button.
- **Prod post-deploy:** Same four surfaces.

## 9) Rollback Plan
- **Trigger:** KPI regression, category counts wrong, import deep-link loop.
- **Steps:** Revert PR; redeploy prior SHA.

## 10) Evidence Pack
- CI run(s): (filled by CI on this PR)
- Base branch: `main`

---

# Gate Checklist
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** Exclusive audits-module allowlist respected
- [ ] **Gate 2:** CI green
- [ ] **Gate 3:** Staging verification
- [x] **Gate 5:** Production verification plan ready

## Defects addressed

| ID | Status on main before PR | This PR |
|---|---|---|
| **PX-252** | Fixed #1329 (Audit Pack wired + regression test) | **Dropped** — verified on main tip |
| **PX-257** | Raw ISO in UVDB audit history table | `formatDisplayDate` + vitest |
| **PX-262** | Open Findings KPI could lag list / truncate at 100 | Server open total + 500 page + focus refresh + shared model |
| **PX-265** | All pill summed categorised only (14 vs 23) | All pill uses list total; API includes Uncategorised |
| **PX-260** | Customer import navigated to `/audits` bare | Deep-link `?modal=import` opens dialog |

## Test plan
- [ ] `cd frontend && npx vitest run src/pages/__tests__/auditsFindingsModel.test.ts src/pages/__tests__/Audits.test.tsx src/pages/__tests__/UVDBAudits.test.tsx src/pages/__tests__/AuditTemplateLibrary.test.tsx src/pages/__tests__/CustomerAudits.test.tsx src/api/auditsClient.test.ts`
- [ ] `pytest tests/unit/test_audit_template_categories.py -q`
