# Change Ledger (CL-STANDARDS-INT-W7-CERT-CYCLE)

> **Start gate:** Int-W6 (#1740) LIVE — tip `6a15ff86a136`. `STACK_MAX=1`. Merge ≠ LIVE.

## 1) Summary
- **Feature / Change name:** Standards Int-W7 — Cert digest feeds by typed scheme.
- **User goal:** Monitoring cert digest no longer dumps PAT, insurance and ISO into one `register` bucket. Framework-named register certificates feed their matrix scheme; operational items stay operational.
- **In scope:** `roll_up_cert_expiry` re-buckets register items via existing `framework_for_certificate`; additive `kind` on digest rows; FE mapper passes `kind` through.
- **Out of scope:** Changing TrapGuard / ingest / `covers_framework`; inventing CHAS/SSIP EXACT; rewriting the certificate register SoR; `/standards` hub; assessment-cycle workflow UI.
- **Feature flag / kill switch:** None. Revert this PR.

## 2) Impact Map (what changed)

| ID | Surface | Before | After |
|---|---|---|---|
| SG-W7-01 | F3 cert digest `by_scheme` | Every register row → `scheme=register` | Named ISO/CE/CHAS/… → matrix framework id; PAT/insurance → `operational` |
| SG-W7-02 | Digest `soonest` | `scheme=register` | Same typed feed as `by_scheme`; additive `kind` |
| SG-W7-03 | Monitoring FE | Displays whatever scheme the API sends | Mapper keeps `kind`; fixture uses `9001` not `register` |
| SG-W7-04 | Cell aggregate `cert_count` | Unchanged (W4 unmatched proof_scope) | Unchanged |
| SG-W7-05 | Shelf SoR `scheme` field | Still `register` on register items | Still `register` — taxonomy is a digest feed, not a SoR rewrite |

## 3) Compatibility & Data Safety
- No schema / migration. Read-model only.
- **Tolerant reader / strict writer applied?** FE treats missing `kind` as `scheme_shelf`.
- **Breaking changes:** Clients that keyed on `by_scheme[].scheme === "register"` for ISO certs will see `9001` (etc.) instead. That is the point of W7.
- **Rollback strategy:** Revert merge; redeploy prior tip `6a15ff86a136`.

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| Register flood in Monitoring digest | One `register` feed | Typed feeds; PAT cannot appear as 9001/CHAS |
| Matrix `cert_count` honesty | W4 unmatched | Unchanged |
| CHAS/SSIP EXACT | Not invented | Still not invented |
| ≥98% + EXACT gate | Unchanged | Unchanged |

## 4) Acceptance Criteria (AC)
- [x] AC-01: Register item named/typed ISO 9001 → digest `by_scheme` key `9001`, `kind=framework_certificate`.
- [x] AC-02: PAT / insurance register items → `operational`; never `9001` or `chas`.
- [x] AC-03: UVDB / Planet Mark scheme-shelf items keep their existing scheme keys (`kind=scheme_shelf`).
- [x] AC-04: No `by_scheme` row with `scheme=register` when items are classifiable or operational.
- [x] AC-05: TrapGuard / ingest / `covers_framework` untouched.
- [ ] AC-06: Hosted CI green; STG+PROD SUCCESS; STG health SHA = PROD health SHA = tip → LIVE / DONE.

## 5) Testing Evidence (link to runs)
- [x] Unit: `tests/unit/test_standards_digest_service.py` (15 passed locally)
- [ ] Vitest: `ComplianceAutomation.standardsDigest.test.tsx` (fixture updated)
- [ ] Hosted CI — pending PR checks

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Monitoring Standards health cert digest feeds ISO 9001 separately from PAT.
- [x] CUJ-02: `/compliance` matrix cert_count still uses W4 unmatched proof_scope (not this PR).

## 7) Observability & Ops
- Digest is read-model. No re-seed required.
- Health SHA matching the merge commit is **not** sufficient if staging/prod deploy fails.

## 8) Release Plan (Local → Staging → Canary → Prod)
1. Branch from LIVE tip `6a15ff86a136` (`STACK_MAX=1`) — done.
2. Implement + focused unit green; open PR with this ledger.
3. Merge after CI green; STG verify; PROD verify; only then mark conveyor **PROD → DONE**.

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Digest invents framework proof for PAT/insurance; CHAS/SSIP EXACT appears; matrix cert_count changes unexpectedly.
- **Rollback steps:** Revert merge; redeploy prior tip `6a15ff86a136` via governed Staging → Production.
- **Owner:** Platform release operator / Standards Governance conveyor.

## 10) Evidence Pack (links)
- Ledger: `scripts/governance/pr_body_standards_int_w7_cert_cycle.md`
- Parent LIVE gate: **PR #1740** (Int-W6) @ `6a15ff86a136`

## Gate checklist
- [x] **Gate 0:** Scope lock + AC + Change Ledger (this doc); #1740 LIVE confirmed
- [x] **Gate 1:** Focused unit tests green locally
- [ ] **Gate 2:** CI green on tip
- [ ] **Gate 3:** STG tip verify
- [ ] **Gate 4:** PROD tip verify
- [ ] **Gate 5:** Master conveyor updated after LIVE
