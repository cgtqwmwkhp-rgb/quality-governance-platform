# Change Ledger (CL-TRAINING-MATRIX-SEED-2024)

## 1) Summary
- **Feature / Change name:** Seed Plantexpand Training Matrix (2024) into editable Admin requirements
- **User goal (1–2 lines):** Load April 2024 role/dept → course + frequency rules into the DB from the PDF SoR, then let admins edit/delete freely. Do not hardcode requirements into the compliance engine.
- **In scope:** Seed template module; match PDF modules → Atlas courses; `POST /requirements/seed`; Admin “Load April 2024 matrix” + frequency edit/delete; unit tests; this Change Ledger
- **Out of scope:** Hardcoding rules in FE/BE compliance paths; changing due-date math; Atlas API sync; production one-off data bake outside Admin seed action
- **Feature flag / kill switch:** N/A — admin-only seed action; rules remain normal DB rows

## 2) Impact Map (what changed)
- **Frontend:** `TrainingMatrixPanels.tsx` Admin requirements card; `trainingMatrixClient.ts` seed/update/delete
- **Backend:** `training_matrix_requirement_seed.py`; `plantexpand_matrix_2024.py` template; routes/schemas for seed
- **APIs:** `POST /api/v1/training-matrix/requirements/seed`
- **Schemas/contracts:** Seed request/response models
- **Database:** None (writes existing `training_matrix_requirements`)
- **Workflows/jobs/queues:** None
- **Config/env/flags:** None
- **Dependencies:** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive endpoint + UI; default mode `fill_missing` never overwrites admin edits
- **Tolerant reader / strict writer applied?** Course match is best-effort; unmatched modules still create rows with normalized keys and are reported
- **Breaking changes:** None
- **Migration plan:** Deploy → Admin → Training → Admin → “Load April 2024 matrix” (after Atlas CSV courses exist)
- **Rollback strategy (DB):** Delete seeded rows (notes `seed:plantexpand_2024_v1`) or revert PR; no schema change

## 4) Acceptance Criteria (AC)
- [x] AC-01: Admin can seed April 2024 matrix into `training_matrix_requirements` via API/UI
- [x] AC-02: Seeded rules remain editable (frequency) and deletable in Admin
- [x] AC-03: Compliance continues to read only DB requirements (no runtime hardcode of PDF matrix)
- [x] AC-04: `fill_missing` skips existing keys; `refresh_template` updates only prior seed-noted rows
- [x] AC-05: Unit tests cover expand + course match aliases

## 5) Testing Evidence (link to runs)
- [ ] Lint — CI after open
- [ ] Typecheck — CI after open
- [ ] Build — CI after open
- [x] Unit tests — `tests/unit/test_training_matrix_requirement_seed.py` (4 passed local)
- [ ] Integration tests — N/A
- [ ] Contract tests — N/A
- [ ] E2E Smoke — Admin seed on staging after merge

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Admin → Training → Admin → Load April 2024 matrix → rules list populated
- [x] CUJ-02: Admin changes frequency or deletes a seeded rule → gap board uses updated DB rows
- [x] CUJ-03: Re-running seed with fill_missing does not duplicate existing rules

## 7) Observability & Ops
- **Logs:** Seed failures surface as API validation/errors
- **Metrics:** None new
- **Alerts:** None new
- **Runbook updates:** After deploy + Atlas CSV upload, click “Load April 2024 matrix”; reconcile any unmatched course names; adjust dept strings if Atlas departments differ from Engineer/Workshop/Office/Management

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Seed on tenant with Atlas courses; confirm rule count; edit one frequency; confirm compliance gap uses new value
- **Canary plan:** N/A
- **Prod post-deploy checks:** Same Admin seed action; spot-check Mobile Engineers match via “Engineer” substring; fix unmatched modules manually

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Seed creates incorrect mass rules that disrupt gap board
- **Rollback steps:** Admin delete bad rules; or revert merge; optional SQL delete where notes = `seed:plantexpand_2024_v1`
- **Owner:** Platform / Workforce Training track

## 10) Evidence Pack (links)
- CI run(s): Linked after PR creation
- Staging deploy evidence: N/A at open
- Canary evidence (if applicable): N/A

## Residuals (explicitly not in this PR)
- PDF upload parser (template is transcribed from April 2024 v1 PDF)
- Auto-remap when Atlas course titles change later
- Bulk CSV import of custom matrices beyond this SoR template

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** Design locked (DB seed only; editable after; no compliance hardcode)
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete (evidence linked)
- [ ] **Gate 4:** Canary healthy (if used) (evidence linked)
- [x] **Gate 5:** Production verification plan + rollback ready
