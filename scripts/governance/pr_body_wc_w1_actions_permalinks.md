# Change Ledger (CL-WC-W1-ACTIONS-PERMALINKS)

## 1) Summary
- **Feature / Change name:** D-W1-04 — RESTful `/actions/:id` permalinks + legacy redirect (P0-UX-2 / Journey A)
- **User goal (1-2 lines):** Action detail pages use stable REST-style URLs (`/actions/capa%3A9`) instead of query-string legacy paths (`/actions/item?key=`), with automatic redirect for bookmarks and outbound links.
- **In scope:** App routes; `actionLinks` helpers; `ActionDetail` param resolution; Actions list + create deep links; frontend unit tests; Change Ledger
- **Out of scope:** Layout nav hub; Incident/Complaint list URL sync; RiskRegister; backend CAPA models; NearMissDetail; non-allowlisted callers still on legacy URLs (Audits, ComplianceAutomation) — follow-up lanes
- **Feature flag / kill switch:** N/A — additive route + replace redirect

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** `App.tsx` (`/actions/:id`, legacy redirect); `actionLinks.tsx` (path builder + redirect); `ActionDetail.tsx` (`useParams` + canonical copy-link); `Actions.tsx` (list links + post-create navigation)
- **Backend (handlers/services):** None — continues `GET /api/v1/actions/by-key?key=`
- **APIs (endpoints changed/added):** None
- **Schemas/contracts:** None
- **Database:** None
- **Config/env/flags:** None
- **Dependencies:** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive + redirect
- **Tolerant reader / strict writer applied?** Yes — legacy `/actions/item?key=` redirects with `replace`; missing key → `/actions`
- **Breaking changes:** None for users (legacy URLs still resolve)
- **Migration plan:** N/A
- **Rollback strategy (DB):** N/A — revert commit only

## 4) Acceptance Criteria (AC)
- [x] AC-01: `/actions/:id` renders action detail (`action_key` URL-encoded)
- [x] AC-02: `/actions/item?key=X` → `/actions/X` redirect (`replace`)
- [x] AC-03: Actions list “Open profile” uses `/actions/:id`
- [x] AC-04: Create CAPA (no `returnTo`) navigates to new permalink
- [x] AC-05: Copy-link on detail uses canonical permalink URL
- [x] AC-06: Unit tests cover helpers, redirect, detail param, list link

## 5) Testing Evidence (link to runs)
- [x] Frontend unit — `actionLinks.test.tsx`, `ActionDetail.test.tsx`, `Actions.test.tsx`
- [ ] CI — linked after PR creation

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Actions list → Open profile → `/actions/capa%3A{id}`
- [x] CUJ-02: Legacy bookmark `/actions/item?key=capa:9` → canonical permalink
- [x] CUJ-03: Create CAPA from list (no return) → land on new action detail

## 7) Observability & Ops
- **Logs:** No change
- **Metrics:** No change
- **Alerts:** No change

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

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** Exclusive allowlist respected
- [ ] **Gate 2:** CI green
- [ ] **Gate 3:** Staging verification complete
- [ ] **Gate 4:** Canary healthy (if used)
- [x] **Gate 5:** Production verification plan + monitoring ready

## Test plan
- [ ] `cd frontend && npm test -- actionLinks ActionDetail Actions`
- [ ] Manual: `/actions/capa%3A<id>` loads detail; `/actions/item?key=capa:<id>` redirects
- [ ] Manual: Create CAPA from Actions (no returnTo) lands on permalink
- [ ] Staging tip after merge

## Out of scope / follow-up
- `Audits.tsx`, `ComplianceAutomation.tsx` still emit legacy `/actions/item?key=` (outside allowlist)
- `PortalWork.tsx` already used `/actions/:id` pattern — no change required
- Layout My Work nav unchanged
