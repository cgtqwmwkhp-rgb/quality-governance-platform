# Change Ledger (CL-INV360-B0)

## File allowlist (exclusive)
- `src/api/routes/investigations.py`
- `src/domain/services/investigation_service.py`
- `tests/unit/test_investigation_comments_tenant_not_null.py`
- `tests/unit/test_investigation_add_comment_tenant.py`
- `frontend/src/pages/InvestigationDetail.tsx`
- `frontend/src/pages/__tests__/InvestigationDetail.test.tsx`
- `frontend/src/pages/investigation/InvestigationActions.tsx`
- `scripts/governance/pr_body_inv360_b0_notes_tenant_capa.md`

**Out of scope / do not touch:** Layout, App, `client.ts`, `api/__init__.py`, Alembic, planet_mark, vehicle-checklists.

## 1) Summary
- **Feature / Change name:** INV360 Wave 0 — notes tenant_id + CAPA/Close/Report honesty
- **User goal (1–2 lines):** Add Note on Investigation Detail must succeed (no 500); CAPA status UI uses honest `display_status` / `action_key`; Close CTA appears when ready; Report errors are visible.
- **In scope:** Stamp `tenant_id` on `InvestigationComment` create (route + service); unit tests; minimal Investigation Detail / Actions FE honesty for CAPA status, Close CTA, Report/notes errors.
- **Out of scope:** Wave 1 screen identity, Timeline manual entries, PDF branding, Alembic, Layout/App/client.ts.
- **Feature flag / kill switch:** None — revert commit.

## 2) Impact Map (what changed)
- **Frontend:** InvestigationDetail Close CTA + honest note/report/close/CAPA-update errors; InvestigationActions uses `display_status` + `action_key` for status UI/updates.
- **Backend:** `POST /investigations/{id}/comments` and `InvestigationService.add_comment` set `tenant_id=investigation.tenant_id`.
- **APIs:** Same contracts; comments write path no longer omits NOT NULL `tenant_id`.
- **Schemas/contracts:** None.
- **Database:** None (no Alembic).
- **Workflows/jobs/queues:** None.
- **Config/env/flags:** None.
- **Dependencies:** None.

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive honesty + required write-path fix for existing NOT NULL column.
- **Tolerant reader / strict writer applied?** Yes — inherit tenant from investigation; never invent `tenant_id=1`.
- **Breaking changes:** None.
- **Migration plan:** N/A.
- **Rollback strategy (DB):** Revert commit only.

## 4) Acceptance Criteria (AC)
- [x] AC-01: `POST /api/v1/investigations/{id}/comments` stamps `tenant_id` from investigation (no IntegrityError 500)
- [x] AC-02: `InvestigationService.add_comment` stamps `tenant_id` and rejects missing investigation tenant
- [x] AC-03: Unit tests cover add_comment tenant_id inheritance (service + route source + runtime)
- [x] AC-04: Investigation Actions tab shows CAPA `display_status` / `action_key`; status updates route via action_key-aware source_type
- [x] AC-05: Close CTA shown when `can_close`; calls `PATCH` status=`closed` with honest errors
- [x] AC-06: Report pack list/generate failures surface inline (and generate toasts); Add Note failures toast

## 5) Testing Evidence (link to runs)
- [x] Unit — `test_investigation_add_comment_tenant.py` + comments tenant write-path assertions
- [x] Frontend unit — InvestigationDetail Close CTA + Report list error
- [ ] CI — pending this PR
- [ ] Tip LIVE — Add Note on REF investigation after deploy

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Add Note → comment created with tenant_id (no Server error toast from 500)
- [x] CUJ-02: Create CAPA → list shows action_key + honest display_status; status change updates via action_key path
- [x] CUJ-03: Closure ready → Close investigation CTA → status closed
- [x] CUJ-04: Report tab pack list failure shows error banner (not silent empty success)

## 7) Observability & Ops
- **Logs:** Existing API/exception paths
- **Metrics:** Monitor 5xx on `POST /api/v1/investigations/*/comments` → expect ~0
- **Alerts:** Existing API 5xx monitors
- **Runbook updates:** N/A

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Open investigation → Add Note; Create CAPA → change status; when can_close → Close; Report tab error path if packs fail.
- **Canary plan:** N/A (write-path fix + FE honesty)
- **Prod post-deploy checks:** Tip LIVE Add Note on a real investigation.

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Comment create regressions, false Close success, CAPA status update failures
- **Rollback steps:** Revert squash-merge commit on main and redeploy previous SHA
- **Owner:** On-call application engineer / release manager

## 10) Evidence Pack (links)
- CI run(s): this PR checks
- Staging deploy evidence: pending tip LIVE
- Canary evidence (if applicable): N/A
- Ledger file: `scripts/governance/pr_body_inv360_b0_notes_tenant_capa.md`

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved (as applicable)
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete (evidence linked)
- [x] **Gate 4:** Canary healthy (if used) (evidence linked) — N/A
- [ ] **Gate 5:** Production verification plan + monitoring ready
