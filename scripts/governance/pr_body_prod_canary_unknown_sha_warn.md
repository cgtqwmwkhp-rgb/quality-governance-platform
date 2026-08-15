# Change Ledger (CL-PROD-CANARY-UNKNOWN-SHA-WARN)

> **Start gate:** #1757 merged `e2ff78647e37` but **not LIVE** — Production 31878431735 fail-closed on SHA unknown while staging healthz was 200. `STACK_MAX=1` hotfix of that tip. Merge ≠ LIVE.

## 1) Summary
- **Feature / Change name:** Staging canary — unknown SHA is a warning again
- **User goal:** Promote a healthy staging tip even when GitHub runners cannot parse `/api/v1/meta/version`, without promoting a *known* wrong SHA or a non-200 healthz.
- **In scope:** `deploy-production.yml` Pre-deploy staging canary only.
- **Out of scope:** Assist triad; Entra flag; Exceptions cap; Azure breakglass unless this still cannot promote.
- **Feature flag / kill switch:** None. Revert this PR.

## 2) Impact Map (what changed)

| ID | Surface | Before (#1757) | After |
|---|---|---|---|
| SG-CANARY-04 | Unknown version SHA | Hard fail after 6 retries | Warning; proceed if healthz 200 |
| SG-CANARY-05 | Known SHA mismatch | Hard fail | Hard fail (unchanged intent) |
| SG-CANARY-06 | healthz non-200 | Hard fail | Hard fail; still retried |
| SG-CANARY-07 | Version diagnostics | SHA unknown only | Log version HTTP code + body size |

## 3) Compatibility & Data Safety
- Workflow-only. Restores pre-#1757 promote behaviour for version flakes; keeps #1757 retries and the 000 concatenation fix.
- **Rollback strategy:** Revert merge; production remains on `8bad35a585e9` until a successful promote.

## Compliance Delta

| Control / concern | Before | After |
| --- | --- | --- |
| D18 canary | healthz 200 + SHA must parse | healthz 200 required; known-wrong SHA fail-closed; unknown SHA warned |
| Prod write | Blocked on GHA version flake | Unblocked when staging healthz is 200 |

## 4) Acceptance Criteria (AC)
- [x] AC-01: healthz != 200 after retries still fail-closes.
- [x] AC-02: A parsed SHA that does not match the release SHA still fail-closes.
- [x] AC-03: SHA `unknown` + healthz 200 warns and proceeds (31878431735 would have promoted).
- [x] AC-04: No Entra/Assist/Exceptions-cap change.
- [ ] AC-05: Hosted CI green; STG+PROD SUCCESS (Build and Deploy not skipped); STG health SHA = PROD health SHA = tip → LIVE / DONE.

## 5) Testing Evidence (link to runs)
- [x] #1757 Production `31878431735`: 6/6 healthz 200, SHA unknown, no prod write. Staging from this operator: `e2ff78647e37` + healthz 200.
- [ ] Hosted CI — pending PR checks

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: GHA version flake + healthz 200 can promote.
- [x] CUJ-02: Wrong parsed SHA cannot promote.
- [x] CUJ-03: Unhealthy staging cannot promote.

## 7) Observability & Ops
- Canary logs `version_http` and `version_bytes` when probing `/version`.

## 8) Release Plan
1. Hotfix branch from `e2ff78647e37`.
2. Merge after CI green; Staging SUCCESS; Production SUCCESS (Build and Deploy **not** skipped); only then **LIVE**.

## 9) Rollback Plan
- **Rollback trigger:** Promotes a known-wrong SHA; skips healthz 200; Entra/Assist invented.
- **Rollback steps:** Revert merge. Production is unchanged until a successful Build and Deploy.
- **Owner:** Platform release operator / Standards Governance conveyor.

## 10) Evidence Pack
- Parent: **PR #1757** @ `e2ff78647e37` (merged, not LIVE)
- Blocked run: Production `31878431735`

## Gate checklist
- [x] **Gate 0:** Scope lock + AC + Change Ledger; #1757 cannot go LIVE with unknown-SHA hard fail
- [x] **Gate 1:** Workflow change reviewed locally
- [ ] **Gate 2:** CI green on tip
- [ ] **Gate 3:** STG tip verify
- [ ] **Gate 4:** PROD tip verify
- [ ] **Gate 5:** Master conveyor updated after LIVE
