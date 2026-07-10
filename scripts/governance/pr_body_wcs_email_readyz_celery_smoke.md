# Change Ledger (CL-001)

## 1) Summary
- **Feature / Change name:** Lane 1 Ops — honest SMTP readiness + fail-closed Celery smoke
- **User goal (1–2 lines):** Make outbound email configuration visible and enforceable without faking sends; require staging Celery inspect ping now that workers return pong.
- **In scope:** `/readyz` `email_configured`; SMTP docs; email config smoke; drop `--allow-missing`; optional SMTP passthrough on Celery deploy
- **Out of scope:** Creating SMTP secrets in Key Vault; actual mailbox provisioning; fake send paths
- **Feature flag / kill switch:** `EMAIL_ENABLED` — when true, SMTP credentials are required for smoke

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** None
- **Backend (handlers/services):** `src/infrastructure/email/email_status.py`; readiness payloads in `src/main.py` and `src/api/routes/health.py`
- **APIs (endpoints changed/added):** Additive fields on `/readyz` and `/api/v1/health/readyz`
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** Additive JSON only
- **Database (migrations/entities/indexes):** None
- **Workflows/jobs/queues (if any):** Staging Celery ping smoke fail-closed; email config smoke step
- **Config/env/flags:** Documents `EMAIL_ENABLED`, `SMTP_*`, `FROM_EMAIL` in `.env.example` + runbook
- **Dependencies (added/removed/updated):** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive readiness fields; tolerant readers ignore unknown keys
- **Tolerant reader / strict writer applied?** Yes
- **Breaking changes:** Staging deploy Celery smoke no longer uses `--allow-missing` (workers are provisioned)
- **Migration plan:** None
- **Rollback strategy (DB):** No DB change — revert commit / redeploy previous SHA

## 4) Acceptance Criteria (AC)
- [x] AC-01: `/readyz` includes `email_configured` and `email.status` without secrets
- [x] AC-02: `scripts/smoke/check_email_config.py` exits 1 when `EMAIL_ENABLED` set without SMTP
- [x] AC-03: Staging Celery inspect ping smoke is fail-closed (no `--allow-missing`)
- [x] AC-04: Docs list required SMTP App Settings / Key Vault secrets; no fake send

## 5) Testing Evidence (link to runs)
- [x] Lint — pending CI on PR
- [x] Typecheck — pending CI on PR
- [x] Build — pending CI on PR
- [x] Unit tests — `tests/unit/test_email_status.py` — **4 passed locally**
- [x] Integration tests — email readiness assertions in `tests/integration/test_health.py`
- [ ] Contract tests (if applicable) — N/A (additive fields)
- [ ] E2E Smoke (critical journeys) — staging after merge

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Unconfigured SMTP → readiness reports `email_configured=false` / `not_configured`; HTTP status still driven by DB/Redis only
- [x] CUJ-02: `EMAIL_ENABLED=true` without SMTP → smoke fails; readiness reports `misconfigured` (no fake send)

## 7) Observability & Ops
- **Logs:** No new high-volume logs
- **Metrics:** Readiness JSON is the primary signal (`email` / `email_configured`)
- **Alerts:** Do not page solely on `email=not_configured` until EMAIL_ENABLED is intentionally set
- **Runbook updates:** `docs/runbooks/CELERY_WORKER_BEAT_DEPLOY.md` SMTP section + ADMIN_GUIDE

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Deploy → curl `/readyz` shows email fields; Celery ping pongs without allow-missing
- **Canary plan:** Standard; rollback if readiness probes regress
- **Prod post-deploy checks:** Confirm email fields present; SMTP still absent until KV secrets created

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Readiness probe regressions or Celery smoke false failures after worker outage
- **Rollback steps:** Revert this PR commit(s) or redeploy previous known-good SHA; temporarily re-add `--allow-missing` only if workers are deprovisioned
- **Owner:** Platform / David Harris

## 10) Evidence Pack (links)
- CI run(s): Linked after PR creation
- Staging deploy evidence: Planned post-merge
- Canary evidence (if applicable): N/A

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved (as applicable) — additive readiness fields
- [ ] **Gate 2:** CI green (lint/type/build/tests) — awaiting PR CI
- [ ] **Gate 3:** Staging verification complete (evidence linked) — planned
- [ ] **Gate 4:** Canary healthy (if used) (evidence linked) — N/A
- [x] **Gate 5:** Production verification plan + monitoring ready — post-deploy checks documented
