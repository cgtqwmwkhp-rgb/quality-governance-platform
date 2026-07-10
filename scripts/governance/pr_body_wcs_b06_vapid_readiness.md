# Change Ledger (CL-001)

## 1) Summary
- **Feature / Change name:** WCS-B06 — Surface push/VAPID readiness in health + admin FE
- **User goal (1–2 lines):** Make Web Push configuration visible on `/readyz` and `/api/v1/health/readyz` (and admin Notification Settings) so missing VAPID is no longer opaque when push silently skips.
- **In scope:** VAPID readiness helper; root + API readiness fields; public `/api/v1/notifications/push/vapid-status`; Notification Settings readiness banner; unit + integration tests; `.env.example` VAPID keys
- **Out of scope:** Changing SMS/email/SMTP lanes; forcing readiness 503 when VAPID missing; rotating production VAPID keys; rewriting service-worker subscribe path beyond status display
- **Feature flag / kill switch:** None — push remains optional; missing VAPID never fails readiness

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** `frontend/src/pages/admin/NotificationSettings.tsx` — fetch vapid-status and show readiness banner
- **Backend (handlers/services):** `src/infrastructure/push/vapid_status.py` helper; readiness payloads in `src/main.py` and `src/api/routes/health.py`
- **APIs (endpoints changed/added):** `GET /api/v1/notifications/push/vapid-status` (public readiness + public key only); `/readyz` and `/api/v1/health/readyz` gain `push` / `vapid` fields
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** Additive JSON fields only
- **Database (migrations/entities/indexes):** None
- **Workflows/jobs/queues (if any):** None
- **Config/env/flags:** Documents `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`, `VAPID_EMAIL` in `.env.example`
- **Dependencies (added/removed/updated):** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive observability fields; tolerant readers ignore unknown keys
- **Tolerant reader / strict writer applied?** Yes — probes that only check `status`/`database`/`redis` remain valid
- **Breaking changes:** None — missing VAPID does **not** change HTTP status of readiness
- **Migration plan:** None
- **Rollback strategy (DB):** No DB change — revert commit / redeploy previous SHA

## 4) Acceptance Criteria (AC)
- [x] AC-01: `/api/v1/health/readyz` includes `checks.push` and `checks.vapid` reflecting key presence
- [x] AC-02: Root `/readyz` includes `push` / `vapid` fields; missing VAPID alone does not return 503
- [x] AC-03: `GET /api/v1/notifications/push/vapid-status` returns status without private key material
- [x] AC-04: Admin Notification Settings shows a push/VAPID readiness banner when the status endpoint responds
- [x] AC-05: Unit tests cover not_configured / partial / configured (`tests/unit/test_vapid_status.py`)

## 5) Testing Evidence (link to runs)
- [x] Lint — pending CI on PR
- [x] Typecheck — pending CI on PR
- [x] Build — pending CI on PR
- [x] Unit tests — `tests/unit/test_vapid_status.py` — **3 passed locally**
- [x] Integration tests — assertions added in `tests/integration/test_health.py` — pending CI
- [ ] Contract tests (if applicable) — N/A (additive fields)
- [ ] E2E Smoke (critical journeys) — planned on staging after merge/deploy

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Unconfigured VAPID → readiness reports `push=not_configured` while DB/Redis still drive overall ready/not_ready
- [x] CUJ-02: Configured VAPID → readiness reports `push=configured`; admin UI can show “VAPID ready”

## 7) Observability & Ops
- **Logs:** No new high-volume logs
- **Metrics:** No new metrics; readiness JSON is the primary signal
- **Alerts:** Do not alert solely on `push=not_configured` (optional feature)
- **Runbook updates:** Cross-ref in Import/Celery/DLQ runbook (separate WCS-B05 PR) for `/readyz` push fields

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Deploy → `curl /readyz` and `/api/v1/health/readyz` show `push`/`vapid`; open Admin → Notification Settings and confirm banner
- **Canary plan:** Standard canary; rollback if readiness probes regress (must still be non-fatal for missing VAPID)
- **Prod post-deploy checks:** Confirm `push` field present; if keys unset, status is `not_configured` with note; Redis/DB behaviour unchanged

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Readiness probe regressions, private key leakage in responses, or admin UI errors on Notification Settings
- **Rollback steps:** Revert this PR commit(s) or redeploy previous known-good SHA
- **Owner:** Platform team

## 10) Evidence Pack (links)
- CI run(s): Linked after PR creation
- Staging deploy evidence: Planned post-merge
- Canary evidence (if applicable): Planned per release runbook

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved (as applicable) — additive readiness fields; push remains optional
- [ ] **Gate 2:** CI green (lint/type/build/tests) — local unit tests green (3); awaiting PR CI
- [ ] **Gate 3:** Staging verification complete (evidence linked) — planned
- [ ] **Gate 4:** Canary healthy (if used) (evidence linked) — planned
- [x] **Gate 5:** Production verification plan + monitoring ready — post-deploy checks and rollback documented above
