# Change Ledger (CL-UX-HONESTY-PRB-VAPOUR)

> **Start gate:** #1762 LIVE — tip `891722f48`. `STACK_MAX=1`. Merge ≠ LIVE.
> L11–L16 unchanged: Entra off, no Assist triad, no Exceptions cap, no invented EXACT, Dependabot not this belt, CRM-LIB is CRM work.

## 1) Summary
- **Feature / Change name:** Remove stale “arrive in PR-B” vapour on the Standards matrix shell
- **User goal:** Prod `/compliance?view=matrix` must not tell operators that live graph panels are still coming, when PR-B is already LIVE.
- **In scope:** `compliance.standards_shell.subtitle` and `compliance.standards_matrix.subtitle` (en + cy).
- **Out of scope:** Entra flag, Assist triad, Exceptions cap, invented EXACT, Dependabot, CRM-LIB, operator write CUJs.
- **Feature flag / kill switch:** None. Revert this PR.

## 2) Impact Map (what changed)

| ID | Surface | Before | After |
|---|---|---|---|
| UX-H-01 | Standards shell subtitle | “Live graph panels arrive in PR-B.” | Honest: cells/workspace join live audits, NC, actions, risks, certs |
| UX-H-02 | Matrix subtitle | “Live coverage joins arrive in PR-B.” | Honest: cells reflect live audits, NC, actions, risks, certs |

## 3) Compatibility & Data Safety
- i18n copy only. No schema, flag, or write-path change.
- **Rollback strategy:** Revert merge and redeploy prior tip `891722f48`.

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| Matrix honesty | LIVE graph, vapour subtitle | LIVE graph, matching subtitle |
| TrapGuard / Entra / Assist / Exceptions cap | Untouched | Untouched |

## 4) Acceptance Criteria (AC)
- [x] AC-01: EN/CY subtitles do not mention PR-B.
- [x] AC-02: No Entra/Assist/Exceptions-cap/EXACT/Dependabot/CRM-LIB change.
- [ ] AC-03: Hosted CI green; STG+PROD SUCCESS (Build and Deploy not skipped); STG health SHA = PROD health SHA = tip → LIVE / DONE.

## 5) Testing Evidence (link to runs)
- [x] Unit: `standardsShellCopyHonesty.test.ts`
- [x] Measured on prod FQDN (operator SSO): matrix subtitle still said “arrive in PR-B” on LIVE `891722f48`
- [ ] Hosted CI — pending PR checks

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: `/compliance?view=matrix` still loads live cells (Covered / Gap / Unknown) and clause workspace tabs.
- [x] CUJ-02: Cover gate still honest — ISO 9001 5.2 shows Gap + Cover blocked with open imported NCs.

## 7) Observability & Ops
- Copy-only. Do not tick remaining write CUJs (complete mock audit / raise CAPA) from this PR.

## 8) Release Plan
1. Branch from LIVE tip `891722f48`.
2. Merge after CI green; Staging SUCCESS; Production SUCCESS (Build and Deploy **not** skipped); only then **LIVE**.

## 9) Rollback Plan
- **Rollback trigger:** Matrix/workspace regresses; Entra/Assist invented.
- **Rollback steps:** Revert merge; redeploy `891722f48`.
- **Owner:** Platform release operator / Standards Governance conveyor.

## 10) Evidence Pack
- Parent LIVE: **PR #1762** @ `891722f48`
- Prod CUJ: `/compliance?view=matrix` as `david.harris@plantexpand.com` on purple-water SWA

## Gate checklist
- [x] **Gate 0:** Scope lock + AC + Change Ledger; #1762 LIVE; L11–L16 held
- [x] **Gate 1:** Focused tests
- [ ] **Gate 2:** CI green on tip
- [ ] **Gate 3:** STG tip verify
- [ ] **Gate 4:** PROD tip verify
- [ ] **Gate 5:** Master conveyor updated after LIVE
