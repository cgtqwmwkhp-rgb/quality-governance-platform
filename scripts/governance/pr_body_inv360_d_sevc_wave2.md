# Change Ledger (CL-INV360-D-SEVC)

## File allowlist (exclusive)
- `frontend/src/pages/InvestigationDetail.tsx`
- `frontend/src/pages/investigation/*`
- `frontend/src/pages/__tests__/InvestigationDetail.test.tsx`
- `src/domain/services/investigation_service.py`
- `src/api/routes/investigations.py`
- `src/api/schemas/investigation.py` (timeline fields for spine)
- `tests/unit/test_investigation_wave2_smart_search_omit.py`
- `tests/unit/test_require_permission_modules.py` (approve_customer_omit)
- `tests/integration/conftest.py` / `tests/e2e/conftest.py` (permission seed)
- `scripts/governance/pr_body_inv360_d_sevc_wave2.md`

**Out of scope / do not touch:** Actions.tsx, ActionDetail.tsx, Investigations.tsx (list FE), Risk*, DocumentControl, LookupTables, Layout, App, package.json, PlanetMark OCR, Wave 3 PDF.

## 1) Summary
- **Feature / Change name:** INV360 Wave 2 activity spine + INV-SEV-C pack omit + list BE `q` (flag debt PR-5)
- **User goal (1–2 lines):** Investigation Detail shows a unified activity spine, CAPA handoff/status workflow, RCA→CAPA and closure→CAPA jumps, evidence↔report visibility, and RBAC-approved customer-pack section omit; list API gains additive smart-search `q`.
- **In scope:** Detail FE + investigation/*; investigation routes/service; omit RBAC; list `q`.
- **Out of scope:** Wave 3 PDF branding; list FE (PR-4); system audit event edit/delete.
- **Feature flag / kill switch:** None — revert commit.

## 2) Impact Map (what changed)
- **Frontend:** Activity spine Timeline; manual timeline entry; live CAPA handoff + status workflow chips; closure blocker jump by `action_key`; RCA Create CAPA from root cause; evidence visibility controls; Report section omit request/approve UI + redaction log preview.
- **Backend:** `list_investigations?q=`; `POST .../timeline` MANUAL_ENTRY; `POST .../customer-pack-omit` (+ `/approve` with `investigation:approve_customer_omit`); pack generate fails closed on pending omits; approved omits logged as `SECTION_OMIT_APPROVED`.
- **APIs:** Additive only.
- **Schemas/contracts:** Timeline event response gains optional actor/snippet fields.
- **Database:** None (omit map on `investigation.data.customer_pack_visibility`).
- **Workflows/jobs/queues:** None.
- **Config/env/flags:** Grant `investigation:approve_customer_omit` to H&S Advisor / Admin roles in env.
- **Dependencies:** None.

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive query param + new endpoints; existing clients ignore.
- **Tolerant reader / strict writer applied?** Yes — omit map optional; pack generate fails closed if omit pending.
- **Breaking changes:** None.
- **Migration plan:** N/A.
- **Rollback strategy (DB):** Revert commit only.

## 4) Acceptance Criteria (AC)
- [x] AC-01: Timeline shows unified activity spine (comments + CAPA + evidence + packs + manual + revisions)
- [x] AC-02: Closure blockers jump to CAPA by `action_key`; RCA offers Create CAPA from root cause
- [x] AC-03: Evidence upload/list can set report inclusion visibility
- [x] AC-04: Live CAPA handoff strip + interactive Draft→… status workflow (clears CUJ-061/062/063)
- [x] AC-05: Customer-pack omit-by-level with `investigation:approve_customer_omit`; pending omit blocks generate
- [x] AC-06: Additive `q` on `list_investigations` for InvList smart search

## 5) Testing Evidence (link to runs)
- [x] Frontend unit — activity spine + Detail Wave 2/SEV-C tests
- [x] Backend unit — omit + `q` route contract + permission AST
- [ ] CI — pending this PR
- [ ] Tip LIVE — after merge/deploy by tip-owner

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-061: CAPA handoff strip live count + open Actions/create
- [x] CUJ-062: Interactive status workflow chips (not close bypass)
- [x] CUJ-063: Closure blocker → CAPA jump by action_key
- [x] CUJ-SEV-C: Omit request → approve → section absent from pack / pending blocks generate

## 7) Observability & Ops
- **Logs:** Existing API/exception paths; revision events for omit request/approve/revoke
- **Metrics:** No new metrics
- **Alerts:** Existing API 5xx monitors
- **Runbook updates:** Grant `investigation:approve_customer_omit` to H&S Advisor/Admin

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Investigation Detail Timeline spine; RCA→CAPA; omit pending blocks pack; approve omit; list `?q=` returns matches.
- **Canary plan:** N/A
- **Prod post-deploy checks:** Tip LIVE glance-test + InvList search once PR-4 FE lands.

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Pack generate regressions, false omit hiding, timeline 5xx
- **Rollback steps:** Revert squash-merge commit on main and redeploy previous SHA
- **Owner:** On-call application engineer / release manager

## 10) Evidence Pack (links)
- CI run(s): this PR checks
- Staging deploy evidence: pending tip LIVE
- Canary evidence (if applicable): N/A
- Ledger file: `scripts/governance/pr_body_inv360_d_sevc_wave2.md`

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved (as applicable) — additive
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete (evidence linked)
- [x] **Gate 4:** Canary healthy (if used) (evidence linked) — N/A
- [ ] **Gate 5:** Production verification plan + monitoring ready
