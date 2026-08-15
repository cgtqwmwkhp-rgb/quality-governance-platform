# Change Ledger (CL-PROD-STAGING-CANARY-RETRY)

> **Start gate:** #1649 LIVE — tip `8bad35a585e9`. `STACK_MAX=1`. Merge ≠ LIVE.

## 1) Summary
- **Feature / Change name:** Production staging-canary retries
- **User goal:** A healthy staging tip must not fail-close production promotion because a single 15s curl timed out.
- **In scope:** Retry `/api/v1/meta/version` and `/healthz` in `deploy-production.yml` Pre-deploy staging canary. Fail-closed unless SHA matches **and** healthz is HTTP 200. Fix HTTP `000000` concatenation on curl timeout.
- **Out of scope:** Assist triad; Entra flag; Exceptions cap; weakening the 200 gate; Azure breakglass.
- **Feature flag / kill switch:** None. Revert this PR.

## 2) Impact Map (what changed)

| ID | Surface | Before | After |
|---|---|---|---|
| SG-CANARY-01 | Staging canary curl | One 15s attempt; SHA mismatch was a warning | Up to 6 attempts, 25s each, 10s apart; SHA mismatch is an error |
| SG-CANARY-02 | healthz timeout code | `curl \|\| echo 000` could print `000000` | Empty/000 treated as `000` once |
| SG-CANARY-03 | Promote gate | healthz 200 only (SHA warn-only) | SHA prefix match **and** healthz 200 |

## 3) Compatibility & Data Safety
- Workflow-only. No app/schema/flag change. No production write in this PR until a later tip is promoted through the hardened gate.
- **Rollback strategy:** Revert merge and redeploy prior tip `8bad35a585e9`.

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| D18 progressive delivery | Single 15s canary; SHA warn-only | Retried canary; SHA + 200 fail-closed |
| TrapGuard / Entra | Untouched | Untouched |

## 4) Acceptance Criteria (AC)
- [x] AC-01: Canary retries the same SHA + healthz checks; does not skip them.
- [x] AC-02: Promotion still fails unless staging SHA matches the release SHA and healthz is 200.
- [x] AC-03: Timeout no longer reports HTTP `000000`.
- [x] AC-04: No Entra/Assist/Exceptions-cap change.
- [ ] AC-05: Hosted CI green; STG+PROD SUCCESS (Build and Deploy not skipped); STG health SHA = PROD health SHA = tip → LIVE / DONE.

## 5) Testing Evidence (link to runs)
- [x] Measured failures: #1751 Production `31873845325` and #1649 Production `31875997632` — staging canary HTTP 000 / SHA unknown; no prod write; recover dispatches succeeded once staging answered.
- [ ] Hosted CI — pending PR checks

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Healthy staging that is slow to answer still reaches SHA+200 within retries, then promotes.
- [x] CUJ-02: Unhealthy or wrong-SHA staging still fail-closes after retries.

## 7) Observability & Ops
- Canary attempt lines are echoed in the Production job log.

## 8) Release Plan (Local → Staging → Canary → Prod)
1. Branch from LIVE tip `8bad35a585e9` (`STACK_MAX=1`).
2. Open PR with this ledger.
3. Merge after CI green; Staging SUCCESS; Production SUCCESS (Build and Deploy **not** skipped); only then mark conveyor **PROD → DONE**.

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Canary skips SHA/200; Entra/Assist invented; production promoted on unknown SHA.
- **Rollback steps:** Revert merge; redeploy prior tip `8bad35a585e9` via governed Staging → Production.
- **Owner:** Platform release operator / Standards Governance conveyor.

## 10) Evidence Pack (links)
- Parent LIVE gate: **PR #1649** @ `8bad35a585e9`
- Failed canaries: Production `31873845325` (#1751), `31875997632` (#1649)

## Gate checklist
- [x] **Gate 0:** Scope lock + AC + Change Ledger (this doc); #1649 LIVE confirmed
- [x] **Gate 1:** Workflow change reviewed locally
- [ ] **Gate 2:** CI green on tip
- [ ] **Gate 3:** STG tip verify
- [ ] **Gate 4:** PROD tip verify
- [ ] **Gate 5:** Master conveyor updated after LIVE
