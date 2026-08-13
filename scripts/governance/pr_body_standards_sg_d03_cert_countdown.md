# Change Ledger (CL-STANDARDS-SG-D03-CERT-COUNTDOWN)

> **Start gate:** SG-D-02 (#1745) LIVE — tip `c6580d4a0a3f`. `STACK_MAX=1`. Merge ≠ LIVE.

## 1) Summary
- **Feature / Change name:** Standards SG-D-03 — cert expiry countdown strip on `/compliance` matrix.
- **User goal:** See days-to-expiry per visible framework column, attributed the same way as the live graph (PAT / insurance / training never set ISO or CHAS days).
- **In scope:** `framework_countdown` on `GET /cell-aggregate/matrix`; matrix strip of chips for visible columns; unmatched-on-shelf honesty note.
- **Out of scope:** SLA/owner (D4); export appendix (D5); Entra flag; TrapGuard/ingest; Alembic; inventing EXACT for CHAS/SSIP/PM/UVDB; Monitoring digest rewrite.
- **Feature flag / kill switch:** None. Revert this PR.

## 2) Impact Map (what changed)

| ID | Surface | Before | After |
|---|---|---|---|
| SG-D-03-01 | Matrix API | Cells + truncation only | + `framework_countdown` (soonest attributed expiry per requested column) |
| SG-D-03-02 | `/compliance` matrix | No per-column cert days | Countdown chips for visible columns (expired / due-soon ≤30d / current / none) |
| SG-D-03-03 | Operational shelf items | Could be misread as ISO proof | PAT/insurance/training set `unmatched_on_shelf`; they do not set any column `next_expiry` |

## 3) Compatibility & Data Safety
- Additive JSON field on an existing GET. Older clients ignore it.
- Uses the already-cached cert shelf from `get_cell` — no extra N+1.
- **Rollback strategy:** Revert merge and redeploy prior tip `c6580d4a0a3f`.

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| Attribution honesty | Certs panel + Monitoring board only | Matrix strip uses `framework_for_certificate` + `cert_schemes`; operational items never paint ISO/CHAS days |
| Fake coverage % | Unchanged | Unchanged — days, not percentages |
| Cover / EXACT / catalogues | Unchanged | Unchanged |

## 4) Acceptance Criteria (AC)
- [x] AC-01: Matrix summary includes `framework_countdown` for requested frameworks.
- [x] AC-02: A dated ISO 9001 register cert sets 9001 `next_expiry` / days; CHAS stays `none` unless it has its own cert.
- [x] AC-03: PAT / insurance / training never set any framework `next_expiry`; `unmatched_on_shelf` is true when they are present.
- [x] AC-04: Visible-column chips render expired / due-soon / current / none; unmatched honesty copy shows when needed.
- [x] AC-05: No Alembic; TrapGuard/ingest/`covers_framework`/Entra flag untouched. D4–D5 out of scope.
- [ ] AC-06: Hosted CI green; STG+PROD SUCCESS; STG health SHA = PROD health SHA = tip → LIVE / DONE.

## 5) Testing Evidence (link to runs)
- [x] Unit: `tests/unit/test_standards_cell_aggregate_service.py` (countdown attribution + matrix payload)
- [x] FE: `frontend/src/pages/compliance/__tests__/standardsMatrixCountdown.test.tsx`
- [ ] Hosted CI — pending PR checks

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: ISO 9001 dated cert → 9001 chip shows days; CHAS chip is “No dated cert”.
- [x] CUJ-02: PAT on the shelf → unmatched note; 9001 days unchanged.

## 7) Observability & Ops
- No new telemetry. Countdown is derived from the existing cert shelf snapshot.
- Health SHA matching the merge commit is **not** sufficient if staging/prod deploy fails.

## 8) Release Plan (Local → Staging → Canary → Prod)
1. Branch from LIVE tip `c6580d4a0a3f` (`STACK_MAX=1`).
2. Implement + focused unit green; open PR with this ledger.
3. Merge after CI green; STG verify; PROD verify; only then mark conveyor **PROD → DONE**.

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** PAT/insurance paints ISO/CHAS days; strip invents coverage %; D4–D5 / Entra / TrapGuard accidentally land.
- **Rollback steps:** Revert merge; redeploy prior tip `c6580d4a0a3f` via governed Staging → Production.
- **Owner:** Platform release operator / Standards Governance conveyor.

## 10) Evidence Pack (links)
- Ledger: `scripts/governance/pr_body_standards_sg_d03_cert_countdown.md`
- Parent LIVE gate: **PR #1745** (SG-D-02) @ `c6580d4a0a3f`

## Gate checklist
- [x] **Gate 0:** Scope lock + AC + Change Ledger (this doc); #1745 LIVE confirmed
- [x] **Gate 1:** Focused unit tests green locally
- [ ] **Gate 2:** CI green on tip
- [ ] **Gate 3:** STG tip verify
- [ ] **Gate 4:** PROD tip verify
- [ ] **Gate 5:** Master conveyor updated after LIVE
