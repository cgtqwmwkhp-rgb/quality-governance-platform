# Change Ledger (CL-CB-PR3-ATLAS-FAMILY)

## 1) Summary
- **Feature / Change name:** CB-PR3 — Atlas family on GET competence board + person union
- **User goal:** Show statutory appointments (first aid, fire marshal, MHFA) for every Atlas person, including Office and Management who are not engineers. No new logins.
- **In scope:** `GET /api/v1/workforce/competence/board?family=atlas` behind the existing closed flag; one row per `training_matrix_people` on the latest import; cells carry `passed_on` / `expires_on`; duplicate `engineer_id` mappings stay as separate rows with a banner
- **Out of scope:** Live CompetencyDashboard; assessment overlay (CB-PR4); coverage quorum (CB-PR5); flag-on (CB-PR6); PAMS writes; fuzzy name join; bulk Users; Entra; new User rows
- **Feature flag / kill switch:** Same `COMPETENCE_BOARD_ENABLED` / `FF_COMPETENCE_BOARD` default false. Kill = flag off. Kill SHA = previous LIVE `fda52219bcbf`.

## 2) Impact Map (what changed)
- **Frontend:** none. CompetencyDashboard unchanged.
- **Backend:** Atlas board assembler + GET `family=atlas` on the existing competence router
- **APIs:** Same path; `family=atlas` now returns the Atlas board (404 while flag closed). Was 422 in CB-PR1/PR2.
- **Database / flags:** none. Reads existing training-matrix tables.
- **Workflows/jobs:** none

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive optional fields on the board response (`atlas_person_id`, `department`, `passed_on`, `expires_on`). PAMS family unchanged.
- **Breaking changes:** Clients that treated `family=atlas` 422 as a hard contract must accept 200 when the flag is on. Flag stays false in this slice.
- **Migration plan:** none
- **Rollback strategy (DB):** Flag off. No schema change.

## Compliance Delta
- **ISO 9001 7.2 / ISO 45001 7.2:** Statutory evidence stays in Atlas/Citation. QGP reads the latest import. HR Advisor remains the change path.
- **What this PR does not claim:** Demonstrated overlay on PAMS cells. Location coverage quorum. Live board UI.

## 4) Acceptance Criteria (AC)
- [x] AC-01: Flag default false. Atlas board 404 when closed.
- [x] AC-02: `GET /board?family=atlas` returns Atlas people from the latest import, including rows with `engineer_id` null.
- [x] AC-03: No User / login is created. No fuzzy name join — identity is `training_matrix_people.id` then existing `engineer_id`.
- [x] AC-04: Two Atlas people who share an `engineer_id` stay two rows; banner names the duplicate. Kill if this appears at material rate.
- [x] AC-05: Two Atlas people with the same display name stay two rows.
- [x] AC-06: Empty / date-less cells are absent, never grey `not_assessed`.
- [x] AC-07: PAMS family still serves snapshot cells. CompetencyDashboard unchanged.
- [x] AC-08: QGP never writes PAMS. Coverage endpoint is CB-PR5.

## 5) Testing Evidence (link to runs)
- [ ] Unit — `tests/unit/test_atlas_competence_board.py`
- [ ] Full CI — linked after PR checks

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Flag off → atlas board 404
- [x] CUJ-02: Office person without engineer_id appears; mapped engineer uses Engineer.display_name
- [x] CUJ-03: Duplicate engineer_id is not merged

## 7) Observability & Ops
- **Logs:** none new
- **Runbook:** Leave flag false. Inspect duplicate banner on a tenant with Atlas import before CB-PR4.

## 8) Release Plan
- **Staging:** Flag stays false. Confirm 404 on `/api/v1/workforce/competence/board?family=atlas`.
- **Prod post-deploy:** healthz; `build_sha` == tip; flag false; Entra stays false

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** New User rows, fuzzy name merge, PAMS write, or CompetencyDashboard change
- **Rollback steps:** Revert squash on `main` and redeploy previous LIVE SHA `fda52219bcbf`
- **Owner:** David Harris

## 10) Evidence Pack
- CI run(s): Linked after PR creation

---

# Gate Checklist
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts (closed flag; Atlas read; live page untouched)
- [ ] **Gate 2:** CI green
- [ ] **Gate 3:** Staging verification
- [ ] **Gate 4:** Canary (N/A)
- [x] **Gate 5:** Production verification plan + monitoring ready
