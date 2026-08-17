# Change Ledger (CL-STANDARDS-AP07-ISO-NEAR-SHARE)

> **Start gate:** #1780 LIVE — tip `8ea2b9209956`. `STACK_MAX=1`. Merge ≠ LIVE.
> David said **go Wave 1** and complete it. This PR is **AP-07 only**.

## 1) Summary
- **Feature / Change name:** AP-07 ISO NEAR proposed-share
- **User goal:** On an ISO NEAR cell (e.g. 9001 4.1), propose the same conformance evidence onto ISO NEAR peers. The required addition is named. Coverage does not count until an operator confirms.
- **In scope:** `NearShareService` (ISO family + NEAR only); cell-aggregate `near_share`; `POST /evidence/near-share` + undo; `NearShareBanner` (amber, not EXACT sky); addition_text on candidates and CEL notes.
- **Out of scope:** CE↔CE+ NEAR. Scheme EXACT (CHAS/SSIP/PM/UVDB). Entra flag. Exceptions 200-row cap. A4 four columns. Licensed marks. S4 trees. Assist triad UI.
- **Feature flag / kill switch:** None. Revert this PR.

## 2) Impact Map (what changed)

| ID | Surface | Before | After |
|---|---|---|---|
| AP07-01 | ExactShare | EXACT peers only | Unchanged — NEAR still not offered as EXACT |
| AP07-02 | Cell aggregate GET | `exact_share` only | Additive `near_share` preflight for ISO NEAR |
| AP07-03 | Evidence write API | EXACT share only | `POST /evidence/near-share` + `/undo`; `NEAR_SHARE_*` codes |
| AP07-04 | Evidence workspace | EXACT banner only | Amber NearShareBanner names the addition; apply is Propose |

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive API fields/paths. Create-only CEL writes. Status always PROPOSED + `auto_applied=True`.
- **Tolerant reader / strict writer applied?** Yes — request models `extra="forbid"`.
- **Breaking changes:** None.
- **Migration plan:** None.
- **Rollback strategy:** Revert merge and redeploy `8ea2b9209956`. Soft-deleted links remain tombstoned.

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| NEAR treated as EXACT | Operator had no NEAR share; ExactShare correctly refused | Separate API + amber banner; never CONFIRMED on apply |
| Coverage honesty | `auto_applied && status != confirmed` already excluded | Unchanged — proposed NEAR share does not paint covered |
| Scheme / CE+ leakage | CE↔CE+ NEAR exists in 5064 | Source/target must both be ISO numbering family |
| Exceptions inbox | 200-row page | Untouched |

## 4) Acceptance Criteria (AC)
- [x] AC-01: ISO 4.1 NEAR plan offers ISO peers and surfaces `addition_text`.
- [x] AC-02: ExactShare on 4.1 still returns `no_exact_peers`.
- [x] AC-03: CE firewalls NEAR and CHAS sources return `no_iso_near_peers`.
- [x] AC-04: Apply writes PROPOSED + auto_applied; notes say NEAR is not EXACT; scheme target → `NEAR_SHARE_TARGET_BLOCKED`.
- [x] AC-05: Banner copy is Propose / Required addition / NEAR is not EXACT. Sky EXACT banner unchanged.
- [ ] AC-06: Hosted CI green; STG+PROD SUCCESS (Build and Deploy not skipped); SHA match → LIVE.

## 5) Testing Evidence (link to runs)
- [x] Unit (local): `test_standards_near_share_service`, existing `test_standards_exact_share_service`
- [x] Frontend: `NearShareBanner.test.tsx`
- [ ] Hosted CI — pending PR checks

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Operator opens ISO 9001 4.1 with conformance evidence → amber banner lists ISO NEAR peers and the required addition.
- [x] CUJ-02: Propose share creates PROPOSED peer CEL rows that do not count as coverage; Undo soft-deletes those ids when unmodified.

## 7) Observability & Ops
- Conflict responses use `NEAR_SHARE_*` codes (source blocked, matrix not loaded / version mismatch, target blocked, nonconformance signal).
- Support: if share is refused after matrix re-import, refresh workspace (`matrix_version_id` mismatch).
- Exceptions inbox still pages at 200.

## 8) Release Plan (Local → Staging → Canary → Prod)
1. Merge after required CI green (`STACK_MAX=1`; admin-squash authorised).
2. Staging: `/compliance` matrix → ISO 4.1 workspace → near-share banner → propose → undo. Confirm ExactShare still absent on 4.1.
3. Promote PROD; verify `/api/v1/health` version = main tip; Production **Build and Deploy SUCCESS (not skipped)**.

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** NEAR apply confirms coverage, treats CE/CHAS as ISO NEAR, or ExactShare starts offering NEAR as EXACT.
- **Rollback steps:** Revert merge commit; redeploy prior tip `8ea2b9209956` via governed Staging → Production path.
- **Owner:** Platform release operator / Standards Governance conveyor.

## 10) Evidence Pack (links)
- Branch: `feat/ap07-iso-near-share`
- Ledger: `scripts/governance/pr_body_standards_ap07_iso_near_share.md`
- Parent LIVE: #1780 @ `8ea2b9209956`

## Gate checklist
- [x] **Gate 0:** Scope lock + AC + Change Ledger
- [x] **Gate 1:** Focused unit tests green locally
- [ ] **Gate 2:** CI green on tip
- [ ] **Gate 3:** STG tip verify
- [ ] **Gate 4:** PROD tip verify
- [ ] **Gate 5:** Conveyor / action plan AP-07 stamped LIVE
