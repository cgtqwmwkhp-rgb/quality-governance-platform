# Change Ledger (CL-D-W1-03)

## 1) Summary
- **Feature / Change name:** D-W1-03 / P0-UX-1 — Universal list filter URL sync (Incidents, Complaints, Near Miss, Documents)
- **User goal (1-2 lines):** Operators can copy, share, and bookmark list URLs that restore search (`q`), status, severity (or priority/type where applicable), and page — matching Knowledge Exceptions / Risk Register `replace:true` patterns.
- **In scope:** `Incidents.tsx`, `Complaints.tsx`, `NearMisses.tsx`, `Documents.tsx`; related vitest proofs; Change Ledger
- **Out of scope:** Layout, Actions, RiskRegister, Dashboard, backend APIs, NearMissDetail raise-risk, pagination UI chrome
- **Feature flag / kill switch:** N/A — additive query-param sync

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** Four list pages hydrate filters from `useSearchParams` on mount/back-forward and write non-default `q` / `status` / `severity` / `page` (plus `owner` on incidents/complaints, `type` on documents) with `setSearchParams(..., { replace: true })`
- **Backend (handlers/services):** None
- **APIs (endpoints changed/added):** Existing list endpoints — `page` query now forwarded from URL state where supported
- **Schemas/contracts:** None
- **Database:** None
- **Workflows/jobs/queues:** None
- **Config/env/flags:** None
- **Dependencies:** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive
- **Tolerant reader / strict writer applied?** Yes — unknown or default filter values omitted from URL; invalid `page` falls back to 1
- **Breaking changes:** None — bare list routes unchanged
- **Migration plan:** N/A
- **Rollback strategy (DB):** N/A — revert commit only

## 4) Acceptance Criteria (AC)
- [x] AC-01: Incidents list reads/writes `q`, `status`, `severity`, `page`, `owner` in URL
- [x] AC-02: Complaints list reads/writes `q`, `status`, `severity` (maps to priority), `page`, `owner`
- [x] AC-03: Near Miss list reads/writes `q`, `status`, `severity` (potential severity), `page`
- [x] AC-04: Documents library reads/writes `q`, `status`, `type`, `page` (severity N/A for documents)
- [x] AC-05: Filter changes use `replace: true` (no history spam)
- [x] AC-06: Vitest hydration proofs for Incidents + Documents

## 5) Testing Evidence (link to runs)
- [x] Frontend unit — `Incidents.test.tsx` URL hydration; `Documents.test.tsx` URL hydration
- [ ] CI — linked after PR creation

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Open `/incidents?q=…&status=…&severity=…` → search box + client filters restore without losing owner triage param
- [x] CUJ-02: Open `/complaints?owner=unassigned&page=2` → server owner filter + page forwarded to list API
- [x] CUJ-03: Open `/documents?status=approved&type=policy&q=Safety` → server type/status reload + search prefilled

## 7) Observability & Ops
- **Logs:** No change
- **Metrics:** No change
- **Alerts:** No change
- **Runbook updates:** N/A

## 8) Release Plan (Local -> Staging -> Canary -> Prod)
1. Draft PR — CI green
2. Staging auto-deploy via CI workflow_run
3. Manual spot-check shareable URLs on four list routes
4. Squash-merge when approved (DO NOT merge from authoring step)

## 9) Rollback Plan (Mandatory)
1. Revert squash commit on main
2. Redeploy previous known-good SHA

## 10) Evidence Pack (links)
- CI run(s): Linked after PR creation
- Staging deploy evidence: Linked after staging deploy

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved (frontend-only additive query params)
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete (evidence linked)
- [ ] **Gate 4:** Canary healthy (if used) (evidence linked)
- [x] **Gate 5:** Production verification plan + monitoring ready
