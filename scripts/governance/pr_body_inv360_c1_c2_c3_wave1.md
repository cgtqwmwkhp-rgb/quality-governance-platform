# Change Ledger (CL-INV360-C1-C2-C3)

## File allowlist (exclusive)
- `frontend/src/pages/InvestigationDetail.tsx`
- `frontend/src/pages/investigation/InvestigationHeader.tsx`
- `frontend/src/pages/investigation/InvestigationTimeline.tsx`
- `frontend/src/pages/__tests__/InvestigationDetail.test.tsx`
- `frontend/src/pages/investigation/__tests__/InvestigationHeader.test.tsx`
- `frontend/src/pages/investigation/__tests__/InvestigationTimeline.test.tsx`
- `frontend/src/i18n/locales/en.json`
- `scripts/governance/pr_body_inv360_c1_c2_c3_wave1.md`

**Out of scope / do not touch:** Layout, App, `client.ts`, `api/__init__.py`, Alembic, planet_mark, vehicle-checklists. No new timeline write APIs.

## 1) Summary
- **Feature / Change name:** INV360 Wave 1 — identity chrome + tab controls + Report Internal/External (C1+C2+C3)
- **User goal (1–2 lines):** On Investigation Detail, users can glance-tell Investigation workspace vs source Incident, use honest tab controls (Timeline filters, status/level/assignee, editable findings/notes), and generate Internal/External reports with clear permission honesty.
- **In scope:** Investigation Detail + header/timeline components; i18n; Vitest for new visible controls.
- **Out of scope:** Manual timeline POST API; PDF branding; Incident Detail paired chrome; Layout/App/client.ts; Alembic.
- **Feature flag / kill switch:** None — revert commit.

## 2) Impact Map (what changed)
- **Frontend:** Identity eyebrow + REF primary ID + source chip; Summary source snapshot vs editable findings; status/level/assignee controls; Timeline filters aligned to backend `event_type` enums; Report Internal/External role copy + gated honesty.
- **Backend:** None.
- **APIs:** Consumes existing `PATCH` investigation, `GET` timeline `event_type`, pack generate audiences — no contract changes.
- **Schemas/contracts:** None.
- **Database:** None.
- **Workflows/jobs/queues:** None.
- **Config/env/flags:** None.
- **Dependencies:** None.

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive UI honesty over existing APIs; Timeline filters now send correct enums (previously empty results).
- **Tolerant reader / strict writer applied?** Yes — level shown read-only (from source); close remains checklist-gated.
- **Breaking changes:** None.
- **Migration plan:** N/A.
- **Rollback strategy (DB):** Revert commit only.

## 4) Acceptance Criteria (AC)
- [x] AC-01: Header shows Investigation workspace eyebrow, REF as primary ID, purpose one-liner, source chip + Open source report
- [x] AC-02: Summary separates Source snapshot from editable Findings/Conclusion; Notes section labelled; status/level/assignee surfaced honestly
- [x] AC-03: Timeline filters use backend enums (`STATUS_CHANGED`, `DATA_UPDATED`, `COMMENT_ADDED`, …)
- [x] AC-04: Report tab shows Internal/External buttons with role copy; disabled + honest banner when capability/permission gated
- [x] AC-05: Vitest covers identity chrome, summary controls, timeline filter API param, Report I/E gating

## 5) Testing Evidence (link to runs)
- [x] Frontend unit — InvestigationDetail C1/C2/C3 + Header + Timeline filter tests
- [ ] CI — pending this PR
- [ ] Tip LIVE — glance-test Investigation Detail after deploy

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Open Investigation → see REF workspace identity vs source link
- [x] CUJ-02: Summary → edit findings/lead; change workflow status (not close bypass)
- [x] CUJ-03: Timeline → filter Status Changes → API `event_type=STATUS_CHANGED`
- [x] CUJ-04: Report → Internal/External visible; gated when `canGenerate=false`

## 7) Observability & Ops
- **Logs:** Existing API/exception paths
- **Metrics:** No new metrics
- **Alerts:** Existing API 5xx monitors
- **Runbook updates:** N/A

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Open Investigation Detail → identity glance-test; Timeline filter; Summary save; Report I/E with/without permission.
- **Canary plan:** N/A (FE honesty)
- **Prod post-deploy checks:** Tip LIVE glance-test on a real investigation.

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Identity/copy regressions, false status updates, Report button confusion
- **Rollback steps:** Revert squash-merge commit on main and redeploy previous SHA
- **Owner:** On-call application engineer / release manager

## 10) Evidence Pack (links)
- CI run(s): this PR checks
- Staging deploy evidence: pending tip LIVE
- Canary evidence (if applicable): N/A
- Ledger file: `scripts/governance/pr_body_inv360_c1_c2_c3_wave1.md`

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved (as applicable) — existing APIs only
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete (evidence linked)
- [x] **Gate 4:** Canary healthy (if used) (evidence linked) — N/A
- [ ] **Gate 5:** Production verification plan + monitoring ready
