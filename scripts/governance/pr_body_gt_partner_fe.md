# Change Ledger (GT-PARTNER-FE)

## 1) Summary
- **Feature / Change name:** Golden-Thread residuals R86 + R87 — partner webhook admin UI and database pagination
- **User goal (1–2 lines):** Give tenant administrators a real, authenticated frontend surface to create and manage partner webhook subscriptions, while ensuring subscription pagination executes in the database.
- **In scope:** Partner webhook API client; admin route, navigation, dashboard entry point, subscription list/create/edit/enable/delete UX; event catalog loading; database-backed subscription count/page query; focused tests.
- **Out of scope:** New webhook event types, delivery-log UI, partner authentication changes, migrations, backend route contract changes, live dispatch changes.
- **Feature flag / kill switch:** None. Existing server-side `admin:manage` authorization remains authoritative for writes.

## 2) Impact Map (what changed)
- **Frontend (routes/screens/components):** `frontend/src/pages/admin/PartnerWebhooks.tsx`; lazy route `/admin/partner-webhooks`; Admin navigation and dashboard quick action.
- **Backend (handlers/services):** `PartnerWebhookService.list_subscriptions` executes tenant-filtered count and `LIMIT/OFFSET` page queries.
- **APIs (endpoints changed/added):** Existing `GET /api/v1/partner-webhooks/events` and `POST/GET/PATCH/DELETE /api/v1/partner-webhooks/subscriptions` are consumed; list response contract is unchanged.
- **Schemas/contracts (OpenAPI/Zod/DTO/types):** Frontend subscription DTO and input types added to shared frontend API service.
- **Database (migrations/entities/indexes):** No migration required; existing tenant and active index remains sufficient for this change.
- **Workflows/jobs/queues (if any):** None.
- **Config/env/flags:** None.
- **Dependencies (added/removed/updated):** None.

## 3) Compatibility & Data Safety
- **Compatibility strategy:** Additive admin route and client only; existing server API URLs and response shape are preserved.
- **Tolerant reader / strict writer applied?** Yes — UI reads existing responses; creation requires URL, at least one supported event, and a 16-character signing secret. Edit keeps the existing secret unless a replacement is explicitly provided.
- **Breaking changes:** None.
- **Migration plan:** None.
- **Rollback strategy (DB):** Not applicable.

## 4) Acceptance Criteria (AC)
- [x] **AC-01 / R86:** `/admin/partner-webhooks` provides a role-gated administrator UI.
- [x] **AC-02 / R86:** UI lists tenant-scoped subscriptions, including endpoint, events, status, totals, loading/error/empty states, and API-backed paging.
- [x] **AC-03 / R86:** UI loads the event catalog and creates subscriptions through the existing authenticated client.
- [x] **AC-04 / R86:** UI edits, enables/disables, and deletes subscriptions; signing secrets are write-only.
- [x] **AC-05 / R86:** Admin navigation and dashboard expose the new surface.
- [x] **AC-06 / R87:** Subscription list performs tenant-filtered `COUNT` plus ordered `LIMIT/OFFSET` in the service; route no longer slices a fully loaded collection.
- [x] **AC-07:** Backend and focused frontend tests cover the new behaviors.

## 5) Testing Evidence (link to runs)
- [x] Backend unit tests: `pytest -q tests/unit/test_partner_webhooks.py` — 13 passed.
- [x] Frontend focused tests: `npx vitest run --run src/pages/admin/__tests__/PartnerWebhooks.test.tsx` — 2 passed.
- [x] Frontend production build: `npm run build` — passed.
- [x] Static diagnostics: no IDE linter diagnostics on edited backend/client/page files.
- [ ] Full CI suite: pending PR CI.

## 6) Critical Journeys Verified (CUJ)
- [x] **CUJ-01:** Admin opens Partner Webhooks and sees tenant subscriptions plus supported event catalog.
- [x] **CUJ-02:** Admin adds a subscription with endpoint, signing secret, selected events, and active status; authenticated API client sends create request.
- [x] **CUJ-03:** Admin can edit a subscription without exposing or replacing its secret, toggle active status, and confirm deletion.
- [x] **CUJ-04:** A tenant with many subscriptions receives only requested page rows while retaining the correct total.

## 7) Observability & Ops
- **Logs:** Existing partner webhook service and delivery logs remain unchanged.
- **Metrics:** None new.
- **Alerts:** None new.
- **Runbook updates:** None required; operational behavior is unchanged.

## 8) Release Plan (Local → Staging → Canary → Prod)
- **Staging verification:** Sign in as an administrator; open `/admin/partner-webhooks`; create, update, disable, and delete a test subscription; verify it is scoped to the signed-in tenant.
- **Canary plan:** Deploy through normal frontend canary; monitor browser/API error reporting for the route.
- **Prod post-deploy checks:** Confirm admin-only route protection, create/update/delete calls return successfully, and subscription paging has correct totals.

## 9) Rollback Plan (Mandatory)
- **Rollback trigger:** Admin subscription management regression or unexpected authorization/API failures.
- **Rollback steps:** Revert this PR and redeploy the prior frontend/backend service implementation. No database rollback is necessary.
- **Owner:** Quality Governance Platform team.

## 10) Evidence Pack (links)
- **PR:** Added after PR creation.
- **CI run(s):** Added by GitHub Actions after PR creation.
- **Staging deploy evidence:** Pending deployment.
- **Canary evidence:** Pending deployment.

---

# Gate Checklist (must be complete before merge)
- [x] **Gate 0:** Scope lock, acceptance criteria, and Change Ledger complete.
- [x] **Gate 1:** Existing API/data contract retained; no migration required.
- [x] **Gate 2:** Local backend tests and production frontend build pass; focused frontend test passes without coverage collection.
- [ ] **Gate 3:** PR CI green.
- [ ] **Gate 4:** Staging verification complete.
- [ ] **Gate 5:** Production verification complete.
