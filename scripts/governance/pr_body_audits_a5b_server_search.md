# Change Ledger (CL-AUDITS-A5B-SERVER-SEARCH)

> **Start gate:** #1771 LIVE — tip `02edbdb1a`. `STACK_MAX=1`. Merge ≠ LIVE.
> David unlocked A5b after A3 LIVE. A4 stays 3 columns.
> L11–L16 unchanged: Entra off, no Assist triad, no Exceptions cap, no invented EXACT, Dependabot not this belt.
> S4 CHAS/SSIP trees stay blocked.

## 1) Summary
- **Feature / Change name:** Server `q=` on GET `/api/v1/audits/runs`
- **User goal:** Audits search must locate runs beyond the loaded 100-row client page.
- **In scope:** `list_runs` ilike on title / reference / location / scheme / body; FE passes trimmed `q` via `useDeferredValue`; tests.
- **Out of scope:** Findings search API. Four-column lanes (A4). Entra / EXACT / Dependabot / CHAS trees.
- **Feature flag / kill switch:** None. Revert this PR.

## 2) Impact Map (what changed)

| ID | Surface | Before | After |
|---|---|---|---|
| A5b-01 | GET `/api/v1/audits/runs` | Page of newest 100 only | Optional `q` ilike across title, ref, location, scheme, body |
| A5b-02 | Audits search box | Client filter of the loaded page | Debounced server `q=`; List view still opens on type |

## 3) Compatibility & Data Safety
- Empty / whitespace `q` is ignored (same unfiltered list as today).
- Tenant filter stays exact `tenant_id ==`; search uses `|` ilike, not `or_(`.
- **Rollback strategy:** Revert merge and redeploy `02edbdb1a`.

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| Search locate beyond loaded page | Client-only | Server `q=` |
| Invented EXACT / CHAS % | Refused | Untouched |

## 4) Acceptance Criteria (AC)
- [x] ac-01: `GET /api/v1/audits/runs?q=` returns matching title and not the decoy.
- [x] ac-02: `list_runs(..., q=)` SQL stays exact-tenant and uses ilike.
- [x] ac-03: FE `listRuns` omits `q` when empty and sends `q` when set.
- [x] ac-04: Typing in Audits search refetches with `{ q }` and shows the matching run.
- [x] ac-05: No Entra/Assist/Exceptions-cap/EXACT/Dependabot/CRM-LIB/S4/A4 change. CAPA ribbon unchanged.
- [ ] ac-06: Hosted CI green; STG+PROD SUCCESS (Build and Deploy not skipped); SHA match → LIVE.

## 5) Testing Evidence (link to runs)
- [x] Unit: `test_audit_service_list_runs_q_sql_exact_tenant_and_ilike`
- [x] Integration: `test_list_audit_runs_q_matches_title`
- [x] Unit: `auditsClient.test.ts` q query string
- [x] Unit: Audits search refetch in `Audits.test.tsx`
- [ ] Hosted CI — pending

## 6) Critical Journeys Verified (CUJ)
- [x] cuj-01: Unique title `A5b-locate-needle-Wickford` is returned by `q=` with page_size 1 (unit/integration).
- [x] cuj-02: Operator types a needle not on the loaded page; List shows the server match (unit).

## 7) Observability & Ops
- `data-testid="audits-search"`
- Truncation banner distinguishes matching runs vs loaded page.

## 8) Release Plan
1. Branch from LIVE tip `02edbdb1a`.
2. Merge after CI green; Staging SUCCESS; Production SUCCESS (Build and Deploy **not** skipped); only then **LIVE**.

## 9) Rollback Plan
- **Rollback trigger:** Search misses known runs; tenant leak in `q` SQL; empty search no longer lists runs.
- **Rollback steps:** Revert merge; redeploy `02edbdb1a`.
- **Owner:** Platform release operator / Standards Governance conveyor.

## 10) Evidence Pack
- Parent LIVE: **PR #1771** @ `02edbdb1a`

## Gate checklist
- [x] **Gate 0:** Scope lock + AC + Change Ledger; #1771 LIVE; A5b continue given
- [x] **Gate 1:** Focused tests
- [ ] **Gate 2:** CI green on tip
- [ ] **Gate 3:** STG tip verify
- [ ] **Gate 4:** PROD tip verify
- [ ] **Gate 5:** Master conveyor updated after LIVE
