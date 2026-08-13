# Change Ledger (CL-STANDARDS-SG-D03B-ISO22301-ICON)

> **Start gate:** SG-D-03 (#1746) LIVE — tip `9d5abe754414`. `STACK_MAX=1`. Merge ≠ LIVE.
> **Trigger:** Prod SWA `/compliance` (sidebar Standards) throws minified React #130.

## 1) Summary
- **Feature / Change name:** Standards hotfix — Evidence clause/gaps icons must never be `undefined`.
- **User goal:** Opening Standards from the sidebar must render. ISO 22301 (and any future catalogue id) must not crash the Evidence shell.
- **In scope:** `iconForStandard` fallback; ISO 22301 icon/class rows; unguarded `createElement` / `<Icon />` sites in `ComplianceEvidence.tsx`; regression tests.
- **Out of scope:** D4 SLA/owner; D5 export appendix; Entra flag; TrapGuard/ingest; changing sidebar default from Evidence to `?view=matrix`; ErrorBoundary message surfacing.
- **Feature flag / kill switch:** None. Revert this PR.

## 2) Impact Map (what changed)

| ID | Surface | Before | After |
|---|---|---|---|
| SG-D-03b-01 | `/compliance` Evidence (default clauses, All standards) | `React.createElement(undefined)` for `iso22301` → React #130 | `iconForStandard` always returns a component; 22301 uses Clock |
| SG-D-03b-02 | Gap list + auto-tag + clause details | Unguarded `standardIcons[id]` | Same fallback |
| SG-D-03b-03 | Icon class names | Dynamic `text-${color}-400` (JIT-unsafe) on those headings | Explicit class maps + primary fallback |

## 3) Compatibility & Data Safety
- Frontend-only. No API, schema, or flag change.
- **Rollback strategy:** Revert merge and redeploy prior tip `9d5abe754414`.

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| Operator can open Standards | Prod Evidence shell crashes on ISO 22301 | Catalogue ids without a dedicated icon render Award; 22301 has Clock |
| Cover / EXACT / catalogues | Unchanged | Unchanged |
| Fake coverage % | Unchanged | Unchanged |

## 4) Acceptance Criteria (AC)
- [x] AC-01: Clause View with `iso22301` + an unmapped catalogue id renders without throw.
- [x] AC-02: Gap Analysis row for `iso22301` renders without throw.
- [x] AC-03: No Alembic; TrapGuard/ingest/`covers_framework`/Entra flag/D4–D5 untouched.
- [ ] AC-04: Hosted CI green; STG+PROD SUCCESS; STG health SHA = PROD health SHA = tip → LIVE / DONE.

## 5) Testing Evidence (link to runs)
- [x] FE: `frontend/src/pages/__tests__/ComplianceEvidence.test.tsx` (22301 clauses + 22301 gaps)
- [ ] Hosted CI — pending PR checks

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Operator opens sidebar Standards (`/compliance`, default Evidence/clauses, All standards) while the live catalogue includes ISO 22301 → page renders, no Error Boundary.
- [x] CUJ-02: Operator opens Gap Analysis with an ISO 22301 gap row → row renders, no Error Boundary.

## 7) Observability & Ops
- No new telemetry. Existing `[QGP Error] ErrorBoundary/componentDidCatch` remains the crash signal.
- Workaround until LIVE: `/compliance?view=matrix` (countdown strip) does not mount this Evidence icon path.

## 8) Release Plan (Local → Staging → Canary → Prod)
1. Branch from LIVE tip `9d5abe754414` (`STACK_MAX=1`).
2. Focused Vitest green; open PR with this ledger.
3. Merge after CI green; STG verify; PROD verify; only then mark conveyor **PROD → DONE**.

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Evidence still throws #130; icons missing for mapped ISO ids; D4/D5/Entra/TrapGuard accidentally land.
- **Rollback steps:** Revert merge; redeploy prior tip `9d5abe754414` via governed Staging → Production.
- **Owner:** Platform release operator / Standards Governance conveyor.

## 10) Evidence Pack (links)
- Ledger: `scripts/governance/pr_body_standards_sg_d03b_iso22301_icon.md`
- Parent LIVE gate: **PR #1746** (SG-D-03) @ `9d5abe754414`

## Gate checklist
- [x] **Gate 0:** Scope lock + AC + Change Ledger (this doc); #1746 LIVE confirmed
- [x] **Gate 1:** Focused FE tests green locally
- [ ] **Gate 2:** CI green on tip
- [ ] **Gate 3:** STG tip verify
- [ ] **Gate 4:** PROD tip verify
- [ ] **Gate 5:** Master conveyor updated after LIVE
