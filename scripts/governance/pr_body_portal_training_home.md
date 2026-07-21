# Change Ledger (CL-PORTAL-TRAINING-HOME)

## 1) Summary
- **Feature / Change name:** Employee Portal — Training on home + personal `/me` resolution
- **User goal (1–2 lines):** Training is a first-class home action; logged-in employees see the modules Admin allocated to them via Atlas name map / name match.
- **In scope:** Portal home Training tile; `/training-matrix/me` name-map + name-variant resolution with empty_reason; clearer My Work empty states; hash deep-link `#training`
- **Out of scope:** LMS completion inside QGP; competency passport rewrite
- **Feature flag / kill switch:** N/A

## 2) Impact Map (what changed)
- **Frontend:** `Portal.tsx` Training tile; `PortalWork.tsx` empty-reason copy + `#training` scroll; `trainingMatrixClient.myTraining` types
- **Backend:** `training_matrix.py` portal person resolution; `training_matrix_parser.person_name_match_keys`; compliance list `empty_reason`
- **APIs:** `GET /api/v1/training-matrix/me` (additive diagnostic fields)
- **Schemas/contracts:** Additive optional fields on compliance list response
- **Database:** May self-heal `TrainingMatrixPerson.engineer_id` when name-map/name match succeeds
- **Workflows/jobs/queues:** None
- **Config/env/flags:** None
- **Dependencies:** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive response fields; tolerant FE readers
- **Tolerant reader / strict writer applied?** Yes
- **Breaking changes:** None
- **Migration plan:** None
- **Rollback strategy (DB):** Revert PR; any healed engineer_id links remain (corrective, safe)

## 4) Acceptance Criteria (AC)
- [x] AC-01: Portal home shows a Training action (not only under My Work subtitle)
- [x] AC-02: Training tile navigates to `/portal/work#training` and opens/scrolls Training section
- [x] AC-03: `/me` resolves Atlas people via engineer_id, name-map, or First/Last name variants
- [x] AC-04: Empty portal states distinguish no_import / not_mapped / no_requirements
- [x] AC-05: My Work badge no longer double-counts training gaps (Training tile owns that badge)

## 5) Testing Evidence (link to runs)
- [x] Unit: `person_name_match_keys` parser test
- [ ] CI — after open / push

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Portal home → Training → My Work training section focused
- [x] CUJ-02: Linked user with Atlas name map sees modules from `/training-matrix/me`

## 7) Observability & Ops
- **Logs:** None new
- **Metrics:** N/A
- **Alerts:** N/A
- **Runbook updates:** If portal empty → check engineer user link, Training → People map, Training group / requirements

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Login as mapped employee; confirm Training tile + modules
- **Canary plan:** N/A
- **Prod post-deploy checks:** David Harris portal Training shows modules when mapped in Admin

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Portal Training tile broken or `/me` 5xx
- **Rollback steps:** Revert merge / redeploy prior SWA+API
- **Owner:** Platform / Training

## 10) Evidence Pack (links)
- CI run(s): after push
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
