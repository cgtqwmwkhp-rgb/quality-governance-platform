# Change Ledger (CL-PATH10-S10-CELERY-DEPTH-READYZ)

## File allowlist (exclusive)
- Root/API `/readyz` upstream Celery/Redis depth + OCR ping stub fields
- `src/infrastructure/upstream/celery_status.py` (+ ai_status honesty expand)
- Related unit tests only

## 1) Summary
- **Feature / Change name:** Path-to-10 S10 — Redis/Celery queue depth + honest OCR ping stub on `/readyz`
- **User goal (1-2 lines):** Surface broker/queue depth and OCR timeout/circuit/ping honesty without inventing SMTP secrets or failing the probe.
- **In scope:** Additive `upstream.celery` (+ OCR ping/timeout/circuit metadata on `upstream.ai`); unit tests; no secret leakage
- **Out of scope:** SMTP invent; FE; live OCR/Gemini HTTP ping; forcing probe failure on depth errors; worker inspect.ping on readyz
- **Feature flag / kill switch:** N/A — informational readiness only

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** None
- **Backend (handlers/services):** `celery_status.py`; OCR ping/timeout/circuit on `ai_status.py`; wire into `health.py` + root `main.py` `/readyz`
- **APIs (endpoints changed/added):** Additive `/readyz` fields under `upstream.celery` (+ `upstream_celery_note`); expanded `upstream.ai`
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** Additive JSON fields only
- **Database (migrations/entities/indexes):** None
- **Workflows/jobs/queues (if any):** None (read-only LLEN)
- **Config/env/flags:** Reads existing `CELERY_BROKER_URL` / `REDIS_URL` / `MISTRAL_OCR_TIMEOUT_SECONDS`
- **Dependencies (added/removed/updated):** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive
- **Tolerant reader / strict writer applied?** Yes — new fields optional for consumers
- **Breaking changes:** None
- **Migration plan:** N/A
- **Rollback strategy (DB):** No DB change — revert squash merge

## 4) Acceptance Criteria (AC)
- [x] AC-01: `/readyz` reports `upstream.celery` status + queue depth without secrets
- [x] AC-02: Depth/probe errors stay informational (do not alone 503 the probe)
- [x] AC-03: OCR ping is an honest stub (`skipped` / `unprobed`) with timeout + circuit metadata
- [x] AC-04: No SMTP secrets invented

## 5) Testing Evidence (link to runs)
- [x] Unit tests — `tests/unit/test_upstream_celery_readiness.py`, `tests/unit/test_upstream_ai_readiness.py`
- [ ] CI green — linked after PR creation

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: `/readyz` returns `upstream.celery` honesty fields
- [x] CUJ-02: Unconfigured broker / depth error leaves probe healthy for this channel
- [x] CUJ-03: OCR ping never claims live connectivity from readyz

## 7) Observability & Ops
- **Logs:** Warning on depth probe failure
- **Metrics:** Readyz payload gains celery channel + AI circuit/timeout
- **Alerts:** None (informational; does not 503 on missing celery depth)
- **Runbook updates:** N/A (points to existing celery smoke script)

## 8) Release Plan (Local -> Staging -> Canary -> Prod)
- **Staging verification:** `curl .../readyz` shows `upstream.celery` + `upstream.ai.ocr_ping`
- **Canary plan:** N/A
- **Prod post-deploy checks:** `/readyz` includes celery depth; probe stays ready when Redis ping already ok

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Readyz break, secret leakage, or unexpected probe failure after promote
- **Rollback steps:** Revert squash merge; redeploy prior SHA
- **Owner:** platform / Path-to-10 S10 lane

## 10) Evidence Pack (links)
- CI run(s): Linked after PR creation
- Staging deploy evidence: After auto-deploy
- Canary evidence (if applicable): N/A

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data/UX contracts approved (as applicable)
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete (evidence linked)
- [ ] **Gate 4:** Canary healthy (if used) (evidence linked)
- [x] **Gate 5:** Production verification plan + monitoring ready

Made with [Cursor](https://cursor.com)

<!-- ledger-refresh 2026-07-11T19:45Z -->
