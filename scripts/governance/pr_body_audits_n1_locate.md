# Change Ledger (CL-AUDITS-N1-LOCATE)

> **Start gate:** #1775 LIVE — tip `e8c46a31f4b`. `STACK_MAX=1`. Merge ≠ LIVE.
> David said **continue** (hardened 20m conveyor). L11–L16 unchanged: Entra off, no Assist triad, no Exceptions cap, no invented EXACT, Dependabot not this belt, CRM-LIB is CRM work.
> N-BUILD-3, A4 four columns, Findings redesign, and a new calendar SoR are not this slice.

## 1) Summary
- **Feature / Change name:** N1 — locate complete
- **User goal:** Every programme is findable; the Audits page does not pretend to be the universe.
- **In scope:** Programme chips stay mounted at count 0. Runs truncation banner (`Showing {loaded} of {total} runs`). Planet Mark home strip → `/audits?source=planet_mark`. List Comfort (default) / Compact (tighter rows, same columns, keyboard-openable).
- **Out of scope:** A4 four-column board. N-BUILD-3. Entra. EXACT. Findings redesign. New calendar SoR. UVDB/PM twin kanbans. Dependabot.
- **Feature flag / kill switch:** None. Revert this PR.

## 2) Impact Map (what changed)

| ID | Surface | Before | After |
|---|---|---|---|
| N1-01 | Audits programme chips | Hidden when count is 0 | Internal / UVDB / Planet Mark / Customer always mounted; badge can be 0 |
| N1-02 | Runs truncation banner | Copy implied a loaded page without a crisp N | `Showing {loaded} of {total} runs` when total > loaded |
| N1-03 | Planet Mark home | No strip to the Audits board | `Planet Mark on Audits` → `/audits?source=planet_mark` |
| N1-04 | Audits List | One density | Comfort default (LIVE padding); Compact tighter rows; persists; rows stay keyboard-activatable |

## 3) Compatibility & Data Safety
- No schema change. No alembic. Client-side chips, density, and `source=planet_mark` filter only.
- **Rollback strategy:** Revert merge and redeploy `e8c46a31f4b`.

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| Empty programme undiscoverable | Planet Mark chip vanished at 0 | Chip stays; PM home links to the board slice |
| Truncation honesty | Loaded page could look complete | Banner names loaded vs total |
| A4 / Entra / EXACT | Refused | Untouched |

## 4) Acceptance Criteria (AC)
- [x] AC-01: Programme chips with count 0 stay mounted (except Customer assurance view, which still hides the chip row).
- [x] AC-02: Banner `Showing {loaded} of {total} runs` when `auditsTotal > audits.length`.
- [x] AC-03: Planet Mark strip href is `/audits?source=planet_mark`. Filter uses the live source key.
- [x] AC-04: List Comfort default; Compact does not drop columns or CTAs; toggle persists; Compact rows remain keyboard-activatable.
- [x] AC-05: A4 stays 3 columns. No new calendar SoR. No Entra/Assist/Exceptions-cap/EXACT/Dependabot/CRM-LIB/N-BUILD-3.
- [ ] AC-06: Hosted CI green; STG+PROD SUCCESS (Build and Deploy not skipped); SHA match → LIVE.

## 5) Testing Evidence (link to runs)
- [x] Unit: `Audits.test.tsx` — zero-count chips; Comfort/Compact persist + keyboard
- [x] Unit: `assuranceHubHelpers.test.ts` — `source=planet_mark` path + filter
- [x] Unit: `PlanetMark.test.tsx` — strip href
- [x] Unit: `auditsBoardModel.test.ts` — density parse
- [ ] Hosted CI — pending

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Internal-only tenant still shows UVDB / Planet Mark / Customer chips at 0 (unit).
- [x] CUJ-02: Truncation banner names loaded vs total (unit).
- [x] CUJ-03: Planet Mark home opens `/audits?source=planet_mark` (unit).

## 7) Observability & Ops
- FE only. Density in `localStorage` key `qgp.audits.listDensity`. No new metrics.

## 8) Release Plan
1. Branch from LIVE tip `e8c46a31f4b`.
2. Merge after CI green; Staging SUCCESS; Production SUCCESS (Build and Deploy **not** skipped); only then **LIVE**.

## 9) Rollback Plan
- **Rollback trigger:** Zero-count chips hidden again; truncation omitted when total > page; PM strip missing or wrong href; Compact drops columns/CTAs; A4 becomes 4 columns.
- **Rollback steps:** Revert merge; redeploy `e8c46a31f4b`.
- **Owner:** Platform release operator / Standards Governance conveyor.

## 10) Evidence Pack
- Parent LIVE: **PR #1775** @ `e8c46a31f4b`

## Gate checklist
- [x] **Gate 0:** Scope lock + AC + Change Ledger; #1775 LIVE; L11–L16 held; continue given
- [x] **Gate 1:** Focused tests
- [ ] **Gate 2:** CI green on tip
- [ ] **Gate 3:** STG tip verify
- [ ] **Gate 4:** PROD tip verify
- [ ] **Gate 5:** Master conveyor updated after LIVE
