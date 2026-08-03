# Change Ledger (CL-001)

## 1) Summary
- **Feature / Change name:** Ship `specs/compliance-schedule/catalogue.json` in the production image
- **User goal (1–2 lines):** Unblock the deploy pipeline. `main` currently cannot reach staging or production at all, so nothing merged after `dfb8127f` can ship until this lands.
- **In scope:** One `COPY` line in the `Dockerfile`, plus a comment recording why these spec files must be in the image.
- **Out of scope:** The CI gate that would have caught this (building the image and running migrations inside it). Noted in §7 as follow-up work, deliberately not bundled into a pipeline-unblocking hotfix.
- **Feature flag / kill switch:** None. `COMPLIANCE_SCHEDULE_ENABLED` remains **off** and is untouched by this change.

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** None.
- **Backend (handlers/services):** None.
- **APIs (endpoints changed/added):** None.
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** None.
- **Database (migrations/entities/indexes):** No new migration. This makes the already-merged `20260913_cs_wave0` able to complete its seed step inside the container; the migration itself is unchanged.
- **Workflows/jobs/queues (if any):** None.
- **Config/env/flags:** None.
- **Dependencies (added/removed/updated):** None.

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive. One file added to the image; no existing layer, path or behaviour altered.
- **Tolerant reader / strict writer applied?** Not applicable — no request or response handling changes.
- **Breaking changes:** None.
- **Migration plan:** No new migration. On the next deploy, `20260913_cs_wave0` reaches its seed step and upserts 25 templates idempotently. Because production never got past the failure, it will apply the whole revision cleanly from `20260912_clear_junctions`.
- **Rollback strategy (DB):** No DB change in this PR. Reverting it restores the broken state rather than causing one.

## 4) Acceptance Criteria (AC)
- [x] **AC-01:** `/app/specs/compliance-schedule/catalogue.json` is present in the built production image, at the exact path the failing deploy named.
- [x] **AC-02:** `load_catalogue_templates()` runs inside the container and parses the full catalogue, rather than raising `FileNotFoundError`.
- [x] **AC-03:** No other image path, layer ordering or file ownership changes — the added file is owned by `appuser:appgroup` like every other copied path.
- [ ] **AC-04:** The staging deploy completes its migration step and promotes to production. Only observable on the real pipeline; this is the criterion this PR exists to satisfy.

## 5) Testing Evidence (link to runs)
- [x] **Lint** — no Python or frontend source touched.
- [x] **Typecheck** — no typed source touched.
- [x] **Build** — `docker build --target production` succeeded on the amended `Dockerfile`.
- [x] **Unit tests** — unaffected; no importable code changed.
- [ ] **Integration tests** — unaffected.
- [ ] **Contract tests** — unaffected.
- [ ] **E2E Smoke (critical journeys)** — runs on CI.

**Verified inside the built image, not inferred.** Building the production target and executing the real loader:

```
resolved path : /app/specs/compliance-schedule/catalogue.json
exists        : True
templates     : 25
first key     : fire_risk_assessment
```

Before this change the same code path produced, in the staging deploy:

```
FileNotFoundError: [Errno 2] No such file or directory: '/app/specs/compliance-schedule/catalogue.json'
```

## 6) Critical Journeys Verified (CUJ)
- [x] **CUJ-01:** Deploy migration step — the container can read the catalogue and seed `compliance_requirement_templates` instead of aborting the deploy.
- [x] **CUJ-02:** No regression to the existing spec file — `specs/governance-library/taxonomy.json` remains copied to the same path with the same ownership, so the governance library seeding is unaffected.

## 7) Observability & Ops
- **Logs:** The migration already logs the number of templates it upserted, so a successful seed is visible in the deploy log rather than needing to be inferred.
- **Metrics:** None added.
- **Alerts:** None added.
- **Runbook updates:** None required for this change. **Follow-up worth its own decision:** no CI job builds the image, so any runtime file read from a path outside `src/`, `alembic/` or the two copied spec files can pass all 52 checks and still fail on deploy. A job that builds the image and runs `alembic upgrade head` inside it would close this class of defect.

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Merging triggers CI → staging. Success means the `Run database migrations` step gets past the seed and the staging smoke tests actually execute instead of being skipped.
- **Canary plan:** Not applicable. This is a pipeline fix, and the Compliance Schedule feature it unblocks stays behind a default-off flag.
- **Prod post-deploy checks:** Migration reaches `20260913_cs_wave0`; `/health` green; `COMPLIANCE_SCHEDULE_ENABLED` confirmed still off; the two Compliance Schedule routes still 404.

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** The staging migration failing for any *new* reason after this lands — that would mean a second missing dependency rather than this one.
- **Rollback steps:** Reverting this commit is not a recovery path, since it restores the failing state. If the next deploy fails differently, the correct action is to read the new migration error and fix that cause; if the pipeline must be cleared immediately, revert `dfb8127f` (the Compliance Schedule merge) so the migration leaves the chain entirely.
- **Owner:** David Harris (Governance/Quality platform team).

## 10) Evidence Pack (links)
- CI run(s): this PR's checks.
- Staging deploy evidence: the failing run this fixes is `Deploy to Azure Staging` 30844962873; the production run that correctly refused to promote is 30845370151.
- Canary evidence (if applicable): n/a.

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved — none affected
- [x] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete — this PR is what makes staging able to complete
- [ ] **Gate 4:** Canary healthy (if used) — n/a
- [ ] **Gate 5:** Production verification plan + monitoring ready — plan in §8
