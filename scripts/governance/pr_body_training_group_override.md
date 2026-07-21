# Change Ledger (CL-TRAINING-GROUP-OVERRIDE)

## 1) Summary
- **Feature / Change name:** Per-person Training group mapping (Atlas unchanged)
- **User goal (1–2 lines):** After weekly Atlas CSV upload, Admins assign each person to Engineer / Workshop / Office / Management inside QGP without renaming Atlas departments, so frequency rules and board buckets are correct for Office/Management/Workshop edge cases.
- **In scope:** Durable `board_role_override` on Atlas people; PATCH people endpoint; Admin Training group dropdown; override used for compliance matching + board role resolution; survives CSV re-upload
- **Out of scope:** Changing Atlas export/groups; department-alias bulk table; Overall % metric changes
- **Feature flag / kill switch:** N/A (override defaults null = Auto from Atlas)

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** Training Matrix Admin People mapping — Training group select on all Atlas people; board helpers honour override
- **Backend (handlers/services):** `resolve_board_role` / `normalize_board_role`; compliance matching prefers override; import never clears override
- **APIs (endpoints changed/added):** `PATCH /api/v1/training-matrix/people/{person_id}`; name-maps + compliance rows expose `person_id` / `board_role_override`
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** `TrainingMatrixPersonRoleUpdate`; extended name-map + compliance schemas
- **Database (migrations/entities/indexes):** Alembic `20260802_tm_role` — nullable `board_role_override` + check constraint
- **Workflows/jobs/queues (if any):** None
- **Config/env/flags:** None
- **Dependencies (added/removed/updated):** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive column + endpoint; null override preserves current substring behaviour
- **Tolerant reader / strict writer applied?** Yes — PATCH validates BOARD_ROLES; invalid values rejected
- **Breaking changes:** None
- **Migration plan:** Deploy runs Alembic; Admins set Training groups for non-Engineer Atlas depts (e.g. IT → Office)
- **Rollback strategy (DB):** Column nullable; revert PR leaves column unused (safe). Full rollback: revert PR + optional drop column migration if needed

## 4) Acceptance Criteria (AC)
- [x] AC-01: Admin can set Training group Engineer/Workshop/Office/Management per Atlas person without changing Atlas department text
- [x] AC-02: Override drives frequency-rule matching (e.g. IT + Office override matches Office rules)
- [x] AC-03: Override drives manager board role buckets; Auto (null) keeps Atlas department substring match
- [x] AC-04: Weekly CSV re-upload does not clear `board_role_override`
- [x] AC-05: Invalid override values are rejected; null clears override to Auto

## 5) Testing Evidence (link to runs)
- [x] Unit — `resolve_board_role` override preference; import preserve contract; requirement match with Office override
- [x] Frontend unit — `resolveBoardRole` / `computeRoleStats` / `moduleViewForRole` honour override
- [x] CI — re-run after this ledger + black fix

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Admin uploads Atlas CSV → sets Training group Office on an IT person → person appears in Office board + Office frequency rules
- [x] CUJ-02: Admin clears Training group to Auto → falls back to Atlas department substring (Mobile Engineers → Engineer)
- [x] CUJ-03: Admin re-uploads weekly CSV → Training group overrides remain

## 7) Observability & Ops
- **Logs:** Standard API errors on invalid PATCH
- **Metrics:** N/A new
- **Alerts:** N/A
- **Runbook updates:** Admin uses Training → Admin → People mapping Training group dropdown after each upload wave for non-matching Atlas depts

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Hard-refresh Training Admin; set one Office override; confirm board + compliance rows
- **Canary plan:** N/A — normal merge deploy
- **Prod post-deploy checks:** Migration applied; Admin can PATCH Training group; Mobile Engineers still Auto-bucket correctly

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Wrong overrides mass-misbucket people or compliance rows empty for a role
- **Rollback steps:** Revert PR merge; Admins clear overrides via prior build if needed; DB column may remain unused
- **Owner:** Platform / Workforce Training

## 10) Evidence Pack (links)
- CI run(s): https://github.com/cgtqwmwkhp-rgb/quality-governance-platform/pull/1224/checks
- Staging deploy evidence: after merge
- Canary evidence (if applicable): N/A

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved (as applicable)
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete (evidence linked)
- [x] **Gate 4:** Canary healthy (if used) (evidence linked) — N/A
- [x] **Gate 5:** Production verification plan + monitoring ready
