# Change Ledger (CL-PATH11-CUJ-ACTIONS-MY-WORK)

## 1) Summary
- **Feature / Change name:** Path11 — Actions / My Work Mine + Overdue filter residuals (ops daily driver)
- **User goal (1-2 lines):** Make Mine / Overdue / My-overdue filters honest, deep-linkable, chrome-stable on reload, and backed by proof tests (frontend + backend). Builds on #915.
- **In scope:** Actions list API filter helpers + proof tests; Actions page view modes + URL `view=`; actionsClient scope glue already present; i18n filter/view keys; Change Ledger
- **Out of scope:** Layout.tsx (My Work nav path left as `/actions`); GKB compliance audit-pack; complaints module; SWA workflows; AnimatedOutlet; SMTP (#853 parked)
- **Feature flag / kill switch:** N/A — additive query params + UI view modes

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** `Actions.tsx` (chrome-preserving reload; `my_overdue` mode; `view=` URL sync); `actionsViewScope.ts` (+ unit tests); `Actions.test.tsx` (un-skipped / deep-link proof); Playwright `actions-my-work-cuj.spec.ts`
- **Backend (handlers/services):** No behaviour change beyond existing #915 filters; unit proof for `_resolve_assigned_to_user_id` + `_apply_owner_and_overdue_filters`
- **APIs (endpoints changed/added):** Existing `GET /api/v1/actions/?assigned_to=&overdue=` (combined Mine+Overdue now exercised by UI)
- **Schemas/contracts:** None
- **Database:** None
- **Config/env/flags:** None
- **Dependencies:** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive
- **Tolerant reader / strict writer applied?** Yes — optional query params; unknown `view` → all
- **Breaking changes:** None
- **Migration plan:** N/A
- **Rollback strategy (DB):** N/A — revert commit only

## 4) Acceptance Criteria (AC)
- [x] AC-01: `view=my` / My actions → `assigned_to=me` + honesty label
- [x] AC-02: `view=overdue` / Overdue → `overdue=true` + honesty label
- [x] AC-03: `view=my_overdue` / My overdue → `assigned_to=me&overdue=true` + honesty label
- [x] AC-04: Filter failure toasts + visible alert (no silent empty success)
- [x] AC-05: View-mode chrome stays mounted on filter reload (no full-page skeleton race)
- [x] AC-06: Backend unit proof for assign/overdue SQL helpers

## 5) Testing Evidence (link to runs)
- [x] Frontend unit — `actionsViewScope.test.ts` + `Actions.test.tsx` My/Overdue suite un-skipped
- [x] Frontend client — `actionsClient.test.ts` already covers combined scope query string
- [x] Backend unit — `tests/unit/test_actions_my_work_filters.py`
- [x] Playwright — `actions-my-work-cuj.spec.ts` (+ My overdue deep-link)
- [ ] CI — linked after PR creation

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Actions → My actions → server `assigned_to=me` + honesty label
- [x] CUJ-02: Actions → Overdue → server `overdue=true` (+ failure path toast/label)
- [x] CUJ-03: Actions → My overdue / `?view=my_overdue` → both server params

## 7) Observability & Ops
- **Logs:** Existing `list_actions` per-source warnings retained
- **Metrics:** No change
- **Alerts:** No change
- **Playwright hooks:** `actions-view-mode`, `actions-view-my`, `actions-view-overdue`, `actions-view-my_overdue`, `actions-server-filter-label`, `actions-filter-error`, `actions-filter-loading`

## 8) Release Plan (Local -> Staging -> Canary -> Prod)
1. Squash-merge after CI green (DO NOT merge from this authoring step)
2. Staging auto-deploy via CI workflow_run
3. Confirm staging tip + `/healthz` 200 (2×)
4. Force-deploy production with full 40-char `release_sha` when approved

## 9) Rollback Plan (Mandatory)
1. Revert squash commit on main
2. Redeploy previous known-good SHA via production workflow_dispatch
3. Verify `/api/v1/meta/version` matches rollback SHA

## 10) Evidence Pack (links)
- CI run(s): Linked after PR creation
- Staging deploy evidence: After merge
- Canary evidence: N/A

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** Exclusive allowlist respected (Actions API helpers/tests, Actions list UI/components/tests, i18n filter keys, ledger)
- [ ] **Gate 2:** CI green
- [ ] **Gate 3:** Staging verification complete
- [ ] **Gate 4:** Canary healthy (if used)
- [x] **Gate 5:** Production verification plan + monitoring ready

## Test plan
- [ ] `cd frontend && npm test -- actionsViewScope Actions actionsClient`
- [ ] `pytest tests/unit/test_actions_my_work_filters.py`
- [ ] `npx playwright test actions-my-work-cuj.spec.ts`
- [ ] Manual: `/actions?view=my|overdue|my_overdue` labels + network query params
- [ ] Staging tip after merge

## Out of scope / parked
- Layout.tsx My Work nav still points at `/actions` (exclusive avoid list)
- GKB audit-pack, complaints, SWA, AnimatedOutlet
- #853 SMTP — parked; no invented outbound email
