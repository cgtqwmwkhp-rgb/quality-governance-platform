# Change Ledger (CL-STANDARDS-WAVE3-PR-F1)

## 1) Summary
- **Feature / Change name:** Standards Wave 3 PR-F slice 1 — unified Evidence Centre (catalogue strip + themes).
- **User goal:** Stop Evidence mode looking like an ISO-only four-card centre; show the same programme frameworks as Matrix (Planet Mark, Achilles UVDB, CE/CEP, CHAS/SSIP, IiP, 22301, …) with honest metrics and specialist deep-links — no new hub page.
- **In scope:** Rename Evidence title; score cards driven by `STANDARDS_MATRIX_FRAMEWORKS` + shared theme presets; buyer preset includes CHAS/SSIP; PM/UVDB specialist links; filter bridges; i18n.
- **Out of scope:** Forking `/planet-mark` or `/uvdb` UIs into Evidence; clause-coverage APIs for CE/CHAS/22301; automation digests / analytics (F3); deleting Assurance nav entries.
- **Feature flag / kill switch:** None. Revert this PR.

## 2) Impact Map (what changed)
| ID | Surface | Before | After |
|---|---|---|---|
| SG-F-01 | Evidence title | “ISO Compliance Evidence Center” | “Standards Evidence Center” |
| SG-F-02 | Score cards | `listStandards()` ISO four only | Catalogue frameworks for active preset |
| SG-F-03 | Theme presets | Matrix only (`core`…) | Shared ISO/People/Environment/BCP/Cyber/Buyer/All |
| SG-F-04 | Buyer preset | UVDB + PM | CHAS + SSIP + UVDB + PM |
| SG-F-05 | PM / UVDB | Invisible in Evidence | Cards + deep-link specialist SoR |

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive UI; no schema change; scheme cards never invent Full/Partial/Gaps %.
- **Tolerant reader / strict writer applied?** N/A (read UI).
- **Breaking changes:** Matrix default preset `core` → `iso` (adds 27001 + 22301 columns when preset default used).
- **Migration plan:** None.
- **Rollback strategy (DB):** N/A — revert merge / redeploy prior tip.

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| Evidence honesty | ISO-only branding | Multi-framework; non-ISO cards withhold fake % |
| Specialist SoR | Separate nav only | Deep-link from Evidence cards (no fork) |
| Theme filters | Matrix incomplete vs user ask | Environment + BCP + fixed buyer |

## 4) Acceptance Criteria (AC)
- [x] AC-01: Evidence title is Standards Evidence Center (i18n).
- [x] AC-02: Default All preset shows cards for catalogue frameworks including PM/UVDB/CE/CHAS.
- [x] AC-03: Buyer preset shows CHAS+SSIP+UVDB+PM and hides ISO 9001.
- [x] AC-04: PM/UVDB cards link to `/planet-mark` and `/uvdb` without inventing coverage %.
- [ ] AC-05: Hosted CI green; STG=PROD tip LIVE after merge.

## 5) Testing Evidence (link to runs)
- [x] Unit: `standardsMatrixFilters` + `ComplianceEvidence` (incl. catalogue card test)
- [ ] Hosted CI — pending PR checks

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Open /compliance Evidence → see multi-framework strip.
- [x] CUJ-02: Buyer preset → CHAS/PM/UVDB cards; Open Planet Mark / UVDB links.

## 7) Observability & Ops
- No new backends. Support: if card shows “—”, that is intentional honesty until a coverage API exists for that framework.

## 8) Release Plan (Local → Staging → Canary → Prod)
1. Merge after CI green (STACK_MAX tip-chase).
2. Staging: hard-refresh /compliance Evidence; confirm strip + presets.
3. Promote PROD; verify health tip = main tip.

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Evidence cards invent fake coverage for schemes, or specialist SoRs broken.
- **Rollback steps:** Revert merge; redeploy prior tip via governed Staging → Production.
- **Owner:** Platform release operator / Standards Governance conveyor.

## 10) Evidence Pack (links)
- Branch: `feat/standards-wave3-pr-f-evidence-unify`
- Ledger: `scripts/governance/pr_body_standards_wave3_pr_f1.md`
- Parent LIVE: #1734 @ `8eeaf4ce0456`
- Spec canvas: `standards-unified-evidence-center.canvas.tsx`

## Gate checklist
- [x] **Gate 0:** Scope lock + AC + Change Ledger
- [x] **Gate 1:** Focused unit tests green locally
- [ ] **Gate 2:** CI green on tip
- [ ] **Gate 3:** STG tip verify
- [ ] **Gate 4:** PROD tip verify
- [ ] **Gate 5:** Hero board / mission / allowlist updated after LIVE
