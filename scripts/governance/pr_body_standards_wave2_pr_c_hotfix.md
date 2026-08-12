# Change Ledger (CL-STANDARDS-WAVE2-PR-C-HOTFIX)

## 1) Summary
- **Feature / Change name:** Standards Wave 2 PR-C hotfix — Bugbot findings on relocated clauses / reapply / trap verdicts.
- **User goal:** After #1731 merge, close the three correctness gaps Bugbot flagged so LIVE matrix cells, re-import, and trap hover are honest.
- **In scope:** Framework-local clause load (single getMatrix), reactivate superseded edition on reapply, trap `row_verdict` via matched `clause_ref`, pin ISO 27001 home URL.
- **Out of scope:** Wave 2 PR-D (EXACT/SLA/Schedule), Wave 3.
- **Feature flag / kill switch:** None. Revert this PR.

## 2) Impact Map (what changed)
| ID | Surface | Before | After |
|---|---|---|---|
| SG-C-07a | Matrix live cells | Shared display clause for all frameworks | Union of framework-local clauses; lookup by reloc map |
| SG-C-07b | Alignment reapply | Superseded checksum match no-ops | Reactivates that edition; supersedes current active |
| SG-C-07c | Trap annotate | `row_verdict(clause_number)` misses relocated | Resolve via matched edge `clause_ref` |
| SG-C-07d | ISO 27001 homeUrl | Bare `/standard/27001` alias | Pinned `/standard/82875.html` |

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Behavioural correction only; no schema change.
- **Tolerant reader / strict writer applied?** Yes — empty-edge reactivate refused.
- **Breaking changes:** None.
- **Migration plan:** None.
- **Rollback strategy (DB):** N/A.

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| Relocated clause evidence | Could miss / show Unknown | Loads framework-local cell |
| Superseded reapply | Silent no-op | Reactivation path |
| Trap row verdict on relocated | Null despite trap peers | DIFFERENT/NEAR from printed row |
| ISO 27001 home link | Edition-following alias | Pinned 2022 catalogue record |

## 4) Acceptance Criteria (AC)
- [x] AC-01: Unit test reactivates superseded edition.
- [x] AC-02: Unit test annotate_cell for 45001/8.1.3 and 27001/6.1.
- [x] AC-03: FE still one getMatrix call (no N+1).
- [x] AC-04: ISO 27001 homeUrl pinned in filters test.

## 5) Testing Evidence (link to runs)
- Local: reactivation + relocated annotate unit tests passed; filters vitest passed; mypy clean on touched services.

## 6) Risk Assessment
- **Risk level:** Low–Medium (correctness paths operators use on import/matrix).
- **Blast radius:** Standards matrix chrome + alignment import apply.
- **Monitor:** Staging matrix after tip deploy; re-seed dry-run then apply.

## 7) Operator notes
- Seed script now prints `reactivated` when rolling back to a prior checksum.

## Gate checklist
- [x] **Gate 0:** Scope lock + AC + Change Ledger
- [x] **Gate 1:** Focused unit/FE tests green locally
- [ ] **Gate 2:** CI green on tip
- [ ] **Gate 3:** STG = tip = PROD LIVE
