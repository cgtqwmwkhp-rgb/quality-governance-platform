# Change Ledger (CL-STANDARDS-INT-W10-CASE-AUTOMAP)

> **Start gate:** Int-W9 (#1743) LIVE — tip `e05821280753`. `STACK_MAX=1`. Merge ≠ LIVE.

## 1) Summary
- **Feature / Change name:** Standards Int-W10 — case auto-map across ISO frameworks.
- **User goal:** A Near Miss (and other ops cases) that matches an ISO clause also proposes EXACT ISO-family peers from the imported 5064 edges, always as proposed. Defect F-6: the CTA must not claim UVDB / Planet Mark for cases that do not map them.
- **In scope:** `expand_iso_exact_peers`; `assess_operational_entity` TrapGuard expansion; honest CTA / empty-state / Exceptions banner; tests.
- **Out of scope:** ExactShare apply; inventing EXACT for CHAS/SSIP/CE/CEP/PM/UVDB; flipping `covers_framework`; Entra flag; IMS Overview; mapping Planet Mark from cases; auto-confirm.
- **Feature flag / kill switch:** None. Revert this PR.

## 2) Impact Map (what changed)

| ID | Surface | Before | After |
|---|---|---|---|
| SG-W10-01 | Ops assess | ISO tagging only (complaint + UVDB keywords) | ISO tagging + EXACT ISO-family peers from TrapGuard |
| SG-W10-02 | Case CEL status | `force_proposed=True` | Unchanged — every case link stays PROPOSED / `auto_applied=False` |
| SG-W10-03 | Near Miss CTA | “Map to ISO / UVDB / Planet Mark” | “Map to ISO clauses”; UVDB/PM not claimed |
| SG-W10-04 | Complaint CTA | Same oversell | “Map to ISO / UVDB”; Planet Mark still not claimed |
| SG-W10-05 | ExactShare / TrapGuard / ingest | — | Untouched except read-only `annotate_cell` |

## 3) Compatibility & Data Safety
- No schema / migration. Case links remain PROPOSED writes.
- TrapGuard load failure is swallowed so case save never 500s.
- **Rollback strategy:** Revert merge and redeploy prior tip `e05821280753`.

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| F-6 Near Miss oversells UVDB/PM | CTA names schemes the mapper does not run | CTA matches mapper: ISO (+ UVDB on complaints only) |
| Case auto-confirm | Blocked (`force_proposed`) | Still blocked |
| CHAS/SSIP/PM/UVDB EXACT | Not invented | Still not invented — expansion is ISO-family EXACT only |
| `covers_framework` | Alignment edges only | Unchanged |
| TrapGuard / ingest isolation | No `standards_requirement_axis` import | Unchanged |

## 4) Acceptance Criteria (AC)
- [x] AC-01: ISO match on a case proposes EXACT ISO-family peers from the active TrapGuard edition (e.g. `9001-7.2` → `14001-7.2`).
- [x] AC-02: Every case CEL from assess stays `PROPOSED` / `auto_applied=False` (`force_proposed`). Ingest `entity_type=near_miss` never auto-confirms.
- [x] AC-03: CHAS/SSIP/CE/CEP/PM/UVDB/IiP mappings are not expanded into invented EXACT rows.
- [x] AC-04: Near Miss / incident / RTA CTA and empty-state do not mention UVDB or Planet Mark.
- [x] AC-05: Complaint CTA may name UVDB (keyword mapper still runs); never Planet Mark.
- [x] AC-06: TrapGuard / ingest still do not import `standards_requirement_axis`. ExactShare apply untouched. Entra flag untouched. No Alembic.
- [ ] AC-07: Hosted CI green; STG+PROD SUCCESS; STG health SHA = PROD health SHA = tip → LIVE / DONE.

## 5) Testing Evidence (link to runs)
- [x] Unit: `tests/unit/test_standards_int_w10_case_automap.py`
- [x] Unit: existing `test_governed_knowledge_service.py` (never auto-confirms)
- [x] FE: `frontend/src/components/__tests__/StandardsAssessmentPanel.test.tsx`
- [ ] Hosted CI — pending PR checks

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Near Miss CTA does not promise UVDB/Planet Mark.
- [x] CUJ-02: ISO EXACT peer is proposed, not confirmed.

## 7) Observability & Ops
- TrapGuard expansion failures log `ISO EXACT peer expansion skipped` and continue.
- Health SHA matching the merge commit is **not** sufficient if staging/prod deploy fails.

## 8) Release Plan (Local → Staging → Canary → Prod)
1. Branch from LIVE tip `e05821280753` (`STACK_MAX=1`).
2. Implement + focused unit green; open PR with this ledger.
3. Merge after CI green; STG verify; PROD verify; only then mark conveyor **PROD → DONE**.

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** A case CEL is CONFIRMED without a human confirmer; CTA still names Planet Mark on Near Miss; CHAS/UVDB EXACT rows appear from expansion.
- **Rollback steps:** Revert merge; redeploy prior tip `e05821280753` via governed Staging → Production.
- **Owner:** Platform release operator / Standards Governance conveyor.

## 10) Evidence Pack (links)
- Ledger: `scripts/governance/pr_body_standards_int_w10_case_automap.md`
- Parent LIVE gate: **PR #1743** (Int-W9) @ `e05821280753`

## Gate checklist
- [x] **Gate 0:** Scope lock + AC + Change Ledger (this doc); #1743 LIVE confirmed
- [ ] **Gate 1:** Focused unit tests green locally
- [ ] **Gate 2:** CI green on tip
- [ ] **Gate 3:** STG tip verify
- [ ] **Gate 4:** PROD tip verify
- [ ] **Gate 5:** Master conveyor updated after LIVE
