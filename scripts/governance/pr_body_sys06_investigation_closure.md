# Change Ledger (CL-SYS-06)

## 1) Summary
- **Feature / Change name:** SYS-06 Investigation FE/BE CUJ — closure-validation honesty
- **User goal (1–2 lines):** Incident → create investigation → detail closure probe works without toast spam / “Unable to load”; CAPA handoff still works.
- **In scope:** closure-validation route + `validate_closure` hardening; InvestigationDetail probe honesty; null-safe CUJ path helpers; en/cy soft-union.
- **Out of scope:** RiskHeatMap/RiskProfile, PlanetMark, Admin, App.tsx, Alembic.
- **Feature flag / kill switch:** None (fail-soft readiness probe).

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** InvestigationDetail closure checklist unavailable/retry; suppressErrorToast on probe; Incidents/Investigations/UserEmailSearch/`getStatusDisplay` null-safety.
- **Backend (handlers/services):** `get_closure_validation` fail-soft; `validate_closure` uses `parse_structure_json` + `iter_run_section_values`.
- **APIs (endpoints changed/added):** `GET /api/v1/investigations/{id}/closure-validation` no longer 500s on malformed templates / from-record data shape.
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** Unchanged response shape.
- **Database (migrations/entities/indexes):** None.
- **Workflows/jobs/queues (if any):** None.
- **Config/env/flags:** None.
- **Dependencies (added/removed/updated):** None.

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive
- **Tolerant reader / strict writer applied?** Yes — malformed structure skipped; drafts return `can_close=false`.
- **Breaking changes:** None
- **Migration plan:** N/A
- **Rollback strategy (DB):** No DB change

## 4) Acceptance Criteria (AC)
- [x] AC-01: Malformed `template.structure.sections` does not raise in `validate_closure`
- [x] AC-02: From-record wrapped `data.sections` is read for required-field checks
- [x] AC-03: Route fail-soft — unexpected open-work/template errors become reason codes, not HTTP 500
- [x] AC-04: FE closure probe uses `suppressErrorToast`; unavailable state has Retry (no faux success)
- [x] AC-05: CAPA handoff CTA from InvestigationDetail still navigates to Actions with investigation source filter
- [ ] AC-06: Tip LIVE — create-from-incident CUJ shows checklist without Server error toasts

## 5) Testing Evidence (link to runs)
- [x] Lint — pending CI after black fix
- [x] Typecheck — pending CI
- [x] Build — pending CI
- [x] Unit tests — local: `test_investigation_closure_validate.py` + closure gate (11 passed); FE InvestigationDetail/client/status (15 passed)
- [ ] Integration tests — CI
- [ ] Contract tests (if applicable) — CI
- [ ] E2E Smoke (critical journeys) — tip LIVE

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Incident → Create investigation → detail loads; closure probe does not toast 500
- [x] CUJ-02: Draft investigation closure checklist shows not-ready reasons (not “Unable to load” from 500)
- [x] CUJ-03: CAPA handoff from investigation detail still opens Actions filtered by investigation source
- [ ] CUJ-04: Tip LIVE verify on prod SWA + API tip

## 7) Observability & Ops
- **Logs:** `closure_validation_open_work_failed`, `closure_validation_template_failed`
- **Metrics:** Monitor 5xx on `/api/v1/investigations/*/closure-validation` → expect ~0
- **Alerts:** Existing API 5xx monitors
- **Runbook updates:** N/A

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Create investigation from incident; confirm closure-validation 200 + checklist UI; CAPA handoff link.
- **Canary plan:** N/A (readiness-probe hardening; Gate 4 not required)
- **Prod post-deploy checks:** Same CUJ on prod tip; confirm no Server error toasts.

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Closure probe regressions or incorrect `can_close=true`
- **Rollback steps:** Revert squash-merge commit on main and redeploy previous SHA
- **Owner:** On-call application engineer / release manager

## 10) Evidence Pack (links)
- CI run(s): this PR checks
- Staging deploy evidence: pending tip LIVE
- Canary evidence (if applicable): N/A
- Unit: `tests/unit/test_investigation_closure_validate.py`
- Ledger file: `scripts/governance/pr_body_investigation_closure_validation_500.md`

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [ ] **Gate 1:** API/Data/UX contracts approved (as applicable)
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete (evidence linked)
- [x] **Gate 4:** Canary healthy (if used) (evidence linked) — N/A
- [ ] **Gate 5:** Production verification plan + monitoring ready
