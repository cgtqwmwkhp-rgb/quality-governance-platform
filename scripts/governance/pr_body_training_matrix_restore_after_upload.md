# Change Ledger (CL-TRAINING-MATRIX-RESTORE-AFTER-UPLOAD)

## 1) Summary
- **Feature / Change name:** Preserve & restore Atlas name maps + frequency matrix after weekly upload
- **User goal (1–2 lines):** Stop weekly CSV overwrite from appearing to wipe employee name maps; give one-click restore for April 2024 frequencies and auto-match names so admins do not re-enter every row.
- **In scope:** Import preserves prior engineer links; durable NameMap writes; `POST /name-maps/auto-match`; Admin Restore/auto-match + Restore April 2024 frequencies; Save matrix only sends changed cells
- **Out of scope:** Manual remapping UI redesign; changing due-date math
- **Feature flag / kill switch:** N/A

## 2) Impact Map (what changed)
- **Backend:** `training_matrix_import_service.py` — preserve engineer_id; `_ensure_name_map`; `auto_match_training_matrix_names`
- **API:** `POST /api/v1/training-matrix/name-maps/auto-match`; `GET /name-maps` scoped to latest import people
- **Frontend:** Admin buttons + safer matrix Save; auto-match after upload
- **Database:** None (uses existing tables)

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive endpoint; import behaviour is safer (never clears links)
- **Breaking changes:** None
- **Migration plan:** Deploy → Admin clicks Restore April 2024 frequencies + Restore/auto-match names if needed
- **Rollback:** Revert PR

## 4) Acceptance Criteria (AC)
- [x] AC-01: Re-upload does not set person.engineer_id to null when auto-match misses
- [x] AC-02: Successful links are written to training_matrix_name_maps
- [x] AC-03: Admin can one-click auto-match / restore saved maps
- [x] AC-04: Admin can one-click restore April 2024 frequencies (refresh_template)
- [x] AC-05: Matrix Save only posts changed cells (no mass-deactivate of unchanged empties)

## 5) Testing Evidence
- [x] Unit — import preserve contract + auto_match export
- [ ] CI — after open

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Admin uploads weekly Atlas CSV → prior name links remain; auto-match runs
- [x] CUJ-02: Admin clicks Restore April 2024 frequencies → grid refills Engineer/Workshop/Office/Management cycles
- [x] CUJ-03: Admin clicks Restore/auto-match names → unmatched count drops without line-by-line mapping

## 7) Observability & Ops
- Upload success message includes auto-match counts

## 8) Release Plan
- Staging/prod via normal merge; hard-refresh Training → Admin; click restore buttons if grid still empty

## 9) Rollback Plan
- **Trigger:** Auto-match links wrong people at scale
- **Steps:** Revert PR; manually correct name maps
- **Owner:** Platform / Workforce Training

## 10) Evidence Pack
- CI: linked after open

---

# Gate Checklist
- [x] **Gate 0:** Scope + AC + Change Ledger
- [x] **Gate 1:** Design locked (preserve links + restore buttons)
- [ ] **Gate 2:** CI green
- [ ] **Gate 3:** Staging verification
- [ ] **Gate 4:** N/A
- [x] **Gate 5:** Rollback ready
