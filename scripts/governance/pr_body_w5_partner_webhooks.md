# Change Ledger (CL-W5-PARTNER-WEBHOOKS)

## 1) Summary
- **Feature / Change name:** Wave5 Partner API — webhook subscriptions + delivery log scaffold (cash-in-wall)
- **User goal (1–2 lines):** Give partners a tenant-scoped webhook subscription surface with HMAC-signed payloads and delivery audit trail before wiring live event emitters.
- **In scope:** `WebhookSubscription` + `WebhookDeliveryLog` models; Alembic migration chained after `20260715_audit_db_integrity`; subscription CRUD API; delivery log list; HMAC sign helper; stub dispatch; event catalog constants; unit tests; ops runbook; router mount in `src/api/__init__.py` (allowlisted one-line include)
- **Out of scope:** Live outbound HTTP delivery; event emitter wiring from inspection/finding/CAPA services; Wave2–4 files (investigations, OCR, form_config, audit-builder); frontend; Celery task integration
- **Feature flag / kill switch:** None (v1 scaffold is inert — stub dispatch only)

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** None
- **Backend (handlers/services):** `PartnerWebhookService` — HMAC signing, subscription CRUD, delivery log persistence, stub dispatch
- **APIs (endpoints changed/added):**
  - `GET /api/v1/partner-webhooks/events` — event catalog
  - `POST/GET/PATCH/DELETE /api/v1/partner-webhooks/subscriptions`
  - `GET /api/v1/partner-webhooks/deliveries`
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** `src/api/schemas/partner_webhook.py`
- **Database (migrations/entities/indexes):** `20260716_partner_webhooks` — `webhook_subscriptions`, `webhook_delivery_logs`
- **Workflows/jobs/queues (if any):** None (stub dispatch; no Celery)
- **Config/env/flags:** None
- **Dependencies (added/removed/updated):** None
- **Router registration (allowlist exception):** `src/api/__init__.py` — import `partner_webhooks` + `include_router` mount only

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive tables + new API namespace under `/partner-webhooks`
- **Tolerant reader / strict writer applied?** Yes — subscriptions validate event types against catalog; secrets never returned in responses
- **Breaking changes:** None
- **Migration plan:** `upgrade()` creates two new tables; `down_revision = 20260715_audit_db_integrity` (current origin/main head as of fetch). **Rebase note:** if Wave2a (#1009) merges `20260716_capa_investigation_source` first, rebase `down_revision` to that revision before merge.
- **Rollback strategy (DB):** `alembic downgrade` drops `webhook_delivery_logs` then `webhook_subscriptions`

## 4) Acceptance Criteria (AC)
- [x] AC-01: `WebhookSubscription` + `WebhookDeliveryLog` ORM models with tenant scoping and CASCADE on subscription delete
- [x] AC-02: Alembic migration `20260716_partner_webhooks` chains after current main head (`20260715_audit_db_integrity`)
- [x] AC-03: Subscription CRUD API under `/api/v1/partner-webhooks/subscriptions`
- [x] AC-04: Delivery log list API under `/api/v1/partner-webhooks/deliveries`
- [x] AC-05: HMAC-SHA256 sign helper (`X-Partner-Timestamp` + `X-Partner-Signature`)
- [x] AC-06: Event catalog: `inspection.started|completed`, `finding.created|updated`, `capa.created|status_changed`
- [x] AC-07: v1 stub dispatch records `stubbed` deliveries without external HTTP send
- [x] AC-08: Unit tests in `tests/unit/test_partner_webhooks.py`
- [x] AC-09: Exclusive allowlist — no audits*, investigation*, form_config*, OCR, audit-builder, App.tsx touched

## 5) Testing Evidence (link to runs)
- [x] Lint — `python3.11 -m black` on touched files
- [ ] Typecheck — CI after open
- [ ] Build — CI after open
- [x] Unit tests — `tests/unit/test_partner_webhooks.py` (local run linked in PR comment)
- [ ] Integration tests — N/A for v1 scaffold
- [ ] Contract tests — N/A (OpenAPI baseline not refreshed in scaffold PR)
- [ ] E2E Smoke — N/A (API-only scaffold)

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Create subscription with valid event catalog entries → persisted tenant-scoped row
- [x] CUJ-02: HMAC signature is deterministic for canonical JSON + timestamp
- [x] CUJ-03: Stub dispatch records delivery log with `stubbed` status and signature
- [x] CUJ-04: Inactive / unsubscribed event rejected by stub dispatch guard

## 7) Observability & Ops
- **Logs:** Structured `partner_webhook_delivery_recorded` on delivery log insert
- **Metrics:** None new
- **Alerts:** None new
- **Runbook updates:** `docs/ops/partner-webhooks.md`

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Apply migration; POST subscription; GET deliveries (empty); confirm event catalog endpoint
- **Canary plan:** N/A — no live dispatch in v1
- **Prod post-deploy checks:** Confirm `webhook_subscriptions` + `webhook_delivery_logs` tables exist; subscription CRUD smoke

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Migration failure or subscription API regression
- **Rollback steps:** Revert PR; `alembic downgrade` to predecessor revision (rebase-aware)
- **Owner:** Platform / Wave5 track

## 10) Evidence Pack (links)
- CI run(s): Linked after PR creation
- Staging deploy evidence: N/A (draft — no merge)
- Canary evidence: N/A

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** API/Data contracts approved for v1 scaffold (stub dispatch; no emitters)
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete (evidence linked)
- [ ] **Gate 4:** Canary healthy (if used) — N/A v1 scaffold
- [x] **Gate 5:** Production verification plan + monitoring ready — inert scaffold; Wave5b wires dispatch
