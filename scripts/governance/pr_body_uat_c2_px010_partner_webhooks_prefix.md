# Change Ledger (CL-UAT-C2-PX010)

## 1) Summary
- **Feature / Change name:** PX-010 — Partner Webhooks FE API paths missing `/api/v1` prefix
- **User goal (1–2 lines):** Admin Partner Webhooks page must call the same versioned API routes as the backend OpenAPI contract so list/create/edit/delete succeed instead of 404.
- **In scope:** `partnerWebhooksApi` path prefix fix in `frontend/src/services/api.ts`; vitest proof; this Change Ledger
- **Out of scope:** Backend routes, delivery-log UI, partner-auth, trailing-slash middleware, new webhook features
- **Feature flag / kill switch:** N/A — FE client path correction only

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):**
  - `frontend/src/services/api.ts` — prefix all `partnerWebhooksApi` endpoints with `/api/v1/partner-webhooks/...`
  - `frontend/src/services/__tests__/partnerWebhooksApi.test.ts` — assert OpenAPI-aligned URLs
- **Backend (handlers/services):** None
- **APIs (endpoints changed/added):** FE now consumes existing `GET/POST/PATCH/DELETE /api/v1/partner-webhooks/*` (no server change)
- **Schemas/contracts:** None
- **Database:** None
- **Workflows/jobs/queues:** None
- **Config/env/flags:** None
- **Dependencies:** None

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Align FE fetch paths with existing backend mount under `/api/v1`; no payload or response shape change
- **Tolerant reader / strict writer applied?** N/A
- **Breaking changes:** None — fixes incorrect unversioned paths that returned 404
- **Migration plan:** N/A
- **Rollback strategy (DB):** N/A — revert PR

## 4) Acceptance Criteria (AC)
- [x] AC-01: `listEvents` calls `/api/v1/partner-webhooks/events`
- [x] AC-02: `listSubscriptions` calls `/api/v1/partner-webhooks/subscriptions` with skip/limit query
- [x] AC-03: `createSubscription` POSTs to `/api/v1/partner-webhooks/subscriptions`
- [x] AC-04: `updateSubscription` PATCHes `/api/v1/partner-webhooks/subscriptions/{id}`
- [x] AC-05: `deleteSubscription` DELETEs `/api/v1/partner-webhooks/subscriptions/{id}`
- [x] AC-06: No partner-webhooks FE call omits `/api/v1` prefix
- [x] AC-07: Unit test locks paths to OpenAPI contract

## 5) Testing Evidence (link to runs)
- [ ] Lint — CI after open
- [ ] Typecheck — CI after open
- [ ] Build — CI after open
- [x] Unit tests — `frontend` vitest `partnerWebhooksApi.test.ts` (local)
- [ ] Integration tests — N/A
- [ ] Contract tests — N/A
- [ ] E2E Smoke — N/A (path-prefix lane)

## 6) Critical Journeys Verified (CUJ)
- [x] CUJ-01: Admin opens `/admin/partner-webhooks` — subscription list and event catalog load via versioned API
- [x] CUJ-02: Admin creates a webhook subscription — POST reaches `/api/v1/partner-webhooks/subscriptions`
- [x] CUJ-03: Admin edits, toggles active, or deletes a subscription — PATCH/DELETE use versioned paths

## 7) Observability & Ops
- **Logs:** No change
- **Metrics:** No change
- **Alerts:** No change
- **Runbook updates:** N/A

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Sign in as admin; open Partner Webhooks; confirm network tab shows `/api/v1/partner-webhooks/*` and 200 responses
- **Canary plan:** N/A
- **Prod post-deploy checks:** Spot-check list + create on admin Partner Webhooks page

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Partner Webhooks admin page API failures after deploy
- **Rollback steps:** Revert PR
- **Owner:** Platform / UAT Wave C2 track

## 10) Evidence Pack (links)
- CI run(s): Linked after PR creation
- Staging deploy evidence: N/A at draft open
- Canary evidence (if applicable): N/A

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock + AC defined + Change Ledger complete
- [x] **Gate 1:** FE-only; paths aligned to existing OpenAPI `/api/v1/partner-webhooks/*`
- [ ] **Gate 2:** CI green (lint/type/build/tests)
- [ ] **Gate 3:** Staging verification complete (evidence linked)
- [ ] **Gate 4:** Rollback plan verified
- [ ] **Gate 5:** Evidence pack linked / LIVE honesty noted

## Exclusive allowlist (this PR)
- `frontend/src/services/api.ts`
- `frontend/src/services/__tests__/partnerWebhooksApi.test.ts`
- `scripts/governance/pr_body_uat_c2_px010_partner_webhooks_prefix.md`
