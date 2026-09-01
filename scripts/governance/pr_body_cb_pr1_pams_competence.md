# Change Ledger (CL-CB-PR1-PAMS-COMPETENCE)

## 1) Summary
- **Feature / Change name:** CB-PR1 — read-only PAMS competence snapshot + board API
- **User goal:** Store issued plant skills from PAMS in QGP so a later board can show issued vs demonstrated. This slice does not change the live CompetencyDashboard.
- **In scope:** Snapshot tables; hourly raw SELECT of `vw_plantex_engineercompetence`; `GET /api/v1/workforce/competence/board?family=pams` behind `competence_board_enabled` / `FF_COMPETENCE_BOARD` default false (404 when closed); join on `pams_technician_id` then exact email
- **Out of scope:** Live CompetencyDashboard / WDP analytics; Atlas family (CB-PR3); change requests (CB-PR2); assessment overlay (CB-PR4); schedule quorum (CB-PR5); flag-on (CB-PR6); PAMS writes; bulk Users; Entra
- **Feature flag / kill switch:** `COMPETENCE_BOARD_ENABLED` / `FF_COMPETENCE_BOARD` default false. Kill = flag off + disable `sync-pams-competence` beat. Kill SHA = previous LIVE.

## 2) Impact Map (what changed)
- **Frontend:** `competence_board: false` in `useFeatureFlag` defaults only. CompetencyDashboard unchanged.
- **Backend:** snapshot service, Celery task, board route, models, alembic
- **APIs:** Additive `GET /api/v1/workforce/competence/board` — 404 while flag closed; `engineer:update` when open
- **Database / flags:** Additive `pams_competence_snapshots` / `_rows` / `_current`. No backfill.
- **Workflows/jobs:** Hourly beat at :10, offset from technicians at :00

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive tables and a closed flag. Existing WDP matrix still paints QGP asset types.
- **Breaking changes:** None
- **Migration plan:** Additive. Pointer flip only after rows are intact. Failed fetch does not replace the current snapshot.
- **Rollback strategy (DB):** Flag off. Column/tables may remain unused; drop via reverse migration if needed.

## Compliance Delta
- **ISO 9001 7.2 / ISO 45001 7.2:** Issued plant competence stays in PAMS. QGP reads a snapshot. Assessment overlay is a later slice. QGP never writes PAMS.
- **What this PR does not claim:** Demonstrated dates on PAMS skills. Statutory first-aid/fire-marshal coverage. Live page showing the 114 characteristics.

## 4) Acceptance Criteria (AC)
- [x] AC-01: Flag default false. `require_competence_board_enabled` returns 404 when closed.
- [x] AC-02: `family=atlas` is 422 (CB-PR3). `family=pams` is the only shipped family.
- [x] AC-03: Snapshot uses raw SELECT of `vw_plantex_engineercompetence`, not reflection.
- [x] AC-04: Engineer join is `pams_technician_id` then exact email. Name-only rows stay unmapped.
- [x] AC-05: Stale snapshot (>25h or missing) sets `banner` / `stale`. Missing characteristic is absent, never `not_assessed`.
- [x] AC-06: Failed PAMS read does not flip `pams_competence_current`.
- [x] AC-07: CompetencyDashboard still calls WDP analytics only.
- [x] AC-08: Viewer without `engineer:update` cannot read the board. Census ceiling held.

## 5) Testing Evidence (link to runs)
- [ ] Unit — `tests/unit/test_pams_competence_snapshot.py`
- [ ] Full CI — linked after PR checks

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Flag off → board 404; live CompetencyDashboard unchanged
- [x] CUJ-02: Snapshot row with technician_id maps to Engineer.pams_technician_id; name-only does not
- [x] CUJ-03: Empty/stale snapshot returns a banner, not grey not_assessed cells

## 7) Observability & Ops
- **Logs:** `pams_competence_snapshot` structured info; no tokens
- **Runbook:** After LIVE, leave flag false until a successful snapshot is inspected. Then CB-PR2.

## 8) Release Plan
- **Staging:** Flag stays false. Confirm 404 on `/api/v1/workforce/competence/board?family=pams`. Confirm `/workforce/dashboard` still loads WDP matrix.
- **Prod post-deploy:** healthz; `build_sha` == tip; flag false; Entra stays false

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Board reachable with flag off, or any PAMS write, or CompetencyDashboard changed
- **Rollback steps:** Revert squash on `main` and redeploy previous LIVE SHA
- **Owner:** David Harris

## 10) Evidence Pack
- CI run(s): Linked after PR creation

---

# Gate Checklist
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts (closed flag; additive snapshot; live page untouched)
- [ ] **Gate 2:** CI green
- [ ] **Gate 3:** Staging verification
- [ ] **Gate 4:** Canary (N/A)
- [x] **Gate 5:** Production verification plan + monitoring ready
