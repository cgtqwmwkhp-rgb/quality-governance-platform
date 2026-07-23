# Change Ledger (CL-HOTFIX-HS-EXCEL-RTA-TIME)

## 1) Summary
- **Feature / Change name:** HOTFIX — clip Excel RTA time/strings on historic import Commit
- **User goal (1–2 lines):** Unblock once-off H&S Excel Commit after prod 500 `StringDataRightTruncationError` on `collision_time` VARCHAR(10).
- **Depends on:** #1256 LIVE
- **In scope:** `_clip_str` + defensive clipping in `HsExcelImportService._create_rta`; preserve raw time in `reporter_submission.time_raw`
- **Out of scope:** Widening `collision_time` column; portal time UX
- **Root cause:** Excel free-text times (`Approx 8 am`, `1500 approx`) exceed `road_traffic_collisions.collision_time` VARCHAR(10); flush fails mid-Commit
- **Feature flag / kill switch:** None

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** None
- **Backend (handlers/services):** `hs_excel_import_service.py`
- **APIs (endpoints changed/added):** None (same `/hs-imports/excel/commit`)
- **Schemas/contracts:** None
- **Database (migrations/entities/indexes):** None
- **Workflows/jobs/queues:** None
- **Config/env/flags:** None
- **Dependencies:** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Truncate to column limits; raw value kept in submission JSON
- **Tolerant reader / strict writer applied?** Yes — Excel reader tolerant; DB writer clips
- **Breaking changes:** None
- **Migration plan:** N/A
- **Rollback strategy (DB):** No DB change — redeploy prior SHA

## 4) Acceptance Criteria (AC)
- [x] AC-01: Times longer than 10 chars clip without raising
- [x] AC-02: Raw time preserved in `reporter_submission.time_raw`
- [x] AC-03: Unit coverage for `_clip_str`

## 5) Testing Evidence (link to runs)
- [x] Local — clip against prep workbook over-length times
- [ ] CI — this PR
- [ ] Prod — re-run Commit after tip LIVE

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Dry-run still plans 34/26/0/22 on Round 2 prep workbook
- [x] CUJ-02: Commit no longer fails on VARCHAR(10) collision_time

## 7) Observability & Ops
- **Logs:** Prior prod error request_id `da6022147f3248b1aaaa7e890754ca25`
- **Metrics:** None new
- **Alerts:** None
- **Runbook updates:** Historic Excel Commit uses IMPORT PREP Round2.xlsx after this hotfix

## 8) Release Plan (Local -> Staging -> Canary -> Prod)
- **Staging verification:** Manual staging deploy if auto-gated by advisory DAST
- **Canary plan:** N/A — hotfix
- **Prod post-deploy checks:** Dry-run + Commit prep workbook; KPI spot-check

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Import Commit still 500 after deploy
- **Rollback steps:** Redeploy prior SHA; keep Excel archived
- **Owner:** Governance / Quality platform team

## 10) Evidence Pack (links)
- CI run(s): Linked on this PR checks tab
- Staging deploy evidence: After merge
- Canary evidence (if applicable): N/A
- Prod docker log evidence: `StringDataRightTruncationError` on `collision_time`
- Prod version after fix: TBD

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved (import clip only)
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Prod Commit verification after deploy
- [x] **Gate 4:** Canary healthy (if used) — N/A
- [x] **Gate 5:** Production verification plan + monitoring ready
