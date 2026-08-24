# Change Ledger (CL-STANDARDS-WAVE2-PR-C-HOTFIX)

## 1) Summary
- **Feature / Change name:** Standards Wave 2 PR-C hotfix — Bugbot findings on relocated clauses / reapply / trap verdicts.
- **User goal:** After #1731 LIVE, close the three correctness gaps Bugbot flagged so matrix cells, re-import, and trap hover are honest.
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

- **Frontend:** `StandardsMatrixShell` relocated clause map; filters homeUrl.
- **Backend:** `standards_alignment_import_service` reactivation; `standards_trap_guard` matched-ref row verdict.
- **Database:** No Alembic.

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Behavioural correction only; no schema change.
- **Tolerant reader / strict writer applied?** Yes — empty-edge reactivate refused.
- **Breaking changes:** None.
- **Migration plan:** None.
- **Rollback strategy (DB):** N/A — revert merge / redeploy prior tip.

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
- [ ] AC-05: Hosted CI green; STG=PROD tip LIVE after merge.

## 5) Testing Evidence (link to runs)
- [x] Unit (local): reactivation + relocated annotate tests
- [x] Vitest (local): `standardsMatrixFilters`
- [x] mypy clean on touched services
- [ ] Hosted CI — pending PR checks

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Operator opens matrix on a relocated clause (e.g. 45001 8.1.3 under printed 6.3) → live cell and workspace open use the framework-local number.
- [x] CUJ-02: Operator re-applies a superseded 5064 payload → that edition reactivates and catalogue verdicts roll back; trap hover shows row verdict for relocated cells.

## 7) Observability & Ops
- No new telemetry. Seed script prints `reactivated` when rolling back to a prior checksum.
- Support: if matrix shows Unknown on relocated rows after deploy, confirm tip sha includes this hotfix and refresh `/compliance?view=matrix`.

## 8) Release Plan (Local → Staging → Canary → Prod)
1. Merge after required CI green (STACK_MAX tip-chase; allowlist `!1732`).
2. Staging: `/compliance?view=matrix` — hover a relocated DIFFERENT cell; confirm row verdict; dry-run then re-apply seed if needed.
3. Promote PROD; verify `/api/v1/health` version = main tip; smoke CUJ-01/02.

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Matrix false-Unknown on relocated clauses, import apply no-ops when rolling back, or trap hover missing DIFFERENT.
- **Rollback steps:** Revert merge commit; redeploy prior tip via governed Staging → Production path.
- **Owner:** Platform release operator / Standards Governance conveyor.

## 10) Evidence Pack (links)
- Branch: `feat/standards-wave2-pr-c-bugbot`
- Ledger: `scripts/governance/pr_body_standards_wave2_pr_c_hotfix.md`
- Parent LIVE: #1731 @ `9046a826`

## Gate checklist
- [x] **Gate 0:** Scope lock + AC + Change Ledger
- [x] **Gate 1:** Focused unit/FE tests green locally
- [ ] **Gate 2:** CI green on tip
- [ ] **Gate 3:** STG tip verify
- [ ] **Gate 4:** PROD tip verify
- [ ] **Gate 5:** Hero board / mission / allowlist updated after LIVE
