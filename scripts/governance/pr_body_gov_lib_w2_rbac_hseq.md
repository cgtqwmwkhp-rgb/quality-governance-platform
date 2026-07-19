# Change Ledger (CL-GOV-LIB-W2-RBAC-HSEQ)

## 1) Summary
- **Feature / Change name:** Governance Library Wave W2 — RBAC facets + restricted gates + HSEQ Admin polish
- **User goal (1–2 lines):** Staff/manager/admin facets map onto `Role.permissions`; restricted categories (02.08 / 06.03 / 11.03) are gated by `document:restricted:{oh|driver|breach}`; Admin can edit role permissions and manage engineer groups; user-facing copy stays HSEQ.
- **Depends on:** #1176 LIVE (W0+W1 on tip)
- **In scope:** Restricted ACL by taxonomy→permission; list omit for denied docs; facet bundle catalog API; Library Roles Admin page; Engineer Groups Admin page; FE permissions JSON serialization; HSEC→HSEQ test/copy cleanup
- **Out of scope:** Review packs / AI (W3), HSEQ approve→campaign (W4), disposal (W5), named UID allow-lists
- **Feature flag / kill switch:** None — additive ACL + Admin pages; legacy `all_staff` unchanged

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** `LibraryRoles.tsx`, `EngineerGroups.tsx`, AdminDashboard tiles, App routes, `usersClient` serialize permissions as JSON string
- **Backend (handlers/services):** `document_library_rbac.py`; harden `assert_library_read_access`; list filter in `documents.py`
- **APIs (endpoints changed/added):** `GET /document-categories/rbac-catalog`; list/get/signed-url ACL behaviour
- **Schemas/contracts:** Additive catalog response only
- **Database (migrations/entities/indexes):** None
- **Workflows/jobs/queues:** None
- **Config/env/flags:** None
- **Dependencies:** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive only; no Alembic
- **Tolerant reader / strict writer applied?** Yes
- **Breaking changes:** None
- **Migration plan:** N/A
- **Rollback strategy (DB):** No DB change — revert commit only
- Restricted without known taxonomy fails closed (404 / omit)
- System roles remain immutable — create overlay roles to edit bundles

## 4) Acceptance Criteria (AC)
- [x] AC-01: Facet bundles staff/manager/admin documented + catalog API
- [x] AC-02: 02.08/06.03/11.03 gated by restricted perms (not UID lists)
- [x] AC-03: get + signed-url + list honour ACL
- [x] AC-04: User-facing CUJ copy HSEQ (inbox already HSEQ; test string updated)
- [x] AC-05: Admin Library Roles editor + Engineer Groups page
- [x] AC-06: Unit tests + Change Ledger

## 5) Testing Evidence (link to runs)
- [x] Unit — `tests/unit/test_gov_lib_w2_rbac.py` (local 8/8 + W1 8/8)
- [ ] CI — this PR
- [ ] Staging verification — after merge

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Staff cannot open restricted OH doc; OH-perm can
- [x] CUJ-02: Driver perm cannot open breach taxonomy
- [x] CUJ-03: Admin manage still bypasses restricted
- [x] CUJ-04: Admin can apply facet bundles on a non-system role

## 7) Observability & Ops
- **Logs:** Existing library access logs unchanged; denied reads remain 404-not-403 (no existence leak)
- **Metrics:** No new metrics
- **Alerts:** No new alerts
- **Runbook updates:** N/A — Admin Library Roles / Engineer Groups under Admin dashboard

## 8) Release Plan (Local -> Staging -> Canary -> Prod)
- **Staging verification:** Health + library list/get with restricted category as staff vs OH-perm user
- **Canary plan:** N/A — additive/opt-in RBAC
- **Prod post-deploy checks:** tip_match YES; Admin → Library roles page loads; restricted ACL unit path covered by CI

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Restricted docs incorrectly hidden from authorised users, or Admin role editor cannot save permissions
- **Rollback steps:** Revert PR on main; force_deploy prior SHA
- **Owner:** Governance / Quality platform team

## 10) Evidence Pack (links)
- CI run(s): Linked on this PR checks tab
- Staging deploy evidence: After tip deploy
- Canary evidence (if applicable): N/A

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved (additive-only)
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete (evidence linked)
- [x] **Gate 4:** Canary healthy (if used) — N/A, additive/opt-in rollout
- [x] **Gate 5:** Production verification plan + monitoring ready
